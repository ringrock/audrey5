# Tests Fonctionnels AskMe - Multi-LLM

Ce répertoire contient une suite complète de tests fonctionnels pour l'application AskMe avec support de tous les LLM intégrés.

## 🎯 Vue d'ensemble

Les tests vérifient le bon fonctionnement de l'application avec tous les LLM supportés :
- **AZURE_OPENAI** - Azure OpenAI Service
- **CLAUDE** - Anthropic Claude AI  
- **OPENAI_DIRECT** - API OpenAI directe
- **MISTRAL** - Mistral AI
- **GEMINI** - Google Gemini AI

## 📁 Structure des Tests

```
tests/
├── functional_tests/           # Tests fonctionnels principaux
│   ├── test_language.py       # Tests de langue (français/anglais/italien)
│   ├── test_search.py         # Tests Azure AI Search avec citations
│   ├── test_response_length.py # Tests longueur réponse (short/medium/long)
│   ├── test_document_count.py # Tests nombre de documents (2/6/12)
│   └── conftest.py            # Configuration pytest pour tests fonctionnels
├── integration_tests/         # Tests d'intégration existants
├── unit_tests/               # Tests unitaires existants
├── run_test.py              # Runner principal de tests
├── pytest.ini              # Configuration pytest
└── README.md               # Cette documentation
```

## 🚀 Utilisation Rapide

### Installation et Configuration

```bash
# Créer et configurer l'environnement de test
python tests/run_test.py --setup-only

# Lister les tests disponibles
python tests/run_test.py --list
```

### Exécution des Tests

```bash
# Tous les tests fonctionnels pour tous les LLM
python tests/run_test.py --type functional

# Tests pour un LLM spécifique
python tests/run_test.py --type functional --llm AZURE_OPENAI

# Tests avec exclusion d'un LLM
python tests/run_test.py --type functional --llm-skip GEMINI

# Tests par catégorie (markers)
python tests/run_test.py --type functional --markers language
python tests/run_test.py --type functional --markers search,response_length

# Tests d'images seulement (LLM supportés)
python tests/run_test.py --type functional --markers image --llm CLAUDE,GEMINI,OPENAI_DIRECT

# Mode verbose avec rapport HTML
python tests/run_test.py --type functional --verbose --html-report
```

## 🧪 Types de Tests Disponibles

### 1. Tests de Langue (`test_language.py`)

Vérification du support multilingue :

| Test | Description | Validation |
|------|-------------|------------|
| **test_french_identity_question** | Question "Qui es-tu ?" en français | Réponse mentionne "AskMe" ou équivalent |
| **test_english_language_response** | Question "Who are you?" en anglais | Réponse en anglais |
| **test_italian_poem_generation** | Demande de poème en italien | Poème généré en italien |
| **test_language_consistency** | Cohérence entre langues | Réponses différentes selon la langue |

### 2. Tests Azure AI Search (`test_search.py`)

Vérification de l'intégration avec Azure AI Search :

| Test | Description | Validation |
|------|-------------|------------|
| **test_search_french_with_citations** | Recherche nouveautés en français | Citations Azure AI Search présentes |
| **test_search_spanish_with_citations** | Même recherche en espagnol | Citations présentes, réponse en espagnol |
| **test_search_consistency_between_languages** | Cohérence citations | Documents similaires entre langues |
| **test_search_without_results** | Question sans résultats pertinents | Gestion gracieuse sans erreur |

### 3. Tests Longueur de Réponse (`test_response_length.py`)

Vérification du respect des contraintes de longueur :

| Test | Description | Validation |
|------|-------------|------------|
| **test_response_length_progression** | Progression short → medium → long | `short < medium < long` en nombre de mots |
| **test_short_response_quality** | Qualité réponses courtes | 10-150 mots, informative |
| **test_long_response_depth** | Profondeur réponses longues | ≥100 mots, structure détaillée |
| **test_response_length_with_search** | Longueurs avec recherche | Progression respectée avec citations |

### 4. Tests Nombre de Documents (`test_document_count.py`)

Vérification du paramètre `documents_count` :

| Test | Description | Validation |
|------|-------------|------------|
| **test_document_count_progression** | Progression 2 → 6 → 12 documents | Plus de documents = plus de contenu |
| **test_limited_documents_available** | Peu de documents disponibles | Fonctionnement sans erreur |
| **test_document_count_consistency** | Cohérence entre nombres | Subset des citations |
| **test_document_count_quality** | Qualité avec beaucoup de docs | Citations valides, pas de répétitions |

### 5. Tests d'Images (`test_image_upload.py`)

Vérification de l'analyse d'images pour **CLAUDE, GEMINI, OPENAI_DIRECT** :

| Test | Description | Validation |
|------|-------------|------------|
| **test_broken_bottle_analysis_french** | Image bouteille cassée + "Qu'est-ce que tu vois ?" | Identifie problème production |
| **test_engine_fire_procedure_french** | Image moteur en feu + "Que faire ?" | Procédures urgence + citations Azure AI Search |
| **test_broken_bottle_analysis_english** | Même image + "What do you see?" | Réponse en anglais cohérente |
| **test_engine_fire_procedure_english** | Même image + "What to do?" | Procédures en anglais + citations |
| **test_image_analysis_consistency** | Cohérence entre français/anglais | Contenu similaire, langues différentes |

