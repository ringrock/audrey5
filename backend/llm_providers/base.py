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
    
    def _adjust_max_tokens_for_response_size(self, base_max_tokens: int, response_size: str) -> int:
        """
        Adjust max_tokens based on response size preference.
        
        Args:
            base_max_tokens: Base max tokens value
            response_size: Response size preference (veryShort, medium, comprehensive)
            
        Returns:
            Adjusted max_tokens value
        """
        from backend.settings import app_settings
        
        if response_size == "veryShort":
            return min(base_max_tokens, app_settings.response.very_short_max_tokens)
        elif response_size == "comprehensive":
            return max(base_max_tokens, app_settings.response.comprehensive_max_tokens)
        else:
            return base_max_tokens
    
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