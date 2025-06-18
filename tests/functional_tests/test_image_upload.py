"""
Tests d'upload d'images pour les LLM supportant les images.

Ce module teste la capacité des LLM avec support d'images à :
1. Analyser une image de bouteille cassée sur chaîne de production
2. Analyser une image de moteur d'avion en feu et retourner des procédures
3. Répondre dans la langue de la question (français/anglais)
4. Intégrer avec Azure AI Search pour les procédures d'incident

LLM testés : CLAUDE, GEMINI, OPENAI_DIRECT
"""
import pytest
import base64
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# Définir les LLM qui supportent les images
IMAGE_SUPPORTED_LLMS = ["CLAUDE", "GEMINI", "OPENAI_DIRECT"]


def encode_image_to_base64(image_path: str) -> str:
    """Encoder une image en base64 pour les LLM."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def create_image_message(image_path: str, text_prompt: str) -> dict:
    """
    Créer un message avec image au format OpenAI/Claude compatible.
    
    Args:
        image_path: Chemin vers l'image
        text_prompt: Texte de la question
        
    Returns:
        Message formaté avec image et texte
    """
    # Encoder l'image en base64
    base64_image = encode_image_to_base64(image_path)
    
    # Déterminer le type MIME
    extension = Path(image_path).suffix.lower()
    mime_type = "image/jpeg" if extension in [".jpg", ".jpeg"] else "image/png"
    
    # Format compatible avec OpenAI/Claude
    return {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": text_prompt
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}"
                }
            }
        ]
    }


class TestImageUpload:
    """Tests d'upload et analyse d'images pour les LLM supportés."""
    
    @pytest.fixture(autouse=True)
    def setup_test_paths(self):
        """Setup des chemins vers les images de test."""
        self.test_dir = Path(__file__).parent
        self.img_dir = self.test_dir / "img"
        self.test1_path = self.img_dir / "test1.jpg"  # Bouteille cassée
        self.test2_path = self.img_dir / "test2.jpg"  # Moteur avion en feu
        
        # Vérifier que les images existent
        if not self.test1_path.exists():
            pytest.skip(f"Image test1.jpg non trouvée: {self.test1_path}")
        if not self.test2_path.exists():
            pytest.skip(f"Image test2.jpg non trouvée: {self.test2_path}")

    @pytest.mark.image
    @pytest.mark.asyncio
    @pytest.mark.parametrize("llm_provider_type", IMAGE_SUPPORTED_LLMS)
    async def test_broken_bottle_analysis_french(self, llm_provider_type, llm_provider):
        """
        Test 1: Upload test1.jpg + "Qu'est-ce que tu vois ?" 
        → Système doit parler d'un problème de bouteille cassée sur chaîne de production
        """
        # Skip si le provider ne supporte pas les images
        if llm_provider_type not in IMAGE_SUPPORTED_LLMS:
            pytest.skip(f"Provider {llm_provider_type} ne supporte pas les images")
            
        question = "Qu'est-ce que tu vois ?"
        image_file = "test1.jpg"
        
        logger.info(f"\n=== TEST: Analyse bouteille cassée (français) ===")
        logger.info(f"Provider: {llm_provider_type}")
        logger.info(f"Image uploadée: {image_file}")
        logger.info(f"Question posée: '{question}'")
        
        # Créer le message avec image
        image_message = create_image_message(
            str(self.test1_path), 
            question
        )
        
        response, _ = await llm_provider.send_request(
            messages=[image_message],
            stream=False,
            response_size="medium"
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        # Extraire le contenu de la réponse
        content = self._extract_response_content(response)
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        logger.info(f"\n=== RÉPONSE OBTENUE ===")
        logger.info(f"Longueur: {len(content)} caractères, {len(content.split())} mots")
        logger.info(f"Description complète:\n{content}")
        
        # Vérifier que la réponse mentionne des éléments liés à la production/bouteille cassée
        content_lower = content.lower()
        production_terms = [
            "bouteille", "cassée", "cassé", "brisée", "brisé", "production", 
            "chaîne", "défaut", "problème", "incident", "usine", "fabrication",
            "verre", "éclat", "fragment", "damage", "broken", "factory"
        ]
        
        found_terms = [term for term in production_terms if term in content_lower]
        logger.info(f"\n=== ANALYSE DU CONTENU ===")
        logger.info(f"Termes recherchés: {production_terms}")
        logger.info(f"Termes trouvés: {found_terms}")
        logger.info(f"Nombre de termes pertinents: {len(found_terms)} (minimum: 2)")
        
        content_analysis_ok = len(found_terms) >= 2
        logger.info(f"Validation analyse: {content_analysis_ok}")
        
        assert content_analysis_ok, \
            f"La réponse devrait mentionner des termes liés à la production/bouteille cassée. Trouvés: {found_terms}. Description: {content}"
        
        logger.info(f"✓ {llm_provider_type} - Test réussi: identification bouteille cassée")
        logger.info(f"=== FIN TEST ===\n")

    @pytest.mark.image
    @pytest.mark.asyncio
    @pytest.mark.parametrize("llm_provider_type", IMAGE_SUPPORTED_LLMS)
    async def test_engine_fire_procedure_french(self, llm_provider_type, llm_provider):
        """
        Test 2: Upload test2.jpg + "Que faire ?" 
        → Système doit parler de procédure de gestion d'incident moteur d'avion en feu avec références Azure AI Search
        """
        if llm_provider_type not in IMAGE_SUPPORTED_LLMS:
            pytest.skip(f"Provider {llm_provider_type} ne supporte pas les images")
            
        question = "Que faire ?"
        image_file = "test2.jpg"
        
        logger.info(f"\n=== TEST: Procédure moteur en feu (français) ===")
        logger.info(f"Provider: {llm_provider_type}")
        logger.info(f"Image uploadée: {image_file}")
        logger.info(f"Question posée: '{question}'")
        logger.info(f"Documents demandés: 6 (pour procédures)")
        
        # Créer le message avec image
        image_message = create_image_message(
            str(self.test2_path), 
            "Que faire ?"
        )
        
        response, _ = await llm_provider.send_request(
            messages=[image_message],
            stream=False,
            response_size="medium",
            documents_count=6  # Demander des documents pour les procédures
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        content = self._extract_response_content(response)
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        # Vérifier que la réponse mentionne des éléments liés aux procédures d'urgence aviation
        content_lower = content.lower()
        aviation_emergency_terms = [
            "moteur", "feu", "incendie", "urgence", "procédure", "sécurité",
            "avion", "aviation", "pilote", "cockpit", "emergency", "engine", 
            "fire", "aircraft", "procedure", "evacuation", "évacuation"
        ]
        
        found_terms = [term for term in aviation_emergency_terms if term in content_lower]
        assert len(found_terms) >= 2, \
            f"La réponse devrait mentionner des termes liés aux procédures d'urgence aviation. Trouvés: {found_terms}. Contenu: {content}"
        
        # Vérifier la présence de citations (procédures documentées)
        citations = self._extract_citations(response, content)
        if len(citations) > 0:
            logger.info(f"Citations trouvées: {len(citations)} (procédures documentées)")
        else:
            logger.warning("Aucune citation trouvée - vérifier l'intégration Azure AI Search")
        
        logger.info(f"✓ {llm_provider_type} identifie correctement l'urgence moteur et suggère des procédures")

    @pytest.mark.image
    @pytest.mark.asyncio
    @pytest.mark.parametrize("llm_provider_type", IMAGE_SUPPORTED_LLMS)
    async def test_broken_bottle_analysis_english(self, llm_provider_type, llm_provider):
        """
        Test 3: Upload test1.jpg + "What do you see?" (English)
        → Réponse en anglais sur le problème de bouteille cassée
        """
        if llm_provider_type not in IMAGE_SUPPORTED_LLMS:
            pytest.skip(f"Provider {llm_provider_type} ne supporte pas les images")
            
        logger.info(f"Testing {llm_provider_type} - Broken bottle analysis (English)")
        
        # Créer le message avec image en anglais
        image_message = create_image_message(
            str(self.test1_path), 
            "What do you see?"
        )
        
        response, _ = await llm_provider.send_request(
            messages=[image_message],
            stream=False,
            response_size="medium"
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        content = self._extract_response_content(response)
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        # Vérifier que la réponse est en anglais et mentionne les bons éléments
        content_lower = content.lower()
        
        # Termes anglais pour production/bouteille cassée
        english_production_terms = [
            "bottle", "broken", "shattered", "production", "line", "manufacturing",
            "factory", "defect", "problem", "incident", "glass", "fragment"
        ]
        
        # Éviter les termes français
        french_terms = [
            "bouteille", "cassée", "production", "chaîne", "usine", "problème"
        ]
        
        english_found = [term for term in english_production_terms if term in content_lower]
        french_found = [term for term in french_terms if term in content_lower]
        
        assert len(english_found) >= 2, \
            f"La réponse devrait contenir des termes anglais liés à la production. Trouvés: {english_found}"
        
        # La réponse devrait avoir plus de termes anglais que français
        assert len(english_found) >= len(french_found), \
            f"La réponse devrait être principalement en anglais. Anglais: {english_found}, Français: {french_found}"
        
        logger.info(f"✓ {llm_provider_type} répond en anglais pour l'analyse de bouteille cassée")

    @pytest.mark.image
    @pytest.mark.asyncio
    @pytest.mark.parametrize("llm_provider_type", IMAGE_SUPPORTED_LLMS)
    async def test_engine_fire_procedure_english(self, llm_provider_type, llm_provider):
        """
        Test 4: Upload test2.jpg + "What to do?" (English)
        → Réponse en anglais sur les procédures d'urgence moteur d'avion
        """
        if llm_provider_type not in IMAGE_SUPPORTED_LLMS:
            pytest.skip(f"Provider {llm_provider_type} ne supporte pas les images")
            
        logger.info(f"Testing {llm_provider_type} - Engine fire procedure (English)")
        
        # Créer le message avec image en anglais
        image_message = create_image_message(
            str(self.test2_path), 
            "What to do?"
        )
        
        response, _ = await llm_provider.send_request(
            messages=[image_message],
            stream=False,
            response_size="medium",
            documents_count=6
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        content = self._extract_response_content(response)
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        # Vérifier les termes anglais d'urgence aviation
        content_lower = content.lower()
        english_aviation_terms = [
            "engine", "fire", "emergency", "procedure", "aircraft", "pilot",
            "safety", "evacuation", "shutdown", "cockpit", "crew"
        ]
        
        # Éviter les termes français
        french_aviation_terms = [
            "moteur", "feu", "urgence", "procédure", "avion", "pilote", "sécurité"
        ]
        
        english_found = [term for term in english_aviation_terms if term in content_lower]
        french_found = [term for term in french_aviation_terms if term in content_lower]
        
        assert len(english_found) >= 2, \
            f"La réponse devrait contenir des termes anglais d'urgence aviation. Trouvés: {english_found}"
        
        # La réponse devrait être principalement en anglais
        assert len(english_found) >= len(french_found), \
            f"La réponse devrait être principalement en anglais. Anglais: {english_found}, Français: {french_found}"
        
        # Vérifier les citations de procédures
        citations = self._extract_citations(response, content)
        if len(citations) > 0:
            logger.info(f"Citations trouvées: {len(citations)} (procédures documentées)")
        
        logger.info(f"✓ {llm_provider_type} répond en anglais pour les procédures d'urgence moteur")

    @pytest.mark.image
    @pytest.mark.asyncio
    @pytest.mark.parametrize("llm_provider_type", IMAGE_SUPPORTED_LLMS)
    async def test_image_analysis_consistency(self, llm_provider_type, llm_provider):
        """
        Test 5: Vérifier la cohérence d'analyse entre français et anglais pour la même image
        """
        if llm_provider_type not in IMAGE_SUPPORTED_LLMS:
            pytest.skip(f"Provider {llm_provider_type} ne supporte pas les images")
            
        logger.info(f"Testing {llm_provider_type} - Image analysis consistency")
        
        # Analyser la même image en français et anglais
        french_message = create_image_message(
            str(self.test1_path), 
            "Décris ce que tu vois dans cette image"
        )
        
        english_message = create_image_message(
            str(self.test1_path), 
            "Describe what you see in this image"
        )
        
        # Réponse française
        french_response, _ = await llm_provider.send_request(
            messages=[french_message],
            stream=False,
            response_size="medium"
        )
        
        # Réponse anglaise
        english_response, _ = await llm_provider.send_request(
            messages=[english_message],
            stream=False,
            response_size="medium"
        )
        
        french_content = self._extract_response_content(french_response)
        english_content = self._extract_response_content(english_response)
        
        assert french_content and english_content, "Les deux réponses doivent avoir du contenu"
        
        # Les réponses ne devraient pas être identiques
        assert french_content.lower() != english_content.lower(), \
            "Les réponses dans différentes langues ne devraient pas être identiques"
        
        # Vérifier que les deux décrivent des éléments similaires (bouteille/bottle)
        french_lower = french_content.lower()
        english_lower = english_content.lower()
        
        bottle_terms_fr = ["bouteille", "verre", "cassé", "brisé"]
        bottle_terms_en = ["bottle", "glass", "broken", "shattered"]
        
        french_has_bottle = any(term in french_lower for term in bottle_terms_fr)
        english_has_bottle = any(term in english_lower for term in bottle_terms_en)
        
        assert french_has_bottle and english_has_bottle, \
            "Les deux réponses devraient identifier l'objet principal (bouteille/bottle)"
        
        logger.info(f"✓ {llm_provider_type} maintient la cohérence d'analyse entre langues")

    def _extract_response_content(self, response):
        """Extraire le contenu textuel de la réponse."""
        if hasattr(response, 'choices') and response.choices:
            return response.choices[0].message.content
        elif hasattr(response, 'content'):
            return response.content
        elif isinstance(response, dict) and 'choices' in response:
            return response['choices'][0]['message']['content']
        else:
            return str(response)

    def _extract_citations(self, response, content):
        """Extraire les citations de la réponse."""
        citations = []
        
        # Citations dans la métadata
        if hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'context') and choice.context:
                if hasattr(choice.context, 'citations') and choice.context.citations:
                    citations.extend(choice.context.citations)
        elif isinstance(response, dict) and 'choices' in response:
            choice = response['choices'][0]
            if 'context' in choice and choice['context']:
                if 'citations' in choice['context']:
                    citations.extend(choice['context']['citations'])
        
        # Citations dans le texte (format [doc1], [doc2], etc.)
        import re
        text_citations = re.findall(r'\[([^\]]+)\]', content)
        if text_citations:
            citations.extend([{'content': cite} for cite in text_citations])
        
        return citations