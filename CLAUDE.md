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

## Voice Features

The application includes comprehensive voice capabilities for both input and output, providing a hands-free user experience.

### Voice Input (Speech Recognition)

#### Configuration
```env
# Voice input settings
VOICE_INPUT_ENABLED=true
WAKE_WORD_ENABLED=true
WAKE_WORD_PHRASES=["Patrick", "AskMe", "AskMi", "AsMi"]
```

#### Recognition Modes

**Manual Mode (Single Click)**
- Click once on microphone (🎤) to start voice dictation
- Automatically stops when speech is detected as complete
- Question is sent immediately after recognition

**Wake Word Mode (Double Click)**
- Double-click microphone to activate continuous listening
- System listens for wake words: "Patrick", "AskMe", "AskMi", "AsMi"
- Say wake word followed by question: "Patrick, résume-moi la charte informatique"
- **Visual Feedback**: Red blinking dot appears instantly on microphone icon when wake word is detected
- Remains active between conversations for hands-free operation
- Double-click again or single-click during listening to deactivate

#### Smart Integration
- Automatically pauses during text-to-speech playback to prevent audio feedback
- Seamlessly resumes wake word mode after audio playback (if it was active before)
- Compatible with both Azure Speech and browser-based speech synthesis
- **Instant Visual Response**: Wake word indicator activates on interim speech results for immediate user feedback

### Text-to-Speech (Voice Output)

#### Configuration
```env
# Azure Speech Services settings
AZURE_SPEECH_ENABLED=true
AZURE_SPEECH_KEY=your_azure_speech_key
AZURE_SPEECH_REGION=your_azure_region
AZURE_SPEECH_VOICE_FR=fr-FR-DeniseNeural
AZURE_SPEECH_VOICE_EN=en-US-AriaNeural
```

#### Playback Modes

**Manual Playback**
- Click speaker icon (🔊) next to any response to trigger text-to-speech
- Click again to stop ongoing playback
- Works with both completed and partial responses

**Automatic Playback**
- Toggle with "🔊 ON/OFF" button at bottom of each response
- Automatically reads new responses as they complete generation
- Waits for streaming to finish before starting playback
- Can be interrupted by user at any time

#### Technology Stack

**Azure Speech Services (Primary)**
- High-quality neural voices with natural intonation
- Intelligent text processing with SSML enhancement
- Automatic segmentation for long texts (>1000 characters)
- Sequential playback of segments with minimal pauses (50ms)

**Browser Speech Synthesis (Fallback)**
- Used when Azure Speech is unavailable or disabled
- Automatic fallback on Azure Speech errors
- Cross-browser compatibility

#### Intelligent Text Processing

**Backend Text Cleaning (`backend/speech_services.py`)**
- Centralized text processing for consistent quality
- Markdown and HTML structure preservation during analysis
- Intelligent title, list, and section detection
- Comprehensive emoji and special character removal
- Pronunciation corrections via custom dictionary

