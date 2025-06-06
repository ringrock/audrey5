"""
Internationalization (i18n) module for multilingual support.

This module centralizes all translations and localized messages used across
LLM providers, eliminating code duplication and making it easy to add new
languages or modify existing translations.

Key features:
- Centralized translation dictionaries
- Consistent fallback to English
- Easy extensibility for new languages
- Type-safe translation functions
"""

from typing import Dict, Optional
from enum import Enum


class SupportedLanguage(Enum):
    """Enumeration of supported languages with their ISO 639-1 codes."""
    FRENCH = "fr"
    ENGLISH = "en"
    SPANISH = "es"
    PORTUGUESE = "pt"
    ITALIAN = "it"
    GERMAN = "de"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    ARABIC = "ar"
    RUSSIAN = "ru"
    HINDI = "hi"
    DUTCH = "nl"
    SWEDISH = "sv"
    DANISH = "da"
    NORWEGIAN = "no"
    FINNISH = "fi"
    POLISH = "pl"
    CZECH = "cs"
    TURKISH = "tr"
    THAI = "th"
    VIETNAMESE = "vi"


class TranslationKey(Enum):
    """Enumeration of translation keys used across the application."""
    DOCUMENTS_HEADER = "documents_header"
    USER_QUESTION_PREFIX = "user_question_prefix"
    HELP_REQUEST = "help_request"


# Centralized translation dictionaries
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    TranslationKey.DOCUMENTS_HEADER.value: {
        SupportedLanguage.FRENCH.value: "Documents disponibles :",
        SupportedLanguage.ENGLISH.value: "Available documents:",
        SupportedLanguage.SPANISH.value: "Documentos disponibles:",
        SupportedLanguage.PORTUGUESE.value: "Documentos disponíveis:",
        SupportedLanguage.ITALIAN.value: "Documenti disponibili:",
        SupportedLanguage.GERMAN.value: "Verfügbare Dokumente:",
        SupportedLanguage.CHINESE.value: "可用文档：",
        SupportedLanguage.JAPANESE.value: "利用可能な文書：",
        SupportedLanguage.KOREAN.value: "사용 가능한 문서:",
        SupportedLanguage.ARABIC.value: "الوثائق المتاحة:",
        SupportedLanguage.RUSSIAN.value: "Доступные документы:",
        SupportedLanguage.HINDI.value: "उपलब्ध दस्तावेज़:",
        SupportedLanguage.DUTCH.value: "Beschikbare documenten:",
        SupportedLanguage.SWEDISH.value: "Tillgängliga dokument:",
        SupportedLanguage.DANISH.value: "Tilgængelige dokumenter:",
        SupportedLanguage.NORWEGIAN.value: "Tilgjengelige dokumenter:",
        SupportedLanguage.FINNISH.value: "Saatavilla olevat asiakirjat:",
        SupportedLanguage.POLISH.value: "Dostępne dokumenty:",
        SupportedLanguage.CZECH.value: "Dostupné dokumenty:",
        SupportedLanguage.TURKISH.value: "Mevcut belgeler:",
        SupportedLanguage.THAI.value: "เอกสารที่มีอยู่:",
        SupportedLanguage.VIETNAMESE.value: "Tài liệu có sẵn:"
    },
    
    TranslationKey.USER_QUESTION_PREFIX.value: {
        SupportedLanguage.FRENCH.value: "Question de l'utilisateur :",
        SupportedLanguage.ENGLISH.value: "User question:",
        SupportedLanguage.SPANISH.value: "Pregunta del usuario:",
        SupportedLanguage.PORTUGUESE.value: "Pergunta do usuário:",
        SupportedLanguage.ITALIAN.value: "Domanda dell'utente:",
        SupportedLanguage.GERMAN.value: "Benutzerfrage:",
        SupportedLanguage.CHINESE.value: "用户问题：",
        SupportedLanguage.JAPANESE.value: "ユーザーの質問：",
        SupportedLanguage.KOREAN.value: "사용자 질문:",
        SupportedLanguage.ARABIC.value: "سؤال المستخدم:",
        SupportedLanguage.RUSSIAN.value: "Вопрос пользователя:",
        SupportedLanguage.HINDI.value: "उपयोगकर्ता का प्रश्न:",
        SupportedLanguage.DUTCH.value: "Gebruikersvraag:",
        SupportedLanguage.SWEDISH.value: "Användarfråga:",
        SupportedLanguage.DANISH.value: "Brugerspørgsmål:",
        SupportedLanguage.NORWEGIAN.value: "Brukerspørsmål:",
        SupportedLanguage.FINNISH.value: "Käyttäjän kysymys:",
        SupportedLanguage.POLISH.value: "Pytanie użytkownika:",
        SupportedLanguage.CZECH.value: "Otázka uživatele:",
        SupportedLanguage.TURKISH.value: "Kullanıcı sorusu:",
        SupportedLanguage.THAI.value: "คำถามของผู้ใช้:",
        SupportedLanguage.VIETNAMESE.value: "Câu hỏi của người dùng:"
    },
    
    TranslationKey.HELP_REQUEST.value: {
        SupportedLanguage.FRENCH.value: "Veuillez m'aider avec la question suivante.",
        SupportedLanguage.ENGLISH.value: "Please help me with the following question.",
        SupportedLanguage.SPANISH.value: "Por favor ayúdame con la siguiente pregunta.",
        SupportedLanguage.PORTUGUESE.value: "Por favor me ajude com a seguinte pergunta.",
        SupportedLanguage.ITALIAN.value: "Per favore aiutami con la seguente domanda.",
        SupportedLanguage.GERMAN.value: "Bitte hilf mir mit der folgenden Frage.",
        SupportedLanguage.CHINESE.value: "请帮我解答以下问题。",
        SupportedLanguage.JAPANESE.value: "以下の質問についてお手伝いください。",
        SupportedLanguage.KOREAN.value: "다음 질문에 대해 도움을 주세요.",
        SupportedLanguage.ARABIC.value: "من فضلك ساعدني في السؤال التالي.",
        SupportedLanguage.RUSSIAN.value: "Пожалуйста, помогите мне с следующим вопросом.",
        SupportedLanguage.HINDI.value: "कृपया निम्नलिखित प्रश्न में मेरी सहायता करें।",
        SupportedLanguage.DUTCH.value: "Help me alsjeblieft met de volgende vraag.",
        SupportedLanguage.SWEDISH.value: "Hjälp mig med följande fråga.",
        SupportedLanguage.DANISH.value: "Hjælp mig venligst med følgende spørgsmål.",
        SupportedLanguage.NORWEGIAN.value: "Vennligst hjelp meg med følgende spørsmål.",
        SupportedLanguage.FINNISH.value: "Auta minua seuraavassa kysymyksessä.",
        SupportedLanguage.POLISH.value: "Proszę pomóż mi z następującym pytaniem.",
        SupportedLanguage.CZECH.value: "Prosím pomozte mi s následující otázkou.",
        SupportedLanguage.TURKISH.value: "Lütfen aşağıdaki soruyla ilgili yardım edin.",
        SupportedLanguage.THAI.value: "กรุณาช่วยฉันกับคำถามต่อไปนี้",
        SupportedLanguage.VIETNAMESE.value: "Vui lòng giúp tôi với câu hỏi sau."
    }
}


