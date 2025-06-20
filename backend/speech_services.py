"""
Services de synthèse vocale Azure Speech Services
"""
import re
import html
import base64
import logging
import requests
from typing import List, Dict, Any, Optional
from backend.settings import app_settings
from backend.pronunciation_dict import apply_pronunciation_corrections, load_pronunciation_from_file
import os

# Charger les prononciations personnalisées au démarrage du module
custom_pronunciation_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pronunciation_custom.json')
load_pronunciation_from_file(custom_pronunciation_file)


def clean_markdown_and_html(text: str) -> str:
    """Préparation initiale du texte en préservant la structure pour l'analyse"""
    
    # Supprimer seulement les balises HTML dangereuses mais garder la structure
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Convertir les balises HTML de titre en markdown pour uniformiser
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1', text, flags=re.IGNORECASE)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1', text, flags=re.IGNORECASE)  
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1', text, flags=re.IGNORECASE)
    text = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1', text, flags=re.IGNORECASE)
    text = re.sub(r'<h5[^>]*>(.*?)</h5>', r'##### \1', text, flags=re.IGNORECASE)
    text = re.sub(r'<h6[^>]*>(.*?)</h6>', r'###### \1', text, flags=re.IGNORECASE)
    
    # Convertir les listes HTML en markdown avec numérotation pour les listes ordonnées
    # D'abord traiter les listes ordonnées
    ol_counter = 1
    def replace_ol_item(match):
        nonlocal ol_counter
        content = match.group(1)
        result = f"{ol_counter}. {content}"
        ol_counter += 1
        return result
    
    # Identifier les listes ordonnées et les convertir
    text = re.sub(r'<ol[^>]*>', '<!--OL_START-->', text, flags=re.IGNORECASE)
    text = re.sub(r'</ol>', '<!--OL_END-->', text, flags=re.IGNORECASE)
    
    # Traiter chaque liste ordonnée séparément
    def process_ordered_list(match):
        nonlocal ol_counter
        ol_counter = 1
        content = match.group(1)
        content = re.sub(r'<li[^>]*>(.*?)</li>', replace_ol_item, content, flags=re.IGNORECASE | re.DOTALL)
        return content
    
    text = re.sub(r'<!--OL_START-->(.*?)<!--OL_END-->', process_ordered_list, text, flags=re.DOTALL)
    
    # Traiter les listes non ordonnées
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<ul[^>]*>|</ul>', '', text, flags=re.IGNORECASE)
    
    # Supprimer les autres balises HTML mais garder le contenu
    text = re.sub(r'<[^>]*>', '', text)
    
    # Nettoyer les caractères d'échappement HTML
    text = html.unescape(text)
    
    return text


