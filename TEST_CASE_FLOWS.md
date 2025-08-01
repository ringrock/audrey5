# Test Case Flows

Ce document décrit les scénarios de test systématiques pour valider les fonctionnalités de l'application AskMe après modifications du code.

## 🎯 Objectif

Assurer la non-régression sur tous les providers LLM et configurations de données supportés par l'application.

## ⚡ Test Case Matrix

L'application doit être testée avec chaque combinaison de :

### Providers LLM
- **AZURE_OPENAI** - Azure OpenAI service
- **CLAUDE** - Anthropic Claude AI  
- **OPENAI_DIRECT** - API OpenAI directe
- **MISTRAL** - Mistral AI services
- **GEMINI** - Google Gemini AI

### Modes de Réponse
- **Streaming** (`stream=true`) - Réponses en temps réel
- **Non-streaming** (`stream=false`) - Réponses complètes

### Sources de Données
- **Avec données** - Azure Search configuré
- **Sans données** - Mode conversationnel pur

### Historique des Conversations
- **Avec historique** - CosmosDB configuré
- **Sans historique** - Sessions temporaires

## 🧪 Scénarios de Test Principaux

### 1. Test Multi-Provider avec Données + Streaming

**Configuration requise :**
```env
# Source de données (obligatoire)
AZURE_SEARCH_SERVICE=your-search-service
AZURE_SEARCH_INDEX=your-index  
AZURE_SEARCH_KEY=your_search_key

# Provider sélectionné (un parmi)
LLM_PROVIDER=CLAUDE
CLAUDE_API_KEY=your_claude_key

# Streaming activé
STREAM_ENABLED=true
```

**Test à effectuer :**
1. Poser une question nécessitant des données contextuelles
2. Vérifier que les citations apparaissent
3. Valider le streaming des réponses
4. Répéter pour chaque provider disponible

### 2. Test Multi-Provider sans Données + Non-streaming  

**Configuration requise :**
```env
# Aucune source de données
# AZURE_SEARCH_* non défini

# Provider sélectionné
LLM_PROVIDER=OPENAI_DIRECT  
OPENAI_DIRECT_API_KEY=your_openai_key

# Streaming désactivé
STREAM_ENABLED=false
```

**Test à effectuer :**
1. Poser une question générale
2. Vérifier l'absence de citations
3. Valider la réponse complète non-streamée
4. Tester le changement de provider via UI

### 3. Test Historique des Conversations

**Configuration requise :**
```env
# Historique activé
AZURE_COSMOSDB_DATABASE=your_db
AZURE_COSMOSDB_ACCOUNT=your_account
AZURE_COSMOSDB_CONVERSATIONS_CONTAINER=conversations
AZURE_COSMOSDB_ACCOUNT_KEY=your_key

# Un provider quelconque
LLM_PROVIDER=MISTRAL
MISTRAL_API_KEY=your_mistral_key
```

**Test à effectuer :**
1. Créer une nouvelle conversation
2. Poser plusieurs questions liées
3. Vérifier la continuité du contexte
4. Recharger la page et vérifier la persistance
5. Tester la suppression d'historique

### 4. Test Fonctionnalités Avancées

**Reconnaissance Vocale :**
```env
VOICE_INPUT_ENABLED=true
WAKE_WORD_ENABLED=true
```

**Synthèse Vocale :**
```env  
AZURE_SPEECH_ENABLED=true
AZURE_SPEECH_KEY=your_speech_key
AZURE_SPEECH_REGION=your_region
```

**Upload d'Images :**
```env
IMAGE_MAX_SIZE_MB=10.0
LLM_PROVIDER=CLAUDE  # Provider supportant les images
```

## 🔧 Scripts de Test Automatisés

### Test Rapide Multi-Provider
```bash
# Tests automatisés pour tous les providers
./scripts/test-all-providers.sh

# Test d'un provider spécifique  
./scripts/test-provider.sh CLAUDE
```

### Test de Non-Régression
```bash
# Suite complète de tests
pytest tests/functional_tests/

# Tests d'intégration provider
pytest tests/integration_tests/test_llm_providers.py

# Tests E2E avec Playwright
cd tests/e2e && npx playwright test
```

## ✅ Checklist de Validation

### Avant Release
- [ ] Tous les providers LLM fonctionnent (streaming + non-streaming)
- [ ] Sources de données optionnelles (avec/sans Azure Search)
- [ ] Historique des conversations (avec/sans CosmosDB)
- [ ] Interface de personnalisation (changement provider, paramètres)
- [ ] Fonctionnalités vocales (reconnaissance + synthèse)
- [ ] Upload et analyse d'images
- [ ] Gestion d'erreurs avec messages localisés
- [ ] Performance et stabilité sur charge

### Tests d'Intégration Continue  
- [ ] Pipeline GitHub Actions passe
- [ ] Build Docker réussit
- [ ] Déploiement Kubernetes sans erreur
- [ ] Tests E2E sur environnement de staging

## 🚨 Cas d'Erreur à Tester

### Gestion des Erreurs Provider
1. **Clé API invalide** - Message d'erreur localisé
2. **Quota dépassé** - Gestion gracieuse avec fallback
3. **Timeout réseau** - Retry automatique et message utilisateur
4. **Provider indisponible** - Basculement vers provider alternatif

### Configuration Incomplète  
1. **Provider manquant** - Liste des providers disponibles uniquement
2. **Source de données partielle** - Mode dégradé sans citations
3. **Historique inaccessible** - Session temporaire sans persistance

## 📋 Rapports de Test

Documenter les résultats dans `tests/results/` avec :
- **Timestamp** et **version** testée
- **Provider LLM** et **configuration** utilisée  
- **Résultats** des tests (✅ Pass / ❌ Fail)
- **Temps de réponse** moyens par provider
- **Issues** rencontrées et **résolutions**