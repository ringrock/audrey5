import copy
import json
import os
import logging
import uuid
import httpx
import asyncio

import requests

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import base64
from datetime import datetime
from hashlib import sha256

from requests.adapters import HTTPAdapter, Retry

from quart import (
    Blueprint,
    Quart,
    jsonify,
    make_response,
    request,
    send_from_directory,
    render_template,
    current_app,
)

from openai import AsyncAzureOpenAI
from azure.identity.aio import (
    DefaultAzureCredential,
    get_bearer_token_provider
)
from backend.auth.auth_utils import get_authenticated_user_details
from backend.security.ms_defender_utils import get_msdefender_user_json
from backend.history.cosmosdbservice import CosmosConversationClient
from backend.settings import (
    app_settings,
    MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION
)
from backend.utils import (
    format_as_ndjson,
    format_stream_response,
    format_non_streaming_response,
    convert_to_pf_format,
    format_pf_non_streaming_response,
)
from backend.document_processor import DocumentProcessor
from backend.llm_providers import LLMProviderFactory
from backend.speech_services import synthesize_speech_azure, clean_text_for_speech
from backend.pronunciation_dict import get_pronunciation_dict, add_pronunciation, remove_pronunciation
from backend.chat_commands import command_parser, ChatCommandExecutor

bp = Blueprint("routes", __name__, static_folder="static", template_folder="static")

cosmos_db_ready = asyncio.Event()

# Dictionnaire global pour stocker les sessions utilisateur
user_sessions = {}


def create_app():
    app = Quart(__name__)
    app.register_blueprint(bp)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    
    @app.before_serving
    async def init():
        try:
            app.cosmos_conversation_client = await init_cosmosdb_client()
            cosmos_db_ready.set()
        except Exception as e:
            logging.exception("Failed to initialize CosmosDB client")
            app.cosmos_conversation_client = None
            raise e
    
    return app


@bp.route("/")
async def index():
    response = await make_response(await render_template(
        "index.html",
        title=app_settings.ui.title,
        favicon=app_settings.ui.favicon
    ))
    # Allow microphone access in iframe
    response.headers['Permissions-Policy'] = 'microphone=*'
    return response


@bp.route("/favicon.ico")
async def favicon():
    return await bp.send_static_file("favicon.ico")


@bp.route("/assets/<path:path>")
async def assets(path):
    return await send_from_directory("static/assets", path)


# Debug settings
DEBUG = os.environ.get("DEBUG", "false")
if DEBUG.lower() == "true":
    logging.basicConfig(level=logging.DEBUG)
else:
    # Configure logging to show INFO level for debugging but suppress Azure SDK noise
    logging.basicConfig(level=logging.DEBUG)
    
    # Set specific loggers to appropriate levels
    logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    logging.getLogger('azure').setLevel(logging.DEBUG)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

USER_AGENT = "GitHubSampleWebApp/AsyncAzureOpenAI/1.0.0"


# Frontend Settings via Environment Variables
frontend_settings = {
    "auth_enabled": app_settings.base_settings.auth_enabled,
    "feedback_enabled": (
        app_settings.chat_history and
        app_settings.chat_history.enable_feedback
    ),
    "ui": {
        "title": app_settings.ui.title,
        "logo": app_settings.ui.logo,
        "chat_logo": app_settings.ui.chat_logo or app_settings.ui.logo,
        "chat_title": app_settings.ui.chat_title,
        "chat_description": app_settings.ui.chat_description,
        "show_share_button": app_settings.ui.show_share_button,
        "show_chat_history_button": app_settings.ui.show_chat_history_button,
        "show_export_button": app_settings.ui.show_export_button,
    },
    "sanitize_answer": app_settings.base_settings.sanitize_answer,
    "oyd_enabled": app_settings.base_settings.datasource_type,
    "available_llm_providers": app_settings.base_settings.available_llm_providers,
    "voice_input_enabled": app_settings.base_settings.voice_input_enabled,
    "wake_word_enabled": app_settings.base_settings.wake_word_enabled,
    "wake_word_phrases": app_settings.base_settings.wake_word_phrases,
    "wake_word_variants": app_settings.base_settings.get_wake_word_variants_map(),
    "azure_speech_enabled": app_settings.base_settings.azure_speech_enabled,
    "azure_speech_voice_fr": app_settings.base_settings.azure_speech_voice_fr,
    "azure_speech_voice_en": app_settings.base_settings.azure_speech_voice_en,
    "image_max_size_mb": app_settings.base_settings.image_max_size_mb,
}


# Enable Microsoft Defender for Cloud Integration
MS_DEFENDER_ENABLED = os.environ.get("MS_DEFENDER_ENABLED", "true").lower() == "true"


azure_openai_tools = []
azure_openai_available_tools = []

# Initialize Azure OpenAI Client
async def init_openai_client():
    azure_openai_client = None
    
    try:
        # API version check
        if (
            app_settings.azure_openai.preview_api_version
            < MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION
        ):
            raise ValueError(
                f"The minimum supported Azure OpenAI preview API version is '{MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION}'"
            )

        # Endpoint
        if (
            not app_settings.azure_openai.endpoint and
            not app_settings.azure_openai.resource
        ):
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_RESOURCE is required"
            )

        endpoint = (
            app_settings.azure_openai.endpoint
            if app_settings.azure_openai.endpoint
            else f"https://{app_settings.azure_openai.resource}.openai.azure.com/"
        )

        # Authentication
        aoai_api_key = app_settings.azure_openai.key
        ad_token_provider = None
        if not aoai_api_key:
            logging.debug("No AZURE_OPENAI_KEY found, using Azure Entra ID auth")
            async with DefaultAzureCredential() as credential:
                ad_token_provider = get_bearer_token_provider(
                    credential,
                    "https://cognitiveservices.azure.com/.default"
                )

        # Deployment
        deployment = app_settings.azure_openai.model
        if not deployment:
            raise ValueError("AZURE_OPENAI_MODEL is required")

        # Default Headers
        default_headers = {"x-ms-useragent": USER_AGENT}

        # Remote function calls
        if app_settings.azure_openai.function_call_azure_functions_enabled:
            azure_functions_tools_url = f"{app_settings.azure_openai.function_call_azure_functions_tools_base_url}?code={app_settings.azure_openai.function_call_azure_functions_tools_key}"
            async with httpx.AsyncClient() as client:
                response = await client.get(azure_functions_tools_url)
            response_status_code = response.status_code
            if response_status_code == httpx.codes.OK:
                azure_openai_tools.extend(json.loads(response.text))
                for tool in azure_openai_tools:
                    azure_openai_available_tools.append(tool["function"]["name"])
            else:
                logging.error(f"An error occurred while getting OpenAI Function Call tools metadata: {response.status_code}")

        
        azure_openai_client = AsyncAzureOpenAI(
            api_version=app_settings.azure_openai.preview_api_version,
            api_key=aoai_api_key,
            azure_ad_token_provider=ad_token_provider,
            default_headers=default_headers,
            azure_endpoint=endpoint,
        )

        return azure_openai_client
    except Exception as e:
        logging.exception("Exception in Azure OpenAI initialization", e)
        azure_openai_client = None
        raise e

