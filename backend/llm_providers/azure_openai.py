"""
Azure OpenAI provider implementation.

This module implements the LLM provider for Azure OpenAI services.
Since Azure OpenAI already returns responses in the standard format,
this provider requires minimal response transformation.

Key features:
- Azure AD authentication support
- Managed identity integration
- Full compatibility with existing Azure OpenAI configurations
- Azure Search integration via "On Your Data" (data_sources)
- Automatic documents_count parameter handling
- Minimal overhead since responses are already in standard format
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from openai import AsyncAzureOpenAI
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

from backend.settings import app_settings
from .base import LLMProvider, LLMProviderInitializationError, LLMProviderRequestError
from .models import StandardResponse, StandardResponseAdapter, StandardChoice, StandardMessage, StandardUsage
from .language_detection import detect_language, get_system_message_for_language


class AzureOpenAIProvider(LLMProvider):
    """
    Azure OpenAI provider implementation.
    
    This provider handles communication with Azure OpenAI services.
    Since Azure OpenAI responses are already in the standard OpenAI format,
    minimal transformation is needed.
    
    Features:
    - Supports both API key and Azure AD authentication
    - Handles managed identity scenarios
    - Maintains full compatibility with existing configurations
    - Azure Search integration via "On Your Data" (automatic data_sources construction)
    - Documents count parameter support via top_n_documents
    - User permissions filtering support
    - Supports all Azure OpenAI parameters (temperature, max_tokens, etc.)
    """
    
    def __init__(self):
        """Initialize the Azure OpenAI provider."""
        super().__init__()
        self.client = None
        self.logger = logging.getLogger("AzureOpenAIProvider")
    
    async def init_client(self):
        """
        Initialize Azure OpenAI client with authentication.
        
        Supports both API key and Azure AD token authentication.
        Uses managed identity when auth is enabled but no API key is provided.
        
        Raises:
            LLMProviderInitializationError: If initialization fails
        """
        if self.initialized:
            return
            
        try:
            # Configure authentication
            token_provider = None
            if app_settings.base_settings.auth_enabled and not app_settings.azure_openai.key:
                # Use Azure AD authentication with managed identity
                async with DefaultAzureCredential() as credential:
                    token_provider = get_bearer_token_provider(
                        credential, "https://cognitiveservices.azure.com/.default"
                    )
                self.logger.debug("Using Azure AD authentication")
            else:
                self.logger.debug("Using API key authentication")

            # Initialize the Azure OpenAI client
            self.client = AsyncAzureOpenAI(
                api_version=app_settings.azure_openai.preview_api_version,
                api_key=app_settings.azure_openai.key,
                azure_ad_token_provider=token_provider,
                default_headers={"x-ms-useragent": "GitHubSampleWebApp/AsyncAzureOpenAI/1.0.0"},
                azure_endpoint=app_settings.azure_openai.endpoint
            )
            
            self.initialized = True
            self.logger.info("Azure OpenAI client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            raise LLMProviderInitializationError(f"Azure OpenAI initialization failed: {e}")
    
    async def send_request(
        self, 
        messages: List[Dict[str, Any]], 
        stream: bool = True, 
        **kwargs
    ) -> Tuple[Any, Optional[str]]:
        """
        Send request to Azure OpenAI.
        
        Args:
            messages: List of messages in OpenAI chat format
            stream: Whether to return a streaming response
            **kwargs: Additional Azure OpenAI parameters
            
        Returns:
            Tuple of (response, apim_request_id)
            
        Raises:
            LLMProviderRequestError: If the request fails
        """
        await self.init_client()
        
        try:
            # Detect language from user's last message
            user_message = messages[-1]["content"] if messages else ""
            detected_language = detect_language(user_message)
            self.logger.debug(f"Detected language: {detected_language}")
            
            # Apply response size customization using centralized methods
            response_size = kwargs.get("response_size", "medium")
            base_max_tokens = kwargs.get("max_tokens", app_settings.azure_openai.max_tokens)
            adjusted_max_tokens = self._adjust_max_tokens_for_response_size(base_max_tokens, response_size)
            
            # For Azure OpenAI, we handle both language and response size instructions:
            # - If datasource is configured: inject into role_information (done in _build_azure_search_extra_body)
            # - If no datasource: enhance system message normally
            if app_settings.datasource:
                # Don't enhance messages here - will be handled in datasource role_information
                enhanced_messages = messages
                self.logger.debug("Azure OpenAI with datasource: language and response size instructions will be in role_information")
            else:
                # No datasource - enhance system message with language awareness
                enhanced_messages = self._enhance_messages_with_language_and_response_size(messages, detected_language, response_size)
                self.logger.debug(f"Azure OpenAI without datasource: enhanced system message with {detected_language} language and {response_size} response size instructions")
            
            # Build request parameters with defaults from settings
            model_args = {
                "messages": enhanced_messages,
                "temperature": kwargs.get("temperature", app_settings.azure_openai.temperature),
                "max_tokens": adjusted_max_tokens,
                "top_p": kwargs.get("top_p", app_settings.azure_openai.top_p),
                "stop": kwargs.get("stop", app_settings.azure_openai.stop_sequence),
                "stream": stream,
                "model": kwargs.get("model", app_settings.azure_openai.model),
                "user": kwargs.get("user"),
            }
            
            # Add Azure Search integration via data_sources (Azure OpenAI "On Your Data")
            extra_body = self._build_azure_search_extra_body(detected_language=detected_language, **kwargs)
            if extra_body:
                model_args["extra_body"] = extra_body
                self.logger.debug("Added Azure Search data_sources to request with multilingual support")
            
            # Add optional parameters if provided
            if "tools" in kwargs:
                model_args["tools"] = kwargs["tools"]
            # Manual extra_body parameter overrides automatic data_sources
            if "extra_body" in kwargs:
                model_args["extra_body"] = kwargs["extra_body"]
                self.logger.debug("Using manual extra_body parameter")
            
            self.logger.debug(f"Sending request to Azure OpenAI: stream={stream}, model={model_args['model']}")
            
            # Make the request with raw response to get headers
            raw_response = await self.client.chat.completions.with_raw_response.create(**model_args)
            response = raw_response.parse()
            apim_request_id = raw_response.headers.get("apim-request-id")
            
            self.logger.debug(f"Azure OpenAI request completed, APIM ID: {apim_request_id}")
            
            return response, apim_request_id
            
        except Exception as e:
            self.logger.error(f"Azure OpenAI request failed: {e}")
            raise LLMProviderRequestError(f"Azure OpenAI request failed: {e}")
    
    def format_response(
        self, 
        raw_response: Any, 
        stream: bool = True
    ) -> Union[StandardResponseAdapter, Any]:
        """
        Format Azure OpenAI response to standard format.
        
        Since Azure OpenAI responses are already in the standard OpenAI format,
        minimal transformation is needed. We primarily just wrap the response
        in our adapter for consistency.
        
        Args:
            raw_response: Tuple of (response, apim_request_id) from send_request()
            stream: Whether this is a streaming response
            
        Returns:
            For streaming: The response object (already compatible)
            For non-streaming: StandardResponseAdapter wrapping the response
        """
        response, apim_request_id = raw_response
        
        if stream:
            # For streaming responses, Azure OpenAI format is already compatible
            # with existing streaming processing code
            self.logger.debug("Returning streaming response (already compatible)")
            return response
        else:
            # For non-streaming responses, convert to our standard format
            self.logger.debug("Converting non-streaming response to standard format")
            
            # Azure OpenAI response is already in the correct format,
            # but we create a StandardResponse for consistency
            standard_response = self._convert_azure_response(response)
            return StandardResponseAdapter(standard_response)
    
    def _build_azure_search_extra_body(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Build extra_body with data_sources configuration for Azure OpenAI "On Your Data".
        
        This method constructs the data_sources payload that enables Azure OpenAI's
        native integration with Azure Search, similar to the original implementation.
        
        Args:
            **kwargs: Request parameters including documents_count, search_filters, user_permissions
            
        Returns:
            Dictionary with data_sources configuration, or None if no datasource configured
        """
        # Skip if no datasource configured
        if not app_settings.datasource:
            self.logger.debug("No datasource configured - skipping Azure Search integration")
            return None
        
        try:
            # Prepare parameters for construct_payload_configuration
            config_kwargs = {}
            
            # Pass documents_count if specified
            if kwargs.get("documents_count") is not None:
                config_kwargs["documents_count"] = kwargs["documents_count"]
            
            # Pass user permissions as fullDefinition for filtering
            if kwargs.get("user_permissions") is not None:
                config_kwargs["fullDefinition"] = kwargs["user_permissions"]
            
            # Use the datasource's construct_payload_configuration method
            # The methods expect documents_count and fullDefinition as kwargs
            datasource_config = app_settings.datasource.construct_payload_configuration(
                **config_kwargs
            )
            
            # CRITICAL: Inject both language and response size instructions into role_information for Azure OpenAI On Your Data
            detected_language = kwargs.get("detected_language", "en")
            response_size = kwargs.get("response_size", "medium")
            
            if "parameters" in datasource_config:
                # Get base role information or use default
                base_role_info = datasource_config["parameters"].get("role_information", 
                                                                   app_settings.azure_openai.system_message)
                
                # Build multilingual system message
                multilingual_role_info = get_system_message_for_language(detected_language, base_role_info)
                
                # Add response size instructions if specified
                if response_size != "medium":
                    enhanced_role_info = self._build_response_size_instructions(multilingual_role_info, response_size)
                else:
                    enhanced_role_info = multilingual_role_info
                
                datasource_config["parameters"]["role_information"] = enhanced_role_info
                self.logger.debug(f"Enhanced role_information with {detected_language} language and {response_size} instructions for Azure OpenAI")
            
            # Build the extra_body with data_sources
            extra_body = {
                "data_sources": [datasource_config]
            }
            
            self.logger.debug(f"Built Azure Search data_sources configuration with top_k={kwargs.get('documents_count', 'default')}")
            return extra_body
            
        except Exception as e:
            self.logger.error(f"Failed to build Azure Search extra_body: {e}")
            # Return None to continue without Azure Search rather than failing the request
            return None
    
    def _convert_azure_response(self, azure_response) -> StandardResponse:
        """
        Convert Azure OpenAI response to StandardResponse format.
        
        Args:
            azure_response: Raw Azure OpenAI response object
            
        Returns:
            StandardResponse object
        """
        # Convert choices
        choices = []
        for choice in azure_response.choices:
            # Convert message
            message = None
            if hasattr(choice, 'message') and choice.message:
                message = StandardMessage(
                    role=choice.message.role,
                    content=choice.message.content,
                    tool_calls=getattr(choice.message, 'tool_calls', None),
                    context=getattr(choice.message, 'context', None),
                    function_call=getattr(choice.message, 'function_call', None)
                )
            
            # Convert delta (for streaming compatibility)
            delta = None
            if hasattr(choice, 'delta') and choice.delta:
                delta = StandardMessage(
                    role=getattr(choice.delta, 'role', None),
                    content=getattr(choice.delta, 'content', None),
                    tool_calls=getattr(choice.delta, 'tool_calls', None),
                    context=getattr(choice.delta, 'context', None),
                    function_call=getattr(choice.delta, 'function_call', None)
                )
            
            standard_choice = StandardChoice(
                index=choice.index,
                message=message,
                delta=delta,
                finish_reason=choice.finish_reason
            )
            choices.append(standard_choice)
        
        # Convert usage if available
        usage = None
        if hasattr(azure_response, 'usage') and azure_response.usage:
            usage = StandardUsage(
                prompt_tokens=azure_response.usage.prompt_tokens,
                completion_tokens=azure_response.usage.completion_tokens,
                total_tokens=azure_response.usage.total_tokens
            )
        
        return StandardResponse(
            id=azure_response.id,
            object=azure_response.object,
            created=azure_response.created,
            model=azure_response.model,
            choices=choices,
            usage=usage
        )
    
    async def close(self):
        """Close the Azure OpenAI client and clean up resources."""
        await super().close()
        if self.client:
            # Azure OpenAI client doesn't require explicit closing
            self.client = None
            self.logger.debug("Azure OpenAI client cleaned up")