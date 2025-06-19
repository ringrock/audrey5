import { Action, AppState } from './AppProvider'
import { CustomizationPreferences } from '../components/Customization/CustomizationPanel'

// Define the reducer function
export const appStateReducer = (state: AppState, action: Action): AppState => {
  switch (action.type) {
    case 'TOGGLE_CHAT_HISTORY':
      // Si le panneau d'aide ou de personnalisation est ouvert, le fermer quand l'historique des chats est ouvert
      return { 
        ...state, 
        isChatHistoryOpen: !state.isChatHistoryOpen,
        // Fermer les autres panneaux si on ouvre l'historique
        isHelpPanelOpen: !state.isChatHistoryOpen ? false : state.isHelpPanelOpen,
        isCustomizationPanelOpen: !state.isChatHistoryOpen ? false : state.isCustomizationPanelOpen
      }
    case 'TOGGLE_HELP_PANEL':
      // Si l'historique des chats ou le panneau de personnalisation est ouvert, le fermer quand le panneau d'aide est ouvert
      return { 
        ...state, 
        isHelpPanelOpen: !state.isHelpPanelOpen,
        // Fermer les autres panneaux si on ouvre l'aide
        isChatHistoryOpen: !state.isHelpPanelOpen ? false : state.isChatHistoryOpen,
        isCustomizationPanelOpen: !state.isHelpPanelOpen ? false : state.isCustomizationPanelOpen
      }
    case 'TOGGLE_CUSTOMIZATION_PANEL':
      // Si l'historique des chats ou le panneau d'aide est ouvert, le fermer quand le panneau de personnalisation est ouvert
      return { 
        ...state, 
        isCustomizationPanelOpen: !state.isCustomizationPanelOpen,
        // Fermer les autres panneaux si on ouvre la personnalisation
        isChatHistoryOpen: !state.isCustomizationPanelOpen ? false : state.isChatHistoryOpen,
        isHelpPanelOpen: !state.isCustomizationPanelOpen ? false : state.isHelpPanelOpen
      }
    case 'UPDATE_CUSTOMIZATION_PREFERENCES':
      return {
        ...state,
        customizationPreferences: action.payload
      }
    case 'UPDATE_CURRENT_CHAT':
      return { ...state, currentChat: action.payload }
    case 'UPDATE_CHAT_HISTORY_LOADING_STATE':
      return { ...state, chatHistoryLoadingState: action.payload }
    case 'UPDATE_CHAT_HISTORY':
      if (!state.chatHistory || !state.currentChat) {
        return state
      }
      const conversationIndex = state.chatHistory.findIndex(conv => conv.id === action.payload.id)
      if (conversationIndex !== -1) {
        const updatedChatHistory = [...state.chatHistory]
        updatedChatHistory[conversationIndex] = state.currentChat
        return { ...state, chatHistory: updatedChatHistory }
      } else {
        return { ...state, chatHistory: [...state.chatHistory, action.payload] }
      }
    case 'UPDATE_CHAT_TITLE':
      if (!state.chatHistory) {
        return { ...state, chatHistory: [] }
      }
      const updatedChats = state.chatHistory.map(chat => {
        if (chat.id === action.payload.id) {
          if (state.currentChat?.id === action.payload.id) {
            state.currentChat.title = action.payload.title
          }
          //TODO: make api call to save new title to DB
          return { ...chat, title: action.payload.title }
        }
        return chat
      })
      return { ...state, chatHistory: updatedChats }
    case 'DELETE_CHAT_ENTRY':
      if (!state.chatHistory) {
        return { ...state, chatHistory: [] }
      }
      const filteredChat = state.chatHistory.filter(chat => chat.id !== action.payload)
      state.currentChat = null
      //TODO: make api call to delete conversation from DB
      return { ...state, chatHistory: filteredChat }
    case 'DELETE_CHAT_HISTORY':
      //TODO: make api call to delete all conversations from DB
      return { ...state, chatHistory: [], filteredChatHistory: [], currentChat: null }
    case 'DELETE_CURRENT_CHAT_MESSAGES':
      //TODO: make api call to delete current conversation messages from DB
      if (!state.currentChat || !state.chatHistory) {
        return state
      }
      const updatedCurrentChat = {
        ...state.currentChat,
        messages: []
      }
      return {
        ...state,
        currentChat: updatedCurrentChat
      }
    case 'FETCH_CHAT_HISTORY':
      return { ...state, chatHistory: action.payload }
    case 'SET_COSMOSDB_STATUS':
      return { ...state, isCosmosDBAvailable: action.payload }
    case 'FETCH_FRONTEND_SETTINGS':
      return { ...state, isLoading: false, frontendSettings: action.payload }
    case 'SET_FEEDBACK_STATE':
      return {
        ...state,
        feedbackState: {
          ...state.feedbackState,
          [action.payload.answerId]: action.payload.feedback
        }
      }
    case 'SET_ANSWER_EXEC_RESULT':
      return {
        ...state,
        answerExecResult: {
          ...state.answerExecResult,
          [action.payload.answerId]: action.payload.exec_result
        }
      }
    case 'SET_AUTH_TOKEN':
      return {
        ...state,
        authToken: action.payload, 
      };
    case 'SET_USER_LANGUAGE':
      return {
        ...state,
        userLanguage: action.payload, 
      };
    case 'SET_USERNAME':
      return {
        ...state,
        username: action.payload, 
      };
    case 'SET_ENCRYPTED_USERNAME':
      return {
        ...state,
        encryptedUsername: action.payload, 
      };
    case 'SET_INITIAL_QUESTION':
      return {
        ...state,
        initialQuestion: action.payload, 
      };
    case 'SET_AUTHENTICATION_STATUS':
      return { ...state, isAuthenticated: action.payload }
    case 'TOGGLE_AUTO_AUDIO':
      // Save to localStorage
      try {
        localStorage.setItem('isAutoAudioEnabled', action.payload.toString())
      } catch (error) {
        console.warn('Failed to save audio settings to localStorage:', error)
      }
      return { ...state, isAutoAudioEnabled: action.payload }
    default:
      return state
  }
}