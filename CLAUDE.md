# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment
- **Development OS**: Windows with WSL (Windows Subsystem for Linux)
- **File paths**: Use `/mnt/c/` to access Windows C: drive from WSL
- **Line endings**: Be aware of CRLF (Windows) vs LF (Unix) differences
- **Scripts**: Prefer `.cmd` or PowerShell scripts for Windows, but can use bash scripts in WSL

## LLM Provider Configuration

The application supports multiple LLM providers that can be configured via environment variables:

### Available Providers
- `AZURE_OPENAI`: Azure OpenAI service (default)
- `CLAUDE`: Anthropic Claude AI
- `OPENAI_DIRECT`: Direct OpenAI API access
- `MISTRAL`: Mistral AI services

### Configuration Variables
```env
# Default provider
LLM_PROVIDER=AZURE_OPENAI

# Providers available in UI (comma-separated)
AVAILABLE_LLM_PROVIDERS=AZURE_OPENAI,CLAUDE,OPENAI_DIRECT,MISTRAL
```

### Provider-Specific Settings
```env
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
MISTRAL_MAX_TOKENS=1000
MISTRAL_TEMPERATURE=0.7
MISTRAL_TOP_P=1.0
MISTRAL_SYSTEM_MESSAGE="Tu es un assistant IA serviable et précis."
```

## Operational Guidelines
- ATTENTION : toutes les modifications que tu fais pour faire fonctionner un LLM ne doivent pas casser le bon fonctionnement des autres LLM supportés par le module
- Ne modifie jamais des paramètres directement dans le code si ils sont présent dans un fichier de conf comme le .env
- pas de commit en auto, c'est moi qui te dis quand faire les commit
- je construis toujours le frontend moi-même

## Build Commands

### Frontend Development (from /frontend directory)
```bash
npm install          # Install dependencies
npm run build        # Build production bundle
npm run dev          # Development server with hot reload (port 5173)
npm run test         # Run Jest tests
npm run lint         # Run ESLint
npm run lint:fix     # Fix ESLint issues
npm run format       # Run prettier:fix and lint:fix
```

### Backend Development
```bash
python -m pip install -r requirements.txt      # Install dependencies
python -m pip install -r requirements-dev.txt  # Install dev dependencies
python -m uvicorn app:app --port 50505 --reload # Development server
python -m gunicorn app:app                     # Production server
```

### Full Application
```bash
# Windows
start.cmd   # Builds frontend, installs dependencies, starts backend

# Linux/Mac
./start.sh  # Builds frontend, installs dependencies, starts backend
```

### Testing
```bash
# Frontend tests (from /frontend)
npm run test

# Backend tests (from root)
pytest
pytest tests/unit_tests/        # Unit tests only
pytest tests/integration_tests/ # Integration tests only
```

## Architecture Overview

This is an Azure OpenAI chat application with the following structure:

### Frontend (`/frontend`)
- **Framework**: React with TypeScript
- **Build Tool**: Vite
- **State Management**: Custom AppProvider using React Context
- **Key Components**:
  - `src/pages/chat/Chat.tsx`: Main chat interface
  - `src/components/Answer/`: Response rendering with streaming support
  - `src/api/`: API client for backend communication
  - `src/state/`: Application state management

### Backend
- **Framework**: Quart (async Flask)
- **Entry Point**: `app.py`
- **Core Modules** (`/backend`):
  - `auth/`: Microsoft Entra ID authentication
  - `history/`: CosmosDB integration for chat history
  - `security/`: Security utilities including MS Defender integration
  - `settings.py`: Configuration management via environment variables
  - `llm_providers/`: Unified LLM provider abstraction with centralized error handling
- **API Endpoints**:
  - `/conversation`: Streaming chat responses
  - `/conversation/custom`: Non-streaming chat
  - `/history/*`: Chat history management

### Data Source Integration
The application supports multiple data sources configured via environment variables:
- Azure AI Search (`DATASOURCE_TYPE=AzureCognitiveSearch`)
- Azure CosmosDB Mongo vCore (`DATASOURCE_TYPE=AzureCosmosDB`)
- Elasticsearch (`DATASOURCE_TYPE=Elasticsearch`)
- Pinecone (`DATASOURCE_TYPE=Pinecone`)
- Azure SQL (`DATASOURCE_TYPE=AzureMLIndex`)
- MongoDB (`DATASOURCE_TYPE=MongoDB`)

