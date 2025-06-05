"""
Extended LLM Providers Architecture - Example for future providers
This file demonstrates how to add new LLM providers to the system
"""

from backend.llm_providers import LLMProvider, LLMProviderFactory
from typing import List, Dict, Any, AsyncGenerator
import httpx
import json
import time


class MistralProvider(LLMProvider):
    """Mistral AI provider implementation"""
    
    def __init__(self):
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.api_key = None
        self.model = None
        self.initialized = False
    
    async def init_client(self):
        """Initialize Mistral provider with settings"""
        if self.initialized:
            return
        
        # Get settings from app_settings.mistral
        from backend.settings import app_settings
        self.api_key = app_settings.mistral.api_key
        self.model = app_settings.mistral.model
        
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is required")
        
        self.initialized = True
    
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Send request to Mistral API"""
        await self.init_client()
        
        # Mistral uses OpenAI-compatible format
        request_body = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
            "stream": stream
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        async with httpx.AsyncClient() as client:
            if stream:
                async with client.stream(
                    "POST",
                    self.api_url,
                    json=request_body,
                    headers=headers,
                    timeout=300.0
                ) as response:
                    response.raise_for_status()
                    return self._stream_response(response), None
            else:
                response = await client.post(
                    self.api_url,
                    json=request_body,
                    headers=headers,
                    timeout=300.0
                )
                response.raise_for_status()
                return response.json(), None
    
    async def _stream_response(self, response: httpx.Response) -> AsyncGenerator:
        """Stream response from Mistral"""
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    yield chunk
                except json.JSONDecodeError:
                    continue
    
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """Mistral already uses OpenAI format"""
        return raw_response


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation"""
    
    def __init__(self):
        self.api_key = None
        self.model = None
        self.initialized = False
    
    async def init_client(self):
        """Initialize Gemini provider"""
        if self.initialized:
            return
        
        from backend.settings import app_settings
        self.api_key = app_settings.gemini.api_key
        self.model = app_settings.gemini.model
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        self.initialized = True
    
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Send request to Gemini API"""
        await self.init_client()
        
        # Convert messages to Gemini format
        gemini_messages = self._convert_to_gemini_format(messages)
        
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        
        request_body = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.7),
                "maxOutputTokens": kwargs.get("max_tokens", 1000),
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        async with httpx.AsyncClient() as client:
            if stream:
                # Gemini streaming endpoint
                stream_url = f"{api_url}?alt=sse"
                async with client.stream(
                    "POST",
                    stream_url,
                    json=request_body,
                    headers=headers,
                    timeout=300.0
                ) as response:
                    response.raise_for_status()
                    return self._stream_gemini_response(response), None
            else:
                response = await client.post(
                    api_url,
                    json=request_body,
                    headers=headers,
                    timeout=300.0
                )
                response.raise_for_status()
                return response.json(), None
    
    def _convert_to_gemini_format(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI format to Gemini format"""
        gemini_messages = []
        
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        return gemini_messages
    
    async def _stream_gemini_response(self, response: httpx.Response) -> AsyncGenerator:
        """Convert Gemini streaming response to OpenAI format"""
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                try:
                    chunk = json.loads(data)
                    yield self._format_gemini_chunk(chunk)
                except json.JSONDecodeError:
                    continue
    
    def _format_gemini_chunk(self, gemini_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """Format Gemini chunk to OpenAI format"""
        text = ""
        if "candidates" in gemini_chunk and len(gemini_chunk["candidates"]) > 0:
            candidate = gemini_chunk["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "text" in part:
                        text += part["text"]
        
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": text
                },
                "finish_reason": None
            }]
        }
    
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """Format Gemini response to OpenAI format"""
        if stream:
            return raw_response
        
        # Extract text from Gemini response
        text = ""
        if "candidates" in raw_response and len(raw_response["candidates"]) > 0:
            candidate = raw_response["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "text" in part:
                        text += part["text"]
        
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text
                },
                "finish_reason": "stop"
            }]
        }


class OpenAIDirectProvider(LLMProvider):
    """Direct OpenAI provider (without Azure)"""
    
    def __init__(self):
        self.client = None
        self.initialized = False
    
    async def init_client(self):
        """Initialize OpenAI client"""
        if self.initialized:
            return
        
        from openai import AsyncOpenAI
        from backend.settings import app_settings
        
        self.client = AsyncOpenAI(
            api_key=app_settings.openai_direct.api_key
        )
        self.initialized = True
    
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Send request to OpenAI API"""
        await self.init_client()
        
        from backend.settings import app_settings
        
        model_args = {
            "messages": messages,
            "model": kwargs.get("model", app_settings.openai_direct.model),
            "temperature": kwargs.get("temperature", app_settings.openai_direct.temperature),
            "max_tokens": kwargs.get("max_tokens", app_settings.openai_direct.max_tokens),
            "top_p": kwargs.get("top_p", app_settings.openai_direct.top_p),
            "stream": stream
        }
        
        response = await self.client.chat.completions.create(**model_args)
        return response, None
    
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """OpenAI responses are already in the correct format"""
        return raw_response


# Extended Factory with registration mechanism
class ExtendedLLMProviderFactory(LLMProviderFactory):
    """Extended factory with dynamic provider registration"""
    
    _providers = {
        "AZURE_OPENAI": "AzureOpenAIProvider",
        "CLAUDE": "ClaudeProvider",
        "MISTRAL": "MistralProvider",
        "GEMINI": "GeminiProvider",
        "OPENAI_DIRECT": "OpenAIDirectProvider"
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a new provider dynamically"""
        cls._providers[name.upper()] = provider_class.__name__
    
    @classmethod
    def create_provider(cls, provider_type: str) -> LLMProvider:
        """Create and return the appropriate LLM provider"""
        provider_type = provider_type.upper()
        
        if provider_type not in cls._providers:
            raise ValueError(f"Unknown provider type: {provider_type}")
        
        # Dynamic import and instantiation
        if provider_type == "AZURE_OPENAI":
            from backend.llm_providers import AzureOpenAIProvider
            return AzureOpenAIProvider()
        elif provider_type == "CLAUDE":
            from backend.llm_providers import ClaudeProvider
            return ClaudeProvider()
        elif provider_type == "MISTRAL":
            return MistralProvider()
        elif provider_type == "GEMINI":
            return GeminiProvider()
        elif provider_type == "OPENAI_DIRECT":
            return OpenAIDirectProvider()
        else:
            raise ValueError(f"Provider {provider_type} not implemented")


# Example of how to add a custom provider
class CustomLLMProvider(LLMProvider):
    """Template for custom LLM providers"""
    
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Implement your custom API call here"""
        raise NotImplementedError("Custom provider must implement send_request")
    
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """Convert your API response to OpenAI format"""
        raise NotImplementedError("Custom provider must implement format_response")


# Register the custom provider
ExtendedLLMProviderFactory.register_provider("CUSTOM", CustomLLMProvider)