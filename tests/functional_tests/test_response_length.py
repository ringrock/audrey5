"""
Tests de longueur de réponse pour tous les LLM supportés.

Ce module teste la capacité des LLM à :
1. Générer des réponses de différentes longueurs (short, medium, long)
2. Respecter les contraintes de longueur demandées
3. Maintenir la qualité du contenu selon la longueur
4. Conserver la cohérence des citations selon la longueur
"""
import pytest
import re
import logging

logger = logging.getLogger(__name__)


class TestResponseLength:
    """Tests de longueur de réponse pour tous les LLM."""
    
    @pytest.mark.response_length
    @pytest.mark.asyncio
    async def test_response_length_progression(self, llm_provider, response_sizes):
        """
        Test 6: Vérifier que veryShort < normal < comprehensive pour les longueurs de réponse
        """
        provider_name = llm_provider.__class__.__name__
        question = "Explique-moi les principales nouveautés techniques récentes"
        
        logger.info(f"\n=== TEST: Progression de longueur de réponse ===")
        logger.info(f"Provider: {provider_name}")
        logger.info(f"Question posée: '{question}'")
        logger.info(f"Tailles testées: {response_sizes}")
        
        # Question de test avec recherche pour avoir du contenu substantiel
        test_messages = [
            {"role": "user", "content": question}
        ]
        
        responses = {}
        word_counts = {}
        
        # Tester chaque taille de réponse
        for size in response_sizes:
            logger.info(f"\n--- Test de taille: {size} ---")
            
            response, _ = await llm_provider.send_request(
                messages=test_messages,
                stream=False,
                response_size=size,
                documents_count=6
            )
            
            assert response is not None, f"La réponse ne doit pas être None pour {size}"
            
            content = self._extract_response_content(response)
            assert content, f"Le contenu ne doit pas être vide pour {size}"
            
            responses[size] = content
            word_counts[size] = self._count_words(content)
            
            # Log détaillé pour chaque taille
            logger.info(f"Taille {size}:")
            logger.info(f"  - Nombre de mots: {word_counts[size]}")
            logger.info(f"  - Nombre de caractères: {len(content)}")
            logger.info(f"  - Aperçu réponse (100 premiers chars): {content[:100]}...")
        
        # Rapport final des mesures
        logger.info(f"\n=== RESULTATS MESURÉS ===")
        for size in response_sizes:
            logger.info(f"{size.upper()}: {word_counts[size]} mots")
        
        # Vérifier la progression des longueurs: veryShort < normal < comprehensive
        logger.info(f"\n=== VALIDATION PROGRESSION ===")
        
        very_short_normal_ok = word_counts['veryShort'] < word_counts['normal']
        normal_comprehensive_ok = word_counts['normal'] < word_counts['comprehensive']
        
        logger.info(f"VeryShort < Normal: {word_counts['veryShort']} < {word_counts['normal']} = {very_short_normal_ok}")
        logger.info(f"Normal < Comprehensive: {word_counts['normal']} < {word_counts['comprehensive']} = {normal_comprehensive_ok}")
        
        assert very_short_normal_ok, \
            f"VeryShort ({word_counts['veryShort']}) devrait être plus court que normal ({word_counts['normal']})"
        
        assert normal_comprehensive_ok, \
            f"Normal ({word_counts['normal']}) devrait être plus court que comprehensive ({word_counts['comprehensive']})"
        
        # Vérifier des ratios raisonnables
        very_short_to_normal_ratio = word_counts['normal'] / word_counts['veryShort']
        normal_to_comprehensive_ratio = word_counts['comprehensive'] / word_counts['normal']
        
        logger.info(f"\n=== RATIOS CALCULÉS ===")
        logger.info(f"Ratio Normal/VeryShort: {very_short_to_normal_ratio:.2f}")
        logger.info(f"Ratio Comprehensive/Normal: {normal_to_comprehensive_ratio:.2f}")
        
        assert 1.2 <= very_short_to_normal_ratio <= 10.0, \
            f"Ratio normal/veryShort devrait être entre 1.2 et 10.0, obtenu: {very_short_to_normal_ratio:.2f}"
        
        assert 1.05 <= normal_to_comprehensive_ratio <= 5.0, \
            f"Ratio comprehensive/normal devrait être entre 1.05 et 5.0, obtenu: {normal_to_comprehensive_ratio:.2f}"
        
        logger.info(f"✓ {provider_name} - Test réussi: progression de longueur respectée")
        logger.info(f"=== FIN TEST ===\n")

    @pytest.mark.response_length
    @pytest.mark.asyncio
    async def test_short_response_quality(self, llm_provider):
        """
        Test 7: Vérifier que les réponses courtes restent informatives
        """
        provider_name = llm_provider.__class__.__name__
        question = "Qu'est-ce que l'intelligence artificielle ?"
        
        logger.info(f"\n=== TEST: Qualité des réponses courtes ===")
        logger.info(f"Provider: {provider_name}")
        logger.info(f"Question posée: '{question}'")
        logger.info(f"Taille demandée: SHORT")
        
        test_messages = [
            {"role": "user", "content": question}
        ]
        
        response, _ = await llm_provider.send_request(
            messages=test_messages,
            stream=False,
            response_size="short"
        )
        
        content = self._extract_response_content(response)
        word_count = self._count_words(content)
        
        logger.info(f"\n=== RÉPONSE OBTENUE ===")
        logger.info(f"Contenu: '{content}'")
        logger.info(f"Longueur: {word_count} mots, {len(content)} caractères")
        
        # Une réponse courte devrait être informative mais concise
        logger.info(f"\n=== VALIDATION LONGUEUR ===")
        logger.info(f"Plage attendue: 10-150 mots")
        logger.info(f"Mesuré: {word_count} mots")
        length_ok = 10 <= word_count <= 150
        logger.info(f"Validation longueur: {length_ok}")
        
        assert length_ok, \
            f"Réponse courte devrait avoir 10-150 mots, obtenu: {word_count}"
        
        # Vérifier qu'elle contient des termes pertinents
        content_lower = content.lower()
        relevant_terms = [
            "intelligence", "artificielle", "ia", "machine", "apprentissage",
            "algorithme", "données", "automatisation", "technologie"
        ]
        
        found_terms = [term for term in relevant_terms if term in content_lower]
        logger.info(f"\n=== VALIDATION CONTENU ===")
        logger.info(f"Termes pertinents recherchés: {relevant_terms}")
        logger.info(f"Termes trouvés: {found_terms}")
        logger.info(f"Nombre de termes trouvés: {len(found_terms)} (minimum: 2)")
        
        content_quality_ok = len(found_terms) >= 2
        logger.info(f"Validation contenu: {content_quality_ok}")
        
        assert content_quality_ok, \
            f"Réponse courte devrait contenir au moins 2 termes pertinents. Trouvés: {found_terms}"
        
        logger.info(f"✓ {provider_name} - Test réussi: réponse courte de qualité")
        logger.info(f"=== FIN TEST ===\n")

    @pytest.mark.response_length
    @pytest.mark.asyncio
    async def test_long_response_depth(self, llm_provider):
        """
        Test 8: Vérifier que les réponses longues sont plus détaillées
        """
        provider_name = llm_provider.__class__.__name__
        question = "Explique en détail l'impact de l'intelligence artificielle sur la société"
        
        logger.info(f"\n=== TEST: Profondeur des réponses longues ===")
        logger.info(f"Provider: {provider_name}")
        logger.info(f"Question posée: '{question}'")
        logger.info(f"Taille demandée: LONG")
        logger.info(f"Documents demandés: 8")
        
        test_messages = [
            {"role": "user", "content": question}
        ]
        
        response, _ = await llm_provider.send_request(
            messages=test_messages,
            stream=False,
            response_size="long",
            documents_count=8
        )
        
        content = self._extract_response_content(response)
        word_count = self._count_words(content)
        
        logger.info(f"\n=== RÉPONSE OBTENUE ===")
        logger.info(f"Longueur: {word_count} mots, {len(content)} caractères")
        logger.info(f"Aperçu (200 premiers chars): {content[:200]}...")
        
        # Analyser la structure
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        sentences = [s.strip() for s in re.split(r'[.!?]+', content) if s.strip()]
        words = re.findall(r'\b\w+\b', content.lower())
        unique_words = set(words)
        vocabulary_ratio = len(unique_words) / len(words) if words else 0
        
        logger.info(f"\n=== ANALYSE STRUCTURELLE ===")
        logger.info(f"Nombre de paragraphes: {len(paragraphs)}")
        logger.info(f"Nombre de phrases: {len(sentences)}")
        logger.info(f"Mots totaux: {len(words)}")
        logger.info(f"Mots uniques: {len(unique_words)}")
        logger.info(f"Ratio de diversité vocabulaire: {vocabulary_ratio:.3f}")
        
        # Afficher quelques paragraphes pour débug
        logger.info(f"\n=== STRUCTURE DES PARAGRAPHES ===")
        for i, para in enumerate(paragraphs[:3]):
            logger.info(f"Paragraphe {i+1} ({len(para.split())} mots): {para[:100]}...")
        
        # Validations
        logger.info(f"\n=== VALIDATIONS ===")
        
        # Une réponse longue devrait être substantielle
        length_ok = word_count >= 100
        logger.info(f"Longueur minimale (100 mots): {word_count} >= 100 = {length_ok}")
        assert length_ok, \
            f"Réponse longue devrait avoir au moins 100 mots, obtenu: {word_count}"
        
        # Vérifier la structure (paragraphes, points, etc.)
        paragraphs_ok = len(paragraphs) >= 2
        logger.info(f"Paragraphes multiples (min 2): {len(paragraphs)} >= 2 = {paragraphs_ok}")
        assert paragraphs_ok, \
            f"Réponse longue devrait avoir au moins 2 paragraphes, obtenu: {len(paragraphs)}"
        
        sentences_ok = len(sentences) >= 5
        logger.info(f"Phrases multiples (min 5): {len(sentences)} >= 5 = {sentences_ok}")
        assert sentences_ok, \
            f"Réponse longue devrait avoir au moins 5 phrases, obtenu: {len(sentences)}"
        
        # Vérifier la diversité du vocabulaire
        vocab_ok = vocabulary_ratio >= 0.3
        logger.info(f"Diversité vocabulaire (min 0.3): {vocabulary_ratio:.3f} >= 0.3 = {vocab_ok}")
        assert vocab_ok, \
            f"Réponse longue devrait avoir un vocabulaire diversifié. Ratio obtenu: {vocabulary_ratio:.3f}"
        
        logger.info(f"✓ {provider_name} - Test réussi: réponse longue détaillée")
        logger.info(f"=== FIN TEST ===\n")

    @pytest.mark.response_length
    @pytest.mark.asyncio
    async def test_response_length_with_search(self, llm_provider, response_sizes):
        """
        Test 9: Vérifier que les longueurs sont respectées même avec recherche Azure AI Search
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - Response length with search")
        
        search_messages = [
            {"role": "user", "content": "Quelles sont les dernières innovations mentionnées dans les documents ?"}
        ]
        
        search_responses = {}
        search_word_counts = {}
        
        for size in response_sizes:
            response, _ = await llm_provider.send_request(
                messages=search_messages,
                stream=False,
                response_size=size,
                documents_count=6
            )
            
            content = self._extract_response_content(response)
            citations = self._extract_citations(response, content)
            
            search_responses[size] = content
            search_word_counts[size] = self._count_words(content)
            
            # Vérifier que des citations sont présentes (si la recherche fonctionne)
            if len(citations) > 0:
                logger.info(f"Size {size}: {len(citations)} citations found")
        
        # Même avec recherche, la progression de longueur devrait être respectée
        if all(size in search_word_counts for size in response_sizes):
            assert search_word_counts['short'] <= search_word_counts['medium'], \
                f"Avec recherche: Short ({search_word_counts['short']}) devrait être ≤ medium ({search_word_counts['medium']})"
            
            assert search_word_counts['medium'] <= search_word_counts['long'], \
                f"Avec recherche: Medium ({search_word_counts['medium']}) devrait être ≤ long ({search_word_counts['long']})"
        
        logger.info(f"✓ {llm_provider.__class__.__name__} respecte les longueurs avec recherche")

    @pytest.mark.response_length
    @pytest.mark.asyncio
    async def test_response_length_consistency(self, llm_provider):
        """
        Test 10: Vérifier la cohérence des longueurs entre questions similaires
        """
        logger.info(f"Testing {llm_provider.__class__.__name__} - Response length consistency")
        
        similar_questions = [
            {"role": "user", "content": "Qu'est-ce que le machine learning ?"},
            {"role": "user", "content": "Explique-moi l'apprentissage automatique"},
            {"role": "user", "content": "Comment fonctionne l'apprentissage machine ?"}
        ]
        
        response_size = "medium"
        word_counts = []
        
        for messages in [[q] for q in similar_questions]:
            response, _ = await llm_provider.send_request(
                messages=messages,
                stream=False,
                response_size=response_size
            )
            
            content = self._extract_response_content(response)
            word_count = self._count_words(content)
            word_counts.append(word_count)
        
        # Calculer la variance des longueurs
        mean_count = sum(word_counts) / len(word_counts)
        variance = sum((count - mean_count) ** 2 for count in word_counts) / len(word_counts)
        coefficient_of_variation = (variance ** 0.5) / mean_count if mean_count > 0 else 0
        
        # La variation ne devrait pas être trop importante
        assert coefficient_of_variation <= 0.5, \
            f"Les longueurs devraient être cohérentes. CV: {coefficient_of_variation:.2f}, counts: {word_counts}"
        
        logger.info(f"✓ {llm_provider.__class__.__name__} maintient des longueurs cohérentes")

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

    def _count_words(self, text):
        """Compter le nombre de mots dans un texte."""
        if not text:
            return 0
        
        # Supprimer la ponctuation et compter les mots
        words = re.findall(r'\b\w+\b', text)
        return len(words)

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