async def openai_remote_azure_function_call(function_name, function_args):
    if app_settings.azure_openai.function_call_azure_functions_enabled is not True:
        return

    azure_functions_tool_url = f"{app_settings.azure_openai.function_call_azure_functions_tool_base_url}?code={app_settings.azure_openai.function_call_azure_functions_tool_key}"
    headers = {'content-type': 'application/json'}
    body = {
        "tool_name": function_name,
        "tool_arguments": json.loads(function_args)
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(azure_functions_tool_url, data=json.dumps(body), headers=headers)
    response.raise_for_status()

    return response.text

async def init_cosmosdb_client():
    cosmos_conversation_client = None
    if app_settings.chat_history:
        try:
            cosmos_endpoint = (
                f"https://{app_settings.chat_history.account}.documents.azure.com:443/"
            )

            if not app_settings.chat_history.account_key:
                async with DefaultAzureCredential() as cred:
                    credential = cred
                    
            else:
                credential = app_settings.chat_history.account_key

            cosmos_conversation_client = CosmosConversationClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=credential,
                database_name=app_settings.chat_history.database,
                container_name=app_settings.chat_history.conversations_container,
                enable_message_feedback=app_settings.chat_history.enable_feedback,
            )
        except Exception as e:
            logging.exception("Exception in CosmosDB initialization", e)
            cosmos_conversation_client = None
            raise e
    else:
        logging.debug("CosmosDB not configured")

    return cosmos_conversation_client



async def promptflow_request(request):
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {app_settings.promptflow.api_key}",
        }
        # Adding timeout for scenarios where response takes longer to come back
        logging.debug(f"Setting timeout to {app_settings.promptflow.response_timeout}")
        async with httpx.AsyncClient(
            timeout=float(app_settings.promptflow.response_timeout)
        ) as client:
            pf_formatted_obj = convert_to_pf_format(
                request,
                app_settings.promptflow.request_field_name,
                app_settings.promptflow.response_field_name
            )
            # NOTE: This only support question and chat_history parameters
            # If you need to add more parameters, you need to modify the request body
            response = await client.post(
                app_settings.promptflow.endpoint,
                json={
                    app_settings.promptflow.request_field_name: pf_formatted_obj[-1]["inputs"][app_settings.promptflow.request_field_name],
                    "chat_history": pf_formatted_obj[:-1],
                },
                headers=headers,
            )
        resp = response.json()
        resp["id"] = request["messages"][-1]["id"]
        return resp
    except Exception as e:
        logging.error(f"An error occurred while making promptflow_request: {e}")


async def process_function_call(response):
    response_message = response.choices[0].message
    messages = []

    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            # Check if function exists
            if tool_call.function.name not in azure_openai_available_tools:
                continue
            
            function_response = await openai_remote_azure_function_call(tool_call.function.name, tool_call.function.arguments)

            # adding assistant response to messages
            messages.append(
                {
                    "role": response_message.role,
                    "function_call": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                    "content": None,
                }
            )
            
            # adding function response to messages
            messages.append(
                {
                    "role": "function",
                    "name": tool_call.function.name,
                    "content": function_response,
                }
            )  # extend conversation with function response
        
        return messages
    
    return None

async def send_chat_request(request_body, request_headers, shouldStream = True):
    filtered_messages = []
    messages = request_body.get("messages", [])
    
    # DEBUG: Log incoming messages to see if images are present
    logging.info(f"DEBUG: Received {len(messages)} messages in send_chat_request")
    for i, msg in enumerate(messages):
        logging.info(f"DEBUG: Message {i} - role: {msg.get('role')}, content type: {type(msg.get('content'))}")
        if isinstance(msg.get('content'), list):
            for j, part in enumerate(msg['content']):
                logging.info(f"DEBUG: Message {i}, part {j} - type: {part.get('type')}")
                if part.get('type') == 'image_url':
                    image_url = part.get('image_url', {}).get('url', '')
                    logging.info(f"DEBUG: Found image_url in send_chat_request, length: {len(image_url)}, preview: {image_url[:50]}...")
    
    for message in messages:
        if message.get("role") != 'tool':
            filtered_messages.append(message)
            
    request_body['messages'] = filtered_messages
    
    # Get provider from request or customizationPreferences, fallback to default
    provider_type = request_body.get("provider")
    
    # If provider not directly specified, check customizationPreferences
    if not provider_type:
        customization_preferences = request_body.get("customizationPreferences", {})
        provider_type = customization_preferences.get("llmProvider")
    
    # Fallback to default if still not found
    if not provider_type:
        provider_type = LLMProviderFactory.get_default_provider()
    
    print(f"🤖 LLM Provider utilisé: {provider_type}")
    logging.info(f"🤖 LLM Provider utilisé: {provider_type}")
    logging.debug(f"send_chat_request: Using provider = {provider_type}")
    
    # Use the unified LLM provider abstraction for ALL providers
    try:
        logging.info(f"DEBUG APP: About to create provider: {provider_type}")
        provider = LLMProviderFactory.create_provider(provider_type)
        logging.info(f"DEBUG APP: Created provider instance: {provider.__class__.__name__}")
        logging.info(f"DEBUG APP: Provider module: {provider.__class__.__module__}")
        
        # Extract messages for all providers (they handle their own model args)
        request_messages = request_body.get("messages", [])
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in request_messages]
        
        # Send request to provider
        logging.debug(f"Sending request to {provider_type} with shouldStream={shouldStream}")
        
        # Extract customization preferences
        customization_preferences = request_body.get("customizationPreferences", {})
        documents_count = customization_preferences.get("documentsCount")
        response_size = customization_preferences.get("responseSize", "medium")
        
        print(f"📊 Paramètres de personnalisation:")
        print(f"   - Nombre de documents: {documents_count}")
        print(f"   - Taille de réponse: {response_size}")
        
        # Extract search filters and user permissions properly
        user_full_definition = request_body.get("userFullDefinition", "*")
        search_filters = None
        user_permissions = None
        
        if user_full_definition and user_full_definition != "*":
            # For Claude, we need to pass this as user permissions for rights management
            user_permissions = user_full_definition
            logging.debug(f"Setting user_permissions for {provider_type}: {user_permissions}")
        
        response, apim_request_id = await provider.send_request(
            messages=messages,
            stream=shouldStream,
            documents_count=documents_count,
            response_size=response_size,
            search_filters=search_filters,
            user_permissions=user_permissions
        )
        
        logging.debug(f"Response from {provider_type}: {type(response)} - {str(response)[:200]}...")
        
        return response, apim_request_id
    except Exception as e:
        from backend.llm_providers.errors import LLMProviderErrorHandler
        
        logging.exception(f"Exception in send_chat_request with provider {provider_type}")
        
        # Create user-friendly error and re-raise with enhanced message
        user_message, status_code = LLMProviderErrorHandler.handle_provider_error(
            exception=e,
            provider_name=provider_type,
            language="fr"  # Default to French for AskMe
        )
        
        # Create a new exception with user-friendly message but preserve original for debugging
        enhanced_error = Exception(user_message)
        enhanced_error.status_code = status_code
        enhanced_error.original_error = e
        raise enhanced_error


