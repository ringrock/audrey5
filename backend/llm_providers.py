import json
import logging
import time
import httpx
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional, List
from openai import AsyncAzureOpenAI
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

from backend.settings import app_settings


class MockAzureOpenAIResponse:
    """Mock class to make Claude responses compatible with Azure OpenAI format functions"""
    def __init__(self, response_dict):
        self.id = response_dict.get("id")
        self.model = response_dict.get("model")
        self.created = response_dict.get("created")
        self.object = response_dict.get("object")
        self.choices = [MockChoice(choice) for choice in response_dict.get("choices", [])]
        
class MockChoice:
    def __init__(self, choice_dict):
        self.message = MockMessage(choice_dict.get("message", {}))
        self.delta = MockMessage(choice_dict.get("delta", {}))
        
        # For Claude streaming: if delta is empty but message has content, 
        # copy message content to delta so format_stream_response finds it
        if not self.delta.content and self.message.content:
            self.delta.role = self.message.role
            self.delta.content = self.message.content
        
class MockMessage:
    def __init__(self, message_dict):
        self.role = message_dict.get("role")
        self.content = message_dict.get("content")
        # Azure OpenAI specific attributes that Claude doesn't have
        self.tool_calls = message_dict.get("tool_calls")  # None for Claude
        self.context = message_dict.get("context")  # None for Claude
        self.function_call = message_dict.get("function_call")  # None for Claude
        logging.debug(f"MockMessage created with attributes: role={self.role}, content={self.content[:50] if self.content else None}, tool_calls={self.tool_calls}")


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Send a request to the LLM provider"""
        pass
    
    @abstractmethod
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """Format the raw response to match Azure OpenAI format"""
        pass


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider implementation"""
    
    def __init__(self):
        self.client = None
        self.initialized = False
    
    async def init_client(self):
        """Initialize Azure OpenAI client"""
        if self.initialized:
            return
            
        try:
            if app_settings.base_settings.auth_enabled and not app_settings.azure_openai.key:
                async with DefaultAzureCredential() as credential:
                    token_provider = get_bearer_token_provider(
                        credential, "https://cognitiveservices.azure.com/.default"
                    )
            else:
                token_provider = None

            self.client = AsyncAzureOpenAI(
                api_version=app_settings.azure_openai.preview_api_version,
                api_key=app_settings.azure_openai.key,
                azure_ad_token_provider=token_provider,
                default_headers={"x-ms-useragent": "GitHubSampleWebApp/AsyncAzureOpenAI/1.0.0"},
                azure_endpoint=app_settings.azure_openai.endpoint
            )
            self.initialized = True
        except Exception as e:
            logging.exception("Exception in Azure OpenAI initialization", e)
            raise e
    
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Send request to Azure OpenAI"""
        await self.init_client()
        
        # Extract Azure-specific parameters
        model_args = {
            "messages": messages,
            "temperature": kwargs.get("temperature", app_settings.azure_openai.temperature),
            "max_tokens": kwargs.get("max_tokens", app_settings.azure_openai.max_tokens),
            "top_p": kwargs.get("top_p", app_settings.azure_openai.top_p),
            "stop": kwargs.get("stop", app_settings.azure_openai.stop_sequence),
            "stream": stream,
            "model": kwargs.get("model", app_settings.azure_openai.model),
            "user": kwargs.get("user"),
        }
        
        # Add optional parameters
        if "tools" in kwargs:
            model_args["tools"] = kwargs["tools"]
        if "extra_body" in kwargs:
            model_args["extra_body"] = kwargs["extra_body"]
            
        raw_response = await self.client.chat.completions.with_raw_response.create(**model_args)
        response = raw_response.parse()
        apim_request_id = raw_response.headers.get("apim-request-id")
        
        return response, apim_request_id
    
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """Azure OpenAI responses are already in the correct format"""
        return raw_response


class ClaudeProvider(LLMProvider):
    """Claude AI provider implementation"""
    
    def __init__(self):
        self.api_key = None
        self.model = None
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.initialized = False
    
    async def init_client(self):
        """Initialize Claude provider with settings"""
        if self.initialized:
            return
            
        # Get Claude-specific settings from app_settings
        self.api_key = app_settings.claude.api_key
        self.model = app_settings.claude.model
        
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY environment variable is required")
            
        self.initialized = True
    
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Send request to Claude API"""
        await self.init_client()
        
        # Convert messages format from OpenAI to Claude
        claude_messages = self._convert_messages_to_claude_format(messages)
        
        # Extract Claude-compatible parameters
        request_body = {
            "model": self.model,
            "messages": claude_messages,
            "max_tokens": kwargs.get("max_tokens", app_settings.claude.max_tokens),
            "temperature": kwargs.get("temperature", app_settings.claude.temperature)
        }
        
        # Explicitly set streaming behavior
        request_body["stream"] = stream
        
        # Add optional parameters
        if kwargs.get("top_p"):
            request_body["top_p"] = kwargs["top_p"]
        if kwargs.get("stop"):
            request_body["stop_sequences"] = kwargs["stop"] if isinstance(kwargs["stop"], list) else [kwargs["stop"]]
        
        # Debug logging
        logging.debug(f"Claude API Request Body: {request_body}")
        logging.debug(f"Original messages count: {len(messages)}, Claude messages count: {len(claude_messages)}")
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        if stream:
            # For streaming requests, return a generator that manages its own client
            return self._create_streaming_generator(request_body, headers), None
        else:
            # For non-streaming requests, parse as JSON
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=request_body,
                    headers=headers,
                    timeout=300.0
                )
                
                # Debug logging
                logging.debug(f"Claude API Response Status: {response.status_code}")
                logging.debug(f"Claude API Response Headers: {dict(response.headers)}")
                logging.debug(f"Claude API Response Content Length: {len(response.content)}")
                logging.debug(f"Claude API Response Content: {response.content[:500]}...")
                
                response.raise_for_status()
                
                if len(response.content) == 0:
                    raise ValueError("Claude API returned empty response")
                
                try:
                    response_json = response.json()
                    logging.debug(f"Parsed Claude response: {type(response_json)}")
                    return response_json, None
                except Exception as e:
                    logging.error(f"Failed to parse Claude response as JSON: {e}")
                    logging.error(f"Raw response content: {response.content}")
                    raise
    
    def _convert_messages_to_claude_format(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI message format to Claude format"""
        claude_messages = []
        system_message = None
        
        for msg in messages:
            if msg["role"] == "system":
                # Claude handles system messages differently
                system_message = msg["content"]
            elif msg["role"] in ["user", "assistant"]:
                claude_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            # Skip function/tool messages for now as Claude handles them differently
            
        # If there's a system message, prepend it to the first user message
        if system_message and claude_messages:
            if claude_messages[0]["role"] == "user":
                claude_messages[0]["content"] = f"{system_message}\n\n{claude_messages[0]['content']}"
        
        return claude_messages
    
    async def _create_streaming_generator(self, request_body: Dict[str, Any], headers: Dict[str, str]) -> AsyncGenerator:
        """Create a streaming generator that manages its own HTTP client"""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                self.api_url,
                json=request_body,
                headers=headers,
                timeout=300.0
            ) as response:
                logging.debug(f"Claude API Stream Response Status: {response.status_code}")
                response.raise_for_status()
                
                async for chunk in self._stream_claude_response(response):
                    yield chunk
    
    async def _stream_claude_response(self, response: httpx.Response) -> AsyncGenerator:
        """Convert Claude streaming response to OpenAI format"""
        async for line in response.aiter_lines():
            line = line.strip()
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                    
                try:
                    chunk = json.loads(data)
                    logging.debug(f"Claude streaming chunk: {chunk}")
                    
                    # Convert Claude chunk to OpenAI format based on event type
                    if chunk.get("type") == "content_block_delta":
                        # This contains the actual text content
                        if chunk.get("delta", {}).get("text"):
                            yield self._format_streaming_chunk(chunk)
                    elif chunk.get("type") == "content_block_start":
                        # Initial content block
                        logging.debug("Claude content block started")
                    elif chunk.get("type") == "message_delta":
                        # Message metadata changes
                        logging.debug("Claude message delta")
                    elif chunk.get("type") == "message_stop":
                        # End of message
                        logging.debug("Claude message stopped")
                        break
                        
                except json.JSONDecodeError as e:
                    logging.warning(f"Failed to parse Claude streaming data: {e}, data: {data}")
                    continue
    
    def _format_streaming_chunk(self, claude_chunk: Dict[str, Any]) -> 'MockAzureOpenAIResponse':
        """Format Claude streaming chunk to match OpenAI format"""
        chunk_dict = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": claude_chunk.get("delta", {}).get("text", "")
                },
                "finish_reason": None
            }]
        }
        
        # Return a MockAzureOpenAIResponse object that's compatible with format_stream_response
        return MockAzureOpenAIResponse(chunk_dict)
    
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """Format Claude response to match Azure OpenAI format"""
        if stream:
            # For streaming responses, return the generator as-is
            # Individual chunks are already formatted by _format_streaming_chunk
            return raw_response
        
        # Format non-streaming response
        claude_response = raw_response
        logging.debug(f"Formatting Claude response: {claude_response}")
        
        # Extract text content from Claude response
        content = ""
        if isinstance(claude_response.get("content"), list):
            for item in claude_response["content"]:
                if item.get("type") == "text":
                    content += item.get("text", "")
        else:
            content = str(claude_response.get("content", ""))
        
        # For non-streaming responses, use 'message'
        formatted_response = {
            "id": claude_response.get("id", f"chatcmpl-{int(time.time())}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": claude_response.get("model", self.model),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": claude_response.get("stop_reason", "stop")
            }],
            "usage": claude_response.get("usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            })
        }
        
        logging.debug(f"Formatted response: {formatted_response}")
        
        # Return a mock object that's compatible with Azure OpenAI format functions
        return MockAzureOpenAIResponse(formatted_response)


class LLMProviderFactory:
    """Factory class to create LLM providers"""
    
    @staticmethod
    def create_provider(provider_type: str) -> LLMProvider:
        """Create and return the appropriate LLM provider"""
        provider_type = provider_type.upper()
        
        if provider_type == "AZURE_OPENAI":
            return AzureOpenAIProvider()
        elif provider_type == "CLAUDE":
            return ClaudeProvider()
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
    
    @staticmethod
    def get_default_provider() -> str:
        """Get the default provider from environment settings"""
        return app_settings.base_settings.llm_provider