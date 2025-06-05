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