async def complete_chat_request(request_body, request_headers):
    if app_settings.base_settings.use_promptflow:
        response = await promptflow_request(request_body)
        history_metadata = request_body.get("history_metadata", {})
        return format_pf_non_streaming_response(
            response,
            history_metadata,
            app_settings.promptflow.response_field_name,
            app_settings.promptflow.citations_field_name
        )
    else:
        logging.debug("Calling send_chat_request with shouldStream=False")
        response, apim_request_id = await send_chat_request(request_body, request_headers, False)
        logging.debug(f"send_chat_request response type: {type(response)}, apim_request_id: {apim_request_id}")
        history_metadata = request_body.get("history_metadata", {})
        non_streaming_response = format_non_streaming_response(response, history_metadata, apim_request_id)
        logging.debug(f"non_streaming_response: {type(non_streaming_response)} - {str(non_streaming_response)[:200]}...")

        if app_settings.azure_openai.function_call_azure_functions_enabled:
            function_response = await process_function_call(response)  # Add await here

            if function_response:
                request_body["messages"].extend(function_response)

                response, apim_request_id = await send_chat_request(request_body, request_headers)
                history_metadata = request_body.get("history_metadata", {})
                non_streaming_response = format_non_streaming_response(response, history_metadata, apim_request_id)

    return non_streaming_response

class AzureOpenaiFunctionCallStreamState():
    def __init__(self):
        self.tool_calls = []                # All tool calls detected in the stream
        self.tool_name = ""                 # Tool name being streamed
        self.tool_arguments_stream = ""     # Tool arguments being streamed
        self.current_tool_call = None       # JSON with the tool name and arguments currently being streamed
        self.function_messages = []         # All function messages to be appended to the chat history
        self.streaming_state = "INITIAL"    # Streaming state (INITIAL, STREAMING, COMPLETED)


async def process_function_call_stream(completionChunk, function_call_stream_state, request_body, request_headers, history_metadata, apim_request_id):
    if hasattr(completionChunk, "choices") and len(completionChunk.choices) > 0:
        response_message = completionChunk.choices[0].delta
        
        # Function calling stream processing
        if response_message.tool_calls and function_call_stream_state.streaming_state in ["INITIAL", "STREAMING"]:
            function_call_stream_state.streaming_state = "STREAMING"
            for tool_call_chunk in response_message.tool_calls:
                # New tool call
                if tool_call_chunk.id:
                    if function_call_stream_state.current_tool_call:
                        function_call_stream_state.tool_arguments_stream += tool_call_chunk.function.arguments if tool_call_chunk.function.arguments else ""
                        function_call_stream_state.current_tool_call["tool_arguments"] = function_call_stream_state.tool_arguments_stream
                        function_call_stream_state.tool_arguments_stream = ""
                        function_call_stream_state.tool_name = ""
                        function_call_stream_state.tool_calls.append(function_call_stream_state.current_tool_call)

                    function_call_stream_state.current_tool_call = {
                        "tool_id": tool_call_chunk.id,
                        "tool_name": tool_call_chunk.function.name if function_call_stream_state.tool_name == "" else function_call_stream_state.tool_name
                    }
                else:
                    function_call_stream_state.tool_arguments_stream += tool_call_chunk.function.arguments if tool_call_chunk.function.arguments else ""
                
        # Function call - Streaming completed
        elif response_message.tool_calls is None and function_call_stream_state.streaming_state == "STREAMING":
            function_call_stream_state.current_tool_call["tool_arguments"] = function_call_stream_state.tool_arguments_stream
            function_call_stream_state.tool_calls.append(function_call_stream_state.current_tool_call)
            
            for tool_call in function_call_stream_state.tool_calls:
                tool_response = await openai_remote_azure_function_call(tool_call["tool_name"], tool_call["tool_arguments"])

                function_call_stream_state.function_messages.append({
                    "role": "assistant",
                    "function_call": {
                        "name" : tool_call["tool_name"],
                        "arguments": tool_call["tool_arguments"]
                    },
                    "content": None
                })
                function_call_stream_state.function_messages.append({
                    "tool_call_id": tool_call["tool_id"],
                    "role": "function",
                    "name": tool_call["tool_name"],
                    "content": tool_response,
                })
            
            function_call_stream_state.streaming_state = "COMPLETED"
            return function_call_stream_state.streaming_state
        
        else:
            return function_call_stream_state.streaming_state


