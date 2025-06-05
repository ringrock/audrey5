# Architecture d'extensibilité LLM

## Vue d'ensemble

L'architecture actuelle permet d'ajouter facilement de nouveaux providers LLM grâce à plusieurs design patterns bien établis.

## Composants clés

### 1. Interface abstraite (LLMProvider)
```python
class LLMProvider(ABC):
    @abstractmethod
    async def send_request(self, messages, stream, **kwargs) -> Any:
        pass
    
    @abstractmethod
    def format_response(self, raw_response, stream) -> Dict[str, Any]:
        pass
```

### 2. Factory Pattern (LLMProviderFactory)
- Centralise la création des providers
- Permet l'ajout dynamique de nouveaux providers
- Gère la logique de sélection

### 3. Configuration modulaire
- Chaque provider a sa propre classe de settings
- Variables d'environnement préfixées (CLAUDE_, MISTRAL_, etc.)
- Validation automatique avec Pydantic

## Guide d'ajout d'un nouveau provider

### Étape 1: Créer la classe Provider

```python
class NouveauProvider(LLMProvider):
    async def init_client(self):
        # Initialiser le client API
        pass
    
    async def send_request(self, messages, stream=True, **kwargs):
        # Implémenter l'appel API
        # Gérer streaming et non-streaming
        pass
    
    def format_response(self, raw_response, stream=True):
        # Convertir au format OpenAI
        pass
```

### Étape 2: Ajouter les settings

```python
class _NouveauProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOUVEAU_",
        env_file=DOTENV_PATH
    )
    
    api_key: Optional[str] = None
    model: str = "default-model"
    # Autres paramètres...
```

### Étape 3: Mettre à jour la Factory

```python
# Dans LLMProviderFactory.create_provider()
elif provider_type == "NOUVEAU":
    return NouveauProvider()
```

### Étape 4: Configuration Frontend

Ajouter l'option dans `CustomizationPanel.tsx`:
```typescript
const llmProviderOptions: IChoiceGroupOption[] = [
    { key: 'AZURE_OPENAI', text: 'Azure OpenAI' },
    { key: 'CLAUDE', text: 'Claude AI' },
    { key: 'NOUVEAU', text: 'Nouveau Provider' }
]
```

### Étape 5: Documentation

Mettre à jour `.env.sample` et `README.md` avec les nouvelles variables.

## Exemples de providers additionnels

### Mistral AI
- API compatible OpenAI
- Streaming natif
- Support des fonctions

### Google Gemini
- Format de messages différent
- Nécessite conversion des rôles
- Gestion spéciale du streaming

### OpenAI Direct
- Utilise le SDK OpenAI officiel
- Pas de conversion nécessaire
- Support complet des fonctionnalités

## Capacités par provider

| Provider | Functions | Data Sources | Streaming | Embeddings | Max Context |
|----------|-----------|--------------|-----------|------------|-------------|
| Azure OpenAI | ✅ | ✅ | ✅ | ✅ | 128K |
| Claude | ❌ | ❌ | ✅ | ❌ | 200K |
| Mistral | ✅ | ❌ | ✅ | ✅ | 32K |
| Gemini | ✅ | ❌ | ✅ | ❌ | 1M |
| OpenAI Direct | ✅ | ❌ | ✅ | ✅ | 128K |

## Considérations importantes

### 1. Homogénéisation des réponses
- Tous les providers doivent retourner le format OpenAI
- Permet au frontend de rester agnostique
- Simplifie la maintenance

### 2. Gestion des erreurs
- Chaque provider doit gérer ses propres erreurs
- Conversion en format d'erreur standard
- Retry logic si nécessaire

### 3. Rate limiting
- Implémenter au niveau du provider
- Respecter les limites de chaque API
- Backoff exponentiel recommandé

### 4. Coûts et quotas
- Documenter les coûts par provider
- Implémenter des alertes de quota
- Possibilité de fallback entre providers

## Améliorations futures possibles

1. **Provider Chain**: Fallback automatique entre providers
2. **Load Balancing**: Répartition entre plusieurs providers
3. **Caching**: Cache des réponses pour économiser les appels
4. **Métriques**: Suivi des performances par provider
5. **A/B Testing**: Comparaison des providers en production

## Conclusion

L'architecture actuelle est bien conçue pour l'extensibilité. L'ajout de nouveaux providers est simple et ne nécessite pas de modifications majeures du code existant. Le pattern Factory et l'interface abstraite garantissent une séparation claire des responsabilités.