def get_translation(key: TranslationKey, language_code: str) -> str:
    """
    Get a translation for the specified key and language.
    
    Args:
        key: The translation key to look up
        language_code: Two-letter language code (ISO 639-1)
        
    Returns:
        Translated string, or English fallback if translation not found
        
    Example:
        >>> get_translation(TranslationKey.DOCUMENTS_HEADER, "fr")
        "Documents disponibles :"
    """
    translations = TRANSLATIONS.get(key.value, {})
    return translations.get(language_code, translations.get(SupportedLanguage.ENGLISH.value, ""))


def get_documents_header(language_code: str) -> str:
    """Get the localized 'Available documents' header."""
    return get_translation(TranslationKey.DOCUMENTS_HEADER, language_code)


def get_user_question_prefix(language_code: str) -> str:
    """Get the localized 'User question' prefix."""
    return get_translation(TranslationKey.USER_QUESTION_PREFIX, language_code)


def get_help_request(language_code: str) -> str:
    """Get the localized help request message."""
    return get_translation(TranslationKey.HELP_REQUEST, language_code)


def is_language_supported(language_code: str) -> bool:
    """
    Check if a language is supported.
    
    Args:
        language_code: Two-letter language code
        
    Returns:
        True if the language is supported, False otherwise
    """
    return any(lang.value == language_code for lang in SupportedLanguage)


def get_supported_languages() -> Dict[str, str]:
    """
    Get a dictionary of supported languages with their full names.
    
    Returns:
        Dictionary mapping language codes to language names
    """
    return {
        SupportedLanguage.FRENCH.value: "Français",
        SupportedLanguage.ENGLISH.value: "English", 
        SupportedLanguage.SPANISH.value: "Español",
        SupportedLanguage.PORTUGUESE.value: "Português",
        SupportedLanguage.ITALIAN.value: "Italiano",
        SupportedLanguage.GERMAN.value: "Deutsch",
        SupportedLanguage.CHINESE.value: "中文",
        SupportedLanguage.JAPANESE.value: "日本語",
        SupportedLanguage.KOREAN.value: "한국어",
        SupportedLanguage.ARABIC.value: "العربية",
        SupportedLanguage.RUSSIAN.value: "Русский",
        SupportedLanguage.HINDI.value: "हिन्दी",
        SupportedLanguage.DUTCH.value: "Nederlands",
        SupportedLanguage.SWEDISH.value: "Svenska",
        SupportedLanguage.DANISH.value: "Dansk",
        SupportedLanguage.NORWEGIAN.value: "Norsk",
        SupportedLanguage.FINNISH.value: "Suomi",
        SupportedLanguage.POLISH.value: "Polski",
        SupportedLanguage.CZECH.value: "Čeština",
        SupportedLanguage.TURKISH.value: "Türkçe",
        SupportedLanguage.THAI.value: "ไทย",
        SupportedLanguage.VIETNAMESE.value: "Tiếng Việt"
    }


def normalize_language_code(language_code: str) -> str:
    """
    Normalize language code to ensure consistency.
    
    Args:
        language_code: Language code to normalize
        
    Returns:
        Normalized two-letter language code
    """
    if not language_code:
        return SupportedLanguage.ENGLISH.value
    
    # Convert to lowercase and take first 2 characters
    normalized = language_code.lower()[:2]
    
    # Handle common variations
    language_mappings = {
        "zh-cn": SupportedLanguage.CHINESE.value,
        "zh-tw": SupportedLanguage.CHINESE.value, 
        "pt-br": SupportedLanguage.PORTUGUESE.value,
        "pt-pt": SupportedLanguage.PORTUGUESE.value,
        "en-us": SupportedLanguage.ENGLISH.value,
        "en-gb": SupportedLanguage.ENGLISH.value
    }
    
    return language_mappings.get(language_code.lower(), normalized)