async def stream_chat_request(request_body, request_headers):
    # Get provider from request or customizationPreferences, fallback to default
    provider_type = request_body.get("provider")
    
    # If provider not directly specified, check customizationPreferences
    if not provider_type:
        customization_preferences = request_body.get("customizationPreferences", {})
        provider_type = customization_preferences.get("llmProvider")
    
    # Fallback to default if still not found
    if not provider_type:
        provider_type = LLMProviderFactory.get_default_provider()
    
    logging.debug(f"stream_chat_request: Using provider = {provider_type}")
    
    # Enable streaming for both providers
    shouldStream = True
    
    response, apim_request_id = await send_chat_request(request_body, request_headers, shouldStream)
    history_metadata = request_body.get("history_metadata", {})
    
    async def generate(apim_request_id, history_metadata):
        # Azure OpenAI specific function calling logic
        if provider_type == "AZURE_OPENAI" and app_settings.azure_openai.function_call_azure_functions_enabled:
            # Maintain state during function call streaming
            function_call_stream_state = AzureOpenaiFunctionCallStreamState()
            
            async for completionChunk in response:
                stream_state = await process_function_call_stream(completionChunk, function_call_stream_state, request_body, request_headers, history_metadata, apim_request_id)
                
                # No function call, asistant response
                if stream_state == "INITIAL":
                    yield format_stream_response(completionChunk, history_metadata, apim_request_id)

                # Function call stream completed, functions were executed.
                # Append function calls and results to history and send to OpenAI, to stream the final answer.
                if stream_state == "COMPLETED":
                    request_body["messages"].extend(function_call_stream_state.function_messages)
                    function_response, apim_request_id = await send_chat_request(request_body, request_headers)
                    async for functionCompletionChunk in function_response:
                        yield format_stream_response(functionCompletionChunk, history_metadata, apim_request_id)
                
        else:
            # For Claude and non-function Azure OpenAI requests
            if hasattr(response, '__aiter__'):
                # Response is already an async generator (streaming)
                async for completionChunk in response:
                    yield format_stream_response(completionChunk, history_metadata, apim_request_id)
            elif isinstance(response, dict):
                # Response is a single completion object (non-streaming) - but this shouldn't happen for Claude
                logging.warning(f"Received dict response in stream_chat_request: {type(response)}")
                yield format_stream_response(response, history_metadata, apim_request_id)
            elif hasattr(response, 'id'):
                # Response is a single completion object (MockAzureOpenAIResponse for Claude)
                formatted_response = format_stream_response(response, history_metadata, apim_request_id)
                yield formatted_response
            else:
                # Response is a regular iterable (fallback)
                for completionChunk in response:
                    yield format_stream_response(completionChunk, history_metadata, apim_request_id)

    return generate(apim_request_id=apim_request_id, history_metadata=history_metadata)

def LogCallToAiManager(request_body):
    
    try:
        if (app_settings.custom_avanteam_settings.licencehub_key is None or app_settings.custom_avanteam_settings.licencehub_key == ""):
            return jsonify({"status":"ERR", "details":"AVANTEAM_LICENCEHUB_KEY n'est pas défini"}), 200

        logContent = {
            'licenceHubKey' : app_settings.custom_avanteam_settings.licencehub_key,
            'who' : request_body.get("currentUser", "-"),
            'messages' : json.dumps(request_body.get("messages", [])) 
        }

        query_params = {
            'q': 'LogAskMeCall',
            'logContent': encrypt_string(json.dumps(logContent))
        }

        response = requests.get(app_settings.custom_avanteam_settings.licencehub_handlerurl, params=query_params)
        response.raise_for_status()  # raise an exception for HTTP errors

    except Exception as e:
        return jsonify({"status":"ERR", "details":str(e)}), 200
    


async def conversation_internal(request_body, request_headers, preventShouldStream = False):
    try:
        # LogCallToAiManager(request_body)
        logging.debug(f"conversation_internal: stream={app_settings.azure_openai.stream}, use_promptflow={app_settings.base_settings.use_promptflow}, preventShouldStream={preventShouldStream}")

        # Récupérer l'ID utilisateur pour gérer les sessions
        class MockRequest:
            def __init__(self, headers):
                self.headers = headers
        mock_request = MockRequest(request_headers)
        user_id = GetDecryptedUsername(mock_request)
        if user_id:
            # Initialiser la session utilisateur si elle n'existe pas
            if user_id not in user_sessions:
                user_sessions[user_id] = {}
        
        # Vérifier si c'est une commande
        messages = request_body.get("messages", [])
        if messages:
            last_message = messages[-1]
            if last_message.get("role") == "user":
                content = last_message.get("content", "")
                
                # Extraire le texte du contenu (peut être string ou list avec images)
                text_content = ""
                if isinstance(content, str):
                    text_content = content
                elif isinstance(content, list):
                    for part in content:
                        if part.get("type") == "text":
                            text_content = part.get("text", "")
                            break
                
                # Détecter les commandes
                if text_content:
                    commands = command_parser.parse_commands(text_content)
                    if commands:
                        # Exécuter les commandes
                        executor = ChatCommandExecutor(app_settings)
                        current_session = user_sessions.get(user_id, {})
                        result = await executor.execute_commands(commands, current_session)
                        
                        # Mettre à jour la session utilisateur
                        if 'user_session' in result:
                            user_sessions[user_id] = result['user_session']
                        
                        # Gérer les actions spéciales
                        if result.get('action') == 'new_conversation':
                            # Ajouter l'ID de nouvelle conversation
                            result['new_conversation_id'] = str(uuid.uuid4())
                        elif result.get('action') == 'clear_conversation':
                            # Ajouter l'action de nettoyage
                            result['clear_messages'] = True
                        
                        # Retourner la réponse de la commande directement
                        response_id = str(uuid.uuid4())
                        return jsonify({
                            "id": response_id,
                            "choices": [{
                                "messages": [{
                                    "id": response_id,
                                    "role": "assistant", 
                                    "content": result['message'],
                                    "date": datetime.now().isoformat()
                                }]
                            }],
                            "command_result": result
                        })

        # DEBUG: Log incoming messages to see if images are present BEFORE processing
        logging.info(f"DEBUG: conversation_internal received {len(messages)} messages")
        for i, msg in enumerate(messages):
            logging.info(f"DEBUG: Message {i} - role: {msg.get('role')}, content type: {type(msg.get('content'))}")
            if isinstance(msg.get('content'), list):
                for j, part in enumerate(msg['content']):
                    logging.info(f"DEBUG: Message {i}, part {j} - type: {part.get('type')}")
                    if part.get('type') == 'image_url':
                        image_url = part.get('image_url', {}).get('url', '')
                        logging.info(f"DEBUG: Found image_url in conversation_internal, length: {len(image_url)}, preview: {image_url[:50]}...")

        # Appliquer les préférences de session de l'utilisateur
        if user_id and user_id in user_sessions:
            session = user_sessions[user_id]
            logging.info(f"Application des préférences de session pour {user_id}: {session}")
            
            # Appliquer le provider LLM de la session
            if 'llm_provider' in session:
                request_body['customizationPreferences'] = request_body.get('customizationPreferences', {})
                request_body['customizationPreferences']['llmProvider'] = session['llm_provider']
                logging.info(f"Provider LLM appliqué: {session['llm_provider']}")
            
            # Appliquer le nombre de documents de la session
            if 'documents_count' in session:
                request_body['documents_count'] = session['documents_count']
            
            # Appliquer la longueur de réponse de la session
            if 'response_length' in session:
                request_body['customizationPreferences'] = request_body.get('customizationPreferences', {})
                # Mapper les valeurs du backend vers les valeurs du frontend
                response_mapping = {
                    'VERY_SHORT': 'veryShort',
                    'NORMAL': 'medium',
                    'COMPREHENSIVE': 'comprehensive'
                }
                mapped_size = response_mapping.get(session['response_length'], 'medium')
                request_body['customizationPreferences']['responseSize'] = mapped_size

        if app_settings.azure_openai.stream and not app_settings.base_settings.use_promptflow and not preventShouldStream:
            logging.debug("Using streaming chat request")
            result = await stream_chat_request(request_body, request_headers)
            
            # Extract provider name for better error messages
            provider_type = request_body.get("provider") or \
                           request_body.get("customizationPreferences", {}).get("llmProvider") or \
                           "AZURE_OPENAI"
            
            response = await make_response(format_as_ndjson(result, provider_name=provider_type))
            response.timeout = None
            response.mimetype = "application/json-lines"
            return response
        else:
            logging.debug("Using complete chat request")
            result = await complete_chat_request(request_body, request_headers)
            logging.debug(f"complete_chat_request result: {type(result)} - {str(result)[:200]}...")
            return jsonify(result)

    except Exception as ex:
        from backend.llm_providers.errors import LLMProviderErrorHandler
        
        logging.exception(f"Exception in conversation_internal: {ex}")
        
        # Check if this is already an enhanced error with user-friendly message
        if hasattr(ex, 'original_error'):
            # Already processed by our error handler
            error_message = str(ex)
            status_code = getattr(ex, 'status_code', 500)
        else:
            # Process with our error handler
            error_message, status_code = LLMProviderErrorHandler.handle_provider_error(
                exception=ex,
                provider_name="SYSTEM",
                language="fr"
            )
        
        return jsonify({"error": error_message}), status_code

