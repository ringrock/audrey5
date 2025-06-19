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
from .base import LLMProvider, LLMProviderInitializationError, LLMProviderRequestError, handle_provider_errors
from .models import StandardResponse, StandardResponseAdapter, StandardChoice, StandardMessage, StandardUsage
from .utils import AzureSearchService, build_search_context
from .language_detection import get_system_message_for_language
from .i18n import get_documents_header, get_user_question_prefix, get_help_request
try:
    from backend.document_processor import ImageProcessor, ProcessingConfig, create_claude_image_data, ProcessingResult
    IMAGE_PROCESSING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Image processing not available: {e}")
    ImageProcessor = None
    ProcessingConfig = None
    create_claude_image_data = None
    ProcessingResult = None
    IMAGE_PROCESSING_AVAILABLE = False


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
        
        # Initialize image processor for optimized Claude image handling
        # TEMPORARY: Disable image processing for debugging
        # if IMAGE_PROCESSING_AVAILABLE:
        #     self.image_processor = ImageProcessor(ProcessingConfig())
        # else:
        #     self.image_processor = None
        #     self.logger.warning("Advanced image processing not available - using basic processing")
        
        # TEMPORARILY disable image processing to test if compression is causing the issue
        self.image_processor = None
        self.logger.warning("DEBUG: Image processing DISABLED to test if JPEG compression is corrupting images")
    
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
    
    @handle_provider_errors("CLAUDE")
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
        
        self.logger.debug(f"Claude: send_request called with stream={stream}")
        
        # Reset citation state for new request
        self._current_search_citations = None
        
        # Detect language from user's last message using LLM for accuracy
        # Skip language detection if this is an internal call to avoid recursion
        if kwargs.get("_skip_language_detection", False):
            detected_language = "en"  # Default for internal calls
            self.logger.debug("Skipping language detection for internal call")
        else:
            user_message = messages[-1]["content"] if messages else ""
            detected_language = await self.detect_language_with_llm(user_message)
            self.logger.debug(f"Detected language: {detected_language}")
        
        # Convert messages from OpenAI to Claude format with language awareness
        claude_messages = self._convert_messages_to_claude_format(messages, detected_language)
        
        # Perform Azure Search if configured and inject context
        claude_messages = await self._enhance_with_search_context(claude_messages, detected_language=detected_language, **kwargs)
        
        # Get max_tokens based on response size
        response_size = kwargs.get("response_size", "medium")
        max_tokens = self._get_max_tokens_for_response_size("claude", response_size)
        
        # Extract system message if present and use dedicated system parameter
        system_message = None
        clean_messages = []
        
        for msg in claude_messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Check if this message contains system instructions
                if isinstance(content, str) and content.startswith(("Tu es un assistant", "You are an assistant", "Eres un asistente")):
                    # Extract system part and user part
                    parts = content.split("\n\nQuestion de l'utilisateur:", 1)
                    if len(parts) == 2:
                        system_message = parts[0]
                        clean_messages.append({
                            "role": "user",
                            "content": f"Question de l'utilisateur:{parts[1]}"
                        })
                    else:
                        # Try other patterns
                        parts = content.split("\n\nUser question:", 1)
                        if len(parts) == 2:
                            system_message = parts[0]
                            clean_messages.append({
                                "role": "user", 
                                "content": f"User question:{parts[1]}"
                            })
                        else:
                            parts = content.split("\n\nPregunta del usuario:", 1)
                            if len(parts) == 2:
                                system_message = parts[0]
                                clean_messages.append({
                                    "role": "user",
                                    "content": f"Pregunta del usuario:{parts[1]}"
                                })
                            else:
                                # No clear split found, keep as is
                                clean_messages.append(msg)
                elif isinstance(content, list):
                    # Handle multimodal content
                    enhanced_content = []
                    extracted_system = None
                    
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text = part.get("text", "")
                            if text.startswith(("Tu es un assistant", "You are an assistant", "Eres un asistente")):
                                # Extract system part
                                parts = text.split("\n\nQuestion de l'utilisateur:", 1)
                                if len(parts) == 2:
                                    extracted_system = parts[0]
                                    enhanced_content.append({
                                        "type": "text",
                                        "text": f"Question de l'utilisateur:{parts[1]}"
                                    })
                                else:
                                    # Try other patterns
                                    parts = text.split("\n\nUser question:", 1)
                                    if len(parts) == 2:
                                        extracted_system = parts[0]
                                        enhanced_content.append({
                                            "type": "text",
                                            "text": f"User question:{parts[1]}"
                                        })
                                    else:
                                        parts = text.split("\n\nPregunta del usuario:", 1)
                                        if len(parts) == 2:
                                            extracted_system = parts[0]
                                            enhanced_content.append({
                                                "type": "text", 
                                                "text": f"Pregunta del usuario:{parts[1]}"
                                            })
                                        else:
                                            enhanced_content.append(part)
                            else:
                                enhanced_content.append(part)
                        else:
                            enhanced_content.append(part)
                    
                    if extracted_system:
                        system_message = extracted_system
                    
                    clean_messages.append({
                        "role": "user",
                        "content": enhanced_content
                    })
                else:
                    clean_messages.append(msg)
            else:
                clean_messages.append(msg)
        
        # Build Claude API request with dedicated system parameter
        request_body = {
            "model": self.model,
            "messages": clean_messages,
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", app_settings.claude.temperature),
            "stream": stream
        }
        
        # Add system message if extracted
        if system_message:
            request_body["system"] = system_message
            self.logger.debug(f"Claude: Using dedicated system parameter with {len(system_message)} chars")
        
        # Add optional parameters
        if kwargs.get("top_p"):
            request_body["top_p"] = kwargs["top_p"]
        if kwargs.get("stop"):
            stop_sequences = kwargs["stop"] if isinstance(kwargs["stop"], list) else [kwargs["stop"]]
            request_body["stop_sequences"] = stop_sequences
        
        self.logger.debug(f"Claude API request: stream={stream}, messages={len(claude_messages)}")
        
        # Log message count for debugging
        self.logger.debug(f"Claude: sending {len(claude_messages)} messages to API")
        
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
            
        # Error handling is now done by the @handle_provider_errors decorator
    
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
        detected_language: str = "en",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Enhance Claude messages with Azure Search context if configured, with multilingual support.
        
        Args:
            claude_messages: Messages in Claude format
            detected_language: Detected language code for response localization
            **kwargs: Additional parameters including search configuration
            
        Returns:
            Enhanced messages with search context injected and multilingual instructions
        """
        # Check datasource configuration
        self.logger.debug(f"Claude: datasource configured = {bool(app_settings.datasource)}")
        
        # Skip search if no datasource configured, but still apply response size
        if not app_settings.datasource:
            self.logger.debug("Claude: No Azure Search datasource configured - responding without search context")
            return self._apply_response_size_only(claude_messages, kwargs.get("response_size", "medium"), detected_language)
        
        self.logger.info(f"Claude: Azure Search datasource IS configured, proceeding with search")
        
        if not claude_messages:
            self.logger.warning("No messages to enhance with search context")
            return claude_messages
        
        # Extract user query for search
        user_query = self._extract_user_query(claude_messages)
        if not user_query:
            self.logger.warning("No user query found for search")
            return claude_messages
        
        self.logger.debug(f"Claude: Performing Azure Search for query: '{user_query[:50]}...'")
        self.logger.debug(f"Claude: documents_count parameter: {kwargs.get('documents_count')}")
        
        # Perform search
        try:
            # Calling Azure Search service
            search_results = await self.search_service.search_documents(
                query=user_query,
                top_k=kwargs.get("documents_count"),
                filters=kwargs.get("search_filters"),
                user_permissions=kwargs.get("user_permissions")
            )
            self.logger.debug(f"Claude: search_documents completed successfully")
        except Exception as e:
            self.logger.error(f"Claude: search_documents FAILED: {e}")
            search_results = []
        
        self.logger.debug(f"Claude: Azure Search returned {len(search_results) if search_results else 0} results")
        
        if not search_results:
            self.logger.warning("No search results found - Claude will respond without context")
            return claude_messages
        
        # Inject search context into messages with language awareness
        response_size = kwargs.get("response_size", "medium")
        return self._inject_search_context(claude_messages, search_results, response_size, detected_language)
    
    def _convert_messages_to_claude_format(self, messages: List[Dict[str, Any]], detected_language: str = "en") -> List[Dict[str, Any]]:
        """
        Convert OpenAI message format to Claude format with multilingual support.
        
        Claude has different requirements:
        - System messages are handled differently
        - Only user/assistant roles are supported
        - Function/tool messages are not directly supported
        
        Args:
            messages: Messages in OpenAI format
            detected_language: Detected language code for response localization
            
        Returns:
            Messages converted to Claude format with multilingual system message
        """
        claude_messages = []
        original_system_message = None
        
        for msg in messages:
            if msg["role"] == "system":
                # Store original system message
                original_system_message = msg["content"]
            elif msg["role"] in ["user", "assistant"]:
                # Handle multimodal content (images + text) for Claude
                content = self._convert_content_to_claude_format(msg["content"])
                claude_messages.append({
                    "role": msg["role"],
                    "content": content
                })
            # Skip function/tool messages as Claude handles them differently
            
        # Build multilingual system message (response size will be handled later in enhance_with_search_context)
        multilingual_system_message = get_system_message_for_language(detected_language, original_system_message)
        
        # If there's a system message, prepend it to the first user message
        if multilingual_system_message and claude_messages and claude_messages[0]["role"] == "user":
            original_content = claude_messages[0]["content"]
            
            # Handle multimodal content properly
            if isinstance(original_content, list):
                # Find the text part and prepend system message to it
                enhanced_content = []
                for part in original_content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        # Prepend system message to the text part
                        enhanced_text = f"{multilingual_system_message}\n\n{part.get('text', '')}"
                        enhanced_content.append({
                            "type": "text",
                            "text": enhanced_text
                        })
                    else:
                        # Keep other parts (images) as-is
                        enhanced_content.append(part)
                claude_messages[0]["content"] = enhanced_content
            else:
                # Simple text content
                claude_messages[0]["content"] = f"{multilingual_system_message}\n\n{original_content}"
        elif multilingual_system_message and not claude_messages:
            # If no user messages, create one with the system message
            claude_messages.append({
                "role": "user", 
                "content": multilingual_system_message
            })
        
        return claude_messages
    
    def _convert_content_to_claude_format(self, content):
        """
        Convert OpenAI content format to Claude format for multimodal support with optimized image processing.
        
        OpenAI format: [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:image/..."}}]
        Claude format: [{"type": "text", "text": "..."}, {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "..."}}]
        
        Args:
            content: Content in OpenAI format (str or list)
            
        Returns:
            Content in Claude format with optimized images
        """
        
        # DEBUG: Log what we're converting
        self.logger.info(f"DEBUG: _convert_content_to_claude_format called with content type: {type(content)}")
        if isinstance(content, list):
            self.logger.info(f"DEBUG: Content is list with {len(content)} parts")
            for i, part in enumerate(content):
                self.logger.info(f"DEBUG: Part {i}: {part.get('type', 'unknown type')}")
        else:
            self.logger.info(f"DEBUG: Content is string: {str(content)[:100]}...")
        # If it's just a string, return as is
        if isinstance(content, str):
            return content
        
        # If it's a list (multimodal), convert each part
        if isinstance(content, list):
            claude_content = []
            for part in content:
                if part.get("type") == "text":
                    claude_content.append({
                        "type": "text",
                        "text": part.get("text", "")
                    })
                elif part.get("type") == "image_url":
                    # Convert OpenAI image format to Claude format with optimization
                    image_url = part.get("image_url", {}).get("url", "")
                    if image_url.startswith("data:"):
                        try:
                            # Extract media type and base64 data
                            # Format: data:image/jpeg;base64,/9j/4AAQSkZJRgABA...
                            header, raw_data = image_url.split(",", 1)
                            original_media_type = header.split(";")[0].replace("data:", "")
                            
                            self.logger.info(f"Claude: Processing image - original type: {original_media_type}, original size: {len(raw_data)} chars")
                            
                            # DEBUG: Log image data preview for debugging
                            self.logger.info(f"DEBUG: Backend received image data preview: {raw_data[:50]}...")
                            self.logger.info(f"DEBUG: Backend image media type: {original_media_type}")
                            self.logger.info(f"DEBUG: Backend image size chars: {len(raw_data)}")
                            
                            # Detect content type from text context if available
                            content_type = self._detect_image_content_type_from_context(content)
                            
                            # Debug: Log detection details
                            self.logger.info(f"Claude: Image processing debug - "
                                           f"original_media_type: {original_media_type}, "
                                           f"detected_content_type: {content_type}, "
                                           f"original_size_chars: {len(raw_data)}")
                            
                            # Process image with Claude optimization if available
                            if self.image_processor and IMAGE_PROCESSING_AVAILABLE:
                                try:
                                    # Decode base64 to bytes for processing
                                    import base64
                                    image_bytes = base64.b64decode(raw_data)
                                    
                                    # Debug: Log first 100 chars of original data
                                    self.logger.debug(f"Claude: Original image data preview: {raw_data[:100]}...")
                                    
                                    # Process image for Claude optimization
                                    processing_result = self.image_processor.process_for_claude(
                                        image_bytes, 
                                        content_type=content_type
                                    )
                                    
                                    # Log optimization results with debug info
                                    self.logger.info(f"Claude: Image optimized - "
                                                   f"format: {processing_result.original_format} → {processing_result.final_format}, "
                                                   f"size: {processing_result.original_size} → {processing_result.final_size}, "
                                                   f"file_size: {processing_result.file_size_mb:.2f}MB, "
                                                   f"estimated_tokens: {processing_result.estimated_tokens}")
                                    
                                    # Debug: Log first 100 chars of optimized data to verify it's different
                                    self.logger.debug(f"Claude: Optimized image data preview: {processing_result.data[:100]}...")
                                    
                                    # Create optimized Claude image data
                                    claude_image = create_claude_image_data(processing_result)
                                    claude_content.append(claude_image)
                                    
                                except Exception as processing_error:
                                    # Fallback to original processing if optimization fails
                                    self.logger.warning(f"Image optimization failed, using original: {processing_error}")
                                    self._add_original_image(claude_content, original_media_type, raw_data)
                            else:
                                # Use original processing when advanced image processing is not available
                                self.logger.debug("Using basic image processing (PIL not available)")
                                self._add_original_image(claude_content, original_media_type, raw_data)
                                
                        except Exception as e:
                            self.logger.error(f"Failed to convert image format for Claude: {e}")
                            # Skip malformed images
                            continue
            return claude_content
        
        # Fallback: return content as is
        return content
    
    def _detect_image_content_type_from_context(self, content_list):
        """
        Detect likely image content type from surrounding text context.
        
        Args:
            content_list: List of content parts including text and images
            
        Returns:
            str: Detected content type for image optimization
        """
        # Extract all text from the content
        text_parts = []
        for part in content_list:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", "").lower())
        
        combined_text = " ".join(text_parts)
        
        # Analyze text for content type hints
        if any(keyword in combined_text for keyword in ["screenshot", "écran", "capture", "interface", "twitter", "facebook", "instagram", "linkedin", "réseau social", "social media", "publication", "post", "tweet"]):
            return "screenshot"
        elif any(keyword in combined_text for keyword in ["diagramme", "schema", "graphique", "diagram", "chart", "flowchart"]):
            return "diagram"
        elif any(keyword in combined_text for keyword in ["texte", "text", "document", "page", "lecture", "read", "lire", "écrit", "écris", "contenu"]):
            return "text"
        elif any(keyword in combined_text for keyword in ["logo", "icône", "icon", "symbole"]):
            return "logo"
        elif any(keyword in combined_text for keyword in ["photo", "image", "picture", "photographie"]):
            return "photo"
        
        # Default to general if no specific context detected
        return "general"
    
    def _add_original_image(self, claude_content: List[Dict], media_type: str, raw_data: str):
        """
        Add original image data to Claude content with basic size check.
        
        Args:
            claude_content: List to append image data to
            media_type: Original media type
            raw_data: Base64 encoded image data
        """
        # Check original size limit
        if len(raw_data) > 4000000:  # ~4MB limit for base64 data
            self.logger.warning(f"Image trop volumineuse pour Claude: {len(raw_data)} chars. Ignorée.")
            return
        
        claude_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": raw_data
            }
        })
    
    def _apply_response_size_only(
        self, 
        claude_messages: List[Dict[str, Any]], 
        response_size: str = "medium",
        detected_language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Apply response size preference to messages without search context, with multilingual support.
        
        Args:
            claude_messages: Messages in Claude format
            response_size: Response size preference (veryShort, medium, comprehensive)
            detected_language: Detected language code for response localization
            
        Returns:
            Enhanced messages with response size instructions
        """
        if response_size == "medium":
            # No modification needed for default size
            return claude_messages
        
        # Apply response size instructions for non-medium sizes with language awareness
        updated_messages = claude_messages.copy()
        base_system_message = app_settings.claude.system_message
        enhanced_system_message = get_system_message_for_language(detected_language, base_system_message, response_size)
        
        # Get localized user interaction text
        user_question_prefix = get_user_question_prefix(detected_language)
        help_request = get_help_request(detected_language)
        
        # Update the first user message to include the enhanced system message
        if updated_messages and updated_messages[0].get("role") == "user":
            original_content = updated_messages[0]['content']
            
            # Handle multimodal content properly (same fix as in _convert_messages_to_claude_format)
            if isinstance(original_content, list):
                # Find the text part and prepend system message to it
                enhanced_content = []
                for part in original_content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        # Prepend system message to the text part
                        enhanced_text = f"{enhanced_system_message}\n\n{user_question_prefix} {part.get('text', '')}"
                        enhanced_content.append({
                            "type": "text",
                            "text": enhanced_text
                        })
                    else:
                        # Keep other parts (images) as-is
                        enhanced_content.append(part)
                updated_messages[0]["content"] = enhanced_content
            else:
                # Simple text content
                enhanced_content = f"{enhanced_system_message}\n\n{user_question_prefix} {original_content}"
                updated_messages[0]["content"] = enhanced_content
        else:
            # If no user message, prepend as a system instruction
            enhanced_content = f"{enhanced_system_message}\n\n{help_request}"
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
            The last user message content for searching (enriched with image context if present)
        """
        # Get the last user message as the search query
        for msg in reversed(claude_messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                
                # Handle multimodal content
                if isinstance(content, list):
                    text_parts = []
                    has_image = False
                    
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                            elif part.get("type") == "image":
                                has_image = True
                    
                    base_query = " ".join(text_parts)
                    
                    # Enrich query with context (image or general enrichment)
                    if has_image and base_query:
                        enriched_query = self._enrich_query_with_context(base_query, has_image)
                        if enriched_query != base_query:
                            self.logger.info(f"Requête enrichie avec image: '{base_query[:50]}...' → '{enriched_query[:100]}...'")
                            return enriched_query
                    
                    return base_query
                
                return content
        return None
    
    def _has_document_content(self, text: str) -> bool:
        """Check if the text contains uploaded document content"""
        return "\n\n[Document:" in text and "]\n" in text
    
    def _extract_keywords_from_text(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract relevant keywords from text for search enhancement"""
        import re
        
        # Remove document markers and get clean text
        if self._has_document_content(text):
            # Extract text after document header (new format)
            parts = text.split("\n\n[Document:", 1)
            if len(parts) > 1:
                doc_parts = parts[1].split("]\n", 1)
                if len(doc_parts) > 1:
                    text = doc_parts[1]
        
        # Clean and normalize text
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        
        # Filter relevant keywords (remove common words, keep technical terms)
        stop_words = {
            'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'mais', 'donc', 'car',
            'ce', 'cette', 'ces', 'il', 'elle', 'ils', 'elles', 'je', 'tu', 'nous', 'vous',
            'que', 'qui', 'quoi', 'comment', 'pourquoi', 'où', 'quand', 'dans', 'sur', 'avec',
            'par', 'pour', 'sans', 'sous', 'entre', 'vers', 'chez', 'depuis', 'pendant',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
            'document', 'texte', 'text', 'page', 'ligne', 'line'
        }
        
        # Keep words that are longer than 2 chars and not stop words
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        # Remove duplicates and limit count
        unique_keywords = list(dict.fromkeys(keywords))[:max_keywords]
        
        return unique_keywords
    
    def _enrich_query_with_context(self, base_query: str, has_image: bool) -> str:
        """Enrich search query with context from images or documents"""
        original_query = base_query
        
        # Extract the actual user question (before document content)
        user_question = base_query
        document_content = ""
        
        if self._has_document_content(base_query):
            # Format: "Question utilisateur\n\n[Document: nom.ext]\ncontenu..."
            # Split user question from document content
            parts = base_query.split("\n\n[Document:", 1)
            if len(parts) > 1:
                user_question = parts[0].strip()
                # Extract document content after the header
                doc_parts = parts[1].split("]\n", 1)
                if len(doc_parts) > 1:
                    document_content = doc_parts[1]
        
        # For images, add relevant context keywords
        if has_image:
            # Check if this is a help/procedure question
            is_help_question = any(word in user_question.lower() for word in 
                                  ["que faire", "comment", "procédure", "aide", "urgence", "help", "how"])
            
            if is_help_question:
                return f"{user_question} incendie feu moteur avion procédure urgence sécurité"
        
        return original_query
    
    def _inject_search_context(
        self, 
        claude_messages: List[Dict[str, Any]], 
        search_results: List[Dict[str, Any]],
        response_size: str = "medium",
        detected_language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Inject Azure Search results into Claude message context with multilingual support.
        
        Args:
            claude_messages: Messages in Claude format
            search_results: Documents from Azure Search
            response_size: Response size preference
            detected_language: Detected language code for response localization
            
        Returns:
            Enhanced messages with search context and multilingual instructions
        """
        # Build context and citations from search results
        search_context, citations = build_search_context(search_results, app_settings.base_settings.citation_content_max_length)
        
        if not search_context:
            self.logger.warning("No search context built from results")
            return claude_messages
        
        # Store citations for use in response formatting
        self._current_search_citations = citations
        self.logger.debug(f"Claude: stored {len(citations)} citations for response formatting")
        
        # Build enhanced system message with search context, language awareness and response size preference  
        base_system_message = app_settings.claude.system_message
        system_with_size = get_system_message_for_language(detected_language, base_system_message, response_size)
        
        # Get localized documents header
        documents_header = get_documents_header(detected_language)
        
        # Get language instruction to reinforce at the end
        language_reinforcement = ""
        if detected_language == "es":
            language_reinforcement = "\n\nIMPORTANTE: Responde SIEMPRE en español, incluso si los documentos están en francés."
        elif detected_language == "it":
            language_reinforcement = "\n\nIMPORTANTE: Rispondi SEMPRE in italiano, anche se i documenti sono in francese."
        elif detected_language == "en":
            language_reinforcement = "\n\nIMPORTANT: Always respond in English, even if documents are in French."
        elif detected_language == "de":
            language_reinforcement = "\n\nWICHTIG: Antworte IMMER auf Deutsch, auch wenn die Dokumente auf Französisch sind."
        
        enhanced_system_message = f"""{system_with_size}

{documents_header}
{search_context}{language_reinforcement}"""
        
        # Update the first user message to include the enhanced system message
        updated_messages = claude_messages.copy()
        if updated_messages and updated_messages[0].get("role") == "user":
            original_content = updated_messages[0]['content']
            
            # Handle multimodal content properly (same fix as other functions)
            if isinstance(original_content, list):
                # Find the text part and prepend system message to it
                enhanced_content = []
                for part in original_content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        # Prepend system message to the text part
                        user_question_prefix = get_user_question_prefix(detected_language)
                        enhanced_text = f"{enhanced_system_message}\n\n{user_question_prefix} {part.get('text', '')}"
                        enhanced_content.append({
                            "type": "text",
                            "text": enhanced_text
                        })
                    else:
                        # Keep other parts (images) as-is
                        enhanced_content.append(part)
                updated_messages[0]["content"] = enhanced_content
            else:
                # Simple text content
                user_question_prefix = get_user_question_prefix(detected_language)
                enhanced_content = f"{enhanced_system_message}\n\n{user_question_prefix} {original_content}"
                updated_messages[0]["content"] = enhanced_content
        else:
            # If no user message, prepend as a system instruction
            help_request = get_help_request(detected_language)
            enhanced_content = f"{enhanced_system_message}\n\n{help_request}"
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
                if response.status_code != 200:
                    error_text = await response.aread()
                    self.logger.error(f"Claude API error {response.status_code}: {error_text.decode()}")
                    self.logger.error(f"Request body size: {len(str(request_body))} characters")
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