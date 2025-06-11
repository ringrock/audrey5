"""
LLM Providers Package

This package provides a modular, extensible architecture for integrating
different Large Language Model (LLM) providers into the application.

The package supports:
- Azure OpenAI
- Anthropic Claude
- Extensibility for future providers (OpenAI Direct, etc.)

Key Design Principles:
- Standard response format across all providers
- Async support for streaming and non-streaming responses
- Provider-specific optimizations while maintaining consistency
- Backward compatibility with existing Azure OpenAI-based code

Usage:
    from backend.llm_providers import LLMProviderFactory
    
    provider = LLMProviderFactory.create_provider("AZURE_OPENAI")
    response = await provider.get_response(messages, stream=True)

Architecture:
    - base.py: Abstract base class and interfaces
    - models.py: Standard data models and adapters
    - utils.py: Shared utilities (Azure Search, etc.)
    - azure_openai.py: Azure OpenAI provider implementation
    - claude.py: Claude AI provider implementation
    - __init__.py: Factory and public exports (this file)
"""

import logging
from typing import Dict, Type

from backend.settings import app_settings
from .base import LLMProvider, LLMProviderError, LLMProviderInitializationError, LLMProviderRequestError
from .models import StandardResponse, StandardResponseAdapter
from .azure_openai import AzureOpenAIProvider
from .claude import ClaudeProvider
from .openai_direct import OpenAIDirectProvider
from .mistral import MistralProvider
from .gemini import GeminiProvider


class LLMProviderFactory:
    """
    Factory class for creating and managing LLM providers.
    
    This factory provides a centralized way to create LLM providers
    based on configuration. It ensures consistent initialization
    and provides a clean interface for switching between providers.
    
    Supported Providers:
    - AZURE_OPENAI: Azure OpenAI services
    - CLAUDE: Anthropic Claude AI
    - OPENAI_DIRECT: Direct OpenAI API access
    - MISTRAL: Mistral AI services
    - GEMINI: Google Gemini AI services
    
    Future providers can be easily added by:
    1. Implementing the LLMProvider interface
    2. Adding the provider to _PROVIDER_REGISTRY
    3. Updating the docstring and configuration
    """
    
    # Registry of available providers
    _PROVIDER_REGISTRY: Dict[str, Type[LLMProvider]] = {
        "AZURE_OPENAI": AzureOpenAIProvider,
        "CLAUDE": ClaudeProvider,
        "OPENAI_DIRECT": OpenAIDirectProvider,
        "MISTRAL": MistralProvider,
        "GEMINI": GeminiProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_type: str) -> LLMProvider:
        """
        Create and return the appropriate LLM provider.
        
        Args:
            provider_type: Type of provider to create (case-insensitive)
                          Valid values: "AZURE_OPENAI", "CLAUDE", "OPENAI_DIRECT", "MISTRAL", "GEMINI"
        
        Returns:
            Initialized LLM provider instance
            
        Raises:
            ValueError: If provider_type is not supported
            
        Example:
            provider = LLMProviderFactory.create_provider("AZURE_OPENAI")
            response = await provider.get_response(messages)
        """
        provider_type = provider_type.upper().strip()
        
        if provider_type not in cls._PROVIDER_REGISTRY:
            available_providers = list(cls._PROVIDER_REGISTRY.keys())
            raise ValueError(
                f"Unknown provider type: {provider_type}. "
                f"Available providers: {available_providers}"
            )
        
        provider_class = cls._PROVIDER_REGISTRY[provider_type]
        logger = logging.getLogger("LLMProviderFactory")
        logger.info(f"DEBUG FACTORY: Creating provider: {provider_type}")
        logger.info(f"DEBUG FACTORY: Provider class: {provider_class.__name__}")
        
        instance = provider_class()
        logger.info(f"DEBUG FACTORY: Created instance: {instance.__class__.__name__}")
        return instance
    
    @classmethod
    def get_default_provider(cls) -> str:
        """
        Get the default provider type from application settings.
        
        Returns:
            Default provider type string
            
        The default provider is determined by the LLM_PROVIDER
        environment variable or application configuration.
        """
        default_provider = app_settings.base_settings.llm_provider
        logger = logging.getLogger("LLMProviderFactory")
        logger.debug(f"Default provider: {default_provider}")
        
        return default_provider
    
    @classmethod
    def create_default_provider(cls) -> LLMProvider:
        """
        Create the default LLM provider based on application settings.
        
        Returns:
            Default LLM provider instance
            
        This is a convenience method that combines get_default_provider()
        and create_provider() for the most common use case.
        """
        default_type = cls.get_default_provider()
        return cls.create_provider(default_type)
    
    @classmethod
    def list_available_providers(cls) -> list[str]:
        """
        Get a list of all available provider types.
        
        Returns:
            List of provider type strings
            
        Useful for validation, configuration UI, or debugging.
        """
        return list(cls._PROVIDER_REGISTRY.keys())
    
    @classmethod
    def register_provider(cls, provider_type: str, provider_class: Type[LLMProvider]):
        """
        Register a new provider type.
        
        Args:
            provider_type: Unique identifier for the provider
            provider_class: Provider class that implements LLMProvider
            
        This method allows for dynamic registration of new providers
        without modifying the core factory code.
        
        Example:
            LLMProviderFactory.register_provider("OPENAI_DIRECT", OpenAIDirectProvider)
        """
        provider_type = provider_type.upper().strip()
        
        if not issubclass(provider_class, LLMProvider):
            raise ValueError(f"Provider class must inherit from LLMProvider")
        
        cls._PROVIDER_REGISTRY[provider_type] = provider_class
        
        logger = logging.getLogger("LLMProviderFactory")
        logger.info(f"Registered new provider: {provider_type}")


# Public exports - maintain backward compatibility
__all__ = [
    # Factory class
    "LLMProviderFactory",
    
    # Base classes and exceptions
    "LLMProvider", 
    "LLMProviderError",
    "LLMProviderInitializationError", 
    "LLMProviderRequestError",
    
    # Data models
    "StandardResponse",
    "StandardResponseAdapter",
    
    # Provider implementations
    "AzureOpenAIProvider",
    "ClaudeProvider", 
    "OpenAIDirectProvider",
    "MistralProvider",
    "GeminiProvider",
]


# Backward compatibility: Support the old import pattern
# This ensures existing code continues to work without changes
def create_provider(provider_type: str) -> LLMProvider:
    """
    Backward compatibility function.
    
    This function maintains the same interface as the old LLMProviderFactory
    to ensure existing code continues to work without modification.
    """
    return LLMProviderFactory.create_provider(provider_type)


def get_default_provider() -> str:
    """
    Backward compatibility function.
    
    This function maintains the same interface as the old LLMProviderFactory
    to ensure existing code continues to work without modification.
    """
    return LLMProviderFactory.get_default_provider()


# Initialize logging for the package
logger = logging.getLogger(__name__)
logger.debug("LLM Providers package initialized")
logger.debug(f"Available providers: {LLMProviderFactory.list_available_providers()}")
logger.debug(f"Default provider: {LLMProviderFactory.get_default_provider()}")