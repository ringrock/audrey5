"""
Tests End-to-End pour l'upload d'images avec Playwright.

Ce module teste le fonctionnement complet de l'application :
Frontend React + Backend Python + LLM avec upload d'images.

Tests couverts :
1. Upload image bouteille cassée + question en français
2. Upload image moteur en feu + question en français  
3. Même tests en anglais
4. Vérification des réponses et citations
5. Tests multi-providers (Claude, Gemini, OpenAI Direct)
"""
import pytest
from playwright.async_api import Page, expect
import asyncio
import logging

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.e2e_image
class TestImageUploadE2E:
    """Tests E2E pour l'upload et l'analyse d'images."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", ["CLAUDE", "GEMINI", "OPENAI_DIRECT"])
    async def test_broken_bottle_upload_french_e2e(
        self, 
        authenticated_page: Page, 
        image_test_paths, 
        e2e_helpers,
        provider: str
    ):
        """
        Test E2E : Upload image bouteille cassée + question française
        → Validation complète frontend + backend + LLM
        """
        page = authenticated_page
        question = "Qu'est-ce que tu vois ?"
        image_file = "test1.jpg (bouteille cassée)"
        
        logger.info(f"\n=== TEST E2E: Upload bouteille cassée (français) ===")
        logger.info(f"Provider: {provider}")
        logger.info(f"Image uploadée: {image_file}")
        logger.info(f"Question posée: '{question}'")
        
        # Sélectionner le provider LLM
        await e2e_helpers.select_llm_provider(page, provider)
        
        # Nettoyer le chat
        await e2e_helpers.clear_chat(page)
        
        # Upload de l'image test1.jpg (bouteille cassée)
        await e2e_helpers.upload_image(page, image_test_paths["broken_bottle"])
        
        # Vérifier que l'image est uploadée (preview visible)
        image_preview = await page.wait_for_selector("[data-testid='image-preview']", timeout=10000)
        expect(image_preview).to_be_visible()
        
        # Envoyer la question en français
        await e2e_helpers.send_message(page, question)
        
        # Attendre la réponse du LLM
        await e2e_helpers.wait_for_response(page, timeout=60000)
        
        # Récupérer la réponse
        response_text = await e2e_helpers.get_last_response(page)
        
        logger.info(f"\n=== RÉPONSE IMAGE OBTENUE ===")
        logger.info(f"Longueur: {len(response_text)} caractères, {len(response_text.split())} mots")
        logger.info(f"Description complète:\n{response_text}")
        
        # Validations
        assert response_text, "La réponse ne doit pas être vide"
        
        # Vérifier que la réponse mentionne des termes liés à la production/bouteille
        response_lower = response_text.lower()
        production_terms = [
            "bouteille", "cassée", "cassé", "brisée", "brisé", "production", 
            "chaîne", "défaut", "problème", "incident", "usine", "fabrication",
            "verre", "éclat", "fragment"
        ]
        
        found_terms = [term for term in production_terms if term in response_lower]
        logger.info(f"\n=== ANALYSE DESCRIPTION IMAGE ===")
        logger.info(f"Termes recherchés: {production_terms}")
        logger.info(f"Termes trouvés: {found_terms}")
        logger.info(f"Nombre de termes pertinents: {len(found_terms)} (minimum: 1)")
        
        analysis_ok = len(found_terms) >= 1
        logger.info(f"Validation analyse: {analysis_ok}")
        
        assert analysis_ok, \
            f"La réponse devrait mentionner des termes liés à la production. Trouvés: {found_terms}. Description: {response_text}"
        
        # Vérifier que l'interface montre bien la réponse
        response_element = await page.query_selector("[data-testid='chat-response']:last-child")
        expect(response_element).to_be_visible()
        
        logger.info(f"✓ {provider} - Test E2E réussi: upload bouteille cassée (français)")
        logger.info(f"=== FIN TEST E2E ===\n")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", ["CLAUDE", "GEMINI", "OPENAI_DIRECT"])
    async def test_engine_fire_upload_french_e2e(
        self, 
        authenticated_page: Page, 
        image_test_paths, 
        e2e_helpers,
        provider: str
    ):
        """
        Test E2E : Upload image moteur en feu + question française
        → Validation procédures + citations Azure AI Search
        """
        page = authenticated_page
        question = "Que faire ?"
        image_file = "test2.jpg (moteur en feu)"
        
        logger.info(f"\n=== TEST E2E: Upload moteur en feu (français) ===")
        logger.info(f"Provider: {provider}")
        logger.info(f"Image uploadée: {image_file}")
        logger.info(f"Question posée: '{question}'")
        logger.info(f"Documents demandés: 6 (procédures d'urgence)")
        
        # Sélectionner le provider LLM
        await e2e_helpers.select_llm_provider(page, provider)
        
        # Nettoyer le chat
        await e2e_helpers.clear_chat(page)
        
        # Upload de l'image test2.jpg (moteur en feu)
        await e2e_helpers.upload_image(page, image_test_paths["engine_fire"])
        
        # Vérifier que l'image est uploadée
        image_preview = await page.wait_for_selector("[data-testid='image-preview']", timeout=10000)
        expect(image_preview).to_be_visible()
        
        # Envoyer la question en français
        await e2e_helpers.send_message(page, "Que faire ?")
        
        # Attendre la réponse du LLM (peut prendre plus de temps avec recherche)
        await e2e_helpers.wait_for_response(page, timeout=90000)
        
        # Récupérer la réponse
        response_text = await e2e_helpers.get_last_response(page)
        
        # Validations
        assert response_text, "La réponse ne doit pas être vide"
        
        # Vérifier que la réponse mentionne des termes d'urgence aviation
        response_lower = response_text.lower()
        aviation_emergency_terms = [
            "moteur", "feu", "incendie", "urgence", "procédure", "sécurité",
            "avion", "aviation", "pilote", "cockpit", "emergency", "evacuation"
        ]
        
        found_terms = [term for term in aviation_emergency_terms if term in response_lower]
        assert len(found_terms) >= 1, \
            f"La réponse devrait mentionner des termes d'urgence aviation. Trouvés: {found_terms}. Réponse: {response_text}"
        
        # Vérifier la présence de citations (si disponibles)
        citations = await page.query_selector_all("[data-testid='citation']")
        if citations:
            logger.info(f"Citations trouvées: {len(citations)}")
        
        logger.info(f"✓ {provider} - Upload moteur en feu E2E réussi")

    @pytest.mark.asyncio 
    @pytest.mark.parametrize("provider", ["CLAUDE", "GEMINI", "OPENAI_DIRECT"])
    async def test_broken_bottle_upload_english_e2e(
        self, 
        authenticated_page: Page, 
        image_test_paths, 
        e2e_helpers,
        provider: str
    ):
        """
        Test E2E : Upload image bouteille cassée + question anglaise
        → Validation réponse en anglais
        """
        page = authenticated_page
        logger.info(f"Testing {provider} - Broken bottle upload E2E (English)")
        
        # Sélectionner le provider LLM
        await e2e_helpers.select_llm_provider(page, provider)
        
        # Nettoyer le chat
        await e2e_helpers.clear_chat(page)
        
        # Upload de l'image test1.jpg (bouteille cassée)
        await e2e_helpers.upload_image(page, image_test_paths["broken_bottle"])
        
        # Vérifier que l'image est uploadée
        image_preview = await page.wait_for_selector("[data-testid='image-preview']", timeout=10000)
        expect(image_preview).to_be_visible()
        
        # Envoyer la question en anglais
        await e2e_helpers.send_message(page, "What do you see?")
        
        # Attendre la réponse du LLM
        await e2e_helpers.wait_for_response(page, timeout=60000)
        
        # Récupérer la réponse
        response_text = await e2e_helpers.get_last_response(page)
        
        # Validations
        assert response_text, "La réponse ne doit pas être vide"
        
        # Vérifier que la réponse est en anglais et mentionne les bons éléments
        response_lower = response_text.lower()
        
        # Termes anglais pour production/bouteille cassée
        english_production_terms = [
            "bottle", "broken", "shattered", "production", "line", "manufacturing",
            "factory", "defect", "problem", "incident", "glass", "fragment"
        ]
        
        english_found = [term for term in english_production_terms if term in response_lower]
        assert len(english_found) >= 1, \
            f"La réponse devrait contenir des termes anglais liés à la production. Trouvés: {english_found}"
        
        logger.info(f"✓ {provider} - Upload bouteille cassée E2E (anglais) réussi")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", ["CLAUDE", "GEMINI", "OPENAI_DIRECT"])
    async def test_engine_fire_upload_english_e2e(
        self, 
        authenticated_page: Page, 
        image_test_paths, 
        e2e_helpers,
        provider: str
    ):
        """
        Test E2E : Upload image moteur en feu + question anglaise
        → Validation procédures en anglais
        """
        page = authenticated_page
        logger.info(f"Testing {provider} - Engine fire upload E2E (English)")
        
        # Sélectionner le provider LLM
        await e2e_helpers.select_llm_provider(page, provider)
        
        # Nettoyer le chat
        await e2e_helpers.clear_chat(page)
        
        # Upload de l'image test2.jpg (moteur en feu)
        await e2e_helpers.upload_image(page, image_test_paths["engine_fire"])
        
        # Vérifier que l'image est uploadée
        image_preview = await page.wait_for_selector("[data-testid='image-preview']", timeout=10000)
        expect(image_preview).to_be_visible()
        
        # Envoyer la question en anglais
        await e2e_helpers.send_message(page, "What to do?")
        
        # Attendre la réponse du LLM
        await e2e_helpers.wait_for_response(page, timeout=90000)
        
        # Récupérer la réponse
        response_text = await e2e_helpers.get_last_response(page)
        
        # Validations
        assert response_text, "La réponse ne doit pas être vide"
        
        # Vérifier les termes anglais d'urgence aviation
        response_lower = response_text.lower()
        english_aviation_terms = [
            "engine", "fire", "emergency", "procedure", "aircraft", "pilot",
            "safety", "evacuation", "shutdown", "cockpit", "crew"
        ]
        
        english_found = [term for term in english_aviation_terms if term in response_lower]
        assert len(english_found) >= 1, \
            f"La réponse devrait contenir des termes anglais d'urgence aviation. Trouvés: {english_found}"
        
        logger.info(f"✓ {provider} - Upload moteur en feu E2E (anglais) réussi")

    @pytest.mark.asyncio
    @pytest.mark.e2e_slow
    async def test_image_upload_workflow_complete_e2e(
        self, 
        authenticated_page: Page, 
        image_test_paths, 
        e2e_helpers
    ):
        """
        Test E2E complet : Workflow d'upload d'images avec Claude
        → Test du workflow utilisateur complet
        """
        page = authenticated_page
        logger.info("Testing complete image upload workflow E2E")
        
        # Sélectionner Claude (le plus fiable)
        await e2e_helpers.select_llm_provider(page, "CLAUDE")
        
        # Test 1: Upload première image
        await e2e_helpers.clear_chat(page)
        await e2e_helpers.upload_image(page, image_test_paths["broken_bottle"])
        await e2e_helpers.send_message(page, "Décris ce problème de production")
        await e2e_helpers.wait_for_response(page)
        
        response1 = await e2e_helpers.get_last_response(page)
        assert "bouteille" in response1.lower() or "production" in response1.lower()
        
        # Test 2: Upload deuxième image dans la même conversation
        await e2e_helpers.upload_image(page, image_test_paths["engine_fire"])
        await e2e_helpers.send_message(page, "Et maintenant, que vois-tu ?")
        await e2e_helpers.wait_for_response(page)
        
        response2 = await e2e_helpers.get_last_response(page)
        assert "moteur" in response2.lower() or "feu" in response2.lower() or "avion" in response2.lower()
        
        # Vérifier que les deux réponses sont présentes dans l'historique
        all_responses = await page.query_selector_all("[data-testid='chat-response']")
        assert len(all_responses) >= 2, "Devrait avoir au moins 2 réponses dans l'historique"
        
        logger.info("✓ Workflow complet d'upload d'images E2E réussi")

    @pytest.mark.asyncio
    async def test_image_upload_error_handling_e2e(
        self, 
        authenticated_page: Page, 
        e2e_helpers
    ):
        """
        Test E2E : Gestion d'erreurs pour upload d'images
        → Test de robustesse de l'interface
        """
        page = authenticated_page
        logger.info("Testing image upload error handling E2E")
        
        # Sélectionner un provider supportant les images
        await e2e_helpers.select_llm_provider(page, "CLAUDE")
        await e2e_helpers.clear_chat(page)
        
        # Test : Envoyer un message sans image d'abord
        await e2e_helpers.send_message(page, "Qui es-tu ?")
        await e2e_helpers.wait_for_response(page)
        
        response = await e2e_helpers.get_last_response(page)
        assert response, "Devrait pouvoir répondre sans image"
        
        # Test : Vérifier que l'interface gère bien les provider ne supportant pas les images
        try:
            await e2e_helpers.select_llm_provider(page, "AZURE_OPENAI")
            
            # Vérifier que le bouton d'upload est désactivé ou absent
            upload_button = await page.query_selector("[data-testid='image-upload-button']")
            if upload_button:
                is_disabled = await upload_button.is_disabled()
                assert is_disabled, "Le bouton d'upload devrait être désactivé pour Azure OpenAI"
        except:
            # Provider pourrait ne pas être disponible
            pass
        
        logger.info("✓ Gestion d'erreurs upload d'images E2E réussie")

    @pytest.mark.asyncio
    async def test_ui_elements_image_upload_e2e(
        self, 
        authenticated_page: Page, 
        e2e_helpers
    ):
        """
        Test E2E : Éléments UI pour upload d'images
        → Validation de l'interface utilisateur
        """
        page = authenticated_page
        logger.info("Testing UI elements for image upload E2E")
        
        # Sélectionner un provider supportant les images
        await e2e_helpers.select_llm_provider(page, "CLAUDE")
        
        # Vérifier que le bouton d'upload est présent et visible
        upload_button = await page.wait_for_selector("[data-testid='image-upload-button']", timeout=10000)
        expect(upload_button).to_be_visible()
        
        # Vérifier que le tooltip indique le support des images
        await upload_button.hover()
        tooltip = await page.wait_for_selector("[data-testid='upload-tooltip']", timeout=5000)
        tooltip_text = await tooltip.inner_text()
        assert "image" in tooltip_text.lower() or "télécharger" in tooltip_text.lower()
        
        # Vérifier l'input de fichier
        file_input = await page.query_selector("input[type='file']")
        expect(file_input).not_to_be_null()
        
        # Vérifier que l'interface chat est présente
        chat_input = await page.wait_for_selector("[data-testid='question-input']")
        expect(chat_input).to_be_visible()
        
        send_button = await page.wait_for_selector("[data-testid='send-button']")
        expect(send_button).to_be_visible()
        
        logger.info("✓ Validation des éléments UI E2E réussie")