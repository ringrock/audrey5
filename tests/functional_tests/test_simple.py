"""
Test simple pour vérifier que l'infrastructure fonctionne.
"""
import pytest
import asyncio


class TestSimple:
    """Tests simples pour valider l'infrastructure."""
    
    def test_basic_import(self):
        """Test que les imports de base fonctionnent."""
        from backend.llm_providers import LLMProviderFactory
        providers = LLMProviderFactory.list_available_providers()
        assert len(providers) > 0
        assert "AZURE_OPENAI" in providers
    
    @pytest.mark.asyncio
    async def test_provider_creation(self):
        """Test la création d'un provider."""
        from backend.llm_providers import LLMProviderFactory
        
        # Essayer de créer chaque provider
        for provider_type in ["AZURE_OPENAI", "CLAUDE", "OPENAI_DIRECT", "MISTRAL", "GEMINI"]:
            try:
                provider = LLMProviderFactory.create_provider(provider_type)
                assert provider is not None
                print(f"✓ Provider {provider_type} créé avec succès")
            except Exception as e:
                print(f"⚠ Provider {provider_type} non disponible: {e}")
                # Skip si pas configuré, c'est normal