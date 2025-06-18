"""
Base classes and interfaces for LLM providers.

This module defines the abstract base class that all LLM providers must implement.
It ensures a consistent interface across different LLM implementations while
allowing for provider-specific optimizations and features.

Key Design Principles:
- All providers return StandardResponse format for consistency
- Async support for streaming and non-streaming responses  
- Extensible architecture for adding new LLM providers
- Maintains compatibility with existing Azure OpenAI-based code
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, AsyncGenerator, Union

from .models import StandardResponse, StandardResponseAdapter
from .language_detection import get_system_message_for_language


class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    
    This class defines the interface that all LLM providers must implement.
    It ensures consistency while allowing each provider to handle its specific
    authentication, request formatting, and response processing.
    
    Key responsibilities:
    - Send requests to the specific LLM service
    - Handle authentication and connection management
    - Convert responses to the standard format
    - Support both streaming and non-streaming responses
    """
    
    def __init__(self):
        """Initialize the provider."""
        self.initialized = False
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _get_max_tokens_for_response_size(self, provider_name: str, response_size: str) -> int:
        """
        Get max_tokens based on provider and response size preference.
        
        Args:
            provider_name: Name of the LLM provider (azure_openai, claude, openai_direct, mistral, gemini)
            response_size: Response size preference (veryShort, medium, comprehensive)
            
        Returns:
            Max tokens value for the specific provider and response size
        """
        from backend.settings import app_settings
        
        # Get the provider settings
        provider_settings = getattr(app_settings, provider_name)
        
        if response_size == "veryShort":
            return provider_settings.response_very_short_max_tokens
        elif response_size == "comprehensive":
            return provider_settings.response_comprehensive_max_tokens
        else:  # medium/normal
            return provider_settings.response_normal_max_tokens
    
    def _build_response_size_instructions(self, base_message: str, response_size: str) -> str:
        """
        Add response size instructions to system message.
        
        Args:
            base_message: Base system message
            response_size: Response size preference (veryShort, medium, comprehensive)
            
        Returns:
            Enhanced system message with size instructions
        """
        if response_size == "veryShort":
            return base_message + " IMPORTANT: Répondez de manière très concise en 1-2 phrases complètes maximum. Terminez votre réponse par un point final quand vous avez donné l'essentiel."
        elif response_size == "comprehensive":
            return base_message + " IMPORTANT: Fournissez des réponses détaillées et complètes avec des explications approfondies, des exemples et du contexte supplémentaire."
        else:
            return base_message
    
    def _enhance_messages_with_response_size(self, messages: List[Dict[str, Any]], response_size: str) -> List[Dict[str, Any]]:
        """
        Enhance messages with response size instructions (for OpenAI format).
        
        Args:
            messages: Messages in OpenAI format
            response_size: Response size preference (veryShort, medium, comprehensive)
            
        Returns:
            Enhanced messages with response size system message
        """
        if response_size == "medium":
            return messages
            
        enhanced_messages = messages.copy()
        
        # Look for existing system message or create one
        system_message_idx = None
        from backend.settings import app_settings
        base_system_message = getattr(app_settings.azure_openai, 'system_message', "You are an AI assistant that helps people find information.")
        
        for i, msg in enumerate(enhanced_messages):
            if msg.get("role") == "system":
                system_message_idx = i
                base_system_message = msg["content"]
                break
        
        # Create enhanced system message
        enhanced_system_message = self._build_response_size_instructions(base_system_message, response_size)
        
        if system_message_idx is not None:
            # Update existing system message
            enhanced_messages[system_message_idx]["content"] = enhanced_system_message
        else:
            # Insert new system message at the beginning
            enhanced_messages.insert(0, {
                "role": "system",
                "content": enhanced_system_message
            })
        
        return enhanced_messages
    
    def _enhance_messages_with_language_and_response_size(
        self, 
        messages: List[Dict[str, Any]], 
        detected_language: str,
        response_size: str
    ) -> List[Dict[str, Any]]:
        """
        Enhance messages with both language awareness and response size instructions.
        
        Args:
            messages: Original message list
            detected_language: Detected language code for response localization
            response_size: Response size preference (veryShort, medium, comprehensive)
            
        Returns:
            Enhanced message list with multilingual system message and response size instructions
        """
        enhanced_messages = messages.copy()
        
        # Find or create system message
        system_message_idx = None
        for i, msg in enumerate(enhanced_messages):
            if msg.get("role") == "system":
                system_message_idx = i
                break
        
        # Get original system message content
        original_content = ""
        if system_message_idx is not None:
            original_content = enhanced_messages[system_message_idx].get("content", "")
        
        # Build multilingual system message
        multilingual_content = get_system_message_for_language(detected_language, original_content)
        
        # Add response size instructions
        enhanced_content = self._build_response_size_instructions(multilingual_content, response_size)
        
        # Update or create system message
        if system_message_idx is not None:
            enhanced_messages[system_message_idx]["content"] = enhanced_content
        else:
            enhanced_messages.insert(0, {
                "role": "system",
                "content": enhanced_content
            })
        
        return enhanced_messages
    
    async def detect_language_with_llm(self, text) -> str:
        """
        Detect language using the current LLM provider for maximum accuracy.
        
        This method uses the provider's own API to detect language, which is more
        accurate than keyword matching, especially for short texts or technical content.
        
        Args:
            text: The text to analyze (can be str or list for multimodal)
            
        Returns:
            Two-letter language code (ISO 639-1)
        """
        # Handle multimodal content
        if isinstance(text, list):
            text_parts = []
            for part in text:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            text = " ".join(text_parts)
        
        if not text or len(text.strip()) < 2:
            return "en"  # Default to English for empty text
            
        try:
            # Ensure client is initialized
            await self.init_client()
            
            # Create a simple language detection request
            detection_messages = [
                {
                    "role": "user",
                    "content": f"""Identify the language of this text and respond ONLY with the 2-letter ISO language code (fr, en, es, it, de, pt, etc.):

Text: "{text}"

Language code:"""
                }
            ]
            
            # Use provider's own send_request method with minimal parameters
            # IMPORTANT: Set _skip_language_detection to avoid infinite recursion
            response, _ = await self.send_request(
                messages=detection_messages,
                stream=False,
                response_size="veryShort",  # Keep it short
                _skip_language_detection=True  # Avoid recursion
            )
            
            # Extract the detected language from the response
            detected = self._extract_language_from_response(response)
            
            # Validate the response is a proper language code
            if len(detected) == 2 and detected.isalpha():
                self.logger.debug(f"{self.__class__.__name__} detected language: {detected} for text: {text[:50]}...")
                return detected
            else:
                self.logger.warning(f"Invalid {self.__class__.__name__} language detection response: {detected}")
                
        except Exception as e:
            self.logger.debug(f"{self.__class__.__name__} language detection failed: {e}, falling back to keyword detection")
        
        # Fallback to original detection method
        from .language_detection import detect_language
        return detect_language(text)
    
    def _extract_language_from_response(self, response) -> str:
        """
        Extract detected language code from the provider response.
        
        This method handles different response formats from various providers.
        
        Args:
            response: Raw response from the provider
            
        Returns:
            Detected language code or empty string if extraction fails
        """
        try:
            # Handle different response formats
            content = ""
            
            # Azure OpenAI format
            if hasattr(response, 'choices') and response.choices:
                content = response.choices[0].message.content
            # Dict format
            elif isinstance(response, dict) and 'choices' in response:
                content = response['choices'][0]['message']['content']
            # Claude format
            elif isinstance(response, dict) and 'content' in response:
                if isinstance(response['content'], list):
                    content = response['content'][0].get('text', '')
                else:
                    content = str(response['content'])
            # Direct content
            elif hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)
            
            # Extract and clean the language code
            detected = content.strip().lower()
            
            # Remove common prefixes/suffixes
            if detected.startswith('language code:'):
                detected = detected.replace('language code:', '').strip()
            if detected.startswith('code:'):
                detected = detected.replace('code:', '').strip()
            
            return detected
            
        except Exception as e:
            self.logger.debug(f"Failed to extract language from response: {e}")
            return ""
    
    @abstractmethod
    async def init_client(self):
        """
        Initialize the LLM client with necessary credentials and configuration.
        
        This method should:
        - Set up authentication
        - Initialize the client connection
        - Validate configuration
        - Set self.initialized = True when complete
        
        Raises:
            ValueError: If required configuration is missing
            Exception: If initialization fails
        """
        pass
    
    @abstractmethod
    async def send_request(
        self, 
        messages: List[Dict[str, Any]], 
        stream: bool = True, 
        **kwargs
    ) -> Any:
        """
        Send a request to the LLM provider.
        
        Args:
            messages: List of messages in OpenAI chat format
            stream: Whether to return a streaming response
            **kwargs: Additional provider-specific parameters
        
        Returns:
            For streaming: AsyncGenerator yielding response chunks
            For non-streaming: Raw response from the provider
            
        Note: This method returns the raw provider response.
        Use format_response() to convert to standard format.
        """
        pass
    
    @abstractmethod  
    def format_response(
        self, 
        raw_response: Any, 
        stream: bool = True
    ) -> Union[StandardResponseAdapter, AsyncGenerator]:
        """
        Format the raw provider response to standard format.
        
        Args:
            raw_response: The raw response from send_request()
            stream: Whether this is a streaming response
            
        Returns:
            For streaming: AsyncGenerator yielding StandardResponseAdapter objects
            For non-streaming: StandardResponseAdapter object
            
        This method ensures all providers return consistent response formats
        that are compatible with existing code expecting Azure OpenAI responses.
        """
        pass
    
    async def get_response(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = True,
        **kwargs
    ) -> Union[StandardResponseAdapter, AsyncGenerator]:
        """
        High-level method to get a formatted response from the LLM.
        
        This is the main public interface that combines send_request() 
        and format_response() for convenience.
        
        Args:
            messages: List of messages in OpenAI chat format
            stream: Whether to return a streaming response
            **kwargs: Additional provider-specific parameters
            
        Returns:
            For streaming: AsyncGenerator yielding StandardResponseAdapter objects
            For non-streaming: StandardResponseAdapter object
        """
        # Ensure client is initialized
        if not self.initialized:
            await self.init_client()
        
        # Send request to provider
        raw_response = await self.send_request(messages, stream=stream, **kwargs)
        
        # Format response to standard format
        return self.format_response(raw_response, stream=stream)
    
    async def close(self):
        """
        Clean up resources and close connections.
        
        This method should be called when the provider is no longer needed
        to ensure proper cleanup of connections and resources.
        """
        self.logger.debug(f"Closing {self.__class__.__name__}")
        self.initialized = False


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMProviderInitializationError(LLMProviderError):
    """Raised when provider initialization fails."""
    pass


class LLMProviderRequestError(LLMProviderError):
    """Raised when a request to the LLM provider fails."""
    pass


class LLMProviderResponseError(LLMProviderError):
    """Raised when response formatting fails."""
    pass