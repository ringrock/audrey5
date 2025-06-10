import React, {
  createContext,
  ReactNode,
  useEffect,
  useReducer
} from 'react'

import {
  ChatHistoryLoadingState,
  Conversation,
  CosmosDBHealth,
  CosmosDBStatus,
  Feedback,
  FrontendSettings,
  frontendSettings,
  historyEnsure,
  historyList
} from '../api'

import { appStateReducer } from './AppReducer'
import { CustomizationPreferences } from '../components/Customization/CustomizationPanel'

export interface AppState {
  isChatHistoryOpen: boolean
  isHelpPanelOpen: boolean
  isCustomizationPanelOpen: boolean
  chatHistoryLoadingState: ChatHistoryLoadingState
  isCosmosDBAvailable: CosmosDBHealth
  chatHistory: Conversation[] | null
  filteredChatHistory: Conversation[] | null
  currentChat: Conversation | null
  frontendSettings: FrontendSettings | null
  feedbackState: { [answerId: string]: Feedback.Neutral | Feedback.Positive | Feedback.Negative }
  isLoading: boolean;
  answerExecResult: { [answerId: string]: [] }
  authToken: string;
  userLanguage: string;
  username: string;
  encryptedUsername: string;
  initialQuestion: string;
  isAuthenticated: boolean;
  customizationPreferences: CustomizationPreferences;
}

export type Action =
  | { type: 'TOGGLE_CHAT_HISTORY' }
  | { type: 'TOGGLE_HELP_PANEL' }
  | { type: 'TOGGLE_CUSTOMIZATION_PANEL' }
  | { type: 'SET_COSMOSDB_STATUS'; payload: CosmosDBHealth }
  | { type: 'UPDATE_CHAT_HISTORY_LOADING_STATE'; payload: ChatHistoryLoadingState }
  | { type: 'UPDATE_CURRENT_CHAT'; payload: Conversation | null }
  | { type: 'UPDATE_FILTERED_CHAT_HISTORY'; payload: Conversation[] | null }
  | { type: 'UPDATE_CHAT_HISTORY'; payload: Conversation }
  | { type: 'UPDATE_CHAT_TITLE'; payload: Conversation }
  | { type: 'DELETE_CHAT_ENTRY'; payload: string }
  | { type: 'DELETE_CHAT_HISTORY' }
  | { type: 'DELETE_CURRENT_CHAT_MESSAGES'; payload: string }
  | { type: 'FETCH_CHAT_HISTORY'; payload: Conversation[] | null }
  | { type: 'FETCH_FRONTEND_SETTINGS'; payload: FrontendSettings | null }
  | {
    type: 'SET_FEEDBACK_STATE'
    payload: { answerId: string; feedback: Feedback.Positive | Feedback.Negative | Feedback.Neutral }
  }
  | { type: 'GET_FEEDBACK_STATE'; payload: string }
  | { type: 'SET_ANSWER_EXEC_RESULT'; payload: { answerId: string, exec_result: [] } }
  | { type: 'SET_AUTH_TOKEN'; payload: string }
  | { type: 'SET_USER_LANGUAGE'; payload: string }
  | { type: 'SET_USERNAME'; payload: string }
  | { type: 'SET_ENCRYPTED_USERNAME'; payload: string }
  | { type: 'SET_INITIAL_QUESTION'; payload: string }
  | { type: 'SET_AUTHENTICATION_STATUS'; payload: boolean }
  | { type: 'UPDATE_CUSTOMIZATION_PREFERENCES'; payload: CustomizationPreferences }

const initialState: AppState = {
  isChatHistoryOpen: false,
  isHelpPanelOpen: false,
  isCustomizationPanelOpen: false,
  chatHistoryLoadingState: ChatHistoryLoadingState.Loading,
  chatHistory: null,
  filteredChatHistory: null,
  currentChat: null,
  isCosmosDBAvailable: {
    cosmosDB: false,
    status: CosmosDBStatus.NotConfigured
  },
  frontendSettings: null,
  feedbackState: {},
  isLoading: true,
  answerExecResult: {},
  authToken: "",
  userLanguage: "FR",
  username: "",
  encryptedUsername: "",
  initialQuestion: "",
  isAuthenticated: false,
  customizationPreferences: {
    responseSize: 'medium',
    documentsCount: 5,
    llmProvider: 'AZURE_OPENAI'
  }
}