## 📊 Markers et Catégories

Les tests utilisent des markers pytest pour une exécution sélective :

```bash
# Tests par marker
python tests/run_test.py --type functional --markers language    # Tests de langue
python tests/run_test.py --type functional --markers search      # Tests de recherche
python tests/run_test.py --type functional --markers response_length  # Tests longueur
python tests/run_test.py --type functional --markers document_count   # Tests documents
python tests/run_test.py --type functional --markers image       # Tests d'images
python tests/run_test.py --type functional --markers slow        # Tests lents

# Combinaisons de markers
python tests/run_test.py --type functional --markers "language or search"
python tests/run_test.py --type functional --markers "image and not slow"
python tests/run_test.py --type functional --markers "not slow"
```

## 🎛️ Configuration et Paramètres

### Variables d'Environnement

Les tests utilisent la configuration existante de l'application via les variables d'environnement du fichier `.env` :

```env
# LLM Provider Configuration
LLM_PROVIDER=AZURE_OPENAI
AVAILABLE_LLM_PROVIDERS=AZURE_OPENAI,CLAUDE,OPENAI_DIRECT,MISTRAL,GEMINI

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_KEY=your_key
AZURE_OPENAI_MODEL=gpt-4

# Claude
CLAUDE_API_KEY=your_claude_key
CLAUDE_MODEL=claude-3-opus-20240229

# OpenAI Direct
OPENAI_DIRECT_API_KEY=your_openai_key
OPENAI_DIRECT_MODEL=gpt-4

# Mistral
MISTRAL_API_KEY=your_mistral_key
MISTRAL_MODEL=mistral-large-latest

# Gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-pro
```

### Fixtures Pytest

Les tests utilisent des fixtures paramétrées pour tester tous les LLM automatiquement :

- `llm_provider_type` : Paramètre qui itère sur tous les LLM supportés
- `llm_provider` : Instance du provider LLM pour le test
- `test_messages_*` : Messages de test prédéfinis

## 📈 Rapports et Résultats

### Rapport HTML

```bash
python tests/run_test.py --type functional --html-report
# Génère: tests/reports/report.html
```

### Couverture de Code

```bash
python tests/run_test.py --type functional --coverage
# Génère: htmlcov/index.html
```

### Logs Détaillés

```bash
python tests/run_test.py --type functional --verbose
```

## 🔧 Dépannage

### Problèmes Courants

1. **Provider non disponible**
   ```
   pytest.skip: Provider CLAUDE non disponible: Missing API key
   ```
   → Vérifier les variables d'environnement pour le LLM

2. **Timeout sur tests lents**
   ```bash
   # Augmenter le timeout (défaut: 300s)
   python tests/run_test.py --type functional --markers "not slow"
   ```

3. **Environnement virtuel**
   ```bash
   # Recréer l'environnement de test
   rm -rf test_env
   python tests/run_test.py --setup-only
   ```

### Debug Mode

```bash
# Mode debug avec arrêt sur première erreur
python tests/run_test.py --type functional --verbose --exit-on-fail -x
```

## 🎯 Validation des Exigences

Les tests couvrent **toutes** les exigences spécifiées :

✅ **Test 1** : Question "Qui es-tu ?" → Réponse "AskMe"  
✅ **Test 2** : Question anglaise → Réponse en anglais  
✅ **Test 3** : Poème en italien → Poème généré en italien  
✅ **Test 4** : Recherche nouveautés → Citations Azure AI Search  
✅ **Test 5** : Même recherche en espagnol → Citations en espagnol  
✅ **Test 6** : Longueurs short/medium/long → Progression cohérente  
✅ **Test 7** : Documents 2/6/12 → Nombre de citations cohérent  
✅ **Test 8** : Image bouteille cassée → Analyse problème production (FR/EN)  
✅ **Test 9** : Image moteur en feu → Procédures urgence + citations (FR/EN)

**Pour TOUS les LLM supportés** : AZURE_OPENAI, CLAUDE, OPENAI_DIRECT, MISTRAL, GEMINI  
**Tests d'images** : CLAUDE, GEMINI, OPENAI_DIRECT

## 📝 Maintenance

### Ajouter un Nouveau LLM

1. Ajouter le provider dans `SUPPORTED_LLMS` dans `run_test.py`
2. Les tests existants testeront automatiquement le nouveau LLM
3. Ajouter la configuration dans `.env`

### Ajouter un Nouveau Test

1. Créer le test dans le fichier approprié (`test_*.py`)
2. Utiliser les fixtures existantes (`llm_provider`, `llm_provider_type`)
3. Ajouter un marker si nécessaire dans `pytest.ini`

### Optimisation des Performances

```bash
# Tests en parallèle (si pytest-xdist installé)
python tests/run_test.py --type functional -n auto

# Tests seulement pour LLM spécifiques
python tests/run_test.py --type functional --llm AZURE_OPENAI,CLAUDE
```