# Tests End-to-End (E2E) avec Playwright

Tests complets de l'application AskMe validant l'intégration frontend + backend + LLM.

## 🎯 Vue d'ensemble

Les tests E2E utilisent Playwright pour simuler des interactions utilisateur réelles et valider le fonctionnement complet de l'application :
- **Frontend React** (interface utilisateur)  
- **Backend Python** (API et logique métier)
- **LLM Providers** (tous les providers supportés)
- **Azure AI Search** (recherche et citations)

## 📁 Structure des Tests E2E

```
tests/e2e/
├── conftest.py                    # Configuration pytest + Playwright
├── test_image_upload_e2e.py      # Tests E2E upload d'images
├── test_chat_interactions_e2e.py # Tests E2E interactions chat
├── playwright.config.js          # Configuration Playwright
└── README.md                     # Cette documentation
```

## 🚀 Installation et Configuration

### Prérequis

```bash
# Installer Playwright et dépendances
test_env/bin/pip install playwright pytest-playwright

# Installer les navigateurs
test_env/bin/playwright install chromium

# Vérifier l'installation
test_env/bin/playwright --version
```

### Variables d'environnement

```bash
# URLs des services (par défaut)
export E2E_BASE_URL="http://localhost:5173"      # Frontend dev server
export E2E_BACKEND_URL="http://localhost:50505"  # Backend server

# Mode d'affichage (optionnel)
export HEADLESS="true"   # true = mode invisible, false = mode visible
```

## 🧪 Tests Disponibles

### Tests Upload d'Images (`test_image_upload_e2e.py`)

Tests complets pour l'upload et l'analyse d'images :

| Test | Description | Providers |
|------|-------------|-----------|
| **test_broken_bottle_upload_french_e2e** | Upload bouteille cassée + question FR | CLAUDE, GEMINI, OPENAI_DIRECT |
| **test_engine_fire_upload_french_e2e** | Upload moteur en feu + question FR | CLAUDE, GEMINI, OPENAI_DIRECT |
| **test_broken_bottle_upload_english_e2e** | Upload bouteille cassée + question EN | CLAUDE, GEMINI, OPENAI_DIRECT |
| **test_engine_fire_upload_english_e2e** | Upload moteur en feu + question EN | CLAUDE, GEMINI, OPENAI_DIRECT |
| **test_image_upload_workflow_complete_e2e** | Workflow complet utilisateur | CLAUDE |
| **test_image_upload_error_handling_e2e** | Gestion d'erreurs upload | Tous |
| **test_ui_elements_image_upload_e2e** | Validation éléments UI | Tous |

### Tests Interactions Chat (`test_chat_interactions_e2e.py`)

Tests des interactions chat standard :

| Test | Description | Providers |
|------|-------------|-----------|
| **test_simple_french_question_e2e** | Question "Qui es-tu ?" | Tous |
| **test_simple_english_question_e2e** | Question "Who are you?" | Tous |
| **test_search_with_citations_e2e** | Recherche + citations Azure AI Search | CLAUDE |
| **test_response_length_settings_e2e** | Paramètres longueur réponse | CLAUDE |
| **test_provider_switching_e2e** | Changement de providers | CLAUDE, AZURE_OPENAI |
| **test_conversation_history_e2e** | Historique conversations | CLAUDE |
| **test_complete_chat_workflow_e2e** | Workflow chat complet | CLAUDE, AZURE_OPENAI |

## 🏃‍♂️ Exécution des Tests

### Tests Basiques

```bash
# Tous les tests E2E
test_env/bin/python -m pytest tests/e2e/ -v

# Tests d'images seulement
test_env/bin/python -m pytest tests/e2e/ -k "image" -v

# Tests chat seulement  
test_env/bin/python -m pytest tests/e2e/ -k "chat" -v

# Test spécifique
test_env/bin/python -m pytest tests/e2e/test_image_upload_e2e.py::TestImageUploadE2E::test_broken_bottle_upload_french_e2e -v
```

### Tests par Provider

```bash
# Tests pour Claude seulement
test_env/bin/python -m pytest tests/e2e/ -k "CLAUDE" -v

# Tests pour providers supportant les images
test_env/bin/python -m pytest tests/e2e/ -k "CLAUDE or GEMINI or OPENAI_DIRECT" -v

# Exclure les tests lents
test_env/bin/python -m pytest tests/e2e/ -m "not e2e_slow" -v
```

### Tests avec Markers

```bash
# Tests E2E d'images
test_env/bin/python -m pytest tests/e2e/ -m "e2e_image" -v

# Tests E2E de chat
test_env/bin/python -m pytest tests/e2e/ -m "e2e_chat" -v

# Tests E2E lents
test_env/bin/python -m pytest tests/e2e/ -m "e2e_slow" -v
```

### Mode Debug

```bash
# Mode visible (voir le navigateur)
HEADLESS=false test_env/bin/python -m pytest tests/e2e/ -v -s

# Avec screenshots et traces
test_env/bin/python -m pytest tests/e2e/ --screenshot=on --tracing=on -v

# Arrêt sur premier échec
test_env/bin/python -m pytest tests/e2e/ -x -v
```

