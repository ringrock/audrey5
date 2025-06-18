"""
Tests Azure AI Search avec citations pour tous les LLM supportés.

Ce module teste la capacité des LLM à :
1. Interroger l'index Azure AI Search
2. Retourner des citations vers les documents sources
3. Répondre dans la langue de la question 
4. Maintenir la cohérence des citations entre langues
"""
import pytest
import re
import json
import logging

logger = logging.getLogger(__name__)


class TestAzureAISearch:
    """Tests Azure AI Search et citations pour tous les LLM."""
    
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
        
        # Citations dans le texte
        text_citations = re.findall(r'\[([^\]]+)\]', content)
        if text_citations:
            citations.extend([{'content': cite} for cite in text_citations])
        
        return citations

    def _validate_citation_structure(self, citation):
        """Valider qu'une citation a la structure minimale attendue."""
        assert isinstance(citation, dict), f"Citation devrait être un dict: {citation}"
        
        has_identifier = any(key in citation for key in ['id', 'url', 'title', 'filename'])
        has_content = 'content' in citation and citation['content']
        
        assert has_identifier or has_content, \
            f"Citation devrait avoir un identificateur ou du contenu: {citation}"
    
    @pytest.mark.search
    @pytest.mark.asyncio
    async def test_search_french_with_citations(self, llm_provider, test_messages_search_french):
        """
        Test 4: Question sur les nouveautés -> Réponse cohérente avec citations Azure AI Search
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - French search with citations")
        
        response, _ = await llm_provider.send_request(
            messages=test_messages_search_french,
            stream=False,
            documents_count=6  # Demander 6 documents par défaut
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        # Extraire le contenu de la réponse
        content = self._extract_response_content(response)
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        # Vérifier que la réponse est en français
        content_lower = content.lower()
        french_indicators = [
            "nouveautés", "version", "mise à jour", "fonctionnalités", 
            "améliorations", "corrections", "ajouts", "modifications"
        ]
        
        has_french_context = any(indicator in content_lower for indicator in french_indicators)
        assert has_french_context, f"La réponse devrait contenir du contexte en français. Reçu: {content}"
        
        # Vérifier la présence de citations
        citations = self._extract_citations(response, content)
        assert len(citations) > 0, f"La réponse devrait contenir des citations. Reçu: {content}"
        
        # Vérifier que les citations ont la structure attendue
        for citation in citations:
            self._validate_citation_structure(citation)
        
        logger.info(f"✓ {llm_provider.__class__.__name__} retourne des citations en français")

    @pytest.mark.search
    @pytest.mark.asyncio  
    async def test_search_spanish_with_citations(self, llm_provider, test_messages_search_spanish):
        """
        Test 5: Même question en espagnol -> Réponse similaire avec citations en espagnol
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - Spanish search with citations")
        
        response, _ = await llm_provider.send_request(
            messages=test_messages_search_spanish,
            stream=False,
            documents_count=6
        )
        
        assert response is not None, "La réponse ne doit pas être None"
        
        content = self._extract_response_content(response)
        assert content, "Le contenu de la réponse ne doit pas être vide"
        
        # Vérifier que la réponse est en espagnol - VALIDATION STRICTE
        content_lower = content.lower()
        spanish_indicators = [
            "novedades", "versión", "actualización", "funcionalidades",
            "mejoras", "correcciones", "añadidos", "modificaciones",
            "según", "también", "información", "documentos", "últimas",
            "principales", "características", "cambios", "incluyen",
            "nueva", "nuevo", "estas", "algunos", "entre", "como"
        ]
        
        # Indicateurs français qui ne devraient PAS être présents
        french_indicators = [
            "nouveautés", "version", "mise à jour", "fonctionnalités",
            "améliorations", "corrections", "selon", "également", 
            "informations", "documents", "dernières", "principales",
            "caractéristiques", "changements", "incluent", "nouvelle",
            "nouveau", "ces", "quelques", "entre", "comme", "bonjour"
        ]
        
        spanish_count = sum(1 for indicator in spanish_indicators if indicator in content_lower)
        french_count = sum(1 for indicator in french_indicators if indicator in content_lower)
        
        # Log détaillé pour diagnostic
        logger.info(f"Analyse de langue pour {llm_provider.__class__.__name__}:")
        logger.info(f"  - Indicateurs espagnol trouvés: {spanish_count}")
        logger.info(f"  - Indicateurs français trouvés: {french_count}")
        logger.info(f"  - Contenu (200 premiers chars): {content[:200]}...")
        
        # VALIDATION STRICTE: doit avoir des indicateurs espagnols ET pas d'indicateurs français
        has_spanish_context = spanish_count >= 2
        has_french_context = french_count > 0
        
        assert has_spanish_context, \
            f"La réponse devrait contenir au moins 2 indicateurs espagnols. Trouvés: {spanish_count}. Contenu: {content[:300]}..."
        
        assert not has_french_context, \
            f"La réponse NE DEVRAIT PAS contenir d'indicateurs français. Trouvés: {french_count}. Contenu: {content[:300]}..."
        
        # Vérifier la présence de citations
        citations = self._extract_citations(response, content)
        assert len(citations) > 0, f"La réponse devrait contenir des citations. Reçu: {content}"
        
        # Vérifier que les citations ont la structure attendue
        for citation in citations:
            self._validate_citation_structure(citation)
        
        logger.info(f"✓ {llm_provider.__class__.__name__} répond en espagnol avec citations")

    @pytest.mark.search
    @pytest.mark.asyncio
    async def test_search_consistency_between_languages(self, llm_provider, test_messages_search_french, test_messages_search_spanish):
        """
        Test 6: Vérifier la cohérence des citations entre français et espagnol
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - Search consistency between languages")
        
        # Réponse en français
        french_response, _ = await llm_provider.send_request(
            messages=test_messages_search_french,
            stream=False,
            documents_count=6
        )
        
        # Réponse en espagnol
        spanish_response, _ = await llm_provider.send_request(
            messages=test_messages_search_spanish,
            stream=False,
            documents_count=6
        )
        
        # Extraire les citations des deux réponses
        french_content = self._extract_response_content(french_response)
        spanish_content = self._extract_response_content(spanish_response)
        
        french_citations = self._extract_citations(french_response, french_content)
        spanish_citations = self._extract_citations(spanish_response, spanish_content)
        
        assert len(french_citations) > 0, "Réponse française devrait avoir des citations"
        assert len(spanish_citations) > 0, "Réponse espagnole devrait avoir des citations"
        
        # Les citations devraient référencer des documents similaires
        # (au moins quelques documents en commun)
        french_docs = {self._normalize_citation_reference(cite) for cite in french_citations}
        spanish_docs = {self._normalize_citation_reference(cite) for cite in spanish_citations}
        
        common_docs = french_docs.intersection(spanish_docs)
        overlap_ratio = len(common_docs) / max(len(french_docs), len(spanish_docs))
        
        # Au moins 30% des documents devraient être en commun
        assert overlap_ratio >= 0.3, \
            f"Les citations devraient avoir des documents en commun. Overlap: {overlap_ratio:.2%}"
        
        logger.info(f"✓ {llm_provider.__class__.__name__} maintient la cohérence des citations entre langues")

    @pytest.mark.search
    @pytest.mark.asyncio
    async def test_search_without_results(self, llm_provider):
        """
        Test 7: Question qui ne devrait pas retourner de résultats de recherche
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - Search without results")
        
        no_results_messages = [
            {"role": "user", "content": "Quelle est la capitale de Mars ?"}
        ]
        
        response, _ = await llm_provider.send_request(
            messages=no_results_messages,
            stream=False,
            documents_count=6
        )
        
        content = self._extract_response_content(response)
        citations = self._extract_citations(response, content)
        
        # Si aucune citation n'est trouvée, c'est normal pour cette question
        # Le LLM devrait répondre sans citations ou avec très peu de citations non pertinentes
        if len(citations) > 0:
            # Si des citations existent, elles ne devraient pas être pertinentes
            logger.info(f"Citations found for irrelevant question: {len(citations)}")
        
        # Le plus important est que le système réponde sans erreur
        assert content, "Le système devrait répondre même sans résultats de recherche pertinents"
        
        logger.info(f"✓ {llm_provider.__class__.__name__} gère les questions sans résultats de recherche")

    def _extract_response_content(self, response):
        """Extraire le contenu textuel de la réponse selon le format du provider."""
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
        
        # Méthode 1: Citations dans la métadata de la réponse (Azure OpenAI format)
        if hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'context') and choice.context:
                if hasattr(choice.context, 'citations') and choice.context.citations:
                    citations.extend(choice.context.citations)
        
        # Méthode 2: Citations dans le format dict
        elif isinstance(response, dict):
            if 'choices' in response and response['choices']:
                choice = response['choices'][0]
                if 'context' in choice and choice['context']:
                    if 'citations' in choice['context']:
                        citations.extend(choice['context']['citations'])
        
        # Méthode 3: Citations extraites du texte (format [doc1], [doc2], etc.)
        text_citations = re.findall(r'\[([^\]]+)\]', content)
        if text_citations:
            citations.extend([{'content': cite} for cite in text_citations])
        
        # Méthode 4: Citations au format numéroté [1], [2], etc.
        numbered_citations = re.findall(r'\[(\d+)\]', content)
        if numbered_citations:
            citations.extend([{'id': cite} for cite in numbered_citations])
        
        return citations

    def _validate_citation_structure(self, citation):
        """Valider qu'une citation a la structure minimale attendue."""
        assert isinstance(citation, dict), f"Citation devrait être un dict: {citation}"
        
        # Une citation devrait avoir au moins un identificateur ou du contenu
        has_identifier = any(key in citation for key in ['id', 'url', 'title', 'filename'])
        has_content = 'content' in citation and citation['content']
        
        assert has_identifier or has_content, \
            f"Citation devrait avoir un identificateur ou du contenu: {citation}"

    def _normalize_citation_reference(self, citation):
        """Normaliser une référence de citation pour la comparaison."""
        if isinstance(citation, dict):
            # Utiliser l'url, le titre ou le filename comme référence normalisée
            for key in ['url', 'title', 'filename', 'id']:
                if key in citation and citation[key]:
                    return str(citation[key]).lower().strip()
            # Fallback sur le contenu (premiers mots)
            if 'content' in citation and citation['content']:
                return citation['content'][:50].lower().strip()
        
        return str(citation).lower().strip()