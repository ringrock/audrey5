"""
Enhanced error handling system for LLM providers.

This module provides structured error handling with user-friendly messages
and proper error classification for different types of API failures.
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from .base import LLMProviderError, LLMProviderRequestError


@dataclass
class ErrorInfo:
    """Structured error information for user-friendly display."""
    error_type: str
    user_message_fr: str
    user_message_en: str
    technical_details: str
    retry_suggested: bool = False
    contact_support: bool = False


class LLMProviderErrorHandler:
    """
    Centralized error handler for all LLM providers.
    
    Provides consistent error classification and user-friendly messages
    across all supported LLM providers (Azure OpenAI, Claude, OpenAI Direct, Mistral, Gemini).
    """
    
    @staticmethod
    def classify_error(exception: Exception, provider_name: str) -> ErrorInfo:
        """
        Classify an exception and return structured error information.
        
        Args:
            exception: The exception that occurred
            provider_name: Name of the LLM provider (AZURE_OPENAI, CLAUDE, etc.)
            
        Returns:
            ErrorInfo with user-friendly messages and technical details
        """
        error_str = str(exception).lower()
        
        # HTTP 429 - Rate Limiting
        if "429" in error_str or "too many requests" in error_str:
            return ErrorInfo(
                error_type="RATE_LIMITED",
                user_message_fr=f"Trop de requêtes ont été envoyées au service {provider_name}. Veuillez patienter quelques instants avant de réessayer.",
                user_message_en=f"Too many requests sent to {provider_name} service. Please wait a moment before trying again.",
                technical_details=str(exception),
                retry_suggested=True
            )
        
        # HTTP 401/403 - Authentication
        elif any(code in error_str for code in ["401", "403", "unauthorized", "forbidden", "invalid api key"]):
            return ErrorInfo(
                error_type="AUTHENTICATION_ERROR",
                user_message_fr=f"Problème d'authentification avec {provider_name}. Veuillez contacter l'administrateur.",
                user_message_en=f"Authentication issue with {provider_name}. Please contact the administrator.",
                technical_details=str(exception),
                contact_support=True
            )
        
        # HTTP 400 - Bad Request
        elif "400" in error_str or "bad request" in error_str:
            return ErrorInfo(
                error_type="BAD_REQUEST",
                user_message_fr=f"Requête invalide envoyée à {provider_name}. Veuillez reformuler votre question.",
                user_message_en=f"Invalid request sent to {provider_name}. Please rephrase your question.",
                technical_details=str(exception),
                retry_suggested=True
            )
        
        # HTTP 500+ - Server errors
        elif any(code in error_str for code in ["500", "502", "503", "504", "server error", "internal error"]):
            return ErrorInfo(
                error_type="SERVER_ERROR",
                user_message_fr=f"Erreur temporaire du service {provider_name}. Veuillez réessayer dans quelques instants.",
                user_message_en=f"Temporary {provider_name} service error. Please try again in a few moments.",
                technical_details=str(exception),
                retry_suggested=True
            )
        
        # Network/Connection errors
        elif any(term in error_str for term in ["timeout", "connection", "network", "host", "resolve"]):
            return ErrorInfo(
                error_type="NETWORK_ERROR",
                user_message_fr=f"Problème de connexion avec {provider_name}. Vérifiez votre connexion internet et réessayez.",
                user_message_en=f"Connection issue with {provider_name}. Check your internet connection and try again.",
                technical_details=str(exception),
                retry_suggested=True
            )
        
        # Quota/Billing errors
        elif any(term in error_str for term in ["quota", "billing", "insufficient", "limit exceeded"]):
            return ErrorInfo(
                error_type="QUOTA_ERROR",
                user_message_fr=f"Quota ou limite de {provider_name} atteint. Veuillez contacter l'administrateur.",
                user_message_en=f"{provider_name} quota or limit reached. Please contact the administrator.",
                technical_details=str(exception),
                contact_support=True
            )
        
        # Content filtering
        elif any(term in error_str for term in ["content", "filter", "policy", "moderation"]):
            return ErrorInfo(
                error_type="CONTENT_FILTERED",
                user_message_fr="Votre demande a été filtrée par les politiques de contenu. Veuillez reformuler votre question.",
                user_message_en="Your request was filtered by content policies. Please rephrase your question.",
                technical_details=str(exception),
                retry_suggested=True
            )
        
        # Generic fallback
        else:
            return ErrorInfo(
                error_type="UNKNOWN_ERROR",
                user_message_fr=f"Erreur inattendue avec {provider_name}. Veuillez réessayer ou contacter l'administrateur si le problème persiste.",
                user_message_en=f"Unexpected error with {provider_name}. Please try again or contact the administrator if the problem persists.",
                technical_details=str(exception),
                retry_suggested=True,
                contact_support=True
            )

    @staticmethod
    def get_user_message(error_info: ErrorInfo, language: str = "fr") -> str:
        """
        Get the appropriate user message based on language preference.
        
        Args:
            error_info: ErrorInfo object with localized messages
            language: Language code ("fr" or "en")
            
        Returns:
            User-friendly error message in the requested language
        """
        if language.lower() == "en":
            return error_info.user_message_en
        else:
            return error_info.user_message_fr

    @staticmethod
    def handle_provider_error(
        exception: Exception, 
        provider_name: str, 
        language: str = "fr"
    ) -> Tuple[str, int]:
        """
        Handle a provider error and return appropriate response.
        
        Args:
            exception: The exception that occurred
            provider_name: Name of the LLM provider
            language: Language for user message
            
        Returns:
            Tuple of (user_message, http_status_code)
        """
        error_info = LLMProviderErrorHandler.classify_error(exception, provider_name)
        user_message = LLMProviderErrorHandler.get_user_message(error_info, language)
        
        # Log technical details for debugging
        logger = logging.getLogger("LLMProviderErrorHandler")
        logger.error(f"Provider {provider_name} error [{error_info.error_type}]: {error_info.technical_details}")
        
        # Determine HTTP status code based on error type
        status_code_map = {
            "RATE_LIMITED": 429,
            "AUTHENTICATION_ERROR": 401,
            "BAD_REQUEST": 400,
            "SERVER_ERROR": 502,
            "NETWORK_ERROR": 503,
            "QUOTA_ERROR": 402,
            "CONTENT_FILTERED": 400,
            "UNKNOWN_ERROR": 500
        }
        
        status_code = status_code_map.get(error_info.error_type, 500)
        
        return user_message, status_code

    @staticmethod
    def create_provider_error_response(
        exception: Exception,
        provider_name: str,
        language: str = "fr"
    ) -> Dict:
        """
        Create a standardized error response for API consumption.
        
        Args:
            exception: The exception that occurred
            provider_name: Name of the LLM provider
            language: Language for user message
            
        Returns:
            Dictionary with error information
        """
        error_info = LLMProviderErrorHandler.classify_error(exception, provider_name)
        user_message = LLMProviderErrorHandler.get_user_message(error_info, language)
        
        return {
            "error": user_message,
            "error_type": error_info.error_type,
            "provider": provider_name,
            "retry_suggested": error_info.retry_suggested,
            "contact_support": error_info.contact_support,
            "technical_details": error_info.technical_details if logging.getLogger().level <= logging.DEBUG else None
        }


def wrap_provider_exceptions(provider_name: str):
    """
    Decorator to wrap provider methods and handle exceptions consistently.
    
    Args:
        provider_name: Name of the LLM provider
        
    Returns:
        Decorator function
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Convert to LLMProviderRequestError with enhanced error info
                error_info = LLMProviderErrorHandler.classify_error(e, provider_name)
                user_message = LLMProviderErrorHandler.get_user_message(error_info)
                
                # Raise as LLMProviderRequestError with user-friendly message
                raise LLMProviderRequestError(f"{user_message} (Technical: {error_info.technical_details})")
        
        return wrapper
    return decorator