### Deployment
- **Docker**: `WebApp.Dockerfile` for containerized deployment
- **Azure**: Bicep templates in `/infra` for infrastructure as code
- **Azure Developer CLI**: Configured via `azure.yaml`

## Key Development Considerations

1. **Environment Configuration**: All Azure OpenAI and data source settings are managed through environment variables. Create a `.env` file for local development.

2. **Streaming Responses**: The chat interface supports both streaming (`/conversation`) and non-streaming (`/conversation/custom`) endpoints. The frontend handles Server-Sent Events for streaming.

3. **Authentication**: When `AZURE_USE_AUTHENTICATION=true`, the app requires Microsoft Entra ID authentication. User info is passed via headers.

4. **Chat History**: Stored in CosmosDB when configured. Each conversation maintains context through a `conversation_id`.

5. **Frontend Build Output**: The frontend build creates files in `/static` which are served by the Python backend.

6. **Error Handling**: The backend includes comprehensive unified error handling across all LLM providers with user-friendly localized messages (see LLM Provider Error Handling section).

## Code Quality Standards

**IMPORTANT**: Never write unmaintainable code with hardcoded values. Always:
- Use environment variables for configuration values
- Create constants for repeated values
- Use configuration files for settings
- Implement proper abstraction and modularity
- Avoid magic numbers and strings
- Make code reusable and configurable

## LLM Provider Error Handling

The application features a unified error handling system across all LLM providers that provides user-friendly, localized error messages.

### Supported Providers
All providers use the same centralized error handling system:
- **AZURE_OPENAI**: Azure OpenAI service with native "On Your Data" integration
- **CLAUDE**: Anthropic Claude AI
- **OPENAI_DIRECT**: Direct OpenAI API access
- **MISTRAL**: Mistral AI services
- **GEMINI**: Google Gemini AI

### Error Classification

The system automatically classifies errors and provides appropriate French messages:

#### HTTP 429 - Rate Limiting
```
"Trop de requêtes ont été envoyées au service {PROVIDER}. Veuillez patienter quelques instants avant de réessayer."
```

#### HTTP 401/403 - Authentication Issues
```
"Problème d'authentification avec {PROVIDER}. Veuillez contacter l'administrateur."
```

#### HTTP 400 - Bad Request
```
"Requête invalide envoyée à {PROVIDER}. Veuillez reformuler votre question."
```

#### HTTP 500+ - Server Errors
```
"Erreur temporaire du service {PROVIDER}. Veuillez réessayer dans quelques instants."
```

#### Network/Timeout Issues
```
"Problème de connexion avec {PROVIDER}. Vérifiez votre connexion internet et réessayez."
```

#### Quota/Billing Issues
```
"Quota ou limite de {PROVIDER} atteint. Veuillez contacter l'administrateur."
```

#### Content Filtering
```
"Votre demande a été filtrée par les politiques de contenu. Veuillez reformuler votre question."
```

### Implementation

#### Core Components
- **`backend/llm_providers/errors.py`**: Centralized error classification and message generation
- **`backend/llm_providers/base.py`**: `@handle_provider_errors()` decorator for uniform error handling
- **`backend/utils.py`**: Enhanced streaming error handling with provider context
- **`frontend/src/pages/chat/Chat.tsx`**: Frontend error message parsing and display

#### Usage Pattern
All LLM providers use the same error handling decorator:

```python
@handle_provider_errors("PROVIDER_NAME")
async def send_request(self, messages, stream=True, **kwargs):
    # Provider-specific implementation
    # Any exception is automatically caught and converted to user-friendly message
```

#### Error Flow
1. **Exception occurs** in any LLM provider
2. **Decorator intercepts** the exception
3. **Error classifier** analyzes the exception type and content
4. **User-friendly message** is generated in French
5. **Frontend displays** the localized message instead of technical error
6. **Technical details** are logged for debugging

### Benefits
- **Consistent UX**: Same error handling across all providers
- **Localized Messages**: Clear French messages for end users
- **Maintainable**: Single point of error message management
- **Debugging**: Technical details preserved in logs
- **Extensible**: Easy to add new error types and providers

### Citation Configuration

The application supports configurable citation content length:

```env
# Citation Configuration
# Maximum length for citation content displayed in UI (default: 1000 characters)
CITATION_CONTENT_MAX_LENGTH=2000
```

This setting controls how much text is displayed when users click on citations in the sidebar panel. The default value of 1000 characters can be adjusted based on user needs.