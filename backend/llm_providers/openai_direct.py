"""
OpenAI Direct provider implementation.

This module implements the LLM provider for direct OpenAI API access.
It provides direct access to OpenAI's API without going through Azure,
enabling access to latest models and features.

Key features:
- Direct OpenAI API authentication
- Support for latest OpenAI models (GPT-4o, GPT-3.5-turbo, etc.)
- Full compatibility with OpenAI parameters
- Azure Search integration for RAG (Retrieval Augmented Generation)
- Citation display with proper streaming support
- Configurable via environment variables

Azure Search Integration:
- Automatically searches configured Azure Search index for relevant documents
- Injects search context into system message for accurate responses
- Generates proper citations for frontend display
- Supports semantic and vector search

Configuration:
Set AZURE_SEARCH_CONTENT_COLUMNS=chunk in .env to ensure proper content extraction
from vectorial indexes where text content is stored in the 'chunk' field.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from openai import AsyncOpenAI

from backend.settings import app_settings
from .base import LLMProvider, LLMProviderInitializationError, LLMProviderRequestError
from .models import StandardResponse, StandardResponseAdapter, StandardChoice, StandardMessage, StandardUsage
from .utils import AzureSearchService, build_search_context
from .language_detection import get_system_message_for_language
from .i18n import get_documents_header, get_default_system_message, get_emergency_keywords


class OpenAIDirectProvider(LLMProvider):
    """
    OpenAI Direct provider implementation.
    
    This provider handles direct communication with OpenAI's API.
    Since OpenAI responses are already in the standard OpenAI format,
    minimal transformation is needed.
    
    Features:
    - Direct API key authentication to OpenAI
    - Support for latest OpenAI models (GPT-4, GPT-3.5-turbo, etc.)
    - Full parameter support (temperature, max_tokens, tools, etc.)
    - Maintains compatibility with Azure OpenAI configurations
    """
    
    def __init__(self):
        """Initialize the OpenAI Direct provider."""
        super().__init__()
        self.client = None
        self.search_service = AzureSearchService()
        self.logger = logging.getLogger("OpenAIDirectProvider")
    
    async def init_client(self):
        """
        Initialize OpenAI client with API key authentication.
        
        Uses the OpenAI API key from settings to authenticate
        directly with OpenAI's services.
        
        Raises:
            LLMProviderInitializationError: If initialization fails
        """
        if self.initialized:
            return
            
        try:
            # Check if we have OpenAI settings
            if not hasattr(app_settings, 'openai_direct') or not app_settings.openai_direct.api_key:
                raise ValueError("OpenAI Direct API key not configured")
            
            # Initialize the OpenAI client
            base_url = getattr(app_settings.openai_direct, 'base_url', None)
            
            # Only use base_url if it's not empty
            client_kwargs = {
                "api_key": app_settings.openai_direct.api_key
            }
            if base_url and base_url.strip():
                client_kwargs["base_url"] = base_url.strip()
            
            self.client = AsyncOpenAI(**client_kwargs)
            
            self.initialized = True
            self.logger.info("OpenAI Direct client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI Direct client: {e}")
            raise LLMProviderInitializationError(f"OpenAI Direct initialization failed: {e}")
    
    async def send_request(
        self, 
        messages: List[Dict[str, Any]], 
        stream: bool = True, 
        **kwargs
    ) -> Tuple[Any, Optional[str]]:
        """
        Send request to OpenAI Direct API.
        
        Args:
            messages: List of messages in OpenAI chat format
            stream: Whether to return a streaming response
            **kwargs: Additional OpenAI parameters
            
        Returns:
            Tuple of (response, request_id)
            
        Raises:
            LLMProviderRequestError: If the request fails
        """
        await self.init_client()
        
        try:
            # Detect language from user's last message using LLM for accuracy
            # Skip language detection if this is an internal call to avoid recursion
            if kwargs.get("_skip_language_detection", False):
                detected_language = "en"  # Default for internal calls
                self.logger.debug("Skipping language detection for internal call")
            else:
                user_message = messages[-1]["content"] if messages else ""
                detected_language = await self.detect_language_with_llm(user_message)
                self.logger.debug(f"Detected language: {detected_language}")
            
            # Convert OpenAI messages and enhance with Azure Search if configured
            enhanced_messages = await self._enhance_with_search_context(messages, detected_language=detected_language, **kwargs)
            
            # Get max_tokens based on response size
            response_size = kwargs.get("response_size", "medium")
            max_tokens = self._get_max_tokens_for_response_size("openai_direct", response_size)
            
            # Build request parameters with defaults from settings
            model_args = {
                "messages": enhanced_messages,
                "temperature": kwargs.get("temperature", getattr(app_settings.openai_direct, 'temperature', 0.7)),
                "max_tokens": max_tokens,
                "top_p": kwargs.get("top_p", getattr(app_settings.openai_direct, 'top_p', 1.0)),
                "stop": kwargs.get("stop", getattr(app_settings.openai_direct, 'stop_sequence', None)),
                "stream": stream,
                "model": kwargs.get("model", getattr(app_settings.openai_direct, 'model', 'gpt-3.5-turbo')),
                "user": kwargs.get("user"),
            }
            
            # Add optional parameters if provided
            if "tools" in kwargs:
                model_args["tools"] = kwargs["tools"]
            if "tool_choice" in kwargs:
                model_args["tool_choice"] = kwargs["tool_choice"]
            if "frequency_penalty" in kwargs:
                model_args["frequency_penalty"] = kwargs["frequency_penalty"]
            if "presence_penalty" in kwargs:
                model_args["presence_penalty"] = kwargs["presence_penalty"]
            
            # Remove None values to avoid API errors
            model_args = {k: v for k, v in model_args.items() if v is not None}
            
            self.logger.debug(f"Sending request to OpenAI Direct: stream={stream}, model={model_args['model']}")
            
            # Make the request
            response = await self.client.chat.completions.create(**model_args)
            
            # Add citations to the response if we have search results
            if hasattr(self, '_current_search_citations') and self._current_search_citations:
                # For streaming responses, we need to inject citations
                if stream:
                    response = self._inject_citations_in_stream(response)
                else:
                    # For non-streaming, add citations to the message
                    if hasattr(response, 'choices') and response.choices:
                        choice = response.choices[0]
                        if hasattr(choice, 'message'):
                            # Add citations context to the message
                            if not hasattr(choice.message, 'context'):
                                choice.message.context = {}
                            choice.message.context['citations'] = self._current_search_citations
                            choice.message.context['intent'] = 'Azure Search results'
            
            # OpenAI Direct doesn't provide request IDs in the same way as Azure
            # We'll generate a simple identifier for consistency
            request_id = f"openai-direct-{response.id}" if hasattr(response, 'id') else None
            
            self.logger.debug(f"OpenAI Direct request completed, ID: {request_id}")
            
            return response, request_id
            
        except Exception as e:
            self.logger.error(f"OpenAI Direct request failed: {e}")
            raise LLMProviderRequestError(f"OpenAI Direct request failed: {e}")
    
    def format_response(
        self, 
        raw_response: Any, 
        stream: bool = True
    ) -> Union[StandardResponseAdapter, Any]:
        """
        Format OpenAI Direct response to standard format.
        
        Since OpenAI Direct responses are already in the standard OpenAI format,
        minimal transformation is needed. We primarily just wrap the response
        for consistency.
        
        Args:
            raw_response: Tuple of (response, request_id) from send_request()
            stream: Whether this is a streaming response
            
        Returns:
            For streaming: The response object (already compatible)
            For non-streaming: StandardResponseAdapter wrapping the response
        """
        response, request_id = raw_response
        
        if stream:
            # For streaming responses, OpenAI format is already compatible
            # with existing streaming processing code
            self.logger.debug("Returning streaming response (already compatible)")
            return response
        else:
            # For non-streaming responses, convert to our standard format
            self.logger.debug("Converting non-streaming response to standard format")
            
            # OpenAI response is already in the correct format,
            # but we create a StandardResponse for consistency
            standard_response = self._convert_openai_response(response)
            return StandardResponseAdapter(standard_response)
    
    def _convert_openai_response(self, openai_response) -> StandardResponse:
        """
        Convert OpenAI Direct response to StandardResponse format.
        
        Args:
            openai_response: Raw OpenAI response object
            
        Returns:
            StandardResponse object
        """
        # Convert choices
        choices = []
        for choice in openai_response.choices:
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
        if hasattr(openai_response, 'usage') and openai_response.usage:
            usage = StandardUsage(
                prompt_tokens=openai_response.usage.prompt_tokens,
                completion_tokens=openai_response.usage.completion_tokens,
                total_tokens=openai_response.usage.total_tokens
            )
        
        return StandardResponse(
            id=openai_response.id,
            object=openai_response.object,
            created=openai_response.created,
            model=openai_response.model,
            choices=choices,
            usage=usage
        )
    
    async def _enhance_with_search_context(
        self, 
        messages: List[Dict[str, Any]], 
        detected_language: str = "en",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Enhance OpenAI messages with Azure Search context if configured, with multilingual support.
        
        Args:
            messages: Messages in OpenAI format
            detected_language: Detected language code for response localization
            **kwargs: Additional parameters including search configuration
            
        Returns:
            Enhanced messages with search context and multilingual system message
        """
        # Start with a copy of messages
        enhanced_messages = messages.copy()
        
        # Add system message with language awareness and response size preference using centralized method
        base_system_message = getattr(app_settings.openai_direct, 'system_message', 
                                     get_default_system_message(detected_language))
        response_size = kwargs.get("response_size", "medium")
        system_message = get_system_message_for_language(detected_language, base_system_message, response_size)
        
        # Check if we need to perform Azure Search
        search_context = ""
        citations = []
        
        if app_settings.datasource and enhanced_messages:
            # Extract user query for search
            user_query = self._extract_user_query(enhanced_messages)
            if user_query:
                self.logger.debug(f"Performing Azure Search for query: '{user_query}'")
                
                # Perform search
                search_results = await self.search_service.search_documents(
                    query=user_query,
                    top_k=kwargs.get("documents_count"),
                    filters=kwargs.get("search_filters"),
                    user_permissions=kwargs.get("user_permissions")
                )
                
                self.logger.debug(f"Azure Search returned {len(search_results) if search_results else 0} results")
                
                if search_results:
                    # Build context and citations
                    search_context, citations = build_search_context(search_results, app_settings.base_settings.citation_content_max_length)
                    self._current_search_citations = citations
        
        # Build enhanced system message with localization
        if search_context:
            # Get localized documents header
            documents_header = get_documents_header(detected_language)
            
            enhanced_system_message = f"""{system_message}

{documents_header}
{search_context}"""
        else:
            enhanced_system_message = system_message
        
        # Insert system message at the beginning
        enhanced_messages.insert(0, {
            "role": "system",
            "content": enhanced_system_message
        })
        
        return enhanced_messages
    
    def _extract_user_query(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract the user's query from messages for search, handling multimodal content"""
        # Get the last user message as the search query
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                
                # Handle multimodal content (text + images)
                if isinstance(content, list):
                    text_parts = []
                    has_image = False
                    
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                            elif part.get("type") == "image_url":
                                has_image = True
                    
                    base_query = " ".join(text_parts)
                    
                    # Enrich query with image context if needed (same logic as Claude)
                    if has_image and base_query:
                        # Check if this is a help/procedure question
                        is_help_question = any(word in base_query.lower() for word in 
                                              ["que faire", "comment", "procédure", "aide", "urgence", "help", "how"])
                        
                        if is_help_question:
                            emergency_keywords = get_emergency_keywords(detected_language)
                            return f"{base_query} {emergency_keywords}"
                    
                    return base_query
                
                return content
        return None
    
    def _inject_citations_in_stream(self, stream_response):
        """
        Inject citations into OpenAI streaming response.
        
        This creates a wrapper around the OpenAI stream that first yields
        a citation chunk, then yields the actual content chunks.
        
        The citation chunk is structured to be compatible with the existing
        format_stream_response function in backend/utils.py, using proper
        class-based mock objects instead of SimpleNamespace to avoid timing issues.
        """
        import time
        
        async def citation_aware_stream():
            first_chunk = True
            async for chunk in stream_response:
                # Before the first content chunk, inject citations
                if first_chunk and hasattr(self, '_current_search_citations') and self._current_search_citations:
                    # Create a citation chunk similar to Claude's format
                    citation_chunk = {
                        'id': f'openai-direct-citations-{int(time.time())}',
                        'object': 'chat.completion.chunk',
                        'created': int(time.time()),
                        'model': getattr(app_settings.openai_direct, 'model', 'gpt-3.5-turbo'),
                        'choices': [{
                            'index': 0,
                            'delta': {
                                'role': 'assistant',
                                'context': {
                                    'citations': self._current_search_citations,
                                    'intent': 'Azure Search results'
                                }
                            },
                            'finish_reason': None
                        }]
                    }
                    
                    # Create a proper mock response object using the same pattern as OpenAI
                    class MockCitationResponse:
                        def __init__(self, chunk_data):
                            self.id = chunk_data['id']
                            self.object = chunk_data['object'] 
                            self.created = chunk_data['created']
                            self.model = chunk_data['model']
                            self.choices = [MockChoice(chunk_data['choices'][0])]
                    
                    class MockChoice:
                        def __init__(self, choice_data):
                            self.index = choice_data['index']
                            self.finish_reason = choice_data['finish_reason']
                            self.delta = MockDelta(choice_data['delta'])
                    
                    class MockDelta:
                        def __init__(self, delta_data):
                            self.role = delta_data['role']
                            self.context = delta_data['context']
                    
                    citation_response = MockCitationResponse(citation_chunk)
                    
                    yield citation_response
                    first_chunk = False
                
                # Yield the actual content chunk
                yield chunk
        
        return citation_aware_stream()
    
    async def close(self):
        """Close the OpenAI Direct client and clean up resources."""
        await super().close()
        if self.client:
            # OpenAI client cleanup
            await self.client.close()
            self.client = None
            self.logger.debug("OpenAI Direct client cleaned up")
        
        # Close search service
        if self.search_service:
            await self.search_service.close()