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
from .base import LLMProvider, LLMProviderInitializationError, LLMProviderRequestError, handle_provider_errors
from .models import StandardResponse, StandardResponseAdapter, StandardChoice, StandardMessage, StandardUsage
from .language_detection import get_system_message_for_language
from .i18n import (
    get_documents_header, get_user_question_prefix, get_help_request,
    get_image_too_large_message, get_image_format_unsupported_message,
    get_model_name_not_configured_message, get_model_no_image_support_message,
    get_model_vision_detected_message
)

# Import image processing (with fallback)
try:
    from backend.document_processor import DocumentProcessor, ProcessingConfig
    IMAGE_PROCESSING_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger("AzureOpenAIProvider")
    logger.warning(f"Advanced image processing not available: {e}")
    DocumentProcessor = None
    ProcessingConfig = None
    IMAGE_PROCESSING_AVAILABLE = False


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
    
    @handle_provider_errors("AZURE_OPENAI")
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
        
        # Detect language from user's last message using LLM for accuracy
        # Skip language detection if this is an internal call to avoid recursion
        if kwargs.get("_skip_language_detection", False):
            detected_language = "en"  # Default for internal calls
            self.logger.debug("Skipping language detection for internal call")
        else:
            user_message = messages[-1]["content"] if messages else ""
            detected_language = await self.detect_language_with_llm(user_message)
            self.logger.debug(f"Detected language: {detected_language}")
        
        # Get max_tokens based on response size
        response_size = kwargs.get("response_size", "medium")
        max_tokens = self._get_max_tokens_for_response_size("azure_openai", response_size)
        
        # For Azure OpenAI, we handle both language and response size instructions:
        # - If datasource is configured: inject into role_information (done in _build_azure_search_extra_body)
        # - If no datasource: enhance system message normally
        if app_settings.datasource:
            # Don't enhance messages here - will be handled in datasource role_information
            enhanced_messages = messages
            self.logger.debug("Azure OpenAI with datasource: language and response size instructions will be in role_information")
            
            # Still process images even with datasource
            enhanced_messages = self._process_images_for_azure_openai(enhanced_messages)
        else:
            # No datasource - enhance system message with language awareness
            enhanced_messages = self._enhance_messages_with_language_and_response_size(messages, detected_language, response_size)
            self.logger.debug(f"Azure OpenAI without datasource: enhanced system message with {detected_language} language and {response_size} response size instructions")
            
            # Process images for optimal Azure OpenAI performance  
            enhanced_messages = self._process_images_for_azure_openai(enhanced_messages)
        
        # Build request parameters with defaults from settings
        model_args = {
            "messages": enhanced_messages,
            "temperature": kwargs.get("temperature", app_settings.azure_openai.temperature),
            "max_tokens": max_tokens,
            "top_p": kwargs.get("top_p", app_settings.azure_openai.top_p),
            "stop": kwargs.get("stop", app_settings.azure_openai.stop_sequence),
            "stream": stream,
            "model": kwargs.get("model", app_settings.azure_openai.model),
            "user": kwargs.get("user"),
        }
        
        # Add Azure Search integration via data_sources (Azure OpenAI "On Your Data")
        # Remove response_size from kwargs to avoid conflict with explicit parameter
        kwargs_clean = {k: v for k, v in kwargs.items() if k != 'response_size'}
        extra_body = self._build_azure_search_extra_body(detected_language=detected_language, response_size=response_size, **kwargs_clean)
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
        self.logger.debug(f"Number of messages: {len(model_args.get('messages', []))}")
        
        # Check if model supports images and validate multimodal content
        vision_models = ["gpt-4-vision-preview", "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-turbo-vision"]
        has_images = False
        
        for i, msg in enumerate(model_args.get("messages", [])):
            if isinstance(msg.get("content"), list):
                self.logger.debug(f"Message {i} has multimodal content with {len(msg['content'])} parts")
                for j, part in enumerate(msg["content"]):
                    if part.get("type") == "image_url":
                        has_images = True
                        image_url = part.get("image_url", {}).get("url", "")
                        if image_url.startswith("data:"):
                            # Extract format info without logging the actual data
                            header = image_url.split(",")[0]
                            data_size = len(image_url.split(",", 1)[1]) if "," in image_url else 0
                            self.logger.debug(f"  Part {j}: Image {header}, data size: {data_size} chars")
                            
                            # Check image size (Azure OpenAI limit is around 20MB for base64)
                            if data_size > 20000000:  # 20MB
                                error_msg = get_image_too_large_message(detected_language, data_size)
                                self.logger.error(error_msg)
                                raise LLMProviderRequestError(error_msg)
                            
                            # Check supported formats
                            supported_formats = ["image/jpeg", "image/png", "image/gif", "image/webp"]
                            format_from_header = header.replace("data:", "").split(";")[0]
                            if format_from_header not in supported_formats:
                                error_msg = get_image_format_unsupported_message(detected_language, format_from_header, supported_formats)
                                self.logger.error(error_msg)
                                raise LLMProviderRequestError(error_msg)
        
        # Validate model supports images if images are present
        if has_images:
            # Use the actual model name from settings if available
            actual_model_name = app_settings.azure_openai.model_name or model_args['model']
            deployment_name = model_args['model']
            
            self.logger.info(f"Deployment: '{deployment_name}', Actual model: '{actual_model_name}'")
            
            # Check if the actual model supports vision
            current_model = actual_model_name.lower()
            
            # If AZURE_OPENAI_MODEL_NAME is not set (deployment name == model name), allow bypass
            if actual_model_name == deployment_name:
                warning_msg = get_model_name_not_configured_message(detected_language, deployment_name)
                self.logger.warning(warning_msg)
            elif not any(vision_model.lower() in current_model for vision_model in vision_models):
                error_msg = get_model_no_image_support_message(detected_language, actual_model_name)
                self.logger.error(error_msg)
                raise LLMProviderRequestError(error_msg)
            else:
                info_msg = get_model_vision_detected_message(detected_language, actual_model_name)
                self.logger.info(info_msg)
        
        # Make the request with raw response to get headers
        raw_response = await self.client.chat.completions.with_raw_response.create(**model_args)
        response = raw_response.parse()
        apim_request_id = raw_response.headers.get("apim-request-id")
        
        self.logger.debug(f"Azure OpenAI request completed, APIM ID: {apim_request_id}")
        
        return response, apim_request_id
        
        # Error handling is now done by the @handle_provider_errors decorator
    
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
    
    def _build_azure_search_extra_body(self, detected_language: str = "en", response_size: str = "medium", **kwargs) -> Optional[Dict[str, Any]]:
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
            # detected_language and response_size are now passed as explicit parameters
            
            if "parameters" in datasource_config:
                # Get base role information or use default
                base_role_info = datasource_config["parameters"].get("role_information", 
                                                                   app_settings.azure_openai.system_message)
                
                # Build multilingual system message with response size instructions
                multilingual_role_info = get_system_message_for_language(detected_language, base_role_info, response_size)
                
                # The response size instructions are already included in multilingual_role_info
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
    
    def _process_images_for_azure_openai(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process images in messages for optimal Azure OpenAI performance.
        
        Args:
            messages: List of messages that may contain images
            
        Returns:
            List of messages with optimized images
        """
        if not IMAGE_PROCESSING_AVAILABLE:
            self.logger.debug("Advanced image processing not available - using original images")
            return messages
        
        processed_messages = []
        
        for message in messages:
            if not isinstance(message.get("content"), list):
                # No multimodal content, add as-is
                processed_messages.append(message)
                continue
            
            # Process multimodal content
            processed_content = []
            for part in message["content"]:
                if part.get("type") == "image_url":
                    # Process image for Azure OpenAI
                    image_url = part.get("image_url", {}).get("url", "")
                    if image_url.startswith("data:"):
                        try:
                            # Extract base64 data
                            header, raw_data = image_url.split(",", 1)
                            
                            # Detect content type from context
                            content_type = self._detect_image_content_type_from_azure_context(message["content"])
                            
                            # Decode and process with Azure OpenAI optimizations
                            import base64
                            image_bytes = base64.b64decode(raw_data)
                            
                            # Process image for Azure OpenAI
                            result = DocumentProcessor.process_image_for_llm(
                                image_bytes, 
                                provider="AZURE_OPENAI",
                                content_type=content_type
                            )
                            
                            if result["success"]:
                                processing_result = result["processing_result"]
                                self.logger.info(f"Azure OpenAI: Image optimized - "
                                               f"format: {processing_result.original_format} → {processing_result.final_format}, "
                                               f"size: {processing_result.original_size} → {processing_result.final_size}, "
                                               f"file_size: {processing_result.file_size_mb:.2f}MB")
                                
                                # Create optimized data URL
                                optimized_data_url = f"data:{processing_result.media_type};base64,{processing_result.data}"
                                processed_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": optimized_data_url}
                                })
                            else:
                                # Fallback to original on processing error
                                self.logger.warning(f"Azure OpenAI image optimization failed: {result['error']}")
                                processed_content.append(part)
                                
                        except Exception as e:
                            self.logger.warning(f"Azure OpenAI image processing error: {e}")
                            processed_content.append(part)
                    else:
                        # Non-data URL, add as-is
                        processed_content.append(part)
                else:
                    # Non-image content, add as-is
                    processed_content.append(part)
            
            # Create message with processed content
            processed_message = message.copy()
            processed_message["content"] = processed_content
            processed_messages.append(processed_message)
        
        return processed_messages
    
    def _detect_image_content_type_from_azure_context(self, content_list: List[Dict[str, Any]]) -> str:
        """
        Detect likely image content type from Azure OpenAI message context.
        
        Args:
            content_list: List of content parts including text and images
            
        Returns:
            str: Detected content type for image optimization
        """
        # Extract all text from the content
        text_parts = []
        for part in content_list:
            if part.get("type") == "text":
                text_parts.append(part.get("text", "").lower())
        
        combined_text = " ".join(text_parts)
        
        # Analyze text for content type hints (similar to Claude but adapted for Azure OpenAI)
        if any(keyword in combined_text for keyword in ["screenshot", "écran", "capture", "interface"]):
            return "screenshot"
        elif any(keyword in combined_text for keyword in ["diagramme", "schema", "graphique", "diagram", "chart", "flowchart"]):
            return "diagram"
        elif any(keyword in combined_text for keyword in ["texte", "text", "document", "page", "lecture", "read"]):
            return "text"
        elif any(keyword in combined_text for keyword in ["logo", "icône", "icon", "symbole"]):
            return "logo"
        elif any(keyword in combined_text for keyword in ["photo", "image", "picture", "photographie"]):
            return "photo"
        
        # Default to general if no specific context detected
        return "general"
    
    async def close(self):
        """Close the Azure OpenAI client and clean up resources."""
        await super().close()
        if self.client:
            # Azure OpenAI client doesn't require explicit closing
            self.client = None
            self.logger.debug("Azure OpenAI client cleaned up")