"""
Tests de nombre de documents pour tous les LLM supportés.

Ce module teste la capacité des LLM à :
1. Respecter le nombre de documents demandé (2, 6, 12)
2. Adapter le contenu selon le nombre de documents disponibles
3. Maintenir la qualité des citations selon le nombre de documents
4. Gérer les cas où moins de documents sont disponibles que demandé
"""
import pytest
import re
import logging

logger = logging.getLogger(__name__)


class TestDocumentCount:
    """Tests de nombre de documents pour tous les LLM."""
    
    @pytest.mark.document_count
    @pytest.mark.asyncio
    async def test_document_count_progression(self, llm_provider, document_counts):
        """
        Test 7: Vérifier que le nombre de citations augmente avec le nombre de documents demandé
        """
        provider_name = llm_provider.__class__.__name__
        question = "Quelles sont les principales nouveautés techniques documentées ?"
        
        logger.info(f"\n=== TEST: Progression nombre de documents ===")
        logger.info(f"Provider: {provider_name}")
        logger.info(f"Question posée: '{question}'")
        logger.info(f"Nombres de documents testés: {document_counts}")
        
        # Question de recherche qui devrait retourner plusieurs documents
        search_messages = [
            {"role": "user", "content": question}
        ]
        
        citation_counts = {}
        response_contents = {}
        detailed_results = {}
        
        # Tester chaque nombre de documents
        for doc_count in document_counts:
            logger.info(f"\n--- Test avec {doc_count} documents ---")
            
            response, _ = await llm_provider.send_request(
                messages=search_messages,
                stream=False,
                documents_count=doc_count,
                response_size="medium"
            )
            
            assert response is not None, f"La réponse ne doit pas être None pour {doc_count} documents"
            
            content = self._extract_response_content(response)
            assert content, f"Le contenu ne doit pas être vide pour {doc_count} documents"
            
            citations = self._extract_citations(response, content)
            word_count = self._count_words(content)
            
            citation_counts[doc_count] = len(citations)
            response_contents[doc_count] = content
            detailed_results[doc_count] = {
                'citations': len(citations),
                'words': word_count,
                'chars': len(content),
                'preview': content[:150] + '...' if len(content) > 150 else content
            }
            
            logger.info(f"Résultats pour {doc_count} documents:")
            logger.info(f"  - Citations trouvées: {len(citations)}")
            logger.info(f"  - Mots dans la réponse: {word_count}")
            logger.info(f"  - Caractères: {len(content)}")
            logger.info(f"  - Aperçu: {detailed_results[doc_count]['preview']}")
            
            # Détail des citations si présentes
            if citations:
                logger.info(f"  - Détail des citations:")
                for i, cite in enumerate(citations[:3]):  # Afficher max 3 citations
                    cite_info = str(cite)[:100] + '...' if len(str(cite)) > 100 else str(cite)
                    logger.info(f"    {i+1}: {cite_info}")
        
        # Rapport comparatif final
        logger.info(f"\n=== COMPARAISON DES RÉSULTATS ===")
        for doc_count in document_counts:
            result = detailed_results[doc_count]
            logger.info(f"{doc_count} docs: {result['citations']} citations, {result['words']} mots")
        
        word_counts = {count: detailed_results[count]['words'] for count in document_counts}
        
        # Validations
        logger.info(f"\n=== VALIDATIONS ===")
        
        # Vérifier que plus de documents demandés = plus de citations (en général)
        if citation_counts[2] > 0:  # Si des citations sont trouvées
            citation_6_vs_2 = citation_counts[6] >= citation_counts[2]
            citation_12_vs_6 = citation_counts[12] >= citation_counts[6]
            
            logger.info(f"Citations 6 docs ({citation_counts[6]}) >= 2 docs ({citation_counts[2]}): {citation_6_vs_2}")
            logger.info(f"Citations 12 docs ({citation_counts[12]}) >= 6 docs ({citation_counts[6]}): {citation_12_vs_6}")
            
            assert citation_6_vs_2, \
                f"6 documents ({citation_counts[6]} citations) devrait avoir ≥ citations que 2 documents ({citation_counts[2]})"
            
            assert citation_12_vs_6, \
                f"12 documents ({citation_counts[12]} citations) devrait avoir ≥ citations que 6 documents ({citation_counts[6]})"
        else:
            logger.info("Aucune citation trouvée avec 2 documents, validation citations ignorée")
        
        # Vérifier que le contenu devient plus riche avec plus de documents
        content_6_vs_2 = word_counts[6] >= word_counts[2] * 0.8
        logger.info(f"Contenu 6 docs ({word_counts[6]}) >= 80% de 2 docs ({word_counts[2] * 0.8:.1f}): {content_6_vs_2}")
        
        assert content_6_vs_2, \
            f"6 docs ({word_counts[6]} mots) devrait avoir ≥80% des mots de 2 docs ({word_counts[2]})"
        
        logger.info(f"✓ {provider_name} - Test réussi: adaptation au nombre de documents")
        logger.info(f"=== FIN TEST ===\n")

    @pytest.mark.document_count
    @pytest.mark.asyncio
    async def test_limited_documents_available(self, llm_provider):
        """
        Test 8: Vérifier le comportement quand moins de documents sont disponibles que demandé
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - Limited documents available")
        
        # Question très spécifique qui pourrait retourner peu de documents
        specific_messages = [
            {"role": "user", "content": "Recherche des informations sur une technologie très spécifique et rare"}
        ]
        
        response, _ = await llm_provider.send_request(
            messages=specific_messages,
            stream=False,
            documents_count=12,  # Demander beaucoup mais peu disponibles
            response_size="medium"
        )
        
        content = self._extract_response_content(response)
        citations = self._extract_citations(response, content)
        
        # Le système devrait fonctionner même avec peu de documents
        assert content, "Le système devrait répondre même avec peu de documents disponibles"
        
        # Si des citations existent, elles devraient être valides
        for citation in citations:
            self._validate_citation_structure(citation)
        
        logger.info(f"✓ {llm_provider.__class__.__name__} gère les cas de documents limités")

    @pytest.mark.document_count
    @pytest.mark.asyncio
    async def test_document_count_consistency(self, llm_provider):
        """
        Test 9: Vérifier la cohérence des citations entre différents nombres de documents
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - Document count consistency")
        
        search_messages = [
            {"role": "user", "content": "Explique les dernières innovations technologiques documentées"}
        ]
        
        responses = {}
        citations_sets = {}
        
        # Tester avec 2 et 6 documents
        for doc_count in [2, 6]:
            response, _ = await llm_provider.send_request(
                messages=search_messages,
                stream=False,
                documents_count=doc_count,
                response_size="medium"
            )
            
            content = self._extract_response_content(response)
            citations = self._extract_citations(response, content)
            
            responses[doc_count] = content
            citations_sets[doc_count] = citations
        
        # Analyser la cohérence des citations
        if len(citations_sets[2]) > 0 and len(citations_sets[6]) > 0:
            # Les citations de 2 documents devraient être un sous-ensemble des citations de 6 documents
            citations_2_refs = {self._normalize_citation_reference(cite) for cite in citations_sets[2]}
            citations_6_refs = {self._normalize_citation_reference(cite) for cite in citations_sets[6]}
            
            # Calculer l'overlap mais être plus flexible dans l'assertion
            overlap = citations_2_refs.intersection(citations_6_refs)
            overlap_ratio = len(overlap) / len(citations_2_refs) if citations_2_refs else 0
            
            # Log détaillé pour analyse
            logger.info(f"=== ANALYSE DE COHÉRENCE DES CITATIONS ===")
            logger.info(f"Citations avec 2 docs: {len(citations_sets[2])} citations")
            logger.info(f"Citations avec 6 docs: {len(citations_sets[6])} citations")
            logger.info(f"Overlap ratio: {overlap_ratio:.2%}")
            logger.info(f"Citations communes: {len(overlap)}")
            
            # Test plus flexible: au moins 1 citation commune OU au moins 25% d'overlap
            has_common_citations = len(overlap) > 0
            reasonable_overlap = overlap_ratio >= 0.25
            
            assert has_common_citations or reasonable_overlap, \
                f"Les citations devraient avoir au moins 1 citation commune ou 25% d'overlap. Overlap: {overlap_ratio:.2%}, Citations communes: {len(overlap)}"
        
        logger.info(f"✓ {llm_provider.__class__.__name__} maintient la cohérence des citations")

    @pytest.mark.document_count
    @pytest.mark.asyncio
    async def test_document_count_quality(self, llm_provider):
        """
        Test 10: Vérifier que la qualité des citations ne se dégrade pas avec plus de documents
        """
        provider_name = llm_provider.__class__.__name__
        question = "Analyse les tendances technologiques récentes dans les documents"
        
        logger.info(f"\n=== TEST: Qualité avec nombreux documents ===")
        logger.info(f"Provider: {provider_name}")
        logger.info(f"Question posée: '{question}'")
        logger.info(f"Nombre de documents demandés: 12")
        logger.info(f"Taille de réponse: LONG")
        
        search_messages = [
            {"role": "user", "content": question}
        ]
        
        # Tester avec le maximum de documents
        response, _ = await llm_provider.send_request(
            messages=search_messages,
            stream=False,
            documents_count=12,
            response_size="long"
        )
        
        content = self._extract_response_content(response)
        citations = self._extract_citations(response, content)
        word_count = self._count_words(content)
        
        logger.info(f"\n=== RÉSULTATS OBTENUS ===")
        logger.info(f"Longueur réponse: {word_count} mots, {len(content)} caractères")
        logger.info(f"Nombre de citations: {len(citations)}")
        logger.info(f"Aperçu réponse: {content[:200]}...")
        
        # Analyse des citations
        if len(citations) > 0:
            logger.info(f"\n=== ANALYSE DES CITATIONS ===")
            
            # Vérifier la qualité de chaque citation
            valid_citations = 0
            citation_details = []
            
            for i, citation in enumerate(citations):
                try:
                    self._validate_citation_structure(citation)
                    valid_citations += 1
                    status = "VALIDE"
                except AssertionError as e:
                    status = f"INVALIDE ({str(e)[:50]}...)"
                
                cite_preview = str(citation)[:100] + '...' if len(str(citation)) > 100 else str(citation)
                citation_details.append(f"  Citation {i+1}: {status}")
                logger.info(f"  Citation {i+1}: {status} - {cite_preview}")
            
            # Au moins 80% des citations devraient être valides
            citation_quality_ratio = valid_citations / len(citations)
            logger.info(f"\n=== QUALITÉ CITATIONS ===")
            logger.info(f"Citations valides: {valid_citations}/{len(citations)}")
            logger.info(f"Ratio de qualité: {citation_quality_ratio:.2%} (minimum: 80%)")
            
            quality_ok = citation_quality_ratio >= 0.8
            logger.info(f"Validation qualité citations: {quality_ok}")
            
            assert quality_ok, \
                f"Au moins 80% des citations devraient être valides. Ratio obtenu: {citation_quality_ratio:.2%}"
        else:
            logger.info(f"Aucune citation trouvée, validation citations ignorée")
        
        # Vérifier que le contenu reste cohérent même avec beaucoup de documents
        logger.info(f"\n=== ANALYSE CONTENU ===")
        
        content_length_ok = word_count >= 50
        logger.info(f"Longueur substantielle (min 50 mots): {word_count} >= 50 = {content_length_ok}")
        
        assert content_length_ok, f"Avec 12 documents, la réponse devrait être substantielle. Mots obtenus: {word_count}"
        
        # Vérifier qu'il n'y a pas de répétitions excessives
        sentences = re.split(r'[.!?]+', content)
        clean_sentences = [s.strip() for s in sentences if s.strip()]
        unique_sentences = set(s.lower() for s in clean_sentences)
        sentence_diversity = len(unique_sentences) / len(clean_sentences) if clean_sentences else 0
        
        logger.info(f"Phrases totales: {len(clean_sentences)}")
        logger.info(f"Phrases uniques: {len(unique_sentences)}")
        logger.info(f"Diversité phrases: {sentence_diversity:.3f} (minimum: 0.7)")
        
        diversity_ok = sentence_diversity >= 0.7
        logger.info(f"Validation diversité: {diversity_ok}")
        
        assert diversity_ok, \
            f"Le contenu devrait être diversifié même avec beaucoup de documents. Diversité obtenue: {sentence_diversity:.3f}"
        
        logger.info(f"✓ {provider_name} - Test réussi: qualité maintenue avec nombreux documents")
        logger.info(f"=== FIN TEST ===\n")

    @pytest.mark.document_count
    @pytest.mark.asyncio
    async def test_document_count_relevance(self, llm_provider, document_counts):
        """
        Test 11: Vérifier que les documents supplémentaires restent pertinents
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - Document count relevance")
        
        focused_messages = [
            {"role": "user", "content": "Quelles sont les améliorations de sécurité mentionnées ?"}
        ]
        
        for doc_count in document_counts:
            response, _ = await llm_provider.send_request(
                messages=focused_messages,
                stream=False,
                documents_count=doc_count,
                response_size="medium"
            )
            
            content = self._extract_response_content(response)
            citations = self._extract_citations(response, content)
            
            # Vérifier que le contenu reste focalisé sur la sécurité
            content_lower = content.lower()
            security_terms = [
                "sécurité", "security", "protection", "vulnérabilité", "authentification",
                "chiffrement", "encryption", "accès", "autorisation", "confidentialité"
            ]
            
            security_mentions = sum(1 for term in security_terms if term in content_lower)
            
            # Plus de documents ne devrait pas diluer le focus sur la sécurité
            assert security_mentions >= 1, \
                f"Avec {doc_count} documents, la réponse devrait mentionner la sécurité. Mentions: {security_mentions}"
            
            logger.info(f"Documents: {doc_count}, Security mentions: {security_mentions}")
        
        logger.info(f"✓ {llm_provider.__class__.__name__} maintient la pertinence avec plus de documents")

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

    def _normalize_citation_reference(self, citation):
        """Normaliser une référence de citation pour la comparaison."""
        if isinstance(citation, dict):
            for key in ['url', 'title', 'filename', 'id']:
                if key in citation and citation[key]:
                    return str(citation[key]).lower().strip()
            if 'content' in citation and citation['content']:
                return citation['content'][:50].lower().strip()
        
        return str(citation).lower().strip()

    def _count_words(self, text):
        """Compter le nombre de mots dans un texte."""
        if not text:
            return 0
        words = re.findall(r'\b\w+\b', text)
        return len(words)