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

6. **Error Handling**: The backend includes comprehensive error handling with proper status codes and error messages for various Azure OpenAI scenarios.

## Code Quality Standards

**IMPORTANT**: Never write unmaintainable code with hardcoded values. Always:
- Use environment variables for configuration values
- Create constants for repeated values
- Use configuration files for settings
- Implement proper abstraction and modularity
- Avoid magic numbers and strings
- Make code reusable and configurable