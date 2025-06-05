"""
OpenAI Direct provider implementation.

This module implements the LLM provider for direct OpenAI API access.
It provides direct access to OpenAI's API without going through Azure,
enabling access to latest models and features.

Key features:
- Direct OpenAI API authentication
- Support for latest OpenAI models
- Full compatibility with OpenAI parameters
- Minimal overhead with native OpenAI responses
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from openai import AsyncOpenAI

from backend.settings import app_settings
from .base import LLMProvider, LLMProviderInitializationError, LLMProviderRequestError
from .models import StandardResponse, StandardResponseAdapter, StandardChoice, StandardMessage, StandardUsage


class OpenAIDirectProvider(LLMProvider):
    """
    OpenAI Direct provider implementation.
    
    This provider handles direct communication with OpenAI's API.
    Since OpenAI responses are already in the standard OpenAI format,
    minimal transformation is needed.
    
    Features:
    - Direct API key authentication to OpenAI
    - Support for latest OpenAI models (GPT-4, GPT-3.5-turbo, etc.)
    - Full parameter support (temperature, max_tokens, tools, etc.)
    - Maintains compatibility with Azure OpenAI configurations
    """
    
    def __init__(self):
        """Initialize the OpenAI Direct provider."""
        super().__init__()
        self.client = None
        self.logger = logging.getLogger("OpenAIDirectProvider")
    
    async def init_client(self):
        """
        Initialize OpenAI client with API key authentication.
        
        Uses the OpenAI API key from settings to authenticate
        directly with OpenAI's services.
        
        Raises:
            LLMProviderInitializationError: If initialization fails
        """
        if self.initialized:
            return
            
        try:
            # Check if we have OpenAI settings
            if not hasattr(app_settings, 'openai_direct') or not app_settings.openai_direct.api_key:
                raise ValueError("OpenAI Direct API key not configured")
            
            # Initialize the OpenAI client
            self.client = AsyncOpenAI(
                api_key=app_settings.openai_direct.api_key,
                # Use custom base URL if provided (for proxies, etc.)
                base_url=getattr(app_settings.openai_direct, 'base_url', None)
            )
            
            self.initialized = True
            self.logger.info("OpenAI Direct client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI Direct client: {e}")
            raise LLMProviderInitializationError(f"OpenAI Direct initialization failed: {e}")
    
    async def send_request(
        self, 
        messages: List[Dict[str, Any]], 
        stream: bool = True, 
        **kwargs
    ) -> Tuple[Any, Optional[str]]:
        """
        Send request to OpenAI Direct API.
        
        Args:
            messages: List of messages in OpenAI chat format
            stream: Whether to return a streaming response
            **kwargs: Additional OpenAI parameters
            
        Returns:
            Tuple of (response, request_id)
            
        Raises:
            LLMProviderRequestError: If the request fails
        """
        await self.init_client()
        
        try:
            # Build request parameters with defaults from settings
            model_args = {
                "messages": messages,
                "temperature": kwargs.get("temperature", getattr(app_settings.openai_direct, 'temperature', 0.7)),
                "max_tokens": kwargs.get("max_tokens", getattr(app_settings.openai_direct, 'max_tokens', 1000)),
                "top_p": kwargs.get("top_p", getattr(app_settings.openai_direct, 'top_p', 1.0)),
                "stop": kwargs.get("stop", getattr(app_settings.openai_direct, 'stop_sequence', None)),
                "stream": stream,
                "model": kwargs.get("model", getattr(app_settings.openai_direct, 'model', 'gpt-3.5-turbo')),
                "user": kwargs.get("user"),
            }
            
            # Add optional parameters if provided
            if "tools" in kwargs:
                model_args["tools"] = kwargs["tools"]
            if "tool_choice" in kwargs:
                model_args["tool_choice"] = kwargs["tool_choice"]
            if "frequency_penalty" in kwargs:
                model_args["frequency_penalty"] = kwargs["frequency_penalty"]
            if "presence_penalty" in kwargs:
                model_args["presence_penalty"] = kwargs["presence_penalty"]
            
            # Remove None values to avoid API errors
            model_args = {k: v for k, v in model_args.items() if v is not None}
            
            self.logger.debug(f"Sending request to OpenAI Direct: stream={stream}, model={model_args['model']}")
            
            # Make the request
            response = await self.client.chat.completions.create(**model_args)
            
            # OpenAI Direct doesn't provide request IDs in the same way as Azure
            # We'll generate a simple identifier for consistency
            request_id = f"openai-direct-{response.id}" if hasattr(response, 'id') else None
            
            self.logger.debug(f"OpenAI Direct request completed, ID: {request_id}")
            
            return response, request_id
            
        except Exception as e:
            self.logger.error(f"OpenAI Direct request failed: {e}")
            raise LLMProviderRequestError(f"OpenAI Direct request failed: {e}")
    
    def format_response(
        self, 
        raw_response: Any, 
        stream: bool = True
    ) -> Union[StandardResponseAdapter, Any]:
        """
        Format OpenAI Direct response to standard format.
        
        Since OpenAI Direct responses are already in the standard OpenAI format,
        minimal transformation is needed. We primarily just wrap the response
        for consistency.
        
        Args:
            raw_response: Tuple of (response, request_id) from send_request()
            stream: Whether this is a streaming response
            
        Returns:
            For streaming: The response object (already compatible)
            For non-streaming: StandardResponseAdapter wrapping the response
        """
        response, request_id = raw_response
        
        if stream:
            # For streaming responses, OpenAI format is already compatible
            # with existing streaming processing code
            self.logger.debug("Returning streaming response (already compatible)")
            return response
        else:
            # For non-streaming responses, convert to our standard format
            self.logger.debug("Converting non-streaming response to standard format")
            
            # OpenAI response is already in the correct format,
            # but we create a StandardResponse for consistency
            standard_response = self._convert_openai_response(response)
            return StandardResponseAdapter(standard_response)
    
    def _convert_openai_response(self, openai_response) -> StandardResponse:
        """
        Convert OpenAI Direct response to StandardResponse format.
        
        Args:
            openai_response: Raw OpenAI response object
            
        Returns:
            StandardResponse object
        """
        # Convert choices
        choices = []
        for choice in openai_response.choices:
            # Convert message
            message = None
            if hasattr(choice, 'message') and choice.message:
                message = StandardMessage(
                    role=choice.message.role,
                    content=choice.message.content,
                    tool_calls=getattr(choice.message, 'tool_calls', None),
                    context=getattr(choice.message, 'context', None),
                    function_call=getattr(choice.message, 'function_call', None)
                )
            
            # Convert delta (for streaming compatibility)
            delta = None
            if hasattr(choice, 'delta') and choice.delta:
                delta = StandardMessage(
                    role=getattr(choice.delta, 'role', None),
                    content=getattr(choice.delta, 'content', None),
                    tool_calls=getattr(choice.delta, 'tool_calls', None),
                    context=getattr(choice.delta, 'context', None),
                    function_call=getattr(choice.delta, 'function_call', None)
                )
            
            standard_choice = StandardChoice(
                index=choice.index,
                message=message,
                delta=delta,
                finish_reason=choice.finish_reason
            )
            choices.append(standard_choice)
        
        # Convert usage if available
        usage = None
        if hasattr(openai_response, 'usage') and openai_response.usage:
            usage = StandardUsage(
                prompt_tokens=openai_response.usage.prompt_tokens,
                completion_tokens=openai_response.usage.completion_tokens,
                total_tokens=openai_response.usage.total_tokens
            )
        
        return StandardResponse(
            id=openai_response.id,
            object=openai_response.object,
            created=openai_response.created,
            model=openai_response.model,
            choices=choices,
            usage=usage
        )
    
    async def close(self):
        """Close the OpenAI Direct client and clean up resources."""
        await super().close()
        if self.client:
            # OpenAI client cleanup
            await self.client.close()
            self.client = None
            self.logger.debug("OpenAI Direct client cleaned up")