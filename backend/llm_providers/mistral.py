"""
Mistral AI provider implementation.

This module implements the LLM provider for Mistral AI's API.
It handles Mistral-specific authentication, message formatting, streaming responses,
and integration with Azure Search for document retrieval.

Key features:
- Mistral API message format conversion
- Azure Search integration for RAG capabilities
- Streaming response support with citations
- Multilingual support optimized for French
"""

import json
import time
import httpx
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from backend.settings import app_settings
from .base import LLMProvider, LLMProviderInitializationError, LLMProviderRequestError
from .models import StandardResponse, StandardResponseAdapter, StandardChoice, StandardMessage, StandardUsage
from .utils import AzureSearchService, build_search_context
from .language_detection import detect_language, get_system_message_for_language
from .i18n import get_documents_header, get_user_question_prefix, get_help_request


class MistralProvider(LLMProvider):
    """
    Mistral AI provider implementation.
    
    This provider handles communication with Mistral's API,
    including message format conversion, streaming responses, and
    integration with Azure Search for document retrieval.
    
    Features:
    - Supports OpenAI-compatible message format
    - Integrates with Azure Search for RAG capabilities
    - Supports streaming responses with real-time citations
    - Handles multilingual system messages
    """
    
    def __init__(self):
        """Initialize the Mistral provider."""
        super().__init__()
        self.api_key = None
        self.model = None
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.search_service = AzureSearchService()
        self.logger = logging.getLogger("MistralProvider")
        
        # State for handling citations in streaming responses
        self._current_search_citations = None
    
    async def init_client(self):
        """
        Initialize Mistral provider with API credentials.
        
        Raises:
            LLMProviderInitializationError: If API key is missing or invalid
        """
        if self.initialized:
            return
            
        # Get Mistral-specific settings
        self.api_key = app_settings.mistral.api_key
        self.model = app_settings.mistral.model
        
        if not self.api_key:
            raise LLMProviderInitializationError("MISTRAL_API_KEY environment variable is required")
        
        # Debug logging for API key (masking for security)
        masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}" if self.api_key else "None"
        self.logger.info(f"Mistral provider initialized with key: {masked_key}, model: {self.model}")
            
        self.initialized = True
    
    async def send_request(
        self, 
        messages: List[Dict[str, Any]], 
        stream: bool = True, 
        **kwargs
    ) -> Tuple[Any, Optional[str]]:
        """
        Send request to Mistral API with Azure Search integration.
        
        Args:
            messages: List of messages in OpenAI chat format
            stream: Whether to return a streaming response
            **kwargs: Additional parameters including search configuration
            
        Returns:
            Tuple of (response, apim_request_id) for compatibility with app.py
            For streaming: (AsyncGenerator, None)
            For non-streaming: (Raw Mistral API response, None)
            
        Raises:
            LLMProviderRequestError: If the request fails
        """
        await self.init_client()
        
        try:
            # Reset citation state for new request
            self._current_search_citations = None
            
            # Detect language from user's last message
            user_message = messages[-1]["content"] if messages else ""
            detected_language = detect_language(user_message)
            self.logger.debug(f"Detected language: {detected_language}")
            
            # Enhance messages with Azure Search if configured
            enhanced_messages = await self._enhance_with_search_context(messages, detected_language=detected_language, **kwargs)
            
            # Use centralized max_tokens adjustment
            response_size = kwargs.get("response_size", "medium")
            base_max_tokens = kwargs.get("max_tokens", app_settings.mistral.max_tokens)
            adjusted_max_tokens = self._adjust_max_tokens_for_response_size(base_max_tokens, response_size)
            
            # Build Mistral API request (OpenAI-compatible format)
            request_body = {
                "model": self.model,
                "messages": enhanced_messages,
                "max_tokens": adjusted_max_tokens,
                "temperature": kwargs.get("temperature", app_settings.mistral.temperature),
                "stream": stream
            }
            
            # Add optional parameters
            if kwargs.get("top_p"):
                request_body["top_p"] = kwargs["top_p"]
            if kwargs.get("stop"):
                stop_sequences = kwargs["stop"] if isinstance(kwargs["stop"], list) else [kwargs["stop"]]
                request_body["stop"] = stop_sequences
            
            self.logger.debug(f"Mistral API request: stream={stream}, messages={len(enhanced_messages)}")
            
            # Configure request headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            self.logger.debug(f"Request URL: {self.api_url}")
            self.logger.debug(f"Request body keys: {list(request_body.keys())}")
            masked_auth = f"Bearer {self.api_key[:8]}...{self.api_key[-4:]}"
            self.logger.debug(f"Authorization header: {masked_auth}")
            
            if stream:
                # Return streaming generator
                generator = self._create_streaming_generator(request_body, headers)
                return generator, None  # (response, apim_request_id)
            else:
                # Make non-streaming request
                response = await self._make_non_streaming_request(request_body, headers)
                return response, None  # (response, apim_request_id)
                
        except Exception as e:
            self.logger.error(f"Mistral request failed: {e}")
            raise LLMProviderRequestError(f"Mistral request failed: {e}")
    
    def format_response(
        self, 
        raw_response: Any, 
        stream: bool = True
    ) -> StandardResponseAdapter:
        """
        Format Mistral response to standard format.
        
        Args:
            raw_response: Raw response from send_request()
            stream: Whether this is a streaming response
            
        Returns:
            For streaming: AsyncGenerator yielding StandardResponseAdapter objects
            For non-streaming: StandardResponseAdapter object
        """
        if stream:
            # For streaming, raw_response is already an AsyncGenerator
            # that yields formatted responses
            return raw_response
        else:
            # Convert non-streaming Mistral response to standard format
            return self._format_non_streaming_response(raw_response)
    
    async def _enhance_with_search_context(
        self, 
        messages: List[Dict[str, Any]], 
        detected_language: str = "en",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Enhance Mistral messages with Azure Search context if configured, with multilingual support.
        
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
        base_system_message = getattr(app_settings.mistral, 'system_message', 
                                     "Tu es un assistant IA serviable et précis.")
        multilingual_system_message = get_system_message_for_language(detected_language, base_system_message)
        response_size = kwargs.get("response_size", "medium")
        system_message = self._build_response_size_instructions(multilingual_system_message, response_size)
        
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
                    search_context, citations = build_search_context(search_results)
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
        
        # Insert system message at the beginning or update existing one
        system_message_exists = False
        for i, msg in enumerate(enhanced_messages):
            if msg.get("role") == "system":
                enhanced_messages[i]["content"] = enhanced_system_message
                system_message_exists = True
                break
        
        if not system_message_exists:
            enhanced_messages.insert(0, {
                "role": "system",
                "content": enhanced_system_message
            })
        
        return enhanced_messages
    
    def _extract_user_query(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract the user's query from messages for search"""
        # Get the last user message as the search query
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return None
    
    async def _create_streaming_generator(
        self, 
        request_body: Dict[str, Any], 
        headers: Dict[str, str]
    ) -> AsyncGenerator[StandardResponseAdapter, None]:
        """
        Create a streaming generator that manages its own HTTP client.
        
        Args:
            request_body: Mistral API request body
            headers: HTTP headers for the request
            
        Yields:
            StandardResponseAdapter objects for each chunk
        """
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                self.api_url,
                json=request_body,
                headers=headers,
                timeout=300.0
            ) as response:
                self.logger.debug(f"Mistral streaming response status: {response.status_code}")
                response.raise_for_status()
                
                async for chunk in self._stream_mistral_response(response):
                    yield chunk
    
    async def _stream_mistral_response(self, response: httpx.Response) -> AsyncGenerator[StandardResponseAdapter, None]:
        """
        Convert Mistral streaming response to standard format.
        
        Args:
            response: HTTP response from Mistral API
            
        Yields:
            StandardResponseAdapter objects for each chunk
        """
        first_content_chunk = True
        citations_sent = False
        
        async for line in response.aiter_lines():
            line = line.strip()
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                    
                try:
                    chunk = json.loads(data)
                    self.logger.debug(f"Mistral streaming chunk: {chunk.get('choices', [{}])[0].get('delta', {})}")
                    
                    # Handle Mistral chunks (OpenAI-compatible format)
                    if chunk.get("choices") and chunk["choices"][0].get("delta"):
                        delta = chunk["choices"][0]["delta"]
                        text_content = delta.get("content")
                        
                        if text_content:
                            # Send citations before first content if available
                            if (first_content_chunk and 
                                self._current_search_citations and 
                                not citations_sent):
                                
                                citations_chunk = self._create_citations_chunk()
                                yield citations_chunk
                                citations_sent = True
                                first_content_chunk = False
                            
                            # Send content chunk
                            yield self._format_streaming_chunk(chunk)
                            
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse Mistral streaming data: {e}")
                    continue
    
    def _create_citations_chunk(self) -> StandardResponseAdapter:
        """
        Create a chunk containing only citations for the frontend.
        
        Returns:
            StandardResponseAdapter with citations in context
        """
        citations_context = {
            "citations": self._current_search_citations,
            "intent": "Azure Search results"
        }
        
        # Create a standard message with context
        message = StandardMessage(
            role=None,
            content=None,
            context=citations_context
        )
        
        choice = StandardChoice(
            index=0,
            delta=message,
            finish_reason=None
        )
        
        response = StandardResponse(
            id=f"chatcmpl-{int(time.time())}",
            object="chat.completion.chunk",
            created=int(time.time()),
            model=self.model,
            choices=[choice]
        )
        
        return StandardResponseAdapter(response)
    
    def _format_streaming_chunk(self, mistral_chunk: Dict[str, Any]) -> StandardResponseAdapter:
        """
        Format a Mistral streaming chunk to standard format.
        
        Args:
            mistral_chunk: Raw chunk from Mistral API
            
        Returns:
            StandardResponseAdapter for the chunk
        """
        # Extract text content from Mistral chunk (OpenAI-compatible)
        delta = mistral_chunk.get("choices", [{}])[0].get("delta", {})
        text_content = delta.get("content", "")
        role = delta.get("role")
        
        # Create standard message
        message = StandardMessage(
            role=role,
            content=text_content
        )
        
        choice = StandardChoice(
            index=0,
            delta=message,
            finish_reason=mistral_chunk.get("choices", [{}])[0].get("finish_reason")
        )
        
        response = StandardResponse(
            id=mistral_chunk.get("id", f"chatcmpl-{int(time.time())}"),
            object="chat.completion.chunk",
            created=int(time.time()),
            model=mistral_chunk.get("model", self.model),
            choices=[choice]
        )
        
        return StandardResponseAdapter(response)
    
    async def _make_non_streaming_request(
        self, 
        request_body: Dict[str, Any], 
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Make a non-streaming request to Mistral API.
        
        Args:
            request_body: Mistral API request body
            headers: HTTP headers for the request
            
        Returns:
            Raw Mistral API response
            
        Raises:
            LLMProviderRequestError: If the request fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=request_body,
                    headers=headers,
                    timeout=300.0
                )
                
                self.logger.debug(f"Mistral API response status: {response.status_code}")
                response.raise_for_status()
                
                if len(response.content) == 0:
                    raise LLMProviderRequestError("Mistral API returned empty response")
                
                return response.json()
                
        except httpx.HTTPError as e:
            raise LLMProviderRequestError(f"Mistral API HTTP error: {e}")
        except json.JSONDecodeError as e:
            raise LLMProviderRequestError(f"Failed to parse Mistral response: {e}")
    
    def _format_non_streaming_response(self, mistral_response: Dict[str, Any]) -> StandardResponseAdapter:
        """
        Format non-streaming Mistral response to standard format.
        
        Args:
            mistral_response: Raw Mistral API response
            
        Returns:
            StandardResponseAdapter for the response
        """
        # Mistral uses OpenAI-compatible format, so minimal conversion needed
        choices = []
        for choice_data in mistral_response.get("choices", []):
            message_data = choice_data.get("message", {})
            
            # Create standard message with content and citations
            message = StandardMessage(
                role=message_data.get("role", "assistant"),
                content=message_data.get("content", "")
            )
            
            # Add citations if available
            if self._current_search_citations:
                message.context = {
                    "citations": self._current_search_citations,
                    "intent": "Azure Search results"
                }
            
            choice = StandardChoice(
                index=choice_data.get("index", 0),
                message=message,
                finish_reason=choice_data.get("finish_reason", "stop")
            )
            choices.append(choice)
        
        # Create usage information
        usage = None
        if "usage" in mistral_response:
            usage = StandardUsage(
                prompt_tokens=mistral_response["usage"].get("prompt_tokens", 0),
                completion_tokens=mistral_response["usage"].get("completion_tokens", 0),
                total_tokens=mistral_response["usage"].get("total_tokens", 0)
            )
        
        response = StandardResponse(
            id=mistral_response.get("id", f"chatcmpl-{int(time.time())}"),
            object="chat.completion",
            created=mistral_response.get("created", int(time.time())),
            model=mistral_response.get("model", self.model),
            choices=choices,
            usage=usage
        )
        
        return StandardResponseAdapter(response)
    
    async def close(self):
        """Close the Mistral provider and clean up resources."""
        await super().close()
        if self.search_service:
            await self.search_service.close()
        self.logger.debug("Mistral provider cleaned up")