## 🎛️ Configuration Avancée

### Timeouts Personnalisés

Les tests E2E utilisent des timeouts adaptés aux réponses LLM :

```python
DEFAULT_TIMEOUT = 30000   # 30 secondes (actions normales)
SLOW_TIMEOUT = 60000     # 60 secondes (réponses LLM simples)
SEARCH_TIMEOUT = 90000   # 90 secondes (réponses avec recherche)
```

### Sélecteurs de Tests

Les tests utilisent des `data-testid` pour identifier les éléments UI :

```javascript
// Éléments attendus dans le frontend
"[data-testid='question-input']"      // Input de question
"[data-testid='send-button']"         // Bouton d'envoi
"[data-testid='image-upload-button']" // Bouton upload image
"[data-testid='image-preview']"       // Aperçu image uploadée
"[data-testid='chat-response']"       // Réponse du chat
"[data-testid='citation']"            // Citations
"[data-testid='llm-provider-selector']" // Sélecteur provider
```

### Navigateurs Supportés

Configuration par défaut :
- **Chromium** (principal)
- Firefox (optionnel, décommenté dans playwright.config.js)
- Safari/WebKit (optionnel, décommenté dans playwright.config.js)

## 📊 Rapports et Debugging

### Rapports HTML

```bash
# Générer rapport HTML automatiquement
test_env/bin/python -m pytest tests/e2e/ --html=reports/e2e_report.html --self-contained-html

# Voir le rapport Playwright
test_env/bin/playwright show-report
```

### Screenshots et Vidéos

Les tests capturent automatiquement :
- **Screenshots** sur échec
- **Vidéos** sur échec (mode retenu)
- **Traces** pour debugging (sur retry)

### Logs et Debug

```bash
# Logs détaillés
test_env/bin/python -m pytest tests/e2e/ -v -s --log-cli-level=INFO

# Debug Playwright
DEBUG=pw:api test_env/bin/python -m pytest tests/e2e/ -v
```

## ⚠️ Prérequis pour l'Exécution

### Services Requis

1. **Frontend Development Server**
   ```bash
   cd frontend
   npm install
   npm run dev  # Port 5173
   ```

2. **Backend API Server**
   ```bash
   python -m uvicorn app:app --port 50505 --reload
   ```

3. **Configuration LLM**
   - Variables d'environnement configurées (`.env`)
   - Clés API valides pour les providers testés
   - Azure AI Search configuré (pour tests de citations)

### Images de Test

Les tests utilisent les images dans `/tests/functional_tests/img/` :
- `test1.jpg` - Bouteille cassée sur chaîne de production
- `test2.jpg` - Moteur d'avion en feu

## 🔧 Dépannage

### Problèmes Courants

1. **Timeout sur réponses LLM**
   ```bash
   # Augmenter les timeouts dans conftest.py
   SLOW_TIMEOUT = 120000  # 2 minutes
   ```

2. **Sélecteurs non trouvés**
   ```bash
   # Vérifier que les data-testid sont présents dans le frontend
   # Utiliser mode visible pour debug
   HEADLESS=false test_env/bin/python -m pytest tests/e2e/ -k "specific_test" -v
   ```

3. **Services non disponibles**
   ```bash
   # Vérifier que frontend et backend sont démarrés
   curl http://localhost:5173  # Frontend
   curl http://localhost:50505/frontend_settings  # Backend
   ```

4. **Provider LLM non configuré**
   ```bash
   # Vérifier les variables d'environnement
   # Les tests skipperont automatiquement les providers non configurés
   ```

## 📈 Métriques et Performance

### Temps d'Exécution Typiques

- **Tests d'images** : 30-90 secondes par test
- **Tests chat simples** : 15-45 secondes par test  
- **Tests avec recherche** : 60-120 secondes par test
- **Suite complète** : 15-30 minutes

### Optimisations

- Tests séquentiels (pas de parallélisme) pour éviter les limites de rate LLM
- Réutilisation des sessions navigateur
- Timeouts adaptatifs selon le type de test

## 🎯 Validation des Exigences

Les tests E2E valident **toutes** les exigences spécifiées :

✅ **Upload Images + Analyse**
- Upload `test1.jpg` + "Qu'est-ce que tu vois ?" → Analyse bouteille cassée
- Upload `test2.jpg` + "Que faire ?" → Procédures moteur + citations

✅ **Support Multilingue** 
- Tests français/anglais pour les mêmes images
- Validation des réponses dans la langue appropriée

✅ **Intégration Complète**
- Frontend React ↔ Backend Python ↔ LLM Providers
- Azure AI Search avec citations
- Changement de providers en temps réel

✅ **Tous les LLM Supportés**
- CLAUDE, GEMINI, OPENAI_DIRECT pour images
- Tous les providers pour chat standard

Les tests E2E garantissent que l'application fonctionne parfaitement de bout en bout ! 🚀