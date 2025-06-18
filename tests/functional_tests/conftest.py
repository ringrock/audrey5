"""
Configuration pytest pour les tests fonctionnels.
"""
import pytest
import asyncio
import os
import sys
from pathlib import Path

# Ajouter le répertoire racine au path pour les imports
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.llm_providers import LLMProviderFactory


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(params=["AZURE_OPENAI", "CLAUDE", "OPENAI_DIRECT", "MISTRAL", "GEMINI"])
def llm_provider_type(request):
    """Fixture qui retourne tous les types de LLM supportés."""
    return request.param


@pytest.fixture(params=["CLAUDE", "GEMINI", "OPENAI_DIRECT"])
def image_llm_provider_type(request):
    """Fixture qui retourne seulement les LLM supportant les images."""
    return request.param


@pytest.fixture
def llm_provider(llm_provider_type):
    """Fixture qui créé une instance du provider LLM."""
    try:
        provider = LLMProviderFactory.create_provider(llm_provider_type)
        return provider
    except Exception as e:
        pytest.skip(f"Provider {llm_provider_type} non disponible: {e}")


@pytest.fixture
def image_llm_provider(image_llm_provider_type):
    """Fixture qui créé une instance du provider LLM supportant les images."""
    try:
        provider = LLMProviderFactory.create_provider(image_llm_provider_type)
        return provider
    except Exception as e:
        pytest.skip(f"Provider {image_llm_provider_type} non disponible: {e}")


@pytest.fixture
def test_messages_simple():
    """Messages de test simples pour les tests de base."""
    return [
        {"role": "user", "content": "Qui es-tu ?"}
    ]


@pytest.fixture  
def test_messages_english():
    """Messages de test en anglais."""
    return [
        {"role": "user", "content": "Who are you?"}
    ]


@pytest.fixture
def test_messages_poem_italian():
    """Messages pour test de question technique en italien."""
    return [
        {"role": "user", "content": "Come posso configurare le funzionalità di QualitySaaS per il mio team?"}
    ]


@pytest.fixture
def test_messages_search_french():
    """Messages pour test de recherche Azure AI Search en français."""
    return [
        {"role": "user", "content": "Quelles sont les nouveautés des release notes ?"}
    ]


@pytest.fixture
def test_messages_search_spanish():
    """Messages pour test de recherche Azure AI Search en espagnol."""
    return [
        {"role": "user", "content": "¿Cuáles son las novedades de las notas de versión?"}
    ]


@pytest.fixture
def test_messages_italian_technical():
    """Messages pour test de question technique en italien."""
    return [
        {"role": "user", "content": "Come faccio a configurare questa funzione in QualitySaaS?"}
    ]


@pytest.fixture
def response_sizes():
    """Tailles de réponse à tester."""
    return ["veryShort", "normal", "comprehensive"]


@pytest.fixture
def document_counts():
    """Nombres de documents à tester."""
    return [2, 6, 12]


def pytest_configure(config):
    """Configuration globale pytest."""
    # Ajouter des markers personnalisés
    config.addinivalue_line(
        "markers", "language: tests de langue et localisation"
    )
    config.addinivalue_line(
        "markers", "search: tests Azure AI Search"
    )
    config.addinivalue_line(
        "markers", "response_length: tests de longueur de réponse"
    )
    config.addinivalue_line(
        "markers", "document_count: tests de nombre de documents"
    )
    config.addinivalue_line(
        "markers", "slow: tests lents"
    )
    config.addinivalue_line(
        "markers", "image: tests d'analyse d'images"
    )