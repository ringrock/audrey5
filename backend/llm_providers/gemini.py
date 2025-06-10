"""
Google Gemini AI provider implementation.

This module implements the LLM provider for Google's Gemini AI service.
It handles Gemini-specific authentication, message formatting, streaming responses,
and integration with Azure Search for document retrieval.

Key features:
- Gemini API message format conversion
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


class GeminiProvider(LLMProvider):
    """
    Google Gemini AI provider implementation.
    
    This provider handles communication with Google's Gemini API,
    including message format conversion, streaming responses, and
    integration with Azure Search for document retrieval.
    
    Features:
    - Converts OpenAI message format to Gemini format
    - Integrates with Azure Search for RAG capabilities
    - Supports streaming responses with real-time citations
    - Handles multilingual system messages
    """
    
    def __init__(self):
        """Initialize the Gemini provider."""
        super().__init__()
        self.api_key = None
        self.model = None
        self.api_url = None
        self.search_service = AzureSearchService()
        self.logger = logging.getLogger("GeminiProvider")
        
        # State for handling citations in streaming responses
        self._current_search_citations = None
    
    async def init_client(self):
        """
        Initialize Gemini provider with API credentials.
        
        Raises:
            LLMProviderInitializationError: If API key is missing or invalid
        """
        if self.initialized:
            return
            
        # Get Gemini-specific settings
        self.api_key = app_settings.gemini.api_key
        self.model = app_settings.gemini.model
        
        # Debug logging
        self.logger.debug(f"Gemini API key from settings: {self.api_key[:10] if self.api_key else 'None'}...")
        
        if not self.api_key or self.api_key == "TBD":
            raise LLMProviderInitializationError("GEMINI_API_KEY environment variable is required and must be set to a valid Google API key (not 'TBD')")
        
        # Build API URL with API key
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        # Debug logging for API key (masking for security)
        masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}" if self.api_key else "None"
        self.logger.info(f"Gemini provider initialized with key: {masked_key}, model: {self.model}")
            
        self.initialized = True
    
    async def send_request(
        self, 
        messages: List[Dict[str, Any]], 
        stream: bool = True, 
        **kwargs
    ) -> Tuple[Any, Optional[str]]:
        """
        Send request to Gemini API with Azure Search integration.
        
        Args:
            messages: List of messages in OpenAI chat format
            stream: Whether to return a streaming response
            **kwargs: Additional parameters including search configuration
            
        Returns:
            Tuple of (response, apim_request_id) for compatibility with app.py
            For streaming: (AsyncGenerator, None)
            For non-streaming: (Raw Gemini API response, None)
            
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
            
            # Convert messages from OpenAI to Gemini format
            gemini_request = self._convert_messages_to_gemini_format(enhanced_messages, **kwargs)
            
            self.logger.debug(f"Gemini API request: stream={stream}, messages={len(enhanced_messages)}")
            
            if stream:
                # Build streaming URL
                stream_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?key={self.api_key}"
                # Return streaming generator
                generator = self._create_streaming_generator(gemini_request, stream_url)
                return generator, None  # (response, apim_request_id)
            else:
                # Make non-streaming request
                response = await self._make_non_streaming_request(gemini_request)
                return response, None  # (response, apim_request_id)
                
        except Exception as e:
            self.logger.error(f"Gemini request failed: {e}")
            raise LLMProviderRequestError(f"Gemini request failed: {e}")
    
    def format_response(
        self, 
        raw_response: Any, 
        stream: bool = True
    ) -> StandardResponseAdapter:
        """
        Format Gemini response to standard format.
        
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
            # Convert non-streaming Gemini response to standard format
            return self._format_non_streaming_response(raw_response)
    
    async def _enhance_with_search_context(
        self, 
        messages: List[Dict[str, Any]], 
        detected_language: str = "en",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Enhance Gemini messages with Azure Search context if configured, with multilingual support.
        
        Args:
            messages: Messages in OpenAI format
            detected_language: Detected language code for response localization
            **kwargs: Additional parameters including search configuration
            
        Returns:
            Enhanced messages with search context and multilingual system message
        """
        # Start with a copy of messages
        enhanced_messages = messages.copy()
        
        # Check if we need to perform Azure Search
        search_context = ""
        citations = []
        
        if app_settings.datasource and enhanced_messages:
            # Extract user query for search
            user_query = self._extract_user_query(enhanced_messages)
            if user_query:
                self.logger.debug(f"Performing Azure Search for query: '{user_query}'")
                
                # Perform search
                documents_count = kwargs.get("documents_count")
                print(f"🔍 Recherche Azure Search:")
                print(f"   - Requête: '{user_query}'")
                print(f"   - Nombre de documents demandés: {documents_count}")
                
                search_results = await self.search_service.search_documents(
                    query=user_query,
                    top_k=documents_count,
                    filters=kwargs.get("search_filters"),
                    user_permissions=kwargs.get("user_permissions")
                )
                
                self.logger.debug(f"Azure Search returned {len(search_results) if search_results else 0} results")
                
                if search_results:
                    # Build context and citations
                    search_context, citations = build_search_context(search_results)
                    self._current_search_citations = citations
        
        # Apply response size and language preferences to system message
        response_size = kwargs.get("response_size", "medium")
        print(f"📝 Configuration du message système:")
        print(f"   - Taille de réponse: {response_size}")
        print(f"   - Langue détectée: {detected_language}")
        
        base_system_message = getattr(app_settings.gemini, 'system_message', 
                                     "You are a helpful and accurate AI assistant.")
        system_message = get_system_message_for_language(detected_language, base_system_message, response_size)
        
        # Build enhanced system message with search context if available
        if search_context:
            # Get localized documents header
            documents_header = get_documents_header(detected_language)
            
            enhanced_system_message = f"""{system_message}

{documents_header}
{search_context}"""
        else:
            enhanced_system_message = system_message
        
        # Insert or update system message
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
    
    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        Convert OpenAI message format to Gemini format.
        
        Gemini has different requirements:
        - Uses "contents" array with "parts" objects
        - Roles are "user" and "model" (not "assistant")
        - System messages are handled via systemInstruction
        
        Args:
            messages: Messages in OpenAI format
            **kwargs: Additional parameters including generation settings
            
        Returns:
            Request body in Gemini format
        """
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg["role"] == "system":
                # Store system message for systemInstruction
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": msg["content"]}]
                })
            elif msg["role"] == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": msg["content"]}]
                })
            # Skip function/tool messages as Gemini handles them differently
        
        # Get generation configuration
        response_size = kwargs.get("response_size", "medium")
        max_tokens = self._get_max_tokens_for_response_size("gemini", response_size)
        
        # Build Gemini request
        request_body = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": kwargs.get("temperature", app_settings.gemini.temperature),
            }
        }
        
        # Add system instruction if available
        if system_instruction:
            request_body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        # Add optional parameters
        if kwargs.get("top_p"):
            request_body["generationConfig"]["topP"] = kwargs["top_p"]
        if kwargs.get("stop"):
            stop_sequences = kwargs["stop"] if isinstance(kwargs["stop"], list) else [kwargs["stop"]]
            request_body["generationConfig"]["stopSequences"] = stop_sequences
        
        return request_body
    
    async def _create_streaming_generator(
        self, 
        request_body: Dict[str, Any], 
        stream_url: str
    ) -> AsyncGenerator[StandardResponseAdapter, None]:
        """
        Create a streaming generator that manages its own HTTP client.
        
        Args:
            request_body: Gemini API request body
            stream_url: Streaming API URL
            
        Yields:
            StandardResponseAdapter objects for each chunk
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                stream_url,
                json=request_body,
                headers=headers,
                timeout=300.0
            ) as response:
                self.logger.debug(f"Gemini streaming response status: {response.status_code}")
                if response.status_code != 200:
                    error_text = await response.aread()
                    self.logger.error(f"Gemini API error {response.status_code}: {error_text.decode()}")
                    if response.status_code == 400:
                        self.logger.error("Check that GEMINI_API_KEY is valid and GEMINI_MODEL is supported")
                response.raise_for_status()
                
                async for chunk in self._stream_gemini_response(response):
                    yield chunk
    
    async def _stream_gemini_response(self, response: httpx.Response) -> AsyncGenerator[StandardResponseAdapter, None]:
        """
        Convert Gemini streaming response to standard format.
        
        Args:
            response: HTTP response from Gemini API
            
        Yields:
            StandardResponseAdapter objects for each chunk
        """
        first_content_chunk = True
        citations_sent = False
        full_buffer = ""
        
        # Collect the entire response first, then parse it properly
        async for line in response.aiter_lines():
            line = line.strip()
            if line:
                full_buffer += line
        
        self.logger.debug(f"Full Gemini buffer: {full_buffer[:300]}...")
        
        # Parse the complete JSON array
        try:
            # The response should be a JSON array
            if full_buffer.startswith('[') and full_buffer.endswith(']'):
                chunks = json.loads(full_buffer)
            else:
                # Fallback: try to parse as single object
                chunks = [json.loads(full_buffer)]
            
            self.logger.info(f"Parsed {len(chunks)} Gemini chunks")
            
            # Process each chunk and yield them one by one to simulate streaming
            for i, chunk in enumerate(chunks):
                self.logger.debug(f"Processing chunk {i}: {chunk}")
                
                if chunk.get("candidates") and len(chunk["candidates"]) > 0:
                    candidate = chunk["candidates"][0]
                    if candidate.get("content") and candidate["content"].get("parts"):
                        # Check if this chunk has text content
                        text_parts = [part.get("text", "") for part in candidate["content"]["parts"] if part.get("text")]
                        
                        if text_parts:
                            self.logger.info(f"Chunk {i} text: {text_parts}")
                            
                            # Send citations before first content if available
                            if (first_content_chunk and 
                                self._current_search_citations and 
                                not citations_sent):
                                
                                citations_chunk = self._create_citations_chunk()
                                yield citations_chunk
                                citations_sent = True
                            
                            first_content_chunk = False
                            
                            # Send content chunk with a small delay to simulate streaming
                            yield self._format_streaming_chunk(chunk)
                            
                            # Add a small delay between chunks to simulate real streaming
                            import asyncio
                            await asyncio.sleep(0.05)  # 50ms delay between chunks
                            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Gemini response: {e}")
            self.logger.error(f"Response content: {full_buffer[:500]}...")
    
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
    
    def _format_streaming_chunk(self, gemini_chunk: Dict[str, Any]) -> StandardResponseAdapter:
        """
        Format a Gemini streaming chunk to standard format.
        
        Args:
            gemini_chunk: Raw chunk from Gemini API
            
        Returns:
            StandardResponseAdapter for the chunk
        """
        # Extract text content from Gemini chunk
        text_content = ""
        finish_reason = None
        
        if gemini_chunk.get("candidates") and len(gemini_chunk["candidates"]) > 0:
            candidate = gemini_chunk["candidates"][0]
            
            # Get text content if available
            if candidate.get("content") and candidate["content"].get("parts"):
                for part in candidate["content"]["parts"]:
                    if part.get("text"):
                        text_content += part["text"]
            
            # Get finish reason if available
            finish_reason = candidate.get("finishReason")
        
        # Create standard message
        message = StandardMessage(
            role="assistant",
            content=text_content
        )
        
        choice = StandardChoice(
            index=0,
            delta=message,
            finish_reason=finish_reason
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
        request_body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make a non-streaming request to Gemini API.
        
        Args:
            request_body: Gemini API request body
            
        Returns:
            Raw Gemini API response
            
        Raises:
            LLMProviderRequestError: If the request fails
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=request_body,
                    headers=headers,
                    timeout=300.0
                )
                
                self.logger.debug(f"Gemini API response status: {response.status_code}")
                if response.status_code != 200:
                    error_text = response.content.decode()
                    self.logger.error(f"Gemini API error {response.status_code}: {error_text}")
                    if response.status_code == 400:
                        self.logger.error("Check that GEMINI_API_KEY is valid and GEMINI_MODEL is supported")
                response.raise_for_status()
                
                if len(response.content) == 0:
                    raise LLMProviderRequestError("Gemini API returned empty response")
                
                return response.json()
                
        except httpx.HTTPError as e:
            raise LLMProviderRequestError(f"Gemini API HTTP error: {e}")
        except json.JSONDecodeError as e:
            raise LLMProviderRequestError(f"Failed to parse Gemini response: {e}")
    
    def _format_non_streaming_response(self, gemini_response: Dict[str, Any]) -> StandardResponseAdapter:
        """
        Format non-streaming Gemini response to standard format.
        
        Args:
            gemini_response: Raw Gemini API response
            
        Returns:
            StandardResponseAdapter for the response
        """
        # Extract text content from Gemini response
        content = ""
        finish_reason = "stop"
        
        if gemini_response.get("candidates") and len(gemini_response["candidates"]) > 0:
            candidate = gemini_response["candidates"][0]
            
            # Get text content from all parts
            if candidate.get("content") and candidate["content"].get("parts"):
                for part in candidate["content"]["parts"]:
                    if part.get("text"):
                        content += part["text"]
            
            # Get finish reason
            finish_reason = candidate.get("finishReason", "stop")
        
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
            finish_reason=finish_reason
        )
        
        # Create usage information
        usage = None
        if "usageMetadata" in gemini_response:
            metadata = gemini_response["usageMetadata"]
            usage = StandardUsage(
                prompt_tokens=metadata.get("promptTokenCount", 0),
                completion_tokens=metadata.get("candidatesTokenCount", 0),
                total_tokens=metadata.get("totalTokenCount", 0)
            )
        
        response = StandardResponse(
            id=f"chatcmpl-{int(time.time())}",
            object="chat.completion",
            created=int(time.time()),
            model=self.model,
            choices=[choice],
            usage=usage
        )
        
        return StandardResponseAdapter(response)
    
    async def close(self):
        """Close the Gemini provider and clean up resources."""
        await super().close()
        if self.search_service:
            await self.search_service.close()
        self.logger.debug("Gemini provider cleaned up")