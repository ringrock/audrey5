"""
Claude AI provider implementation.

This module implements the LLM provider for Anthropic's Claude AI service.
It handles Claude-specific message formatting, streaming responses, and
integration with Azure Search for document retrieval.

Key features:
- Claude API message format conversion
- Azure Search integration for RAG capabilities
- Streaming response support with citations
- French language optimized system messages
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


class ClaudeProvider(LLMProvider):
    """
    Claude AI provider implementation.
    
    This provider handles communication with Anthropic's Claude API,
    including message format conversion, streaming responses, and
    integration with Azure Search for document retrieval.
    
    Features:
    - Converts OpenAI message format to Claude format
    - Integrates with Azure Search for RAG capabilities
    - Supports streaming responses with real-time citations
    - Handles French language system messages
    """
    
    def __init__(self):
        """Initialize the Claude provider."""
        super().__init__()
        self.api_key = None
        self.model = None
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.search_service = AzureSearchService()
        self.logger = logging.getLogger("ClaudeProvider")
        
        # State for handling citations in streaming responses
        self._current_search_citations = None
    
    async def init_client(self):
        """
        Initialize Claude provider with API credentials.
        
        Raises:
            LLMProviderInitializationError: If API key is missing or invalid
        """
        if self.initialized:
            return
            
        # Get Claude-specific settings
        self.api_key = app_settings.claude.api_key
        self.model = app_settings.claude.model
        
        if not self.api_key:
            raise LLMProviderInitializationError("CLAUDE_API_KEY environment variable is required")
            
        self.initialized = True
        self.logger.info("Claude provider initialized successfully")
    
    async def send_request(
        self, 
        messages: List[Dict[str, Any]], 
        stream: bool = True, 
        **kwargs
    ) -> Tuple[Any, Optional[str]]:
        """
        Send request to Claude API with Azure Search integration.
        
        Args:
            messages: List of messages in OpenAI chat format
            stream: Whether to return a streaming response
            **kwargs: Additional parameters including search configuration
            
        Returns:
            Tuple of (response, apim_request_id) for compatibility with app.py
            For streaming: (AsyncGenerator, None)
            For non-streaming: (Raw Claude API response, None)
            
        Raises:
            LLMProviderRequestError: If the request fails
        """
        await self.init_client()
        
        try:
            # Reset citation state for new request
            self._current_search_citations = None
            
            # Convert messages from OpenAI to Claude format
            claude_messages = self._convert_messages_to_claude_format(messages)
            
            # Perform Azure Search if configured and inject context
            claude_messages = await self._enhance_with_search_context(claude_messages, **kwargs)
            
            # Use centralized max_tokens adjustment
            response_size = kwargs.get("response_size", "medium")
            base_max_tokens = kwargs.get("max_tokens", app_settings.claude.max_tokens)
            adjusted_max_tokens = self._adjust_max_tokens_for_response_size(base_max_tokens, response_size)
            
            # Build Claude API request
            request_body = {
                "model": self.model,
                "messages": claude_messages,
                "max_tokens": adjusted_max_tokens,
                "temperature": kwargs.get("temperature", app_settings.claude.temperature),
                "stream": stream
            }
            
            # Add optional parameters
            if kwargs.get("top_p"):
                request_body["top_p"] = kwargs["top_p"]
            if kwargs.get("stop"):
                stop_sequences = kwargs["stop"] if isinstance(kwargs["stop"], list) else [kwargs["stop"]]
                request_body["stop_sequences"] = stop_sequences
            
            self.logger.debug(f"Claude API request: stream={stream}, messages={len(claude_messages)}")
            
            # Configure request headers
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            if stream:
                # Return streaming generator
                generator = self._create_streaming_generator(request_body, headers)
                return generator, None  # (response, apim_request_id)
            else:
                # Make non-streaming request
                response = await self._make_non_streaming_request(request_body, headers)
                return response, None  # (response, apim_request_id)
                
        except Exception as e:
            self.logger.error(f"Claude request failed: {e}")
            raise LLMProviderRequestError(f"Claude request failed: {e}")
    
    def format_response(
        self, 
        raw_response: Any, 
        stream: bool = True
    ) -> StandardResponseAdapter:
        """
        Format Claude response to standard format.
        
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
            # Convert non-streaming Claude response to standard format
            return self._format_non_streaming_response(raw_response)
    
    async def _enhance_with_search_context(
        self, 
        claude_messages: List[Dict[str, Any]], 
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Enhance Claude messages with Azure Search context if configured.
        
        Args:
            claude_messages: Messages in Claude format
            **kwargs: Additional parameters including search configuration
            
        Returns:
            Enhanced messages with search context injected
        """
        # Skip search if no datasource configured, but still apply response size
        if not app_settings.datasource:
            self.logger.warning("No Azure Search datasource configured - Claude will respond without search context")
            return self._apply_response_size_only(claude_messages, kwargs.get("response_size", "medium"))
        
        if not claude_messages:
            self.logger.warning("No messages to enhance with search context")
            return claude_messages
        
        # Extract user query for search
        user_query = self._extract_user_query(claude_messages)
        if not user_query:
            self.logger.warning("No user query found for search")
            return claude_messages
        
        self.logger.debug(f"Performing Azure Search for query: '{user_query}'")
        
        # Perform search
        search_results = await self.search_service.search_documents(
            query=user_query,
            top_k=kwargs.get("documents_count"),
            filters=kwargs.get("search_filters"),
            user_permissions=kwargs.get("user_permissions")
        )
        
        self.logger.debug(f"Azure Search returned {len(search_results) if search_results else 0} results")
        
        if not search_results:
            self.logger.warning("No search results found - Claude will respond without context")
            return claude_messages
        
        # Inject search context into messages
        response_size = kwargs.get("response_size", "medium")
        return self._inject_search_context(claude_messages, search_results, response_size)
    
    def _convert_messages_to_claude_format(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert OpenAI message format to Claude format.
        
        Claude has different requirements:
        - System messages are handled differently
        - Only user/assistant roles are supported
        - Function/tool messages are not directly supported
        
        Args:
            messages: Messages in OpenAI format
            
        Returns:
            Messages converted to Claude format
        """
        claude_messages = []
        system_message = None
        
        for msg in messages:
            if msg["role"] == "system":
                # Claude handles system messages separately
                system_message = msg["content"]
            elif msg["role"] in ["user", "assistant"]:
                claude_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            # Skip function/tool messages as Claude handles them differently
            
        # If there's a system message, prepend it to the first user message
        if system_message and claude_messages and claude_messages[0]["role"] == "user":
            claude_messages[0]["content"] = f"{system_message}\n\n{claude_messages[0]['content']}"
        
        return claude_messages
    
    def _apply_response_size_only(
        self, 
        claude_messages: List[Dict[str, Any]], 
        response_size: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Apply response size preference to messages without search context.
        
        Args:
            claude_messages: Messages in Claude format
            response_size: Response size preference (veryShort, medium, comprehensive)
            
        Returns:
            Enhanced messages with response size instructions
        """
        if response_size == "medium":
            # No modification needed for default size
            return claude_messages
        
        # Apply response size instructions for non-medium sizes
        updated_messages = claude_messages.copy()
        base_system_message = app_settings.claude.system_message
        enhanced_system_message = self._build_response_size_instructions(base_system_message, response_size)
        
        # Update the first user message to include the enhanced system message
        if updated_messages and updated_messages[0].get("role") == "user":
            original_content = updated_messages[0]['content']
            enhanced_content = f"{enhanced_system_message}\n\nQuestion de l'utilisateur : {original_content}"
            updated_messages[0]["content"] = enhanced_content
        else:
            # If no user message, prepend as a system instruction
            enhanced_content = f"{enhanced_system_message}\n\nVeuillez m'aider avec la question suivante."
            updated_messages.insert(0, {
                "role": "user",
                "content": enhanced_content
            })
        
        return updated_messages
    
    def _extract_user_query(self, claude_messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract the user's query from Claude messages for search.
        
        Args:
            claude_messages: Messages in Claude format
            
        Returns:
            The last user message content for searching
        """
        # Get the last user message as the search query
        for msg in reversed(claude_messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return None
    
    def _inject_search_context(
        self, 
        claude_messages: List[Dict[str, Any]], 
        search_results: List[Dict[str, Any]],
        response_size: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Inject Azure Search results into Claude message context.
        
        Args:
            claude_messages: Messages in Claude format
            search_results: Documents from Azure Search
            
        Returns:
            Enhanced messages with search context
        """
        # Build context and citations from search results
        search_context, citations = build_search_context(search_results)
        
        if not search_context:
            self.logger.warning("No search context built from results")
            return claude_messages
        
        # Store citations for use in response formatting
        self._current_search_citations = citations
        
        # Build enhanced system message with search context and response size preference  
        base_system_message = app_settings.claude.system_message
        system_with_size = self._build_response_size_instructions(base_system_message, response_size)
        
        enhanced_system_message = f"""{system_with_size}

Documents disponibles :
{search_context}"""
        
        # Update the first user message to include the enhanced system message
        updated_messages = claude_messages.copy()
        if updated_messages and updated_messages[0].get("role") == "user":
            original_content = updated_messages[0]['content']
            enhanced_content = f"{enhanced_system_message}\n\nQuestion de l'utilisateur : {original_content}"
            updated_messages[0]["content"] = enhanced_content
        else:
            # If no user message, prepend as a system instruction
            enhanced_content = f"{enhanced_system_message}\n\nVeuillez m'aider avec la question suivante."
            updated_messages.insert(0, {
                "role": "user",
                "content": enhanced_content
            })
        
        self.logger.debug(f"Injected search context with {len(citations)} citations")
        return updated_messages
    
    async def _create_streaming_generator(
        self, 
        request_body: Dict[str, Any], 
        headers: Dict[str, str]
    ) -> AsyncGenerator[StandardResponseAdapter, None]:
        """
        Create a streaming generator that manages its own HTTP client.
        
        Args:
            request_body: Claude API request body
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
                self.logger.debug(f"Claude streaming response status: {response.status_code}")
                response.raise_for_status()
                
                async for chunk in self._stream_claude_response(response):
                    yield chunk
    
    async def _stream_claude_response(self, response: httpx.Response) -> AsyncGenerator[StandardResponseAdapter, None]:
        """
        Convert Claude streaming response to standard format.
        
        Args:
            response: HTTP response from Claude API
            
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
                    self.logger.debug(f"Claude streaming chunk type: {chunk.get('type')}")
                    
                    # Handle different chunk types
                    if chunk.get("type") == "content_block_delta":
                        # This contains the actual text content
                        text_content = chunk.get("delta", {}).get("text")
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
                            
                    elif chunk.get("type") in ["content_block_start", "message_delta", "message_stop"]:
                        # Handle other chunk types as needed
                        self.logger.debug(f"Handling chunk type: {chunk.get('type')}")
                        
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse Claude streaming data: {e}")
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
    
    def _format_streaming_chunk(self, claude_chunk: Dict[str, Any]) -> StandardResponseAdapter:
        """
        Format a Claude streaming chunk to standard format.
        
        Args:
            claude_chunk: Raw chunk from Claude API
            
        Returns:
            StandardResponseAdapter for the chunk
        """
        # Extract text content from Claude chunk
        text_content = claude_chunk.get("delta", {}).get("text", "")
        
        # Create standard message
        message = StandardMessage(
            role="assistant",
            content=text_content
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
    
    async def _make_non_streaming_request(
        self, 
        request_body: Dict[str, Any], 
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Make a non-streaming request to Claude API.
        
        Args:
            request_body: Claude API request body
            headers: HTTP headers for the request
            
        Returns:
            Raw Claude API response
            
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
                
                self.logger.debug(f"Claude API response status: {response.status_code}")
                response.raise_for_status()
                
                if len(response.content) == 0:
                    raise LLMProviderRequestError("Claude API returned empty response")
                
                return response.json()
                
        except httpx.HTTPError as e:
            raise LLMProviderRequestError(f"Claude API HTTP error: {e}")
        except json.JSONDecodeError as e:
            raise LLMProviderRequestError(f"Failed to parse Claude response: {e}")
    
    def _format_non_streaming_response(self, claude_response: Dict[str, Any]) -> StandardResponseAdapter:
        """
        Format non-streaming Claude response to standard format.
        
        Args:
            claude_response: Raw Claude API response
            
        Returns:
            StandardResponseAdapter for the response
        """
        # Extract text content from Claude response
        content = ""
        if isinstance(claude_response.get("content"), list):
            for item in claude_response["content"]:
                if item.get("type") == "text":
                    content += item.get("text", "")
        else:
            content = str(claude_response.get("content", ""))
        
        # Create standard message with content and citations
        message = StandardMessage(
            role="assistant",
            content=content
        )
        
        # Add citations if available
        if self._current_search_citations:
            message.context = {
                "citations": self._current_search_citations,
                "intent": "Azure Search results"
            }
        
        choice = StandardChoice(
            index=0,
            message=message,
            finish_reason=claude_response.get("stop_reason", "stop")
        )
        
        # Create usage information
        usage = None
        if "usage" in claude_response:
            usage = StandardUsage(
                prompt_tokens=claude_response["usage"].get("input_tokens", 0),
                completion_tokens=claude_response["usage"].get("output_tokens", 0),
                total_tokens=claude_response["usage"].get("input_tokens", 0) + claude_response["usage"].get("output_tokens", 0)
            )
        
        response = StandardResponse(
            id=claude_response.get("id", f"chatcmpl-{int(time.time())}"),
            object="chat.completion",
            created=int(time.time()),
            model=claude_response.get("model", self.model),
            choices=[choice],
            usage=usage
        )
        
        return StandardResponseAdapter(response)
    
    async def close(self):
        """Close the Claude provider and clean up resources."""
        await super().close()
        if self.search_service:
            await self.search_service.close()
        self.logger.debug("Claude provider cleaned up")