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
    DEFAULT_SYSTEM_MESSAGE = "default_system_message"
    EMERGENCY_KEYWORDS = "emergency_keywords"
    IMAGE_TOO_LARGE = "image_too_large"
    IMAGE_FORMAT_UNSUPPORTED = "image_format_unsupported"
    MODEL_NAME_NOT_CONFIGURED = "model_name_not_configured"
    MODEL_NO_IMAGE_SUPPORT = "model_no_image_support"
    MODEL_VISION_DETECTED = "model_vision_detected"


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
    },
    
    TranslationKey.DEFAULT_SYSTEM_MESSAGE.value: {
        SupportedLanguage.FRENCH.value: "Tu es un assistant IA serviable et précis.",
        SupportedLanguage.ENGLISH.value: "You are a helpful and accurate AI assistant.",
        SupportedLanguage.SPANISH.value: "Eres un asistente de IA útil y preciso.",
        SupportedLanguage.PORTUGUESE.value: "Você é um assistente de IA útil e preciso.",
        SupportedLanguage.ITALIAN.value: "Sei un assistente IA utile e preciso.",
        SupportedLanguage.GERMAN.value: "Du bist ein hilfreicher und genauer KI-Assistent.",
        SupportedLanguage.CHINESE.value: "你是一个有用且准确的AI助手。",
        SupportedLanguage.JAPANESE.value: "あなたは有用で正確なAIアシスタントです。",
        SupportedLanguage.KOREAN.value: "당신은 도움이 되고 정확한 AI 어시스턴트입니다.",
        SupportedLanguage.ARABIC.value: "أنت مساعد ذكي مفيد ودقيق.",
        SupportedLanguage.RUSSIAN.value: "Вы полезный и точный ИИ-помощник.",
        SupportedLanguage.HINDI.value: "आप एक सहायक और सटीक AI सहायक हैं।",
        SupportedLanguage.DUTCH.value: "Je bent een behulpzame en nauwkeurige AI-assistent.",
        SupportedLanguage.SWEDISH.value: "Du är en hjälpsam och noggrann AI-assistent.",
        SupportedLanguage.DANISH.value: "Du er en hjælpsom og præcis AI-assistent.",
        SupportedLanguage.NORWEGIAN.value: "Du er en hjelpsom og nøyaktig AI-assistent.",
        SupportedLanguage.FINNISH.value: "Olet avulias ja tarkka tekoälyavustaja.",
        SupportedLanguage.POLISH.value: "Jesteś pomocnym i dokładnym asystentem AI.",
        SupportedLanguage.CZECH.value: "Jste užitečný a přesný AI asistent.",
        SupportedLanguage.TURKISH.value: "Yardımcı ve doğru bir AI asistanısınız.",
        SupportedLanguage.THAI.value: "คุณเป็นผู้ช่วย AI ที่มีประโยชน์และแม่นยำ",
        SupportedLanguage.VIETNAMESE.value: "Bạn là một trợ lý AI hữu ích và chính xác."
    },
    
    TranslationKey.EMERGENCY_KEYWORDS.value: {
        SupportedLanguage.FRENCH.value: "incendie feu moteur avion procédure urgence sécurité",
        SupportedLanguage.ENGLISH.value: "fire engine aircraft procedure emergency safety",
        SupportedLanguage.SPANISH.value: "incendio fuego motor avión procedimiento emergencia seguridad",
        SupportedLanguage.PORTUGUESE.value: "incêndio fogo motor avião procedimento emergência segurança",
        SupportedLanguage.ITALIAN.value: "incendio fuoco motore aereo procedura emergenza sicurezza",
        SupportedLanguage.GERMAN.value: "brand feuer motor flugzeug verfahren notfall sicherheit",
        SupportedLanguage.CHINESE.value: "火灾 发动机 飞机 程序 紧急情况 安全",
        SupportedLanguage.JAPANESE.value: "火災 エンジン 航空機 手順 緊急事態 安全",
        SupportedLanguage.KOREAN.value: "화재 엔진 항공기 절차 응급상황 안전",
        SupportedLanguage.ARABIC.value: "حريق محرك طائرة إجراء طوارئ أمان",
        SupportedLanguage.RUSSIAN.value: "пожар двигатель самолет процедура аварийная ситуация безопасность",
        SupportedLanguage.HINDI.value: "आग इंजन विमान प्रक्रिया आपातकाल सुरक्षा",
        SupportedLanguage.DUTCH.value: "brand vuur motor vliegtuig procedure noodgeval veiligheid",
        SupportedLanguage.SWEDISH.value: "brand eld motor flygplan procedur nödsituation säkerhet",
        SupportedLanguage.DANISH.value: "brand ild motor fly procedure nødsituation sikkerhed",
        SupportedLanguage.NORWEGIAN.value: "brann ild motor fly prosedyre nødsituasjon sikkerhet",
        SupportedLanguage.FINNISH.value: "tulipalo tuli moottori lentokone menettely hätätilanne turvallisuus",
        SupportedLanguage.POLISH.value: "pożar ogień silnik samolot procedura nagły wypadek bezpieczeństwo",
        SupportedLanguage.CZECH.value: "požár oheň motor letadlo postup nouzová situace bezpečnost",
        SupportedLanguage.TURKISH.value: "yangın ateş motor uçak prosedür acil durum güvenlik",
        SupportedLanguage.THAI.value: "ไฟไหม้ เครื่องยนต์ เครื่องบิน ขั้นตอน เหตุฉุกเฉิน ความปลอดภัย",
        SupportedLanguage.VIETNAMESE.value: "cháy lửa động cơ máy bay quy trình khẩn cấp an toàn"
    },
    
    TranslationKey.IMAGE_TOO_LARGE.value: {
        SupportedLanguage.FRENCH.value: "Image trop volumineuse: {data_size} caractères. Limite: ~20MB.",
        SupportedLanguage.ENGLISH.value: "Image too large: {data_size} characters. Limit: ~20MB.",
        SupportedLanguage.ITALIAN.value: "Immagine troppo grande: {data_size} caratteri. Limite: ~20MB.",
        SupportedLanguage.SPANISH.value: "Imagen demasiado grande: {data_size} caracteres. Límite: ~20MB.",
        SupportedLanguage.GERMAN.value: "Bild zu groß: {data_size} Zeichen. Limit: ~20MB.",
        SupportedLanguage.PORTUGUESE.value: "Imagem muito grande: {data_size} caracteres. Limite: ~20MB."
    },
    
    TranslationKey.IMAGE_FORMAT_UNSUPPORTED.value: {
        SupportedLanguage.FRENCH.value: "Format d'image non supporté: {format}. Formats supportés: {supported}",
        SupportedLanguage.ENGLISH.value: "Unsupported image format: {format}. Supported formats: {supported}",
        SupportedLanguage.ITALIAN.value: "Formato immagine non supportato: {format}. Formati supportati: {supported}",
        SupportedLanguage.SPANISH.value: "Formato de imagen no compatible: {format}. Formatos compatibles: {supported}",
        SupportedLanguage.GERMAN.value: "Nicht unterstütztes Bildformat: {format}. Unterstützte Formate: {supported}",
        SupportedLanguage.PORTUGUESE.value: "Formato de imagem não suportado: {format}. Formatos suportados: {supported}"
    },
    
    TranslationKey.MODEL_NAME_NOT_CONFIGURED.value: {
        SupportedLanguage.FRENCH.value: "Nom de modèle non configuré. Déploiement utilisé: '{deployment}'. Support d'images assumé.",
        SupportedLanguage.ENGLISH.value: "Model name not configured. Using deployment: '{deployment}'. Image support assumed.",
        SupportedLanguage.ITALIAN.value: "Nome modello non configurato. Usando deployment: '{deployment}'. Supporto immagini assunto.",
        SupportedLanguage.SPANISH.value: "Nombre de modelo no configurado. Usando despliegue: '{deployment}'. Soporte de imágenes asumido.",
        SupportedLanguage.GERMAN.value: "Modellname nicht konfiguriert. Verwende Deployment: '{deployment}'. Bildunterstützung angenommen.",
        SupportedLanguage.PORTUGUESE.value: "Nome do modelo não configurado. Usando deployment: '{deployment}'. Suporte a imagens assumido."
    },
    
    TranslationKey.MODEL_NO_IMAGE_SUPPORT.value: {
        SupportedLanguage.FRENCH.value: "Le modèle '{model}' ne supporte pas les images. Utilisez un modèle vision.",
        SupportedLanguage.ENGLISH.value: "Model '{model}' does not support images. Use a vision model.",
        SupportedLanguage.ITALIAN.value: "Il modello '{model}' non supporta le immagini. Usa un modello di visione.",
        SupportedLanguage.SPANISH.value: "El modelo '{model}' no admite imágenes. Use un modelo de visión.",
        SupportedLanguage.GERMAN.value: "Modell '{model}' unterstützt keine Bilder. Verwenden Sie ein Vision-Modell.",
        SupportedLanguage.PORTUGUESE.value: "O modelo '{model}' não suporta imagens. Use um modelo de visão."
    },
    
    TranslationKey.MODEL_VISION_DETECTED.value: {
        SupportedLanguage.FRENCH.value: "Modèle vision détecté: '{model}'. Support d'images confirmé.",
        SupportedLanguage.ENGLISH.value: "Vision model detected: '{model}'. Image support confirmed.",
        SupportedLanguage.ITALIAN.value: "Modello di visione rilevato: '{model}'. Supporto immagini confermato.",
        SupportedLanguage.SPANISH.value: "Modelo de visión detectado: '{model}'. Soporte de imágenes confirmado.",
        SupportedLanguage.GERMAN.value: "Vision-Modell erkannt: '{model}'. Bildunterstützung bestätigt.",
        SupportedLanguage.PORTUGUESE.value: "Modelo de visão detectado: '{model}'. Suporte a imagens confirmado."
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


def get_default_system_message(language_code: str) -> str:
    """Get the localized default system message."""
    return get_translation(TranslationKey.DEFAULT_SYSTEM_MESSAGE, language_code)


def get_emergency_keywords(language_code: str) -> str:
    """Get the localized emergency keywords for search enhancement."""
    return get_translation(TranslationKey.EMERGENCY_KEYWORDS, language_code)


def get_image_too_large_message(language_code: str, data_size: int) -> str:
    """Get the localized image too large error message."""
    template = get_translation(TranslationKey.IMAGE_TOO_LARGE, language_code)
    return template.format(data_size=data_size)


def get_image_format_unsupported_message(language_code: str, format_name: str, supported_formats: list) -> str:
    """Get the localized unsupported image format error message."""
    template = get_translation(TranslationKey.IMAGE_FORMAT_UNSUPPORTED, language_code)
    return template.format(format=format_name, supported=supported_formats)


def get_model_name_not_configured_message(language_code: str, deployment_name: str) -> str:
    """Get the localized model name not configured warning message."""
    template = get_translation(TranslationKey.MODEL_NAME_NOT_CONFIGURED, language_code)
    return template.format(deployment=deployment_name)


def get_model_no_image_support_message(language_code: str, model_name: str) -> str:
    """Get the localized model no image support error message."""
    template = get_translation(TranslationKey.MODEL_NO_IMAGE_SUPPORT, language_code)
    return template.format(model=model_name)


def get_model_vision_detected_message(language_code: str, model_name: str) -> str:
    """Get the localized vision model detected message."""
    template = get_translation(TranslationKey.MODEL_VISION_DETECTED, language_code)
    return template.format(model=model_name)


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