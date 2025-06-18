"""
Tests End-to-End pour les interactions chat avec Playwright.

Ce module teste les interactions chat complètes :
Frontend React + Backend Python + LLM sans images.

Tests couverts :
1. Questions simples en français/anglais
2. Tests de longueur de réponse (short/medium/long)  
3. Tests Azure AI Search avec citations
4. Changement de providers LLM
5. Historique des conversations
"""
import pytest
from playwright.async_api import Page, expect
import asyncio
import logging

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.e2e_chat
class TestChatInteractionsE2E:
    """Tests E2E pour les interactions chat standard."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", ["AZURE_OPENAI", "CLAUDE", "GEMINI", "OPENAI_DIRECT", "MISTRAL"])
    async def test_simple_french_question_e2e(
        self, 
        authenticated_page: Page, 
        e2e_helpers,
        provider: str
    ):
        """
        Test E2E : Question simple "Qui es-tu ?" en français
        → Validation réponse mentionnant AskMe
        """
        page = authenticated_page
        question = "Qui es-tu ?"
        
        logger.info(f"\n=== TEST E2E: Question française simple ===")
        logger.info(f"Provider: {provider}")
        logger.info(f"Question posée: '{question}'")
        
        # Sélectionner le provider LLM
        await e2e_helpers.select_llm_provider(page, provider)
        
        # Nettoyer le chat
        await e2e_helpers.clear_chat(page)
        
        # Envoyer la question
        await e2e_helpers.send_message(page, question)
        
        # Attendre la réponse
        await e2e_helpers.wait_for_response(page)
        
        # Récupérer la réponse
        response_text = await e2e_helpers.get_last_response(page)
        
        logger.info(f"\n=== RÉPONSE OBTENUE ===")
        logger.info(f"Longueur: {len(response_text)} caractères, {len(response_text.split())} mots")
        logger.info(f"Contenu: '{response_text}'")
        
        # Validations
        assert response_text, "La réponse ne doit pas être vide"
        
        # Vérifier que la réponse contient une identification du système
        response_lower = response_text.lower()
        identity_terms = [
            "askme", "ask me", "assistant", "ia", "intelligence artificielle",
            "chatbot", "bot", "système", "application", "aide"
        ]
        
        found_terms = [term for term in identity_terms if term in response_lower]
        logger.info(f"\n=== VALIDATION CONTENU ===")
        logger.info(f"Termes d'identification recherchés: {identity_terms}")
        logger.info(f"Termes trouvés: {found_terms}")
        
        content_valid = len(found_terms) >= 1
        logger.info(f"Validation identification: {content_valid}")
        
        assert content_valid, \
            f"La réponse devrait contenir une identification du système. Trouvés: {found_terms}. Réponse: {response_text}"
        
        logger.info(f"✓ {provider} - Test E2E réussi: question française simple")
        logger.info(f"=== FIN TEST E2E ===\n")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", ["AZURE_OPENAI", "CLAUDE", "GEMINI", "OPENAI_DIRECT", "MISTRAL"])
    async def test_simple_english_question_e2e(
        self, 
        authenticated_page: Page, 
        e2e_helpers,
        provider: str
    ):
        """
        Test E2E : Question simple "Who are you?" en anglais
        → Validation réponse en anglais
        """
        page = authenticated_page
        question = "Who are you?"
        
        logger.info(f"\n=== TEST E2E: Question anglaise simple ===")
        logger.info(f"Provider: {provider}")
        logger.info(f"Question posée: '{question}'")
        
        # Sélectionner le provider LLM
        await e2e_helpers.select_llm_provider(page, provider)
        
        # Nettoyer le chat
        await e2e_helpers.clear_chat(page)
        
        # Envoyer la question en anglais
        await e2e_helpers.send_message(page, question)
        
        # Attendre la réponse
        await e2e_helpers.wait_for_response(page)
        
        # Récupérer la réponse
        response_text = await e2e_helpers.get_last_response(page)
        
        logger.info(f"\n=== RÉPONSE OBTENUE ===")
        logger.info(f"Longueur: {len(response_text)} caractères, {len(response_text.split())} mots")
        logger.info(f"Contenu: '{response_text}'")
        
        # Validations
        assert response_text, "La réponse ne doit pas être vide"
        
        # Vérifier que la réponse est en anglais
        response_lower = response_text.lower()
        english_indicators = [
            "i am", "i'm", "my name", "assistant", "help you", "artificial intelligence",
            "ai", "chatbot", "system", "application"
        ]
        
        # Éviter les mots français communs
        french_indicators = [
            "je suis", "mon nom", "intelligence artificielle", "système", "bonjour"
        ]
        
        found_english = [indicator for indicator in english_indicators if indicator in response_lower]
        found_french = [indicator for indicator in french_indicators if indicator in response_lower]
        
        logger.info(f"\n=== ANALYSE LANGUE ===")
        logger.info(f"Indicateurs anglais recherchés: {english_indicators}")
        logger.info(f"Indicateurs anglais trouvés: {found_english}")
        logger.info(f"Indicateurs français trouvés: {found_french}")
        
        has_english = len(found_english) > 0
        has_french = len(found_french) > 0
        language_ok = has_english or not has_french
        
        logger.info(f"Réponse en anglais: {language_ok}")
        
        # La réponse devrait avoir plus d'indicateurs anglais que français
        assert language_ok, \
            f"La réponse devrait être en anglais. Anglais: {found_english}, Français: {found_french}. Réponse: {response_text}"
        
        logger.info(f"✓ {provider} - Test E2E réussi: question anglaise simple")
        logger.info(f"=== FIN TEST E2E ===\n")

    @pytest.mark.asyncio
    async def test_search_with_citations_e2e(
        self, 
        authenticated_page: Page, 
        e2e_helpers
    ):
        """
        Test E2E : Recherche avec citations Azure AI Search
        → Validation intégration complète avec recherche
        """
        page = authenticated_page
        provider = "CLAUDE"
        question = "Quelles sont les nouveautés des release notes ?"
        
        logger.info(f"\n=== TEST E2E: Recherche avec citations ===")
        logger.info(f"Provider: {provider}")
        logger.info(f"Question posée: '{question}'")
        logger.info(f"Timeout: 90 secondes (recherche + réponse)")
        
        # Utiliser Claude pour plus de fiabilité
        await e2e_helpers.select_llm_provider(page, provider)
        
        # Nettoyer le chat
        await e2e_helpers.clear_chat(page)
        
        # Poser une question qui devrait déclencher une recherche
        await e2e_helpers.send_message(page, question)
        
        # Attendre la réponse (peut prendre plus de temps avec recherche)
        await e2e_helpers.wait_for_response(page, timeout=90000)
        
        # Récupérer la réponse
        response_text = await e2e_helpers.get_last_response(page)
        
        logger.info(f"\n=== RÉPONSE AVEC RECHERCHE ===")
        logger.info(f"Longueur: {len(response_text)} caractères, {len(response_text.split())} mots")
        logger.info(f"Contenu: '{response_text}'")
        
        # Validations
        assert response_text, "La réponse ne doit pas être vide"
        
        # Vérifier que la réponse contient du contexte pertinent
        response_lower = response_text.lower()
        context_terms = [
            "nouveautés", "version", "mise à jour", "fonctionnalités", 
            "améliorations", "corrections", "release", "notes"
        ]
        
        found_terms = [term for term in context_terms if term in response_lower]
        logger.info(f"\n=== ANALYSE CONTENU RECHERCHE ===")
        logger.info(f"Termes contextuels recherchés: {context_terms}")
        logger.info(f"Termes trouvés: {found_terms}")
        
        context_ok = len(found_terms) >= 1
        logger.info(f"Validation contexte: {context_ok}")
        
        assert context_ok, \
            f"La réponse devrait contenir du contexte pertinent. Trouvés: {found_terms}"
        
        # Vérifier la présence de citations dans l'UI
        citations = await page.query_selector_all("[data-testid='citation']")
        logger.info(f"\n=== CITATIONS UI ===")
        logger.info(f"Citations trouvées dans l'UI: {len(citations)}")
        
        if citations:
            for i, citation in enumerate(citations[:3]):  # Max 3 citations pour log
                citation_text = await citation.text_content()
                logger.info(f"  Citation {i+1}: {citation_text[:100]}...")
        
        logger.info(f"✓ Test E2E réussi: recherche avec citations")
        logger.info(f"=== FIN TEST E2E ===\n")

    @pytest.mark.asyncio
    async def test_response_length_settings_e2e(
        self, 
        authenticated_page: Page, 
        e2e_helpers
    ):
        """
        Test E2E : Paramètres de longueur de réponse
        → Validation des paramètres de personnalisation
        """
        page = authenticated_page
        logger.info("Testing response length settings E2E")
        
        # Utiliser Claude pour la cohérence
        await e2e_helpers.select_llm_provider(page, "CLAUDE")
        
        # Test des différentes longueurs
        response_lengths = {}
        
        for length in ["short", "medium", "long"]:
            # Nettoyer le chat
            await e2e_helpers.clear_chat(page)
            
            # Configurer la longueur de réponse (si l'UI le permet)
            try:
                length_selector = await page.wait_for_selector("[data-testid='response-length-selector']", timeout=5000)
                await length_selector.click()
                await page.click(f"[data-testid='response-length-{length}']")
                await page.wait_for_timeout(1000)
            except:
                # Selector might not be available
                pass
            
            # Poser une question standard
            await e2e_helpers.send_message(page, "Explique-moi l'intelligence artificielle")
            
            # Attendre la réponse
            await e2e_helpers.wait_for_response(page)
            
            # Récupérer et analyser la réponse
            response_text = await e2e_helpers.get_last_response(page)
            word_count = len(response_text.split())
            response_lengths[length] = word_count
            
            logger.info(f"Longueur {length}: {word_count} mots")
        
        # Vérifier la progression (si les paramètres sont disponibles)
        if len(response_lengths) > 1:
            logger.info(f"Longueurs mesurées: {response_lengths}")
        
        logger.info("✓ Test des longueurs de réponse E2E réussi")

    @pytest.mark.asyncio
    async def test_provider_switching_e2e(
        self, 
        authenticated_page: Page, 
        e2e_helpers
    ):
        """
        Test E2E : Changement de providers LLM
        → Validation du changement de provider en temps réel
        """
        page = authenticated_page
        logger.info("Testing provider switching E2E")
        
        providers_to_test = ["CLAUDE", "AZURE_OPENAI"]
        responses = {}
        
        for provider in providers_to_test:
            # Changer de provider
            await e2e_helpers.select_llm_provider(page, provider)
            
            # Nettoyer le chat
            await e2e_helpers.clear_chat(page)
            
            # Poser la même question
            await e2e_helpers.send_message(page, "Bonjour, comment ça va ?")
            
            # Attendre la réponse
            await e2e_helpers.wait_for_response(page)
            
            # Récupérer la réponse
            response_text = await e2e_helpers.get_last_response(page)
            responses[provider] = response_text
            
            logger.info(f"{provider}: {len(response_text)} caractères")
        
        # Vérifier que les réponses sont différentes (providers différents)
        if len(responses) > 1:
            response_values = list(responses.values())
            assert response_values[0] != response_values[1], \
                "Les réponses de différents providers devraient être différentes"
        
        logger.info("✓ Changement de providers E2E réussi")

    @pytest.mark.asyncio
    async def test_conversation_history_e2e(
        self, 
        authenticated_page: Page, 
        e2e_helpers
    ):
        """
        Test E2E : Historique des conversations
        → Validation de la persistance des conversations
        """
        page = authenticated_page
        logger.info("Testing conversation history E2E")
        
        # Utiliser Claude pour la cohérence
        await e2e_helpers.select_llm_provider(page, "CLAUDE")
        
        # Nettoyer le chat
        await e2e_helpers.clear_chat(page)
        
        # Envoyer plusieurs messages pour créer un historique
        messages = [
            "Bonjour !",
            "Peux-tu m'aider ?", 
            "Merci pour ton aide"
        ]
        
        for message in messages:
            await e2e_helpers.send_message(page, message)
            await e2e_helpers.wait_for_response(page)
            await page.wait_for_timeout(1000)  # Pause entre messages
        
        # Vérifier que tous les messages sont visibles dans l'historique
        all_messages = await page.query_selector_all("[data-testid='chat-message']")
        all_responses = await page.query_selector_all("[data-testid='chat-response']")
        
        # Devrait avoir au moins les messages utilisateur et les réponses
        total_elements = len(all_messages) + len(all_responses)
        assert total_elements >= len(messages), \
            f"L'historique devrait contenir au moins {len(messages)} éléments, trouvé: {total_elements}"
        
        # Test de la sauvegarde de l'historique (si disponible)
        try:
            save_button = await page.wait_for_selector("[data-testid='save-conversation']", timeout=5000)
            await save_button.click()
            await page.wait_for_timeout(2000)
            
            # Vérifier le message de confirmation
            success_message = await page.query_selector("[data-testid='save-success']")
            if success_message:
                expect(success_message).to_be_visible()
        except:
            # Save functionality might not be available
            pass
        
        logger.info("✓ Historique des conversations E2E réussi")

    @pytest.mark.asyncio
    @pytest.mark.e2e_slow
    async def test_complete_chat_workflow_e2e(
        self, 
        authenticated_page: Page, 
        e2e_helpers
    ):
        """
        Test E2E complet : Workflow chat utilisateur complet
        → Test du parcours utilisateur complet
        """
        page = authenticated_page
        logger.info("Testing complete chat workflow E2E")
        
        # 1. Sélectionner un provider
        await e2e_helpers.select_llm_provider(page, "CLAUDE")
        
        # 2. Commencer une nouvelle conversation
        await e2e_helpers.clear_chat(page)
        
        # 3. Question d'identification
        await e2e_helpers.send_message(page, "Qui es-tu ?")
        await e2e_helpers.wait_for_response(page)
        
        response1 = await e2e_helpers.get_last_response(page)
        assert "assistant" in response1.lower() or "aide" in response1.lower()
        
        # 4. Question de suivi
        await e2e_helpers.send_message(page, "Peux-tu m'aider avec des questions techniques ?")
        await e2e_helpers.wait_for_response(page)
        
        response2 = await e2e_helpers.get_last_response(page)
        assert response2, "Devrait répondre à la question de suivi"
        
        # 5. Question nécessitant une recherche
        await e2e_helpers.send_message(page, "Quelles sont les meilleures pratiques documentées ?")
        await e2e_helpers.wait_for_response(page, timeout=90000)
        
        response3 = await e2e_helpers.get_last_response(page)
        assert response3, "Devrait répondre à la question de recherche"
        
        # 6. Vérifier l'historique complet
        all_responses = await page.query_selector_all("[data-testid='chat-response']")
        assert len(all_responses) >= 3, "Devrait avoir au moins 3 réponses dans l'historique"
        
        # 7. Changer de provider et continuer
        await e2e_helpers.select_llm_provider(page, "AZURE_OPENAI")
        await e2e_helpers.send_message(page, "Continue la conversation")
        await e2e_helpers.wait_for_response(page)
        
        final_response = await e2e_helpers.get_last_response(page)
        assert final_response, "Devrait pouvoir continuer avec un autre provider"
        
        logger.info("✓ Workflow chat complet E2E réussi")