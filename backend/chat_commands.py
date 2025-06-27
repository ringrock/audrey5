"""
Module de gestion des commandes de chat pour AskMe
Permet aux utilisateurs de modifier les paramètres directement depuis le chat.
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum

class CommandType(Enum):
    """Types de commandes supportées"""
    CHANGE_LLM = "change_llm"
    SET_DOCUMENTS_COUNT = "set_documents_count"
    SET_RESPONSE_LENGTH = "set_response_length"
    NEW_CONVERSATION = "new_conversation"
    CLEAR_CONVERSATION = "clear_conversation"
    UNKNOWN = "unknown"

class ResponseLength(Enum):
    """Types de longueur de réponse"""
    VERY_SHORT = "VERY_SHORT"
    NORMAL = "NORMAL" 
    COMPREHENSIVE = "COMPREHENSIVE"

class ChatCommand:
    """Représente une commande de chat parsée"""
    
    def __init__(self, command_type: CommandType, parameters: Dict[str, Any] = None, 
                 original_text: str = "", confidence: float = 1.0):
        self.command_type = command_type
        self.parameters = parameters or {}
        self.original_text = original_text
        self.confidence = confidence

class ChatCommandParser:
    """Parser pour les commandes de chat"""
    
    def __init__(self):
        # Dictionnaire des providers LLM supportés
        self.llm_providers = {
            'azure': 'AZURE_OPENAI',
            'azure openai': 'AZURE_OPENAI',
            'openai': 'AZURE_OPENAI',
            'claude': 'CLAUDE',
            'anthropic': 'CLAUDE',
            'openai direct': 'OPENAI_DIRECT',
            'openai-direct': 'OPENAI_DIRECT',
            'open a i direct': 'OPENAI_DIRECT',
            'open ai direct': 'OPENAI_DIRECT',
            'open a i': 'OPENAI_DIRECT',
            'open ai': 'OPENAI_DIRECT',
            'mistral': 'MISTRAL',
            'gemini': 'GEMINI',
            'google': 'GEMINI'
        }
        
        # Dictionnaire des types de réponses (ordre important pour regex)
        self.response_lengths = {
            'très courtes': ResponseLength.VERY_SHORT,
            'très courte': ResponseLength.VERY_SHORT,
            'très court': ResponseLength.VERY_SHORT,
            'courtes': ResponseLength.VERY_SHORT,
            'courte': ResponseLength.VERY_SHORT,
            'court': ResponseLength.VERY_SHORT,
            'brèves': ResponseLength.VERY_SHORT,
            'brève': ResponseLength.VERY_SHORT,
            'bref': ResponseLength.VERY_SHORT,
            'short': ResponseLength.VERY_SHORT,
            'normal': ResponseLength.NORMAL,
            'normale': ResponseLength.NORMAL,
            'normales': ResponseLength.NORMAL,
            'standard': ResponseLength.NORMAL,
            'moyen': ResponseLength.NORMAL,
            'moyenne': ResponseLength.NORMAL,
            'moyennes': ResponseLength.NORMAL,
            'long': ResponseLength.COMPREHENSIVE,
            'longue': ResponseLength.COMPREHENSIVE,
            'longues': ResponseLength.COMPREHENSIVE,
            'détaillé': ResponseLength.COMPREHENSIVE,
            'détaillée': ResponseLength.COMPREHENSIVE,
            'détaillées': ResponseLength.COMPREHENSIVE,
            'complet': ResponseLength.COMPREHENSIVE,
            'complète': ResponseLength.COMPREHENSIVE,
            'complètes': ResponseLength.COMPREHENSIVE,
            'comprehensive': ResponseLength.COMPREHENSIVE,
            'exhaustif': ResponseLength.COMPREHENSIVE,
            'exhaustive': ResponseLength.COMPREHENSIVE
        }
        
        # Patterns de reconnaissance des commandes
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile les patterns regex pour la reconnaissance des commandes"""
        
        # Pattern pour changement de LLM
        llm_names = '|'.join(self.llm_providers.keys())
        self.llm_pattern = re.compile(
            rf'(?:modifie|change|utilise|passe|switche?).*?(?:config|configuration|modèle|llm|provider|mode)?.*?(?:pour )?(?:utiliser )?(?:le )?(?:modèle |mode )?({llm_names})',
            re.IGNORECASE
        )
        
        # Pattern pour nombre de documents
        self.docs_pattern = re.compile(
            r'(?:modifie|change|utilise|passe|met|récupère?|et).*?(?:config|configuration)?.*?(?:pour )?(?:récupérer?|avoir|utiliser|prendre)?.*?(\d+).*?(?:doc|document|référence)',
            re.IGNORECASE
        )
        
        # Pattern pour longueur de réponse
        response_types = '|'.join(self.response_lengths.keys())
        self.response_length_pattern = re.compile(
            rf'(?:réponse|réponses).*?({response_types})',
            re.IGNORECASE
        )
        
        # Pattern pour nouvelle conversation
        self.new_conversation_pattern = re.compile(
            r'(?:crée?|génère|démarre?|commence|ouvre?).*?(?:une? )?(?:nouvelle|new).*?(?:conversation|chat|discussion)',
            re.IGNORECASE
        )
        
        # Pattern pour nettoyer/vider la conversation
        self.clear_conversation_pattern = re.compile(
            r'(?:nettoie|vide|efface|clear|reset|rase?).*?(?:la |cette )?(?:conversation|chat|discussion|historique)',
            re.IGNORECASE
        )
    
    def parse_command(self, text: str) -> Optional[ChatCommand]:
        """
        Parse le texte pour identifier une commande (pour compatibilité)
        
        Args:
            text: Le texte à analyser
            
        Returns:
            ChatCommand si une commande est détectée, None sinon
        """
        commands = self.parse_commands(text)
        return commands[0] if commands else None
        
    def parse_commands(self, text: str) -> List[ChatCommand]:
        """
        Parse le texte pour identifier toutes les commandes multiples
        
        Cette méthode permet de traiter des phrases contenant plusieurs commandes
        comme "utilise claude avec des réponses courtes et 10 documents max"
        
        Args:
            text: Le texte à analyser
            
        Returns:
            Liste des ChatCommand détectées (peut être vide si aucune commande)
        """
        text = text.strip()
        commands = []
        
        # Analyser le texte pour chaque type de commande possible
        # L'ordre n'est pas important car on collecte toutes les commandes trouvées
        
        # Changement de provider LLM (Claude, Gemini, Azure, etc.)
        command = self._try_parse_llm_change(text)
        if command:
            commands.append(command)
            
        # Modification du nombre de documents de référence
        command = self._try_parse_documents_count(text)
        if command:
            commands.append(command)
            
        # Modification de la longueur des réponses (courte, normale, détaillée)
        command = self._try_parse_response_length(text)
        if command:
            commands.append(command)
            
        # Actions spéciales : nouvelle conversation
        command = self._try_parse_new_conversation(text)
        if command:
            commands.append(command)
            
        # Actions spéciales : nettoyage de conversation
        command = self._try_parse_clear_conversation(text)
        if command:
            commands.append(command)
        
        return commands
    
    def _try_parse_llm_change(self, text: str) -> Optional[ChatCommand]:
        """Tente de parser une commande de changement de LLM"""
        match = self.llm_pattern.search(text)
        if match:
            llm_name = match.group(1).lower()
            provider = self.llm_providers.get(llm_name)
            if provider:
                return ChatCommand(
                    command_type=CommandType.CHANGE_LLM,
                    parameters={'provider': provider, 'provider_name': llm_name},
                    original_text=text,
                    confidence=0.9
                )
        return None
    
    def _try_parse_documents_count(self, text: str) -> Optional[ChatCommand]:
        """Tente de parser une commande de modification du nombre de documents"""
        match = self.docs_pattern.search(text)
        if match:
            try:
                count = int(match.group(1))
                return ChatCommand(
                    command_type=CommandType.SET_DOCUMENTS_COUNT,
                    parameters={'count': count},
                    original_text=text,
                    confidence=0.9
                )
            except ValueError:
                pass
        return None
    
    def _try_parse_response_length(self, text: str) -> Optional[ChatCommand]:
        """Tente de parser une commande de modification de la longueur de réponse"""
        match = self.response_length_pattern.search(text)
        if match:
            length_name = match.group(1).lower()
            response_length = self.response_lengths.get(length_name)
            if response_length:
                return ChatCommand(
                    command_type=CommandType.SET_RESPONSE_LENGTH,
                    parameters={'length': response_length.value, 'length_name': length_name},
                    original_text=text,
                    confidence=0.9
                )
        return None
    
    def _try_parse_new_conversation(self, text: str) -> Optional[ChatCommand]:
        """Tente de parser une commande de création de nouvelle conversation"""
        if self.new_conversation_pattern.search(text):
            return ChatCommand(
                command_type=CommandType.NEW_CONVERSATION,
                parameters={},
                original_text=text,
                confidence=0.85
            )
        return None
    
    def _try_parse_clear_conversation(self, text: str) -> Optional[ChatCommand]:
        """Tente de parser une commande de nettoyage de conversation"""
        if self.clear_conversation_pattern.search(text):
            return ChatCommand(
                command_type=CommandType.CLEAR_CONVERSATION,
                parameters={},
                original_text=text,
                confidence=0.85
            )
        return None
    
    def is_command(self, text: str) -> bool:
        """
        Vérifie si le texte contient une commande
        
        Args:
            text: Le texte à vérifier
            
        Returns:
            True si c'est une commande, False sinon
        """
        return len(self.parse_commands(text)) > 0

