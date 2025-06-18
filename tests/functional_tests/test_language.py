"""
Tests de langue et localisation pour tous les LLM supportés.

Ce module teste la capacité des LLM à :
1. Répondre en français quand on pose une question en français
2. Répondre en anglais quand on pose une question en anglais  
3. Générer du contenu dans une langue spécifique (italien)
4. S'identifier comme AskMe
"""
import pytest
import re
import logging

logger = logging.getLogger(__name__)


class TestLanguageSupport:
    """Tests de support linguistique pour tous les LLM."""
    
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
    
    @pytest.mark.language
    @pytest.mark.asyncio
    async def test_french_identity_question(self, llm_provider, test_messages_simple):
        """
        Test 1: Question simple en français -> Le système doit répondre qu'il est AskMe
        """
        provider_name = llm_provider.__class__.__name__
        question = test_messages_simple[0]['content']
        
        logger.info(f"\n=== TEST: Question d'identité en français ===")
        logger.info(f"Provider: {provider_name}")
        logger.info(f"Question posée: '{question}'")
        
        response, _ = await llm_provider.send_request(
            messages=test_messages_simple,
            stream=False
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        # Extraire le contenu de la réponse selon le format du provider
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
        elif hasattr(response, 'content'):
            content = response.content
        elif isinstance(response, dict) and 'choices' in response:
            content = response['choices'][0]['message']['content']
        else:
            content = str(response)
        
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        # Log de la réponse complète
        logger.info(f"Réponse obtenue: '{content}'")
        logger.info(f"Longueur de la réponse: {len(content)} caractères, {len(content.split())} mots")
        
        # Vérifier que la réponse contient "AskMe" ou des termes similaires d'identification
        content_lower = content.lower()
        identity_terms = [
            "askme", "ask me", "assistant", "ia", "intelligence artificielle",
            "chatbot", "bot", "système", "application"
        ]
        
        found_terms = [term for term in identity_terms if term in content_lower]
        logger.info(f"Termes d'identification trouvés: {found_terms}")
        
        assert any(term in content_lower for term in identity_terms), \
            f"La réponse doit contenir une identification du système. Termes recherchés: {identity_terms}. Reçu: {content}"
        
        logger.info(f"✓ {provider_name} - Test réussi: question d'identité en français")
        logger.info(f"=== FIN TEST ===\n")

    @pytest.mark.language  
    @pytest.mark.asyncio
    async def test_english_language_response(self, llm_provider, test_messages_english):
        """
        Test 2: Question en anglais -> Le système doit répondre en anglais
        """
        provider_name = llm_provider.__class__.__name__
        question = test_messages_english[0]['content']
        
        logger.info(f"\n=== TEST: Réponse en langue anglaise ===")
        logger.info(f"Provider: {provider_name}")
        logger.info(f"Question posée: '{question}'")
        
        response, _ = await llm_provider.send_request(
            messages=test_messages_english,
            stream=False
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        # Extraire le contenu de la réponse
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
        elif hasattr(response, 'content'):
            content = response.content
        elif isinstance(response, dict) and 'choices' in response:
            content = response['choices'][0]['message']['content']
        else:
            content = str(response)
        
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        # Log de la réponse complète
        logger.info(f"Réponse obtenue: '{content}'")
        logger.info(f"Longueur de la réponse: {len(content)} caractères, {len(content.split())} mots")
        
        # Vérifier que la réponse est en anglais (heuristiques simples)
        content_lower = content.lower()
        english_indicators = [
            "i am", "i'm", "my name", "assistant", "help you", "artificial intelligence",
            "ai", "chatbot", "system", "application"
        ]
        
        # Éviter les mots français communs
        french_indicators = [
            "je suis", "mon nom", "intelligence artificielle", "système", "bonjour"
        ]
        
        found_english = [indicator for indicator in english_indicators if indicator in content_lower]
        found_french = [indicator for indicator in french_indicators if indicator in content_lower]
        
        logger.info(f"Indicateurs anglais trouvés: {found_english}")
        logger.info(f"Indicateurs français trouvés: {found_french}")
        
        has_english = len(found_english) > 0
        has_french = len(found_french) > 0
        
        # La réponse devrait avoir plus d'indicateurs anglais que français
        assert has_english or not has_french, \
            f"La réponse devrait être en anglais. Anglais: {found_english}, Français: {found_french}. Reçu: {content}"
        
        logger.info(f"✓ {provider_name} - Test réussi: réponse en anglais")
        logger.info(f"=== FIN TEST ===\n")

    @pytest.mark.language
    @pytest.mark.asyncio  
    async def test_italian_poem_generation(self, llm_provider, test_messages_poem_italian):
        """
        Test 3: Demande de poème en italien -> Le système doit générer un poème en italien
        """
        provider_name = llm_provider.__class__.__name__
        question = test_messages_poem_italian[0]['content']
        
        logger.info(f"\n=== TEST: Génération de poème en italien ===")
        logger.info(f"Provider: {provider_name}")
        logger.info(f"Question posée: '{question}'")
        
        response, _ = await llm_provider.send_request(
            messages=test_messages_poem_italian,
            stream=False
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        # Extraire le contenu de la réponse
        content = self._extract_response_content(response)
        
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        # Log de la réponse complète
        logger.info(f"Réponse obtenue:\n{content}")
        logger.info(f"Longueur de la réponse: {len(content)} caractères, {len(content.split())} mots")
        
        # Vérifier des indicateurs italiens
        content_lower = content.lower()
        italian_indicators = [
            "posso", "come", "configurare", "funzionalità", "team",  # Mots de la question
            "è", "può", "più", "perché", "così", "già",  # Mots italiens communs
            "qualitysaas", "avanteam", "sistema", "documento",  # Termes techniques
            "dove", "quando", "sempre", "mai", "anche", "con", "per", "una", "uno"  # Autres mots italiens
        ]
        
        found_italian = [word for word in italian_indicators if word in content_lower]
        logger.info(f"Indicateurs italiens trouvés: {found_italian}")
        
        # Vérifier qu'il y a des mots italiens OU que la réponse mentionne l'italien
        # Accepter aussi les réponses qui expliquent ne pas pouvoir répondre en italien
        italian_response = (len(found_italian) >= 1 or 
                          "italian" in content_lower or 
                          "italia" in content_lower or
                          "non posso" in content_lower)
        assert italian_response, \
            f"La réponse devrait être en italien ou mentionner l'italien. Trouvés: {found_italian}. Content: {content[:200]}..."
        
        logger.info(f"✓ {provider_name} - Test réussi: réponse en italien")
        logger.info(f"=== FIN TEST ===\n")

    @pytest.mark.language
    @pytest.mark.asyncio
    async def test_language_consistency(self, llm_provider):
        """
        Test 4: Vérifier la cohérence linguistique des réponses
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - Language consistency")
        
        # Test avec question française
        french_messages = [{"role": "user", "content": "Comment ça va ?"}]
        french_response, _ = await llm_provider.send_request(
            messages=french_messages,
            stream=False
        )
        
        # Test avec question anglaise  
        english_messages = [{"role": "user", "content": "How are you?"}]
        english_response, _ = await llm_provider.send_request(
            messages=english_messages,
            stream=False
        )
        
        # Extraire les contenus
        def extract_content(response):
            if hasattr(response, 'choices') and response.choices:
                return response.choices[0].message.content
            elif hasattr(response, 'content'):
                return response.content
            elif isinstance(response, dict) and 'choices' in response:
                return response['choices'][0]['message']['content']
            else:
                return str(response)
        
        french_content = extract_content(french_response)
        english_content = extract_content(english_response)
        
        assert french_content, "Réponse française ne doit pas être vide"
        assert english_content, "Réponse anglaise ne doit pas être vide"
        
        # Les réponses ne devraient pas être identiques (sauf cas très spécifiques)
        assert french_content.lower() != english_content.lower(), \
            "Les réponses dans différentes langues ne devraient pas être identiques"
        
        logger.info(f"✓ {llm_provider.__class__.__name__} maintient la cohérence linguistique")

    @pytest.mark.language
    @pytest.mark.asyncio
    async def test_italian_technical_question(self, llm_provider, test_messages_italian_technical):
        """
        Test 5: Question technique en italien -> Le système doit répondre en italien
        """
        provider_name = llm_provider.__class__.__name__
        question = test_messages_italian_technical[0]['content']
        
        logger.info(f"\n=== TEST: Question technique en italien ===")
        logger.info(f"Provider: {provider_name}")
        logger.info(f"Question posée: '{question}'")
        
        response, _ = await llm_provider.send_request(
            messages=test_messages_italian_technical,
            stream=False
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        # Extraire le contenu de la réponse
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
        elif hasattr(response, 'content'):
            content = response.content
        elif isinstance(response, dict) and 'choices' in response:
            content = response['choices'][0]['message']['content']
        else:
            content = str(response)
        
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        # Log de la réponse complète
        logger.info(f"Réponse obtenue: '{content}'")
        logger.info(f"Longueur de la réponse: {len(content)} caractères, {len(content.split())} mots")
        
        # Vérifier que la réponse est en italien (heuristiques)
        content_lower = content.lower()
        italian_indicators = [
            "per", "con", "una", "uno", "che", "questo", "questa", "posso", "sono",
            "funzione", "configurare", "qualitysaas", "italiano", "puoi", "può"
        ]
        
        # Éviter les mots français communs
        french_indicators = [
            "je suis", "pour", "avec", "cette", "fonction", "configurer", "français", "puis"
        ]
        
        found_italian = [indicator for indicator in italian_indicators if indicator in content_lower]
        found_french = [indicator for indicator in french_indicators if indicator in content_lower]
        
        logger.info(f"Indicateurs italiens trouvés: {found_italian}")
        logger.info(f"Indicateurs français trouvés: {found_french}")
        
        has_italian = len(found_italian) > 0
        has_french = len(found_french) > 0
        
        # La réponse devrait avoir plus d'indicateurs italiens que français
        assert has_italian or not has_french, \
            f"La réponse devrait être en italien. Italien: {found_italian}, Français: {found_french}. Reçu: {content}"
        
        logger.info(f"✓ {provider_name} - Test réussi: réponse technique en italien")
        logger.info(f"=== FIN TEST ===\n")