**Enhanced Speech Features**
- Hierarchical pause system:
  - 800ms for main titles (# ##)
  - 600ms for medium titles (### ####)
  - 400ms for normal sentence transitions
  - 300ms for list item transitions
- SSML markup for natural speech patterns
- Emphasis on important titles and sections
- Optimized prosody (rate: 1.08, pitch: -6%)

#### Voice Recognition Integration

**Automatic Coordination**
- Voice recognition pauses during text-to-speech to prevent interference
- Smart state management preserves wake word mode across audio sessions
- Timing optimization to avoid recognition conflicts

**Architecture**
- Single `useVoiceRecognition` hook to prevent state conflicts
- Props-based function passing to audio components
- Centralized state management with `useRef` for persistent values

### File Organization

**Frontend Voice Components**
- `frontend/src/hooks/useVoiceRecognition.ts`: Core voice recognition logic
- `frontend/src/components/QuestionInput/QuestionInput.tsx`: Voice input interface
- `frontend/src/components/Answer/Answer.tsx`: Text-to-speech integration
- `frontend/src/pages/chat/Chat.tsx`: Voice coordination between components

**Backend Voice Services**
- `backend/speech_services.py`: Azure Speech Services integration and text processing
- `backend/pronunciation_dict.py`: Custom pronunciation corrections
- `app.py`: Speech API endpoints (`/speech/synthesize`, `/speech/clean`)

### Citation Configuration

The application supports configurable citation content length:

```env
# Citation Configuration
# Maximum length for citation content displayed in UI (default: 1000 characters)
CITATION_CONTENT_MAX_LENGTH=2000
```

This setting controls how much text is displayed when users click on citations in the sidebar panel. The default value of 1000 characters can be adjusted based on user needs.

### Image Upload Configuration

The application includes configurable limits for image uploads with user-friendly error handling:

```env
# Image Upload Configuration
# Maximum image size in megabytes (default: 10.0)
IMAGE_MAX_SIZE_MB=12.0
```

#### Features
- **Global size limit**: Configurable via environment variable, applies to all upload methods
- **Multiple upload methods supported**: File input, drag & drop, clipboard paste
- **Clean error display**: Integrated UI error messages replace JavaScript alerts
- **Provider compatibility**: Only enabled for LLM providers that support images (Claude, Gemini, OpenAI Direct)
- **Smart error handling**: Specific messages show the configured size limit from environment

#### Error Display
When an image exceeds the size limit, users see a clean error message above the input field:
- **Format**: "Image trop volumineuse (limite XMB). Veuillez utiliser une image plus petite."
- **Design**: Red-themed error banner with icon and close button
- **Animation**: Smooth slide-down appearance with animation
- **Dismissible**: Users can close the error by clicking the X button

#### Technical Implementation
- Frontend validation uses the limit from `/frontend_settings` API endpoint
- Backend serves the configuration via `app_settings.base_settings.image_max_size_mb`
- Error messages propagate from `convertToBase64` through all upload handlers
- Dual-path processing: original images for LLMs, compressed versions for CosmosDB storage

## Image Handling and Storage

The application includes comprehensive image upload validation and automatic compression for storage optimization.

### Image Upload Configuration and Validation

#### Upload Size Limits
- **Global Limit**: Configurable via `IMAGE_MAX_SIZE_MB` environment variable (default: 10MB)
- **Frontend Validation**: Images are validated before processing to ensure they don't exceed the configured limit
- **User-Friendly Errors**: Clear error messages inform users of size limits when exceeded

#### Upload Methods Supported
1. **File Selection**: Click to browse and select image files
2. **Drag & Drop**: Drag images directly into the chat input area
3. **Paste**: Paste images from clipboard (Ctrl+V)

### Image Processing Pipeline

When users upload images in the chat interface:

1. **Frontend Validation**: Size validation against configured limit with immediate user feedback
2. **LLM Processing**: Original high-quality images are sent to LLM providers for analysis
3. **Backend Storage**: Images are automatically compressed before being stored in CosmosDB to respect the 2MB document limit
4. **History Retrieval**: Compressed images (thumbnails) are displayed in chat history

### Image Compression Features

#### Automatic Compression (`backend/utils.py`)

- **`compress_image_for_storage()`**: Compresses images to a maximum of 300KB
- **`process_message_content_for_storage()`**: Processes message content to detect and compress images

#### Compression Algorithm

1. **Size Check**: If image is already ≤300KB, returns unchanged
2. **Format Conversion**: Converts to RGB/JPEG for optimal compression
3. **Quality Reduction**: Tries different JPEG quality levels (85% down to 25%)
4. **Dimension Scaling**: Reduces image dimensions if needed
5. **Minimum Size**: Ensures images don't become smaller than 50x50 pixels

#### Implementation

```python
# Messages with images are automatically processed before CosmosDB storage
processed_content = process_message_content_for_storage(input_message['content'])
```

#### Benefits

- **Upload Control**: Prevents oversized uploads with configurable limits and clear user feedback
- **Storage Efficiency**: Prevents CosmosDB "Request size is too large" errors
- **LLM Performance**: Original images sent to LLM providers for optimal analysis quality
- **Performance**: Faster chat history loading with compressed thumbnails
- **User Experience**: Clear error messages and maintained visual context
- **Cost Optimization**: Reduces CosmosDB storage and bandwidth costs

#### Technical Details

- Uses PIL (Pillow) for image processing
- Maintains aspect ratio during compression
- Preserves image quality while meeting size constraints
- Graceful fallback: Returns original image if compression fails

## Commandes de Chat

L'application AskMe supporte un système de commandes qui permet aux utilisateurs de modifier les paramètres directement depuis le chat en utilisant des instructions en langage naturel.

### Commandes Disponibles

#### 1. Changement de Modèle LLM

**Syntaxe :** `Modifie la config pour utiliser le modèle [NOM_MODELE]`

**Exemples :**
- `Modifie la config pour utiliser le modèle Gemini`
- `Change la configuration pour passer sur Claude`
- `Utilise le modèle Azure OpenAI`
- `Switche sur Mistral`

**Modèles supportés :**
- `azure`, `azure openai`, `openai` → AZURE_OPENAI
- `claude`, `anthropic` → CLAUDE
- `openai direct`, `openai-direct` → OPENAI_DIRECT
- `mistral` → MISTRAL
- `gemini`, `google` → GEMINI

**Réponse :** Message de confirmation avec le nouveau modèle utilisé ou erreur si le modèle n'est pas disponible.

#### 2. Modification du Nombre de Documents

**Syntaxe :** `Modifie la config pour récupérer [NOMBRE] doc maximum`

**Exemples :**
- `Modifie la config pour récupérer 10 doc maximum`
- `Change la configuration pour avoir 5 documents de référence`
- `Utilise 15 documents max`

**Limites :**
- Minimum : 1 document
- Maximum : 50 documents (configurable)

**Réponse :** Message de confirmation avec le nouveau nombre ou erreur si la limite est dépassée.

#### 3. Modification de la Longueur des Réponses

**Syntaxe :** `Modifie la config pour passer en réponses [TYPE]`

**Exemples :**
- `Modifie la config pour passer en réponses courtes`
- `Change pour des réponses détaillées`
- `Utilise des réponses normales`

**Types supportés :**
- **Courtes :** `court`, `courte`, `bref`, `brève`, `short` → VERY_SHORT
- **Normales :** `normal`, `standard`, `moyen`, `moyenne` → NORMAL  
- **Détaillées :** `long`, `détaillé`, `complet`, `comprehensive`, `exhaustif` → COMPREHENSIVE

**Réponse :** Message de confirmation avec le nouveau type de réponse.

#### 4. Création de Nouvelle Conversation

**Syntaxe :** `Crée une nouvelle conversation`

**Exemples :**
- `Crée une nouvelle conversation`
- `Génère une nouvelle discussion`
- `Démarre un nouveau chat`
- `Ouvre une nouvelle conversation`

**Action :** Initialise une nouvelle conversation vide avec un nouvel ID.

#### 5. Nettoyage de Conversation

**Syntaxe :** `Nettoie la conversation`

**Exemples :**
- `Nettoie la conversation`
- `Vide cette discussion`
- `Efface l'historique`
- `Reset la conversation`

**Action :** Supprime tous les messages de la conversation actuelle.

### Architecture Technique

#### Backend (`backend/chat_commands.py`)

**Classes principales :**
- **`ChatCommandParser`** : Parse les messages en langage naturel pour détecter les commandes
- **`ChatCommandExecutor`** : Exécute les commandes et gère les validations
- **`ChatCommand`** : Représente une commande parsée avec ses paramètres

**Intégration :**
- Le système s'intègre dans `conversation_internal()` dans `app.py`
- Détection automatique des commandes dans les messages utilisateur
- Gestion des sessions utilisateur pour persister les préférences
- Validation des paramètres avec messages d'erreur explicites

#### Frontend (`frontend/src/pages/chat/Chat.tsx`)

**Fonctions principales :**
- **`processCommandResult()`** : Traite les réponses de commandes
- Mise à jour automatique des préférences de personnalisation
- Gestion des actions spéciales (nouvelle conversation, nettoyage)

#### Session Utilisateur

**Endpoint :** `/user/session` (GET/POST)
**Stockage :** En mémoire sur le serveur (dictionnaire global `user_sessions`)
**Paramètres persistés :**
- `llm_provider` : Provider LLM sélectionné
- `documents_count` : Nombre de documents de référence
- `response_length` : Type de longueur de réponse

### Commandes Multiples

Le système supporte l'exécution de **commandes multiples** dans une seule phrase, permettant de modifier plusieurs paramètres en une fois :

**Exemples de commandes multiples :**
- `Modifie la config pour utiliser claude avec des réponses courtes et 5 documents max`
- `Passe sur gemini avec réponses détaillées et 15 documents de référence`
- `Utilise mistral des réponses moyennes et 3 documents maxi`

**Fonctionnalités :**
- **Traitement intelligent** : Le système détecte et exécute automatiquement toutes les commandes trouvées dans le message
- **Réponse unifiée** : Une seule réponse de confirmation résume tous les changements effectués
- **Support nombres écrits** : Reconnaissance des nombres en lettres ("trois documents") pour une meilleure compatibilité vocale
- **Prévention des doublons** : Évite les messages de confirmation répétés grâce à un traitement centralisé

### Gestion des Erreurs

Le système fournit des messages d'erreur explicites en français :

- **Modèle indisponible :** Liste des modèles disponibles
- **Nombre de documents invalide :** Limites min/max autorisées
- **Paramètres incorrects :** Suggestions de syntaxe correcte

### Exemples d'Usage

```
Utilisateur: Modifie la config pour utiliser le modèle Gemini
AskMe: Configuration modifiée avec succès. Le modèle gemini est maintenant utilisé.

Utilisateur: Change pour récupérer 15 doc maximum  
AskMe: Configuration modifiée avec succès. Le nombre maximum de documents de référence est maintenant 15.

Utilisateur: Passe en réponses courtes
AskMe: Configuration modifiée avec succès. Les réponses seront maintenant courtes.

Utilisateur: Crée une nouvelle conversation
AskMe: Nouvelle conversation créée avec succès.
[L'interface se réinitialise avec une conversation vide]
```