class ChatCommandExecutor:
    """Exécuteur des commandes de chat"""
    
    def __init__(self, app_settings):
        self.app_settings = app_settings
        
    async def execute_commands(self, commands: List[ChatCommand], user_session: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Exécute plusieurs commandes de chat en une seule opération
        
        Cette méthode permet de traiter des commandes multiples comme :
        "utilise claude avec des réponses courtes et 10 documents max"
        
        Args:
            commands: Liste des commandes à exécuter
            user_session: Session utilisateur pour stocker les préférences (modifiée in-place)
            
        Returns:
            Dictionnaire avec le résultat de l'exécution combinée contenant :
            - success: True si au moins une commande a réussi
            - message: Message combiné de toutes les commandes réussies
            - command_type: 'multiple_commands'
            - user_session: Session mise à jour avec toutes les préférences
            - action: Action spéciale si présente (new_conversation, clear_conversation)
        """
        if not commands:
            return {'success': False, 'message': 'Aucune commande à exécuter'}
        
        if user_session is None:
            user_session = {}
        
        results = []
        combined_actions = []
        
        # Exécuter chaque commande individuellement en utilisant la même session
        # Cela permet d'accumuler tous les changements de paramètres
        for command in commands:
            result = await self.execute_command(command, user_session)
            results.append(result)
            
            # Conserver les actions spéciales (nouvelle conversation, nettoyage)
            if result.get('action'):
                combined_actions.append(result['action'])
        
        # Analyser les résultats pour créer une réponse unifiée
        successful_commands = [r for r in results if r.get('success')]
        failed_commands = [r for r in results if not r.get('success')]
        
        if not successful_commands:
            return {
                'success': False,
                'message': 'Toutes les commandes ont échoué.',
                'command_type': 'multiple_commands'
            }
        
        # Combiner les messages de succès en une seule réponse
        messages = [r['message'] for r in successful_commands if r.get('message')]
        combined_message = ' '.join(messages)
        
        # Construire la réponse finale
        result = {
            'success': True,
            'message': combined_message,
            'command_type': 'multiple_commands',
            'user_session': user_session  # Session contient tous les changements accumulés
        }
        
        # Ajouter la première action spéciale trouvée
        # Note: En pratique, les actions spéciales (new/clear) sont rarement combinées avec d'autres commandes
        if combined_actions:
            result['action'] = combined_actions[0]
        
        return result

    async def execute_command(self, command: ChatCommand, user_session: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Exécute une commande de chat
        
        Args:
            command: La commande à exécuter
            user_session: Session utilisateur pour stocker les préférences
            
        Returns:
            Dictionnaire avec le résultat de l'exécution
        """
        try:
            if command.command_type == CommandType.CHANGE_LLM:
                return await self._execute_change_llm(command, user_session)
                
            elif command.command_type == CommandType.SET_DOCUMENTS_COUNT:
                return await self._execute_set_documents_count(command, user_session)
                
            elif command.command_type == CommandType.SET_RESPONSE_LENGTH:
                return await self._execute_set_response_length(command, user_session)
                
            elif command.command_type == CommandType.NEW_CONVERSATION:
                return await self._execute_new_conversation(command, user_session)
                
            elif command.command_type == CommandType.CLEAR_CONVERSATION:
                return await self._execute_clear_conversation(command, user_session)
                
            else:
                return {
                    'success': False,
                    'message': f"Type de commande non supporté: {command.command_type}",
                    'command_type': command.command_type.value
                }
                
        except Exception as e:
            logging.exception(f"Erreur lors de l'exécution de la commande {command.command_type}")
            return {
                'success': False,
                'message': f"Erreur lors de l'exécution de la commande: {str(e)}",
                'command_type': command.command_type.value
            }
    
    async def _execute_change_llm(self, command: ChatCommand, user_session: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute le changement de provider LLM"""
        provider = command.parameters['provider']
        provider_name = command.parameters['provider_name']
        
        # Vérifier que le provider est disponible
        if provider not in self.app_settings.base_settings.available_llm_providers:
            return {
                'success': False,
                'message': f"Le modèle {provider_name} n'est pas disponible. Modèles disponibles: {', '.join(self.app_settings.base_settings.available_llm_providers)}",
                'command_type': CommandType.CHANGE_LLM.value
            }
        
        # Sauvegarder dans la session utilisateur
        if user_session is None:
            user_session = {}
        user_session['llm_provider'] = provider
        
        return {
            'success': True,
            'message': f"Configuration modifiée avec succès. Le modèle {provider_name} est maintenant utilisé.",
            'command_type': CommandType.CHANGE_LLM.value,
            'provider': provider,
            'user_session': user_session
        }
    
    async def _execute_set_documents_count(self, command: ChatCommand, user_session: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute la modification du nombre de documents"""
        count = command.parameters['count']
        
        # Validation des limites (à adapter selon votre configuration)
        max_documents = 50  # Limite configurable
        if count <= 0:
            return {
                'success': False,
                'message': f"Le nombre de documents doit être supérieur à 0.",
                'command_type': CommandType.SET_DOCUMENTS_COUNT.value
            }
        
        if count > max_documents:
            return {
                'success': False,
                'message': f"Le nombre maximum de documents autorisé est {max_documents}. Vous avez demandé {count}.",
                'command_type': CommandType.SET_DOCUMENTS_COUNT.value
            }
        
        # Sauvegarder dans la session utilisateur
        if user_session is None:
            user_session = {}
        user_session['documents_count'] = count
        
        return {
            'success': True,
            'message': f"Configuration modifiée avec succès. Le nombre maximum de documents de référence est maintenant {count}.",
            'command_type': CommandType.SET_DOCUMENTS_COUNT.value,
            'documents_count': count,
            'user_session': user_session
        }
    
    async def _execute_set_response_length(self, command: ChatCommand, user_session: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute la modification de la longueur de réponse"""
        length = command.parameters['length']
        length_name = command.parameters['length_name']
        
        # Sauvegarder dans la session utilisateur
        if user_session is None:
            user_session = {}
        user_session['response_length'] = length
        
        length_descriptions = {
            'VERY_SHORT': 'courtes',
            'NORMAL': 'normales',
            'COMPREHENSIVE': 'détaillées'
        }
        
        description = length_descriptions.get(length, length_name)
        
        return {
            'success': True,
            'message': f"Configuration modifiée avec succès. Les réponses seront maintenant {description}.",
            'command_type': CommandType.SET_RESPONSE_LENGTH.value,
            'response_length': length,
            'user_session': user_session
        }
    
    async def _execute_new_conversation(self, command: ChatCommand, user_session: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute la création d'une nouvelle conversation"""
        return {
            'success': True,
            'message': "Nouvelle conversation créée avec succès.",
            'command_type': CommandType.NEW_CONVERSATION.value,
            'action': 'new_conversation'
        }
    
    async def _execute_clear_conversation(self, command: ChatCommand, user_session: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute le nettoyage de la conversation"""
        return {
            'success': True,
            'message': "OK",  # Message simple qui sera affiché puis disparaîtra avec le clear
            'command_type': CommandType.CLEAR_CONVERSATION.value,
            'action': 'clear_conversation'
        }

# Instance globale du parser
command_parser = ChatCommandParser()