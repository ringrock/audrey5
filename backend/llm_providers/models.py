"""
Standard data models for LLM providers.

This module defines the standard response format that all LLM providers must conform to.
This ensures consistency across different LLM implementations while maintaining 
compatibility with the existing codebase.

The standard format is based on OpenAI's chat completion format for maximum compatibility.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class StandardMessage:
    """
    Standard message format for LLM responses.
    
    Compatible with OpenAI chat completion format.
    """
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = None
    function_call: Optional[Dict[str, Any]] = None


@dataclass 
class StandardChoice:
    """
    Standard choice format for LLM responses.
    
    Represents a single response choice from the LLM.
    """
    index: int
    message: Optional[StandardMessage] = None
    delta: Optional[StandardMessage] = None
    finish_reason: Optional[str] = None


@dataclass
class StandardUsage:
    """
    Standard usage statistics for LLM responses.
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class StandardResponse:
    """
    Standard response format that all LLM providers must return.
    
    This format is compatible with OpenAI's chat completion format,
    ensuring seamless integration with existing code that expects
    Azure OpenAI responses.
    """
    id: str
    object: str
    created: int
    model: str
    choices: List[StandardChoice]
    usage: Optional[StandardUsage] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization."""
        result = {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": []
        }
        
        for choice in self.choices:
            choice_dict = {
                "index": choice.index,
                "finish_reason": choice.finish_reason
            }
            
            if choice.message:
                choice_dict["message"] = {
                    "role": choice.message.role,
                    "content": choice.message.content
                }
                if choice.message.context:
                    choice_dict["message"]["context"] = choice.message.context
                if choice.message.tool_calls:
                    choice_dict["message"]["tool_calls"] = choice.message.tool_calls
                if choice.message.function_call:
                    choice_dict["message"]["function_call"] = choice.message.function_call
            
            if choice.delta:
                choice_dict["delta"] = {
                    "role": choice.delta.role,
                    "content": choice.delta.content
                }
                if choice.delta.context:
                    choice_dict["delta"]["context"] = choice.delta.context
                if choice.delta.tool_calls:
                    choice_dict["delta"]["tool_calls"] = choice.delta.tool_calls
                if choice.delta.function_call:
                    choice_dict["delta"]["function_call"] = choice.delta.function_call
            
            result["choices"].append(choice_dict)
        
        if self.usage:
            result["usage"] = {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens
            }
        
        return result


class StandardResponseAdapter:
    """
    Adapter class that makes StandardResponse compatible with existing code
    that expects Azure OpenAI response objects.
    
    This provides the same interface as the old MockAzureOpenAIResponse
    while using the new standard format internally.
    """
    
    def __init__(self, standard_response: StandardResponse):
        """
        Initialize adapter with a StandardResponse.
        
        Args:
            standard_response: The StandardResponse to adapt
        """
        self._response = standard_response
        self.id = standard_response.id
        self.model = standard_response.model
        self.created = standard_response.created
        self.object = standard_response.object
        
        # Create choice adapters
        self.choices = [ChoiceAdapter(choice) for choice in standard_response.choices]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for compatibility."""
        return self._response.to_dict()


class ChoiceAdapter:
    """
    Adapter for StandardChoice to maintain compatibility with existing code.
    """
    
    def __init__(self, choice: StandardChoice):
        """
        Initialize choice adapter.
        
        Args:
            choice: The StandardChoice to adapt
        """
        self.index = choice.index
        self.finish_reason = choice.finish_reason
        
        # Adapt message and delta
        self.message = MessageAdapter(choice.message) if choice.message else None
        self.delta = MessageAdapter(choice.delta) if choice.delta else None


class MessageAdapter:
    """
    Adapter for StandardMessage to maintain compatibility with existing code.
    """
    
    def __init__(self, message: StandardMessage):
        """
        Initialize message adapter.
        
        Args:
            message: The StandardMessage to adapt
        """
        if message:
            self.role = message.role
            self.content = message.content
            self.context = message.context
            self.tool_calls = message.tool_calls
            self.function_call = message.function_call
        else:
            self.role = None
            self.content = None
            self.context = None
            self.tool_calls = None
            self.function_call = None