def CheckAuthenticate(request):
    return True
    # if "AuthToken" in request.headers:
    #     salt = datetime.now().strftime("%d%m%Y")
    #     fullchain = app_settings.custom_avanteam_settings.auth_token + salt
    #     shaEncoded = sha256(fullchain.encode('utf-8')).hexdigest()
    #     return request.headers["AuthToken"] == shaEncoded
    # else:
    #     return False
    
def GetDecryptedUsername(request):
    
    if "EncodedUsername" in request.headers:
        return decrypt_string(request.headers["EncodedUsername"])
    else:
        return None
    

def GetRemainingTokens():
    if (app_settings.custom_avanteam_settings.licencehub_key is None or app_settings.custom_avanteam_settings.licencehub_key == ""):
        return False

    query_params = {
        'q': 'GetTokensForKey',
        'key': app_settings.custom_avanteam_settings.licencehub_key
    }

    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    s = requests.Session()
    s.mount('https://', HTTPAdapter(max_retries=retries))

    try:
        response = s.get(app_settings.custom_avanteam_settings.licencehub_handlerurl, params=query_params)
        response.raise_for_status()  # raise an exception for HTTP errors
        nb = int(response.text)
        return nb
    except requests.exceptions.RequestException as e:
        logging.debug(f"Request failed: {e}")
        return False


@bp.route("/conversation", methods=["POST"])
async def conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401

    if GetRemainingTokens() < 0:
        return jsonify({"error": "No tokens left"}), 401
    
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()

    return await conversation_internal(request_json, request.headers)

@bp.route("/conversation-mobile", methods=["POST"])
async def conversation_mobile():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    
    if GetRemainingTokens() < 0:
        return jsonify({"error": "No tokens left"}), 401
    
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    
    return await conversation_internal(request_json, request.headers, True)

@bp.route("/authenticate", methods=["POST"])
async def authenticate():
    if not(CheckAuthenticate(request)):
        return jsonify({"status": "ko"}), 200

    return jsonify({"status":"ok"}), 200

@bp.route("/frontend_settings", methods=["GET"])
def get_frontend_settings():
    try:
        return jsonify(frontend_settings), 200
    except Exception as e:
        logging.exception("Exception in /frontend_settings")
        return jsonify({"error": str(e)}), 500

@bp.route("/check-tokens", methods=["POST"])
async def check_tokens():

    try:
        if (app_settings.custom_avanteam_settings.licencehub_key is None or app_settings.custom_avanteam_settings.licencehub_key == ""):
            return jsonify({"status":"ERR", "details":"AVANTEAM_LICENCEHUB_KEY n'est pas défini"}), 200

        nb = GetRemainingTokens()
        logging.debug(f"Récupération des tokens : {nb}")
        if (nb <= 0):
            return jsonify({"status":"KO"}), 200
        elif (nb <= app_settings.custom_avanteam_settings.threshold_remaining_alert):
            return jsonify({"status":"WARN"}), 200
        else:
            return jsonify({"status":"OK"}), 200
        

    except Exception as e:
        return jsonify({"status":"ERR", "details":str(e)}), 200
    

