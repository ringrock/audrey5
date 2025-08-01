# 🤖 AskMe - Assistant AI Multi-Client

[![GitHub release](https://img.shields.io/github/v/release/avanteam/askme-app-aoai)](https://github.com/avanteam/askme-app-aoai/releases)
[![Docker](https://img.shields.io/badge/docker-Harbor%20OVH-blue)](https://7wpjr0wh.c1.gra9.container-registry.ovh.net)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.21+-green)](https://kubernetes.io)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](./tests/)

AskMe est un assistant virtuel d'entreprise multi-client qui supporte plusieurs fournisseurs LLM et se déploie facilement via Kubernetes/Rancher.

## 🎯 Fonctionnalités

### 🧠 Multi-LLM Support
- **Azure OpenAI** - Service Azure avec intégration native
- **Claude** - Anthropic Claude 4 Sonnet pour des réponses précises
- **OpenAI Direct** - API OpenAI directe (GPT-4o)
- **Mistral** - Modèles Mistral AI open-source
- **Gemini** - Google Gemini pour la diversité des réponses

### 🏢 Architecture Multi-Client
- **Isolation complète** par namespace Kubernetes
- **Configuration personnalisée** par client via Rancher UI
- **DNS automatique** avec gestion OVH intégrée
- **Scaling indépendant** par déploiement

### 🎤 Fonctionnalités Avancées
- **Reconnaissance vocale** avec mots-clés d'activation
- **Synthèse vocale** Azure Speech Services
- **Upload d'images** avec analyse multimodale
- **Historique conversations** stocké en CosmosDB
- **Citations automatiques** depuis Azure Search

## 🚀 Démarrage Rapide

### Prérequis
- **Docker** & **Docker Compose**
- **Node.js 20+** pour le développement frontend
- **Python 3.11+** pour le backend
- **Kubernetes** cluster pour la production

### Installation Locale

```bash
# 1. Cloner le repository
git clone https://github.com/avanteam/askme-app-aoai.git
cd askme-app-aoai

# 2. Configuration
cp .env.sample .env
# Éditer .env avec vos clés API

# 3. Démarrage (build frontend + backend)
./start.sh
```

L'application sera disponible sur http://localhost:50505

### Déploiement Production

Pour déployer en production via Rancher :

```bash
# 1. Créer une version
./scripts/release-sync.sh

# 2. Déployer via Rancher UI ou CLI
./scripts/deploy-client.sh client-name domain.com
```

## ⚙️ Configuration

### Variables d'Environnement Principales

```env
# Provider LLM par défaut
LLM_PROVIDER=CLAUDE
AVAILABLE_LLM_PROVIDERS=AZURE_OPENAI,CLAUDE,OPENAI_DIRECT,MISTRAL,GEMINI

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_KEY=your_azure_key
AZURE_OPENAI_MODEL=gpt-4o

# Claude AI
CLAUDE_API_KEY=your_claude_key
CLAUDE_MODEL=claude-sonnet-4-20250514

# OpenAI Direct
OPENAI_DIRECT_API_KEY=your_openai_key
OPENAI_DIRECT_MODEL=gpt-4o

# Azure Search (données contextuelles)
AZURE_SEARCH_SERVICE=your-search-service
AZURE_SEARCH_INDEX=your-index
AZURE_SEARCH_KEY=your_search_key
```

Voir `.env.sample` pour la configuration complète.

### Interface de Personnalisation

L'application propose une interface graphique permettant aux utilisateurs de :
- **Changer de provider LLM** en temps réel
- **Ajuster la longueur des réponses** (courtes, normales, détaillées)
- **Modifier le nombre de documents** de référence
- **Configurer la reconnaissance vocale**

## 🏗️ Architecture

### Backend (Python/Quart)
```
backend/
├── llm_providers/          # Abstraction multi-LLM
│   ├── azure_openai.py     # Provider Azure OpenAI
│   ├── claude.py           # Provider Anthropic Claude
│   ├── openai_direct.py    # Provider OpenAI Direct
│   └── ...
├── auth/                   # Authentification
├── history/                # Gestion historique
└── settings.py             # Configuration centralisée
```

### Frontend (React/TypeScript)
```
frontend/src/
├── components/
│   ├── Answer/             # Affichage des réponses
│   ├── QuestionInput/      # Interface de saisie
│   └── Customization/      # Panneau de personnalisation
├── hooks/
│   └── useVoiceRecognition.ts
└── state/                  # Gestion d'état globale
```

### Infrastructure
```
helm-chart/                 # Déploiement Kubernetes
├── templates/              # Manifestes K8s
├── values.yaml            # Configuration par défaut
└── Chart.yaml             # Métadonnées Helm
```

## 🧪 Tests

### Exécution des Tests

```bash
# Tests complets
npm test                    # Frontend
pytest                     # Backend
./scripts/test-workflow.sh  # Tests d'intégration

# Tests par catégorie
pytest tests/unit_tests/           # Tests unitaires
pytest tests/functional_tests/    # Tests fonctionnels
pytest tests/integration_tests/   # Tests d'intégration
```

### Tests E2E

```bash
# Tests End-to-End avec Playwright
cd tests/e2e
npm install
npx playwright test
```

## 🔧 Développement

### Architecture des Providers LLM

Chaque provider implémente l'interface `LLMProvider` :

```python
class LLMProvider(ABC):
    @abstractmethod
    async def send_request(self, messages: List[Dict], stream: bool = True, **kwargs):
        """Envoyer une requête au provider"""
        pass
    
    @abstractmethod  
    def format_response(self, raw_response: Any, stream: bool = True):
        """Formater la réponse en format standard"""
        pass
```

### Ajout d'un Nouveau Provider

1. Créer `backend/llm_providers/nouveau_provider.py`
2. Implémenter la classe `NouveauProvider(LLMProvider)`
3. Ajouter dans `backend/llm_providers/__init__.py`
4. Ajouter la configuration dans `backend/settings.py`

### Commandes de Développement

```bash
# Frontend
cd frontend
npm run dev                 # Serveur de développement
npm run build              # Build production
npm run lint               # Vérification code

# Backend  
python -m uvicorn app:app --port 50505 --reload
python -m pytest --cov    # Tests avec couverture
```

## 📊 Monitoring

### Surveillance des Déploiements

```bash
# Dashboard en temps réel
./scripts/monitor-clients.sh

# Status d'un client spécifique
kubectl get pods -n askme-client-name
kubectl logs deployment/askme-app -n askme-client-name
```

### Métriques Disponibles

- **Performance** : Temps de réponse LLM par provider
- **Utilisation** : Nombre de conversations par client
- **Ressources** : CPU, RAM, stockage par déploiement
- **Santé** : Status des pods et services

## 🔄 Workflow de Release

### 1. Développement
```bash
git checkout test-rg2
# ... développement ...
git commit -m "feat: nouvelle fonctionnalité"
git push origin test-rg2
```

### 2. Release
```bash
# Synchronisation des versions entre repositories
./scripts/release-sync.sh
# Choisir version (ex: v1.2.0)
# Tags automatiquement les deux repos
```

### 3. Déploiement
- **Automatique** : Pipeline CI/CD build l'image Docker et package Helm
- **Manuel** : Interface Rancher ou script CLI

### 4. Mise à Jour Client
- Sélection de version dans Rancher UI
- Rolling update sans interruption
- Rollback 1-clic en cas de problème

## 🤝 Contribution

### Standards de Code

- **Python** : PEP 8, type hints obligatoires
- **TypeScript** : Airbnb config, composants fonctionnels
- **Git** : Conventional commits, rebase workflow
- **Documentation** : Inline + README mis à jour

### Pull Request

1. Fork du repository
2. Feature branch depuis `test-rg2`
3. Tests passants requis
4. Documentation mise à jour
5. Review avant merge

## 📄 Licence

Copyright © 2025 Avanteam. Tous droits réservés.

## 🆘 Support

- **Documentation** : Voir `/docs` et guides spécialisés
- **Issues** : [GitHub Issues](https://github.com/avanteam/askme-app-aoai/issues)
- **Support** : Équipe DevOps Avanteam

---

<div align="center">

**[Rancher Catalog](https://github.com/avanteam/askme-rancher-catalog)** • **[Documentation Complète](./CLAUDE.md)** • **[Guide Workflow](./WORKFLOW_RELEASE.md)**

</div>