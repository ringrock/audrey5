"""
Extended Settings for additional LLM providers
This demonstrates how to add settings for new providers
"""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from backend.settings import DOTENV_PATH


class _MistralSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MISTRAL_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    
    api_key: Optional[str] = None
    model: str = "mistral-large-latest"
    max_tokens: int = 1000
    temperature: float = 0.7
    top_p: float = 1.0


class _GeminiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GEMINI_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    
    api_key: Optional[str] = None
    model: str = "gemini-1.5-pro"
    max_tokens: int = 1000
    temperature: float = 0.7
    top_k: int = 40


class _OpenAIDirectSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENAI_DIRECT_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    
    api_key: Optional[str] = None
    model: str = "gpt-4-turbo-preview"
    max_tokens: int = 1000
    temperature: float = 0.7
    top_p: float = 1.0
    organization_id: Optional[str] = None


# Example of extended app settings
class _ExtendedAppSettings(BaseModel):
    """
    Extended settings that includes all LLM providers
    In production, you would modify the main _AppSettings class
    """
    # Existing settings...
    # azure_openai: _AzureOpenAISettings
    # claude: _ClaudeSettings
    
    # New provider settings
    mistral: _MistralSettings = _MistralSettings()
    gemini: _GeminiSettings = _GeminiSettings()
    openai_direct: _OpenAIDirectSettings = _OpenAIDirectSettings()


# Configuration for provider-specific features
PROVIDER_CAPABILITIES = {
    "AZURE_OPENAI": {
        "supports_functions": True,
        "supports_data_sources": True,
        "supports_streaming": True,
        "supports_embeddings": True,
        "max_context_length": 128000
    },
    "CLAUDE": {
        "supports_functions": False,
        "supports_data_sources": False,
        "supports_streaming": True,
        "supports_embeddings": False,
        "max_context_length": 200000
    },
    "MISTRAL": {
        "supports_functions": True,
        "supports_data_sources": False,
        "supports_streaming": True,
        "supports_embeddings": True,
        "max_context_length": 32000
    },
    "GEMINI": {
        "supports_functions": True,
        "supports_data_sources": False,
        "supports_streaming": True,
        "supports_embeddings": False,
        "max_context_length": 1000000
    },
    "OPENAI_DIRECT": {
        "supports_functions": True,
        "supports_data_sources": False,
        "supports_streaming": True,
        "supports_embeddings": True,
        "max_context_length": 128000
    }
}


def get_provider_capabilities(provider: str) -> dict:
    """Get capabilities for a specific provider"""
    return PROVIDER_CAPABILITIES.get(provider.upper(), {
        "supports_functions": False,
        "supports_data_sources": False,
        "supports_streaming": False,
        "supports_embeddings": False,
        "max_context_length": 4096
    })