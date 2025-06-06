"""
Language detection and multilingual support utilities.

This module provides language detection capabilities and multilingual
system messages for all LLM providers. It ensures that responses are
always provided in the user's query language while maintaining effective
cross-language document search capabilities.

Key features:
- Automatic language detection from user queries
- Comprehensive multilingual system message templates
- Fallback to English for unsupported languages
- Optimized for Azure AI Search cross-language capabilities
"""

import logging
from typing import Dict, Optional

try:
    from langdetect import detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

from .i18n import normalize_language_code, is_language_supported, get_supported_languages

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """
    Detect the language of the input text with robust fallback.
    
    Args:
        text: The text to analyze for language detection
        
    Returns:
        Two-letter language code (ISO 639-1) or configured default
        
    Note:
        - Uses simple word matching when langdetect unavailable
        - Prioritizes French/English for Avanteam business context
        - Configurable via DEFAULT_LANGUAGE environment variable
    """
    # Check for environment override
    import os
    default_language = os.getenv("DEFAULT_LANGUAGE", "fr")
    
    if not text or len(text.strip()) < 2:
        logger.debug(f"Text too short for language detection, defaulting to {default_language}")
        return default_language
    
    text_lower = text.strip().lower()
    words = text_lower.split()
    
    # Simple word-based detection for common cases
    french_words = {
        "salut", "bonjour", "bonsoir", "merci", "oui", "non", "comment", 
        "où", "quand", "pourquoi", "qui", "que", "quoi", "ça", "c'est",
        "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
        "un", "une", "le", "la", "les", "de", "du", "des", "et", "ou",
        "dans", "avec", "pour", "sur", "par", "sans", "sous", "entre"
    }
    
    english_words = {
        "hello", "hi", "thanks", "thank", "you", "yes", "no", "how", "what", 
        "when", "where", "why", "who", "the", "a", "an", "and", "or", "but",
        "i", "me", "my", "we", "us", "our", "he", "she", "it", "they", "them",
        "in", "on", "at", "to", "for", "with", "by", "from", "about", "into"
    }
    
    # Check for explicit language indicators
    french_count = sum(1 for word in words if word in french_words)
    english_count = sum(1 for word in words if word in english_words)
    
    if french_count > 0 and french_count >= english_count:
        logger.debug(f"Detected French words in: {text}")
        return "fr"
    elif english_count > 0:
        logger.debug(f"Detected English words in: {text}")
        return "en"
    
    # Fallback to langdetect if available
    if LANGDETECT_AVAILABLE:
        try:
            detected = detect(text.strip())
            normalized = normalize_language_code(detected)
            
            # Validate detection for short texts
            if len(words) <= 2:
                # Only accept common languages for short messages
                common_languages = {"fr", "en", "es", "de", "it", "pt", "nl"}
                if normalized not in common_languages:
                    logger.debug(f"Short text detected as uncommon language {normalized}, falling back to {default_language}")
                    normalized = default_language
            
            logger.debug(f"langdetect result: {detected} -> normalized: {normalized}")
            return normalized
        except LangDetectException as e:
            logger.debug(f"Language detection failed: {e}, defaulting to {default_language}")
        except Exception as e:
            logger.warning(f"Unexpected error in language detection: {e}, defaulting to {default_language}")
    else:
        logger.warning(f"langdetect not available, using fallback detection")
    
    # Final fallback
    logger.debug(f"No specific language detected, defaulting to {default_language}")
    return default_language