export const AppStateContext = createContext<
  | {
    state: AppState
    dispatch: React.Dispatch<Action>
  }
  | undefined
>(undefined)

type AppStateProviderProps = {
  children: ReactNode
}

export const AppStateProvider: React.FC<AppStateProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(appStateReducer, initialState)

  // Load customization preferences from localStorage on startup
  useEffect(() => {
    const loadPreferencesFromStorage = (): CustomizationPreferences | null => {
      try {
        const saved = localStorage.getItem('userCustomizationPreferences')
        if (saved) {
          const parsed = JSON.parse(saved)
          if (parsed && typeof parsed === 'object') {
            return {
              responseSize: parsed.responseSize || 'medium',
              documentsCount: typeof parsed.documentsCount === 'number' ? parsed.documentsCount : 5,
              llmProvider: parsed.llmProvider || 'AZURE_OPENAI'
            }
          }
        }
      } catch (error) {
        console.warn('Failed to load customization preferences from localStorage:', error)
      }
      return null
    }

    const savedPreferences = loadPreferencesFromStorage()
    if (savedPreferences) {
      dispatch({ type: 'UPDATE_CUSTOMIZATION_PREFERENCES', payload: savedPreferences })
    }
  }, [])

  useEffect(() => {
    // Check for cosmosdb config and fetch initial data here
    const fetchChatHistory = async (offset = 0): Promise<Conversation[] | null> => {
      const result = await historyList(offset, state.authToken, state.encryptedUsername)
        .then(response => {
          if (response) {
            dispatch({ type: 'FETCH_CHAT_HISTORY', payload: response })
          } else {
            dispatch({ type: 'FETCH_CHAT_HISTORY', payload: null })
          }
          return response
        })
        .catch(_err => {
          dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Fail })
          dispatch({ type: 'FETCH_CHAT_HISTORY', payload: null })
          console.error('There was an issue fetching your data.')
          return null
        })
      return result
    }

    const getHistoryEnsure = async (token:string) => {
      if (!state.authToken) return; // Ne rien faire si le token n'est pas défini

      dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Loading })
      historyEnsure(token)
      .then(response => {
        if (response?.cosmosDB) {
          fetchChatHistory()
            .then(res => {
              if (res) {
                dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Success })
                dispatch({ type: 'SET_COSMOSDB_STATUS', payload: response })
              } else {
                dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Fail })
                dispatch({
                  type: 'SET_COSMOSDB_STATUS',
                  payload: { cosmosDB: false, status: CosmosDBStatus.NotWorking }
                })
              }
            })
            .catch(_err => {
              dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Fail })
              dispatch({
                type: 'SET_COSMOSDB_STATUS',
                payload: { cosmosDB: false, status: CosmosDBStatus.NotWorking }
              })
            })
        } else {
          dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Fail })
          dispatch({ type: 'SET_COSMOSDB_STATUS', payload: response })
        }
      })
      .catch(_err => {
        dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Fail })
        dispatch({ type: 'SET_COSMOSDB_STATUS', payload: { cosmosDB: false, status: CosmosDBStatus.NotConfigured } })
      })
    }

    getHistoryEnsure(state.authToken)
    
  }, [state.authToken])

  useEffect(() => {
    const getFrontendSettings = async () => {
      frontendSettings()
        .then(response => {
          dispatch({ type: 'FETCH_FRONTEND_SETTINGS', payload: response as FrontendSettings })
        })
        .catch(_err => {
          console.error('There was an issue fetching your data.')
        })
    }
    getFrontendSettings()
  }, [])

  return <AppStateContext.Provider value={{ state, dispatch }}>{children}</AppStateContext.Provider>
}