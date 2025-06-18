"""
Tests fonctionnels pour l'application AskMe avec support multi-LLM.

Ce module contient les tests fonctionnels qui vérifient le comportement 
de l'application avec tous les LLM supportés :
- AZURE_OPENAI
- CLAUDE  
- OPENAI_DIRECT
- MISTRAL
- GEMINI

Les tests incluent :
- Tests de langue (français, anglais, italien)
- Tests Azure AI Search avec citations
- Tests de longueur de réponse (short, medium, long)
- Tests de nombre de documents retournés
"""