def get_system_message_for_language(language: str, base_message: str = None, response_size: str = "medium") -> str:
    """
    Get a localized system message for the specified language with response size instructions.
    
    Args:
        language: Two-letter language code (ISO 639-1)
        base_message: Optional base message to extend with language instructions
        response_size: Response size preference (veryShort, medium, comprehensive)
        
    Returns:
        Localized system message with language-specific and response size instructions
        
    Note:
        - Always includes explicit instruction to respond in the user's language
        - Maintains original business logic and citation instructions
        - Adds response size constraints when specified
    """
    
    # Language-specific response instructions
    language_instructions = {
        "fr": "Réponds TOUJOURS en français, même si les documents sources sont dans d'autres langues. Tu es un assistant IA serviable et précis qui aide les utilisateurs à trouver des informations dans les documents fournis. Utilise les informations des documents pour répondre aux questions, et cite tes sources quand c'est pertinent.",
        
        "en": "ALWAYS respond in English, even if source documents are in other languages. You are a helpful and accurate AI assistant that helps users find information in the provided documents. Use information from the documents to answer questions, and cite your sources when relevant.",
        
        "es": "Responde SIEMPRE en español, incluso si los documentos fuente están en otros idiomas. Eres un asistente de IA útil y preciso que ayuda a los usuarios a encontrar información en los documentos proporcionados. Usa la información de los documentos para responder preguntas y cita tus fuentes cuando sea relevante.",
        
        "pt": "Responda SEMPRE em português, mesmo que os documentos fonte estejam em outros idiomas. Você é um assistente de IA útil e preciso que ajuda os usuários a encontrar informações nos documentos fornecidos. Use informações dos documentos para responder perguntas e cite suas fontes quando relevante.",
        
        "it": "Rispondi SEMPRE in italiano, anche se i documenti fonte sono in altre lingue. Sei un assistente IA utile e preciso che aiuta gli utenti a trovare informazioni nei documenti forniti. Usa le informazioni dei documenti per rispondere alle domande e cita le tue fonti quando rilevante.",
        
        "de": "Antworte IMMER auf Deutsch, auch wenn die Quelldokumente in anderen Sprachen verfasst sind. Du bist ein hilfsreicher und präziser KI-Assistent, der Benutzern hilft, Informationen in den bereitgestellten Dokumenten zu finden. Verwende Informationen aus den Dokumenten, um Fragen zu beantworten, und zitiere deine Quellen, wenn relevant.",
        
        "zh": "始终用中文回答，即使源文档是其他语言。你是一个有用且准确的AI助手，帮助用户在提供的文档中查找信息。使用文档中的信息来回答问题，并在相关时引用你的来源。",
        
        "ja": "ソース文書が他の言語であっても、常に日本語で回答してください。あなたは提供された文書から情報を見つけるのを助ける、有用で正確なAIアシスタントです。文書の情報を使って質問に答え、関連する場合は出典を引用してください。",
        
        "ko": "소스 문서가 다른 언어로 되어 있어도 항상 한국어로 답변하세요. 당신은 제공된 문서에서 정보를 찾는 데 도움을 주는 유용하고 정확한 AI 어시스턴트입니다. 문서의 정보를 사용하여 질문에 답하고, 관련성이 있을 때 출처를 인용하세요.",
        
        "ar": "أجب دائماً باللغة العربية، حتى لو كانت المستندات المصدرية بلغات أخرى. أنت مساعد ذكي مفيد ودقيق يساعد المستخدمين في العثور على المعلومات في المستندات المقدمة. استخدم المعلومات من المستندات للإجابة على الأسئلة، واذكر مصادرك عند الصلة.",
        
        "ru": "ВСЕГДА отвечайте на русском языке, даже если исходные документы на других языках. Вы полезный и точный ИИ-помощник, который помогает пользователям находить информацию в предоставленных документах. Используйте информацию из документов для ответов на вопросы и цитируйте источники когда это уместно.",
        
        "hi": "स्रोत दस्तावेज़ अन्य भाषाओं में होने पर भी हमेशा हिंदी में उत्तर दें। आप एक सहायक और सटीक AI सहायक हैं जो उपयोगकर्ताओं को प्रदान किए गए दस्तावेज़ों में जानकारी खोजने में मदद करते हैं। प्रश्नों के उत्तर देने के लिए दस्तावेज़ों की जानकारी का उपयोग करें और प्रासंगिक होने पर अपने स्रोतों का हवाला दें।",
        
        "nl": "Antwoord ALTIJD in het Nederlands, zelfs als brondocumenten in andere talen zijn. Je bent een behulpzame en nauwkeurige AI-assistent die gebruikers helpt informatie te vinden in de verstrekte documenten. Gebruik informatie uit de documenten om vragen te beantwoorden en citeer je bronnen wanneer relevant.",
        
        "sv": "Svara ALLTID på svenska, även om källdokumenten är på andra språk. Du är en hjälpsam och noggrann AI-assistent som hjälper användare att hitta information i de tillhandahållna dokumenten. Använd information från dokumenten för att svara på frågor och citera dina källor när det är relevant.",
        
        "da": "Svar ALTID på dansk, selvom kildedokumenterne er på andre sprog. Du er en hjælpsom og præcis AI-assistent, der hjælper brugere med at finde information i de leverede dokumenter. Brug information fra dokumenterne til at besvare spørgsmål og citer dine kilder, når det er relevant.",
        
        "no": "Svar ALLTID på norsk, selv om kildedokumentene er på andre språk. Du er en hjelpsom og nøyaktig AI-assistent som hjelper brukere med å finne informasjon i de oppgitte dokumentene. Bruk informasjon fra dokumentene til å svare på spørsmål og siter kildene dine når det er relevant.",
        
        "fi": "Vastaa AINA suomeksi, vaikka lähdeasiakirjat olisivat muilla kielillä. Olet avulias ja tarkka tekoälyavustaja, joka auttaa käyttäjiä löytämään tietoa annetuista asiakirjoista. Käytä asiakirjojen tietoja vastataksesi kysymyksiin ja viittaa lähteisiisi kun se on asianmukaista.",
        
        "pl": "ZAWSZE odpowiadaj po polsku, nawet jeśli dokumenty źródłowe są w innych językach. Jesteś pomocnym i dokładnym asystentem AI, który pomaga użytkownikom znajdować informacje w dostarczonych dokumentach. Używaj informacji z dokumentów do odpowiadania na pytania i cytuj swoje źródła gdy jest to istotne.",
        
        "cs": "VŽDY odpovídej v češtině, i když jsou zdrojové dokumenty v jiných jazycích. Jsi užitečný a přesný AI asistent, který pomáhá uživatelům najít informace v poskytnutých dokumentech. Používej informace z dokumentů k odpovídání na otázky a cituj své zdroje, když je to relevantní.",
        
        "tr": "Kaynak belgeler başka dillerde olsa bile DAIMA Türkçe yanıtla. Kullanıcıların sağlanan belgelerde bilgi bulmalarına yardımcı olan yararlı ve doğru bir AI asistanısın. Soruları yanıtlamak için belgelerden bilgi kullan ve alakalı olduğunda kaynaklarını belirt.",
        
        "th": "ตอบเป็นภาษาไทยเสมอ แม้ว่าเอกสารต้นฉบับจะเป็นภาษาอื่น คุณเป็นผู้ช่วย AI ที่มีประโยชน์และแม่นยำ ที่ช่วยผู้ใช้ค้นหาข้อมูลในเอกสารที่ให้มา ใช้ข้อมูลจากเอกสารเพื่อตอบคำถาม และอ้างอิงแหล่งที่มาเมื่อเกี่ยวข้อง",
        
        "vi": "LUÔN trả lời bằng tiếng Việt, ngay cả khi tài liệu nguồn bằng ngôn ngữ khác. Bạn là một trợ lý AI hữu ích và chính xác giúp người dùng tìm thông tin trong các tài liệu được cung cấp. Sử dụng thông tin từ tài liệu để trả lời câu hỏi và trích dẫn nguồn khi có liên quan."
    }
    
    # Get the language-specific instruction
    language_instruction = language_instructions.get(language, language_instructions["en"])
    
    # Add response size instruction if not medium (localized by language)
    response_instruction = ""
    if response_size == "veryShort":
        if language == "fr":
            response_instruction = " IMPORTANT: Répondez de manière très concise en 1-2 phrases complètes maximum. Terminez votre réponse par un point final quand vous avez donné l'essentiel."
        else:
            response_instruction = " IMPORTANT: Respond very concisely with 1-2 complete sentences maximum. End your response when you have given the essential information."
    elif response_size == "comprehensive":
        if language == "fr":
            response_instruction = " IMPORTANT: Fournissez des réponses détaillées et complètes avec des explications approfondies, des exemples et du contexte supplémentaire."
        else:
            response_instruction = " IMPORTANT: Provide detailed and comprehensive responses with in-depth explanations, examples, and additional context."
    
    # Combine language and response size instructions
    combined_instruction = language_instruction + response_instruction
    
    # If a base message is provided, combine it with the enhanced instruction
    # IMPORTANT: Preserve the original base message which contains critical business logic
    if base_message and base_message.strip():
        return f"{base_message}\n\nIMPORTANT INSTRUCTION: {combined_instruction}"
    
    return combined_instruction


# Functions now imported from i18n module:
# - get_supported_languages()
# - is_language_supported()
# - normalize_language_code()