def clean_text_for_speech(text: str, for_browser: bool = False) -> str:
    """Nettoie le texte pour la synthèse vocale (Azure ou navigateur)"""
    
    # Nettoyage du markdown et HTML en premier
    text = clean_markdown_and_html(text)
    
    # Traitement intelligent des éléments de structure
    
    # 1. Traiter les titres markdown pour la synthèse vocale
    def process_markdown_title(match):
        level = len(match.group(1))  # Nombre de #
        title_text = match.group(2).strip()
        if level <= 2:  # Titres principaux (# ##)
            return f"{title_text}.\n"  # Pause longue
        else:  # Sous-titres (### #### ##### ######)
            return f"{title_text}.\n"  # Pause moyenne
    
    text = re.sub(r'^(#{1,6})\s*(.+)$', process_markdown_title, text, flags=re.MULTILINE)
    
    # 2. Traiter les listes pour une lecture fluide avec pauses
    # Remplacer les puces markdown par des transitions fluides avec pauses
    text = re.sub(r'^\s*[-*+]\s*(.+)$', r'\1.', text, flags=re.MULTILINE)
    # Remplacer les listes numérotées avec pauses
    text = re.sub(r'^\s*\d+\.\s*(.+)$', r'\1.', text, flags=re.MULTILINE)
    
    # 3. Supprimer le formatage markdown mais garder le texte
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Gras **texte**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italique *texte*
    text = re.sub(r'__([^_]+)__', r'\1', text)      # Gras __texte__
    text = re.sub(r'_([^_]+)_', r'\1', text)        # Italique _texte_
    
    # Supprimer les astérisques restants (non appariés ou multiples)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'_+', '', text)
    
    # 4. Traiter les liens markdown
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # 5. Traiter les blocs de code
    text = re.sub(r'```[\s\S]*?```', 'bloc de code', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Pour le navigateur, arrêter le traitement ici
    if for_browser:
        # Nettoyer les retours à la ligne multiples
        text = re.sub(r'\n\s*\n+', '. ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    # Supprimer les références entre crochets [1], [doc1], etc.
    text = re.sub(r'\[[^\]]*\]', '', text)
    
    # Supprimer les indices et exposants avec accent circonflexe ^2^, ^1^, etc.
    text = re.sub(r'\^[0-9]+\^', '', text)
    
    # Supprimer d'autres types de références numériques ²³¹ etc.
    text = re.sub(r'[²³¹⁴⁵⁶⁷⁸⁹⁰]', '', text)
    
    # Supprimer les références de type (1), (2), etc.
    text = re.sub(r'\([0-9]+\)', '', text)
    
    # Appliquer les corrections de prononciation depuis le dictionnaire
    text = apply_pronunciation_corrections(text)
    
    # Supprimer les caractères problématiques pour Azure Speech
    text = re.sub(r'[<>{}]', '', text)  # Caractères XML/HTML
    
    # Remplacer les guillemets Unicode par des guillemets simples
    text = text.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
    text = text.replace('„', '"').replace('‚', "'")
    
    # Supprimer les émoticônes et caractères Unicode spéciaux de manière complète
    # Pattern pour supprimer tous les émoticônes Unicode
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # émoticônes
        "\U0001F300-\U0001F5FF"  # symboles & pictogrammes
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # drapeaux iOS
        "\U00002500-\U00002BEF"  # caractères divers
        "\U00002702-\U000027B0"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # diacritiques
        "\u3030"
        "]+", 
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    
    # Supprimer les caractères spéciaux ASCII courants
    text = re.sub(r'[→←↑↓⬆⬇➡⬅►◄▲▼]', '', text)  # Flèches
    text = re.sub(r'[★☆✓✗✅❌⭐♦♠♣♥]', '', text)  # Étoiles, coches et symboles
    text = re.sub(r'[•◦‣⁃]', '', text)  # Puces alternatives
    
    # Supprimer les caractères de contrôle et caractères spéciaux problématiques
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)  # Caractères de contrôle
    text = re.sub(r'[&]', 'et', text)  # Remplacer & par "et"
    
    # Échapper les caractères XML restants
    text = html.escape(text, quote=False)
    
    # Améliorer les transitions entre sections
    # Ajouter des pauses après les retours à la ligne multiples
    text = re.sub(r'\n\s*\n', '. ', text)
    
    # Nettoyer les espaces multiples créés par les suppressions
    text = re.sub(r'\s+', ' ', text)  # Espaces multiples → un seul espace
    text = re.sub(r'\s*\.\s*', '. ', text)  # Normaliser les points avec espaces
    text = re.sub(r'\s*,\s*', ', ', text)  # Normaliser les virgules avec espaces
    text = re.sub(r'\s*;\s*', '; ', text)  # Normaliser les points-virgules
    text = re.sub(r'\s*:\s*', ': ', text)  # Normaliser les deux-points
    
    # Nettoyer les espaces en début et fin
    text = text.strip()
    
    return text


def split_text_for_speech(text: str, max_length: int = 600) -> List[str]:
    """Découpe le texte en segments pour éviter les limites Azure Speech"""
    logging.info(f"split_text_for_speech: Input text length = {len(text)}")
    logging.info(f"split_text_for_speech: Input text = '{text}'")
    
    if len(text) <= max_length:
        logging.info("Text is short enough, returning single segment")
        return [text]
    
    segments = []
    current_segment = ""
    
    # Découper par phrases - amélioration pour éviter les coupures sur "2025 s'annonce"
    # Ne couper que sur ". " suivi d'une majuscule ou fin de texte
    sentences = re.split(r'\.\s+(?=[A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ])', text)
    logging.info(f"split_text_for_speech: Found {len(sentences)} sentences")
    
    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if not sentence:
            continue
            
        logging.info(f"split_text_for_speech: Processing sentence {i+1}: '{sentence}'")
        
        # Ajouter le point si ce n'est pas la dernière phrase
        if not sentence.endswith('.') and i != len(sentences) - 1:
            sentence += '.'
            
        # Si ajouter cette phrase dépasse la limite
        if len(current_segment) + len(sentence) + 2 > max_length:
            logging.info(f"split_text_for_speech: Sentence would exceed limit, starting new segment")
            if current_segment:
                segments.append(current_segment.strip())
                current_segment = sentence
            else:
                # Phrase trop longue, la découper par mots
                words = sentence.split(' ')
                temp_segment = ""
                for word in words:
                    if len(temp_segment) + len(word) + 1 > max_length:
                        if temp_segment:
                            segments.append(temp_segment.strip())
                            temp_segment = word
                        else:
                            # Mot trop long, le tronquer
                            segments.append(word[:max_length])
                    else:
                        temp_segment += " " + word if temp_segment else word
                if temp_segment:
                    current_segment = temp_segment
        else:
            current_segment += ". " + sentence if current_segment else sentence
    
    if current_segment:
        segments.append(current_segment.strip())
    
    logging.info(f"split_text_for_speech: Final segments count = {len(segments)}")
    for i, segment in enumerate(segments):
        logging.info(f"split_text_for_speech: Segment {i+1} = '{segment}'")
    
    return segments


def generate_ssml(text: str, voice_name: str) -> str:
    """Génère le code SSML pour Azure Speech Services avec gestion intelligente des pauses"""
    
    enhanced_text = text
    
    # Détecter les titres courts (2-4 mots) suivis de contenu - pause longue
    enhanced_text = re.sub(r'([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ][a-zàâäéèêëïîôöùûüÿç]+(?:\s+[a-zàâäéèêëïîôöùûüÿç]+){1,3})\.\s+([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ][a-zàâäéèêëïîôöùûüÿç])', r'\1. <break time="800ms"/>\2', enhanced_text)
    
    # Détecter les titres moyens (5-8 mots) - pause moyenne
    enhanced_text = re.sub(r'([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ][^.]{20,60})\.\s+([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ][a-zàâäéèêëïîôöùûüÿç])', r'\1. <break time="600ms"/>\2', enhanced_text)
    
    # Pauses après les introductions (phrases commençant par Bonjour, Je vais, etc.)
    enhanced_text = re.sub(r'((?:Bonjour|Je vais|Voici|Voilà)[^.]+\.)\s+', r'\1 <break time="700ms"/>', enhanced_text)
    
    # Pauses après les deux-points - pause moyenne pour introduire une suite/explication
    enhanced_text = re.sub(r':\s*', r': <break time="500ms"/>', enhanced_text)
    
    # Pauses entre éléments de liste - détecter les patterns d'éléments de liste consécutifs
    enhanced_text = re.sub(r'([a-zàâäéèêëïîôöùûüÿç]{2,})\.\s+([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ][a-zàâäéèêëïîôöùûüÿç]+)', r'\1. <break time="300ms"/>\2', enhanced_text)
    
    # Pauses courtes après les points suivis de majuscules (transitions normales)
    enhanced_text = re.sub(r'\. ([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ][a-zàâäéèêëïîôöùûüÿç])', r'. <break time="400ms"/>\1', enhanced_text)
    
    # Amélioration de l'intonation pour les titres courts avec emphase
    enhanced_text = re.sub(r'([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ][a-zàâäéèêëïîôöùûüÿç]+(?:\s+[a-zàâäéèêëïîôöùûüÿç]+){1,3})\.', r'<emphasis level="moderate">\1</emphasis>.', enhanced_text)
    
    return f"""<speak version='1.0' xml:lang='{voice_name[:5]}'>
        <voice xml:lang='{voice_name[:5]}' name='{voice_name}'>
            <prosody rate='1.15' pitch='-6%'>
                {enhanced_text}
            </prosody>
        </voice>
    </speak>"""


def synthesize_speech_azure(text: str, language: str = "FR") -> Dict[str, Any]:
    """
    Synthétise la parole avec Azure Speech Services
    
    Args:
        text: Texte à synthétiser
        language: Langue ('FR' ou 'EN')
        
    Returns:
        Dict avec success, audio_data/audio_segments, content_type, voice_used, error
    """
    
    # Vérifier si Azure Speech est activé et configuré
    if not app_settings.base_settings.azure_speech_enabled:
        return {"success": False, "error": "Azure Speech Services not enabled"}
    
    if not app_settings.base_settings.azure_speech_key:
        return {"success": False, "error": "Azure Speech Services not configured"}
    
    try:
        # Nettoyer le texte pour la synthèse vocale
        logging.info(f"Original text length: {len(text)} characters")
        logging.info(f"Original text preview: {text[:200]}...")
        
        cleaned_text = clean_text_for_speech(text)
        
        if not cleaned_text:
            return {"success": False, "error": "No text to synthesize after cleaning"}
        
        logging.info(f"Cleaned text length: {len(cleaned_text)} characters")
        logging.info(f"Cleaned text preview: {cleaned_text[:200]}...")
        
        # Vérifier si le texte est trop long et le découper si nécessaire
        text_segments = split_text_for_speech(cleaned_text, max_length=1000)
        logging.info(f"Split into {len(text_segments)} segments")
        for i, segment in enumerate(text_segments):
            logging.info(f"Segment {i+1} length: {len(segment)} characters")
            logging.info(f"Segment {i+1} preview: {segment[:100]}...")
        
        # Sélectionner la voix selon la langue
        voice_name = (app_settings.base_settings.azure_speech_voice_fr 
                     if language == "FR" 
                     else app_settings.base_settings.azure_speech_voice_en)
        
        # Configuration Azure Speech Services
        speech_key = app_settings.base_settings.azure_speech_key
        speech_region = app_settings.base_settings.azure_speech_region
        
        headers = {
            'Ocp-Apim-Subscription-Key': speech_key,
            'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'audio-16khz-128kbitrate-mono-mp3',
            'User-Agent': 'AskMe-Application'
        }
        
        # URL de l'API Azure Speech
        url = f"https://{speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
        
        # Si un seul segment, traitement normal
        if len(text_segments) == 1:
            ssml_text = generate_ssml(text_segments[0], voice_name)
            
            # Effectuer la requête
            response = requests.post(url, headers=headers, data=ssml_text.encode('utf-8'))
            
            if response.status_code == 200:
                audio_base64 = base64.b64encode(response.content).decode('utf-8')
                return {
                    "success": True,
                    "audio_data": audio_base64,
                    "content_type": "audio/mpeg",
                    "voice_used": voice_name
                }
            else:
                logging.error(f"Azure Speech API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Azure Speech API error: {response.status_code}",
                    "details": response.text
                }
        else:
            # Traitement de plusieurs segments
            audio_segments = []
            
            for i, segment in enumerate(text_segments):
                ssml_text = generate_ssml(segment, voice_name)
                
                # Effectuer la requête pour ce segment
                response = requests.post(url, headers=headers, data=ssml_text.encode('utf-8'))
                
                if response.status_code == 200:
                    audio_base64 = base64.b64encode(response.content).decode('utf-8')
                    audio_segments.append(audio_base64)
                else:
                    logging.error(f"Azure Speech API error for segment {i}: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": f"Azure Speech API error for segment {i}: {response.status_code}",
                        "details": response.text
                    }
            
            # Retourner tous les segments audio
            return {
                "success": True,
                "audio_segments": audio_segments,
                "content_type": "audio/mpeg",
                "voice_used": voice_name,
                "segment_count": len(audio_segments)
            }
            
    except Exception as e:
        logging.error(f"Error in Azure Speech synthesis: {str(e)}")
        return {"success": False, "error": f"Speech synthesis failed: {str(e)}"}