## Conversation History API ##
@bp.route("/history/generate", methods=["POST"])
async def add_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()

    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400
    

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        # make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        # check for the conversation_id, if the conversation is not set, we will create a new one
        history_metadata = {}
        if not conversation_id:
            title = await generate_title(request_json["messages"])
            conversation_dict = await current_app.cosmos_conversation_client.create_conversation(
                user_id=user_id, title=title
            )
            conversation_id = conversation_dict["id"]
            history_metadata["conversation_id"] = conversation_id
            history_metadata["title"] = title
            history_metadata["date"] = conversation_dict["createdAt"]
        else:
            # For existing conversations, still add the conversation_id to metadata
            history_metadata["conversation_id"] = conversation_id

        ## Format the incoming message object in the "chat/completions" messages format
        ## then write it to the conversation history in cosmos
        messages = request_json["messages"]
        if len(messages) > 0 and messages[-1]["role"] == "user":
            createdMessageValue = await current_app.cosmos_conversation_client.create_message(
                uuid=str(uuid.uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
            if createdMessageValue == "Conversation not found":
                raise Exception(
                    "Conversation not found for the given conversation ID: "
                    + conversation_id
                    + "."
                )
        else:
            raise Exception("No user message found")

        # Submit request to Chat Completions for response
        # Use the already parsed request_json instead of parsing again
        request_json["history_metadata"] = history_metadata
        
        # Debug logging pour vérifier la transmission du provider
        provider_from_request = request_json.get('provider')
        provider_from_prefs = request_json.get('customizationPreferences', {}).get('llmProvider') if request_json.get('customizationPreferences') else None
        final_provider = provider_from_request or provider_from_prefs or "DEFAULT (AZURE_OPENAI)"
        print(f"🤖 LLM Provider utilisé (history/generate): {final_provider}")
        logging.info(f"🤖 LLM Provider utilisé (history/generate): {final_provider}")
        logging.debug(f"history/generate: provider in request = {request_json.get('provider', 'Not specified')}")
        logging.debug(f"history/generate: customizationPreferences = {request_json.get('customizationPreferences', 'None')}")
        
        return await conversation_internal(request_json, request.headers)

    except Exception as e:
        from backend.llm_providers.errors import LLMProviderErrorHandler
        
        logging.exception("Exception in /history/generate")
        
        # Create user-friendly error message
        error_message, status_code = LLMProviderErrorHandler.handle_provider_error(
            exception=e,
            provider_name="HISTORY_SERVICE",
            language="fr"
        )
        
        return jsonify({"error": error_message}), status_code


@bp.route("/history/update", methods=["POST"])
async def update_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for conversation_id
    request_json = await request.get_json()
    logging.debug(f"history/update received request: {request_json}")
    conversation_id = request_json.get("conversation_id", None)
    logging.debug(f"history/update conversation_id: {conversation_id}")

    try:
        # make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        # check for the conversation_id, if the conversation is not set, we will create a new one
        if not conversation_id:
            logging.error(f"No conversation_id found in request: {request_json}")
            raise Exception("No conversation_id found")

        ## Format the incoming message object in the "chat/completions" messages format
        ## then write it to the conversation history in cosmos
        messages = request_json["messages"]
        logging.info(f"DEBUG /history/update received {len(messages)} messages: {[{'role': m.get('role'), 'content_type': type(m.get('content')), 'content_preview': str(m.get('content'))[:50] if m.get('content') else 'None'} for m in messages]}")
        
        # Filter out invalid messages (empty objects, missing role, etc.)
        valid_messages = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") and msg.get("content") is not None:
                valid_messages.append(msg)
            else:
                logging.warning(f"Filtering out invalid message: {msg}")
        
        messages = valid_messages
        logging.info(f"DEBUG /history/update after filtering: {len(messages)} valid messages")
        
        if len(messages) > 0 and messages[-1]["role"] == "assistant":
            if len(messages) > 1 and messages[-2].get("role", None) == "tool":
                # write the tool message first
                await current_app.cosmos_conversation_client.create_message(
                    uuid=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    input_message=messages[-2],
                )
            # write the assistant message
            await current_app.cosmos_conversation_client.create_message(
                uuid=messages[-1]["id"],
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
        else:
            # Pas de messages valides à sauvegarder, retourner succès sans erreur
            logging.warning(f"No valid messages to save for conversation {conversation_id}, skipping history update")
            response = {"success": True}
            return jsonify(response), 200

        # Submit request to Chat Completions for response
        response = {"success": True}
        return jsonify(response), 200

    except Exception as e:
        logging.exception("Exception in /history/update")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/message_feedback", methods=["POST"])
async def update_message():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for message_id
    request_json = await request.get_json()
    message_id = request_json.get("message_id", None)
    message_feedback = request_json.get("message_feedback", None)
    try:
        if not message_id:
            return jsonify({"error": "message_id is required"}), 400

        if not message_feedback:
            return jsonify({"error": "message_feedback is required"}), 400

        ## update the message in cosmos
        updated_message = await current_app.cosmos_conversation_client.update_message_feedback(
            user_id, message_id, message_feedback
        )
        if updated_message:
            return (
                jsonify(
                    {
                        "message": f"Successfully updated message with feedback {message_feedback}",
                        "message_id": message_id,
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "error": f"Unable to update message {message_id}. It either does not exist or the user does not have access to it."
                    }
                ),
                404,
            )

    except Exception as e:
        logging.exception("Exception in /history/message_feedback")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/delete", methods=["DELETE"])
async def delete_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    ## get the user id from the request headers
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400

        ## make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        ## delete the conversation messages from cosmos first
        deleted_messages = await current_app.cosmos_conversation_client.delete_messages(
            conversation_id, user_id
        )

        ## Now delete the conversation
        deleted_conversation = await current_app.cosmos_conversation_client.delete_conversation(
            user_id, conversation_id
        )

        return (
            jsonify(
                {
                    "message": "Successfully deleted conversation and messages",
                    "conversation_id": conversation_id,
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("Exception in /history/delete")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/list", methods=["GET"])
async def list_conversations():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    offset = request.args.get("offset", 0)
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## make sure cosmos is configured
    if not current_app.cosmos_conversation_client:
        raise Exception("CosmosDB is not configured or not working")

    ## get the conversations from cosmos
    conversations = await current_app.cosmos_conversation_client.get_conversations(
        user_id, offset=offset, limit=25
    )
    if not isinstance(conversations, list):
        return jsonify({"error": f"No conversations for {user_id} were found"}), 404

    ## return the conversation ids

    return jsonify(conversations), 200


@bp.route("/history/read", methods=["POST"])
async def get_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400

    ## make sure cosmos is configured
    if not current_app.cosmos_conversation_client:
        raise Exception("CosmosDB is not configured or not working")

    ## get the conversation object and the related messages from cosmos
    conversation = await current_app.cosmos_conversation_client.get_conversation(
        user_id, conversation_id
    )
    ## return the conversation id and the messages in the bot frontend format
    if not conversation:
        return (
            jsonify(
                {
                    "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                }
            ),
            404,
        )

    # get the messages for the conversation from cosmos
    conversation_messages = await current_app.cosmos_conversation_client.get_messages(
        user_id, conversation_id
    )

    ## format the messages in the bot frontend format
    messages = [
        {
            "id": msg["id"],
            "role": msg["role"],
            "content": msg["content"],
            "createdAt": msg["createdAt"],
            "feedback": msg.get("feedback"),
        }
        for msg in conversation_messages
    ]

    return jsonify({"conversation_id": conversation_id, "messages": messages}), 200


@bp.route("/history/rename", methods=["POST"])
async def rename_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400

    ## make sure cosmos is configured
    if not current_app.cosmos_conversation_client:
        raise Exception("CosmosDB is not configured or not working")

    ## get the conversation from cosmos
    conversation = await current_app.cosmos_conversation_client.get_conversation(
        user_id, conversation_id
    )
    if not conversation:
        return (
            jsonify(
                {
                    "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                }
            ),
            404,
        )

    ## update the title
    title = request_json.get("title", None)
    if not title:
        return jsonify({"error": "title is required"}), 400
    conversation["title"] = title
    updated_conversation = await current_app.cosmos_conversation_client.upsert_conversation(
        conversation
    )

    return jsonify(updated_conversation), 200


@bp.route("/history/delete_all", methods=["DELETE"])
async def delete_all_conversations():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    ## get the user id from the request headers
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400
    

    # get conversations for user
    try:
        ## make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        conversations = await current_app.cosmos_conversation_client.get_conversations(
            user_id, offset=0, limit=None
        )
        if not conversations:
            return jsonify({"error": f"No conversations for {user_id} were found"}), 404

        # delete each conversation
        for conversation in conversations:
            ## delete the conversation messages from cosmos first
            deleted_messages = await current_app.cosmos_conversation_client.delete_messages(
                conversation["id"], user_id
            )

            ## Now delete the conversation
            deleted_conversation = await current_app.cosmos_conversation_client.delete_conversation(
                user_id, conversation["id"]
            )
        return (
            jsonify(
                {
                    "message": f"Successfully deleted conversation and messages for user {user_id}"
                }
            ),
            200,
        )

    except Exception as e:
        logging.exception("Exception in /history/delete_all")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/clear", methods=["POST"])
async def clear_messages():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    ## get the user id from the request headers
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400
    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400

        ## make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        ## delete the conversation messages from cosmos
        deleted_messages = await current_app.cosmos_conversation_client.delete_messages(
            conversation_id, user_id
        )

        return (
            jsonify(
                {
                    "message": "Successfully deleted messages in conversation",
                    "conversation_id": conversation_id,
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("Exception in /history/clear_messages")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/ensure", methods=["GET"])
async def ensure_cosmos():
    # return jsonify({"error": "CosmosDB is not configured"}), 404
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    if not app_settings.chat_history:
        return jsonify({"error": "CosmosDB is not configured"}), 404

    try:
        success, err = await current_app.cosmos_conversation_client.ensure()
        if not current_app.cosmos_conversation_client or not success:
            if err:
                return jsonify({"error": err}), 422
            return jsonify({"error": "CosmosDB is not configured or not working"}), 500

        return jsonify({"message": "CosmosDB is configured and working"}), 200
    except Exception as e:
        logging.exception("Exception in /history/ensure")
        cosmos_exception = str(e)
        if "Invalid credentials" in cosmos_exception:
            return jsonify({"error": cosmos_exception}), 401
        elif "Invalid CosmosDB database name" in cosmos_exception:
            return (
                jsonify(
                    {
                        "error": f"{cosmos_exception} {app_settings.chat_history.database} for account {app_settings.chat_history.account}"
                    }
                ),
                422,
            )
        elif "Invalid CosmosDB container name" in cosmos_exception:
            return (
                jsonify(
                    {
                        "error": f"{cosmos_exception}: {app_settings.chat_history.conversations_container}"
                    }
                ),
                422,
            )
        else:
            return jsonify({"error": "CosmosDB is not working"}), 500


@bp.route("/help_content", methods=["GET"])
async def get_help_content():
    """
    Endpoint qui retourne le contenu d'aide à partir d'un fichier JSON.
    Supporte un paramètre de requête 'lang' pour la localisation.
    """
    try:
        language = request.args.get("lang", "FR")
        
        # Chemin vers le fichier de contenu d'aide
        help_content_path = os.path.join(os.path.dirname(__file__), "data", "help_content.json")
        
        # Vérifier si le fichier existe
        if not os.path.exists(help_content_path):
            return jsonify({"error": "Help content file not found"}), 404
            
        # Lire le fichier JSON
        with open(help_content_path, 'r', encoding='utf-8') as file:
            content = json.load(file)
            
        return jsonify(content), 200
        
    except Exception as e:
        logging.exception("Exception in /help_content")
        return jsonify({"error": str(e)}), 500


@bp.route("/upload-document", methods=["POST"])
async def upload_document():
    """
    Endpoint pour traiter l'upload de documents et extraire leur contenu textuel.
    Supporte les formats PDF, Word (.docx) et texte (.txt).
    """
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        # Vérifier qu'un fichier a été uploadé
        files = await request.files
        if 'file' not in files:
            return jsonify({
                "success": False,
                "error": "Aucun fichier fourni. Utilisez le champ 'file' pour l'upload."
            }), 400
        
        uploaded_file = files['file']
        if not uploaded_file.filename:
            return jsonify({
                "success": False,
                "error": "Nom de fichier manquant"
            }), 400
        
        # Lire le contenu du fichier
        file_content = uploaded_file.read()
        if not file_content:
            return jsonify({
                "success": False,
                "error": "Le fichier est vide"
            }), 400
        
        # Traiter le document
        result = DocumentProcessor.process_document(
            filename=uploaded_file.filename,
            file_content=file_content,
            mime_type=uploaded_file.content_type
        )
        
        if result["success"]:
            return jsonify({
                "success": True,
                "text": result["text"],
                "file_info": result["file_info"]
            })
        else:
            return jsonify({
                "success": False,
                "error": result["error"],
                "file_info": result.get("file_info", {})
            }), 400
            
    except Exception as e:
        logging.error(f"Error in upload_document endpoint: {e}")
        return jsonify({
            "success": False,
            "error": f"Erreur serveur lors du traitement du document: {str(e)}"
        }), 500
    

async def generate_title(conversation_messages) -> str:
    ## make sure the messages are sorted by _ts descending
    print("🤖 LLM Provider utilisé (génération titre): AZURE_OPENAI (forcé)")
    logging.info("🤖 LLM Provider utilisé (génération titre): AZURE_OPENAI (forcé)")
    title_prompt = "Résume la conversation précédente en un titre de 4 mots ou moins DANS LA LANGUE de cette même conversation. N'utilise pas de guillemets ni de ponctuation. N'inclus aucun autre commentaire ou description."

    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation_messages
    ]
    messages.append({"role": "user", "content": title_prompt})

    try:
        azure_openai_client = await init_openai_client()
        response = await azure_openai_client.chat.completions.create(
            model=app_settings.azure_openai.model, messages=messages, temperature=1, max_tokens=64
        )

        title = response.choices[0].message.content
        return title
    except Exception as e:
        logging.exception("Exception while generating title", e)
        return messages[-2]["content"]


@bp.route("/user/session", methods=["GET", "POST"])
async def user_session():
    """Endpoint pour gérer les préférences de session utilisateur"""
    if not CheckAuthenticate(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = GetDecryptedUsername(request)
    if not user_id:
        return jsonify({"error": "User not found"}), 400
    
    if request.method == "GET":
        # Récupérer les préférences de session
        session = user_sessions.get(user_id, {})
        return jsonify({
            "llm_provider": session.get('llm_provider'),
            "documents_count": session.get('documents_count'),
            "response_length": session.get('response_length')
        })
    
    elif request.method == "POST":
        # Mettre à jour les préférences de session
        try:
            data = await request.get_json()
            if user_id not in user_sessions:
                user_sessions[user_id] = {}
            
            if 'llm_provider' in data:
                user_sessions[user_id]['llm_provider'] = data['llm_provider']
            if 'documents_count' in data:
                user_sessions[user_id]['documents_count'] = data['documents_count']
            if 'response_length' in data:
                user_sessions[user_id]['response_length'] = data['response_length']
            
            return jsonify({
                "status": "success",
                "session": user_sessions[user_id]
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500


def get_encryption_key():
    # Cette fonction doit retourner la clé de chiffrement en base64, comme dans la version .NET
    # Exemple : 'your_base64_encoded_key'
    key_base64 = '+gSxYLZWesSFOppNJg1v7K7VvK4JzbxrLGPH+C6Ettc='
    return base64.b64decode(key_base64)


def encrypt_string(plain_text):
    key = get_encryption_key()
    iv = os.urandom(16)  # Générer un IV aléatoire de 16 octets (128 bits)
    
    # Créer le chiffreur AES avec la clé et l'IV
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Appliquer le padding PKCS7
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(plain_text.encode()) + padder.finalize()
    
    # Chiffrer les données
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    # Combiner l'IV et les données chiffrées
    combined_data = iv + encrypted_data
    
    # Convertir le résultat en base64
    encrypted_base64 = base64.b64encode(combined_data).decode('utf-8')
    
    return encrypted_base64

def decrypt_string(encrypted_base64):
    key = get_encryption_key()
    
    # Décoder les données en base64
    combined_data = base64.b64decode(encrypted_base64)
    
    # Extraire l'IV (les 16 premiers octets)
    iv = combined_data[:16]
    encrypted_data = combined_data[16:]
    
    # Créer le déchiffreur AES avec la clé et l'IV
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    # Déchiffrer les données
    padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
    
    # Retirer le padding PKCS7
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plain_text = unpadder.update(padded_data) + unpadder.finalize()
    
    # Convertir les données en chaîne de caractères
    return plain_text.decode('utf-8')


@bp.route("/speech/synthesize", methods=["POST"])
async def azure_speech_synthesize():
    """Endpoint pour synthèse vocale Azure Speech Services"""
    try:
        request_json = await request.get_json()
        text = request_json.get("text", "")
        language = request_json.get("language", "FR")
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        # Utiliser le service de synthèse vocale
        result = synthesize_speech_azure(text, language)
        
        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logging.error(f"Error in speech endpoint: {str(e)}")
        return jsonify({"error": f"Speech synthesis failed: {str(e)}"}), 500


@bp.route("/speech/pronunciation", methods=["GET"])
async def get_pronunciations():
    """Récupère le dictionnaire de pronunciations"""
    try:
        return jsonify({"pronunciations": get_pronunciation_dict()})
    except Exception as e:
        logging.error(f"Error getting pronunciations: {str(e)}")
        return jsonify({"error": "Failed to get pronunciations"}), 500


@bp.route("/speech/pronunciation", methods=["POST"])
async def add_pronunciation_rule():
    """Ajoute une règle de pronunciation"""
    try:
        request_json = await request.get_json()
        original = request_json.get("original", "")
        phonetic = request_json.get("phonetic", "")
        
        if not original or not phonetic:
            return jsonify({"error": "Both 'original' and 'phonetic' are required"}), 400
        
        add_pronunciation(original, phonetic)
        return jsonify({"success": True, "message": f"Pronunciation added: {original} -> {phonetic}"})
        
    except Exception as e:
        logging.error(f"Error adding pronunciation: {str(e)}")
        return jsonify({"error": "Failed to add pronunciation"}), 500


@bp.route("/speech/pronunciation/<original>", methods=["DELETE"])
async def remove_pronunciation_rule(original: str):
    """Supprime une règle de pronunciation"""
    try:
        success = remove_pronunciation(original)
        if success:
            return jsonify({"success": True, "message": f"Pronunciation removed: {original}"})
        else:
            return jsonify({"error": f"Pronunciation not found: {original}"}), 404
            
    except Exception as e:
        logging.error(f"Error removing pronunciation: {str(e)}")
        return jsonify({"error": "Failed to remove pronunciation"}), 500


@bp.route("/speech/clean", methods=["POST"])
async def clean_text_for_browser():
    """Nettoie le texte pour la synthèse vocale du navigateur"""
    try:
        request_json = await request.get_json()
        text = request_json.get("text", "")
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        # Nettoyer le texte pour le navigateur
        cleaned_text = clean_text_for_speech(text, for_browser=True)
        
        return jsonify({"success": True, "cleaned_text": cleaned_text})
        
    except Exception as e:
        logging.error(f"Error cleaning text: {str(e)}")
        return jsonify({"error": f"Text cleaning failed: {str(e)}"}), 500


app = create_app()