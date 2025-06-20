import { useRef, useState, useEffect, useContext, useLayoutEffect } from 'react'
import { CommandBarButton, IconButton, Dialog, DialogType, Stack } from '@fluentui/react'
import { SquareRegular, ShieldLockRegular, ErrorCircleRegular } from '@fluentui/react-icons'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import uuid from 'react-uuid'
import { isEmpty } from 'lodash'
import DOMPurify from 'dompurify'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { nord } from 'react-syntax-highlighter/dist/esm/styles/prism'

import styles from './Chat.module.css'
import Contoso from '../../assets/Contoso.svg'
import { XSSAllowTags } from '../../constants/sanatizeAllowables'

import {encryptString} from '../../utils/encryptAES'

import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';

import LocalizedStrings from 'react-localization';

import {
  ChatMessage,
  ConversationRequest,
  conversationApi,
  Citation,
  ToolMessageContent,
  AzureSqlServerExecResults,
  ChatResponse,
  getUserInfo,
  Conversation,
  historyGenerate,
  historyUpdate,
  historyClear,
  ChatHistoryLoadingState,
  CosmosDBStatus,
  ErrorMessage,
  ExecResults,
  authenticate,
  getTokenStatus
} from "../../api";
import { Answer } from "../../components/Answer";
import { QuestionInput } from "../../components/QuestionInput";
import { ChatHistoryPanel } from "../../components/ChatHistory/ChatHistoryPanel";
import { AppStateContext } from "../../state/AppProvider";
import { useBoolean } from "@fluentui/react-hooks";

const enum messageStatus {
  NotRunning = 'Not Running',
  Processing = 'Processing',
  Done = 'Done'
}

const Chat = () => {
  const appStateContext = useContext(AppStateContext)
  const ui = appStateContext?.state.frontendSettings?.ui
  const AUTH_ENABLED = appStateContext?.state.frontendSettings?.auth_enabled
  const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [showLoadingMessage, setShowLoadingMessage] = useState<boolean>(false)
  const [activeCitation, setActiveCitation] = useState<Citation>()
  const [isCitationPanelOpen, setIsCitationPanelOpen] = useState<boolean>(false)
  const [isIntentsPanelOpen, setIsIntentsPanelOpen] = useState<boolean>(false)
  const abortFuncs = useRef([] as AbortController[])
  const [showAuthMessage, setShowAuthMessage] = useState<boolean>(true)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [execResults, setExecResults] = useState<ExecResults[]>([])
  const [processMessages, setProcessMessages] = useState<messageStatus>(messageStatus.NotRunning)
  const [clearingChat, setClearingChat] = useState<boolean>(false)
  const [hideErrorDialog, { toggle: toggleErrorDialog }] = useBoolean(true)
  const [errorMsg, setErrorMsg] = useState<ErrorMessage | null>()
  const [logo, setLogo] = useState('')
  const [answerId, setAnswerId] = useState<string>('')


  const [token, setToken] = useState<string>("");

  const [alertWarnTokens, setAlertWarnTokens] = useState(false);
  const [alertErrTokens, setAlertErrTokens] = useState(false);
  const [shouldDisplayInput, setShouldDisplayInput] = useState(false);
  const [errAlertMsg, setErrAlertMsg] = useState<string>("");
  const [currentUser, setCurrentUser] = useState<string>("");
  const [encryptedCurrentUser, setEncryptedCurrentUser] = useState<string>("");
  const [userFullDef, setUserFullDef] = useState<string>("");
  const [appReady, setAppReady] = useState(false);
  
  // Voice recognition functions from QuestionInput
  const [pauseVoiceRecognition, setPauseVoiceRecognition] = useState<(() => void) | undefined>(undefined)
  const [resumeVoiceRecognition, setResumeVoiceRecognition] = useState<(() => void) | undefined>(undefined) 

  const handleVoiceRecognitionReady = (pause: () => void, resume: () => void) => {
    setPauseVoiceRecognition(() => pause)
    setResumeVoiceRecognition(() => resume)
  }

  const handleCloseAlert = (event?: React.SyntheticEvent | Event, reason?: string) => {
      if (reason == "clickaway"){
          return;
      }
      setAlertWarnTokens(false);
  }

  
  const errorDialogContentProps = {
    type: DialogType.close,
    title: errorMsg?.title,
    closeButtonAriaLabel: 'Close',
    subText: errorMsg?.subtitle
  }

  const modalProps = {
    titleAriaId: 'labelId',
    subtitleAriaId: 'subTextId',
    isBlocking: true,
    styles: { main: { maxWidth: 450 } }
  }

  const [ASSISTANT, TOOL, ERROR] = ['assistant', 'tool', 'error']
  const NO_CONTENT_ERROR = 'No content in messages object.'



  // Notification à l'application parent qu'on est prêt
  useEffect(() => {
    if(appReady){

      const message = {
        action: "AskMeReady",
      };
      console.log("AskMe prêt, notification.");
      window.parent.postMessage(message, "*");
    }
      
  }, [appReady]);

  useEffect(() => {
    if (
      appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.Working &&
      appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured &&
      appStateContext?.state.chatHistoryLoadingState === ChatHistoryLoadingState.Fail &&
      hideErrorDialog
    ) {
      let subtitle = `${appStateContext.state.isCosmosDBAvailable.status}. Please contact the site administrator.`
      setErrorMsg({
        title: 'Chat history is not enabled',
        subtitle: subtitle
      })
      toggleErrorDialog()
    }
  }, [appStateContext?.state.isCosmosDBAvailable])

  const handleErrorDialogClose = () => {
    toggleErrorDialog()
    setTimeout(() => {
      setErrorMsg(null)
    }, 500)
  }

  useEffect(() => {
    if (!appStateContext?.state.isLoading) {
      setLogo(ui?.chat_logo || ui?.logo || Contoso)
    }
  }, [appStateContext?.state.isLoading])

  useEffect(() => {
    setIsLoading(appStateContext?.state.chatHistoryLoadingState === ChatHistoryLoadingState.Loading)
  }, [appStateContext?.state.chatHistoryLoadingState])

  /* Gestion de l'auth */
  useEffect(() => {
    const handleMessage = async (event: any) => {
      
      if (event.data.InitialQuestion){
        appStateContext?.dispatch({ type: 'SET_INITIAL_QUESTION', payload: event.data.InitialQuestion });
      }

      if (event.data.AuthToken) {
        // Définition de la langue de l'appli
        localizedStrings.setLanguage((event.data.Language) ? event.data.Language : 'FR');
        
        // Set du language dans le contexte pour le réutiliser dans d'autres composants
        appStateContext?.dispatch({ type: 'SET_USER_LANGUAGE', payload: (event.data.Language) ? event.data.Language : 'FR' });

        setCurrentUser((event.data.UserNameDN) ? event.data.UserNameDN : "Anonyme (WEB)");
        appStateContext?.dispatch({ type: 'SET_USERNAME', payload: (event.data.UserNameDN) ? event.data.UserNameDN : '' });
        setEncryptedCurrentUser((event.data.UserNameDN) ? encryptString(event.data.UserNameDN) : '');
        appStateContext?.dispatch({ type: 'SET_ENCRYPTED_USERNAME', payload: (event.data.UserNameDN) ? encryptString(event.data.UserNameDN) : '' });
        





        /* Si la full definition n'est pas renseigné, on met *, qui montrera les docs accessibles à tout le monde*/
        setUserFullDef((event.data.FullDefinition) ? event.data.FullDefinition : "*");


        // Est-ce que le token pour accéder à l'appli est OK ?
        const resp = await authenticate(event.data.AuthToken);
        if (resp){
          setShowAuthMessage(false);
          appStateContext?.dispatch({ type: 'SET_AUTHENTICATION_STATUS', payload: true }); // Mise à jour du contexte global
          setToken(event.data.AuthToken);
          // Set le token au niveau du context (utile pour l'utiliser sur l'historique par ex)
          appStateContext?.dispatch({ type: 'SET_AUTH_TOKEN', payload: event.data.AuthToken });

          // vérifier le nombre de crédits restants au client
          const tokenStatus = await getTokenStatus();
          if (tokenStatus == "ERR"){
            setAlertErrTokens(true);
            setErrAlertMsg(localizedStrings.tokenRetrievalError);
            setShouldDisplayInput(false);
          } else if (tokenStatus == "KO"){
            setAlertErrTokens(true);
            setErrAlertMsg(localizedStrings.tokensExpired);
            setShouldDisplayInput(false);
          } else if (tokenStatus == "WARN"){
            setAlertWarnTokens(true);
            setShouldDisplayInput(true);
          } else {
            setShouldDisplayInput(true);
          }
        }
      }

    };

    // Ajout du listener
    window.addEventListener('message', handleMessage);
    setAppReady(true);
    // Cleanup
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [appStateContext]);


  let assistantMessage = {} as ChatMessage
  let toolMessage = {} as ChatMessage
  let assistantContent = ''

  useEffect(() => parseExecResults(execResults), [execResults])

  const parseExecResults = (exec_results_: any): void => {
    if (exec_results_ == undefined) return
    const exec_results = exec_results_.length === 2 ? exec_results_ : exec_results_.splice(2)
    appStateContext?.dispatch({ type: 'SET_ANSWER_EXEC_RESULT', payload: { answerId: answerId, exec_result: exec_results } })
  }

  const processResultMessage = (resultMessage: ChatMessage, userMessage: ChatMessage, conversationId?: string) => {
    if (typeof resultMessage.content === "string" && resultMessage.content.includes('all_exec_results')) {
      const parsedExecResults = JSON.parse(resultMessage.content) as AzureSqlServerExecResults
      setExecResults(parsedExecResults.all_exec_results)
      assistantMessage.context = JSON.stringify({
        all_exec_results: parsedExecResults.all_exec_results
      })
    }

    if (resultMessage.role === ASSISTANT) {
      setAnswerId(resultMessage.id)
      assistantContent += resultMessage.content
      assistantMessage = { ...assistantMessage, ...resultMessage }
      assistantMessage.content = assistantContent

      if (resultMessage.context) {
        toolMessage = {
          id: uuid(),
          role: TOOL,
          content: resultMessage.context,
          date: new Date().toISOString()
        }
      }
    }

    if (resultMessage.role === TOOL) toolMessage = resultMessage

    if (!conversationId) {
      isEmpty(toolMessage)
        ? setMessages([...messages, userMessage, assistantMessage])
        : setMessages([...messages, userMessage, toolMessage, assistantMessage])
    } else {
      isEmpty(toolMessage)
        ? setMessages([...messages, assistantMessage])
        : setMessages([...messages, toolMessage, assistantMessage])
    }
  }

  const getToken = () => {
    return token;
  }

  const makeApiRequestWithoutCosmosDB = async (question: ChatMessage["content"], conversationId?: string) => {
    setIsLoading(true)
    setShowLoadingMessage(true)
    const abortController = new AbortController()
    abortFuncs.current.unshift(abortController)
  
    const textPart = typeof question === 'string' ? question : Array.isArray(question) ? question.find((part): part is { type: "text"; text: string } => part.type === "text")?.text || "" : ""
    const imagePart = typeof question !== 'string' && Array.isArray(question) ? question.find((part): part is { type: "image_url"; image_url: { url: string } } => part.type === "image_url") : null
    const questionContent = typeof question === 'string' ? question : imagePart ? [{ type: "text", text: textPart }, { type: "image_url", image_url: imagePart.image_url }] : textPart
    question = textPart || question
  
    const userMessage: ChatMessage = {
      id: uuid(),
      role: 'user',
      content: questionContent as string,
      date: new Date().toISOString()
    }
  
    let conversation: Conversation | null | undefined
    if (!conversationId) {
      conversation = {
        id: conversationId ?? uuid(),
        title: question as string,
        messages: [userMessage],
        date: new Date().toISOString()
      }
    } else {
      conversation = appStateContext?.state?.currentChat
      if (!conversation) {
        console.error('Conversation not found.')
        setIsLoading(false)
        setShowLoadingMessage(false)
        abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
        return
      } else {
        conversation.messages.push(userMessage)
      }
    }
  
    appStateContext?.dispatch({ type: 'UPDATE_CURRENT_CHAT', payload: conversation })
    setMessages(conversation.messages)
  
    const request: ConversationRequest = {
      messages: [...conversation.messages.filter(answer => answer.role !== ERROR)]
    }
  
    let result = {} as ChatResponse
    try {
      // Récupérer les préférences de personnalisation
      const customizationPreferences = appStateContext?.state.customizationPreferences;
      
      // Passer les préférences à l'API
      const response = await conversationApi(
        request, 
        abortController.signal, 
        getToken(), 
        currentUser, 
        userFullDef, 
        customizationPreferences
      )
      
      if (response?.body) {
        const reader = response.body.getReader()
  
        let runningText = ''
        while (true) {
          setProcessMessages(messageStatus.Processing)
          const { done, value } = await reader.read()
          if (done) break
  
          var text = new TextDecoder('utf-8').decode(value)
          const objects = text.split('\n')
          objects.forEach(obj => {
            try {
              if (obj !== '' && obj !== '{}') {
                runningText += obj
                result = JSON.parse(runningText)
                if (result.choices?.length > 0) {
                  result.choices[0].messages.forEach(msg => {
                    msg.id = result.id
                    msg.date = new Date().toISOString()
                  })
                  if (result.choices[0].messages?.some(m => m.role === ASSISTANT)) {
                    setShowLoadingMessage(false)
                  }
                  result.choices[0].messages.forEach(resultObj => {
                    processResultMessage(resultObj, userMessage, conversationId)
                  })
                } else if (result.error) {
                  throw Error(result.error)
                }
                runningText = ''
              }
            } catch (e) {
              if (!(e instanceof SyntaxError)) {
                console.error(e)
                throw e
              } else {
                console.log('Incomplete message. Continuing...')
              }
            }
          })
        }
        conversation.messages.push(toolMessage, assistantMessage)
        appStateContext?.dispatch({ type: 'UPDATE_CURRENT_CHAT', payload: conversation })
        setMessages([...messages, toolMessage, assistantMessage])
      }
    } catch (e) {
      if (!abortController.signal.aborted) {
        let errorMessage =
          'An error occurred. Please try again. If the problem persists, please contact the site administrator.'
        if (result.error?.message) {
          errorMessage = result.error.message
        } else if (typeof result.error === 'string') {
          errorMessage = result.error
        }
  
        errorMessage = parseErrorMessage(errorMessage)
  
        let errorChatMsg: ChatMessage = {
          id: uuid(),
          role: ERROR,
          content: errorMessage,
          date: new Date().toISOString()
        }
        conversation.messages.push(errorChatMsg)
        appStateContext?.dispatch({ type: 'UPDATE_CURRENT_CHAT', payload: conversation })
        setMessages([...messages, errorChatMsg])
      } else {
        setMessages([...messages, userMessage])
      }
    } finally {
      setIsLoading(false)
      setShowLoadingMessage(false)
      abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
      setProcessMessages(messageStatus.Done)
    }
  
    return abortController.abort()
  }

  const makeApiRequestWithCosmosDB = async (question: ChatMessage["content"], conversationId?: string) => {
    setIsLoading(true)
    setShowLoadingMessage(true)
    const abortController = new AbortController()
    abortFuncs.current.unshift(abortController)
    const textPart = typeof question === 'string' ? question : Array.isArray(question) ? question.find((part): part is { type: "text"; text: string } => part.type === "text")?.text || "" : ""
    const imagePart = typeof question !== 'string' && Array.isArray(question) ? question.find((part): part is { type: "image_url"; image_url: { url: string } } => part.type === "image_url") : null
    const questionContent = typeof question === 'string' ? question : imagePart ? [{ type: "text", text: textPart }, { type: "image_url", image_url: imagePart.image_url }] : textPart
    question = textPart || question
  
    const userMessage: ChatMessage = {
      id: uuid(),
      role: 'user',
      content: questionContent as string,
      date: new Date().toISOString()
    }
  
    let request: ConversationRequest
    let conversation
    if (conversationId) {
      conversation = appStateContext?.state?.chatHistory?.find(conv => conv.id === conversationId)
      if (!conversation) {
        console.error('Conversation not found.')
        setIsLoading(false)
        setShowLoadingMessage(false)
        abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
        return
      } else {
        conversation.messages.push(userMessage)
        request = {
          messages: [...conversation.messages.filter(answer => answer.role !== ERROR)]
        }
      }
    } else {
      request = {
        messages: [userMessage].filter(answer => answer.role !== ERROR)
      }
      setMessages(request.messages)
    }
    let result = {} as ChatResponse
    var errorResponseMessage = 'Please try again. If the problem persists, please contact the site administrator.'
    try {
      // Récupérer les préférences de personnalisation
      const customizationPreferences = appStateContext?.state.customizationPreferences;
      
      const response = conversationId
        ? await historyGenerate(
            token, 
            encryptedCurrentUser, 
            request, 
            abortController.signal, 
            userFullDef, 
            customizationPreferences, 
            conversationId
          )
        : await historyGenerate(
            token, 
            encryptedCurrentUser, 
            request, 
            abortController.signal, 
            userFullDef, 
            customizationPreferences
          )
          
      if (!response?.ok) {
        const responseJson = await response.json()
        errorResponseMessage =
          responseJson.error === undefined ? errorResponseMessage : parseErrorMessage(responseJson.error)
        let errorChatMsg: ChatMessage = {
          id: uuid(),
          role: ERROR,
          content: `There was an error generating a response. Chat history can't be saved at this time. ${errorResponseMessage}`,
          date: new Date().toISOString()
        }
        let resultConversation
        if (conversationId) {
          resultConversation = appStateContext?.state?.chatHistory?.find(conv => conv.id === conversationId)
          if (!resultConversation) {
            console.error('Conversation not found.')
            setIsLoading(false)
            setShowLoadingMessage(false)
            abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
            return
          }
          resultConversation.messages.push(errorChatMsg)
        } else {
          setMessages([...messages, userMessage, errorChatMsg])
          setIsLoading(false)
          setShowLoadingMessage(false)
          abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
          return
        }
        appStateContext?.dispatch({ type: 'UPDATE_CURRENT_CHAT', payload: resultConversation })
        setMessages([...resultConversation.messages])
        return
      }
      
      if (response?.body) {
        const reader = response.body.getReader()
  
        let runningText = ''
        while (true) {
          setProcessMessages(messageStatus.Processing)
          const { done, value } = await reader.read()
          if (done) break
  
          var text = new TextDecoder('utf-8').decode(value)
          const objects = text.split('\n')
          objects.forEach(obj => {
            try {
              if (obj !== '' && obj !== '{}') {
                runningText += obj
                result = JSON.parse(runningText)
                // Skip validation for chunks without content (citations, empty chunks, etc.)
                // Only validate if there are messages but no content and no context
                if (result.choices?.[0]?.messages?.length > 0) {
                  const firstMessage = result.choices[0].messages[0]
                  if (!firstMessage.content && !firstMessage.context && firstMessage.role !== "tool") {
                    errorResponseMessage = NO_CONTENT_ERROR
                    throw Error()
                  }
                }
                if (result.choices?.length > 0) {
                  result.choices[0].messages.forEach(msg => {
                    msg.id = result.id
                    msg.date = new Date().toISOString()
                  })
                  if (result.choices[0].messages?.some(m => m.role === ASSISTANT)) {
                    setShowLoadingMessage(false)
                  }
                  result.choices[0].messages.forEach(resultObj => {
                    processResultMessage(resultObj, userMessage, conversationId)
                  })
                }
                runningText = ''
              } else if (result.error) {
                throw Error(result.error)
              }
            } catch (e) {
              if (!(e instanceof SyntaxError)) {
                console.error(e)
                throw e
              } else {
                console.log('Incomplete message. Continuing...')
              }
            }
          })
        }
  
        let resultConversation
        if (conversationId) {
          resultConversation = appStateContext?.state?.chatHistory?.find(conv => conv.id === conversationId)
          if (!resultConversation) {
            console.error('Conversation not found.')
            setIsLoading(false)
            setShowLoadingMessage(false)
            abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
            return
          }
          isEmpty(toolMessage)
            ? resultConversation.messages.push(assistantMessage)
            : resultConversation.messages.push(toolMessage, assistantMessage)
        } else {
          resultConversation = {
            id: result.history_metadata.conversation_id,
            title: result.history_metadata.title,
            messages: [userMessage],
            date: result.history_metadata.date
          }
          isEmpty(toolMessage)
            ? resultConversation.messages.push(assistantMessage)
            : resultConversation.messages.push(toolMessage, assistantMessage)
        }
        if (!resultConversation) {
          setIsLoading(false)
          setShowLoadingMessage(false)
          abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
          return
        }
        appStateContext?.dispatch({ type: 'UPDATE_CURRENT_CHAT', payload: resultConversation })
        isEmpty(toolMessage)
          ? setMessages([...messages, assistantMessage])
          : setMessages([...messages, toolMessage, assistantMessage])
      }
    } catch (e) {
      if (!abortController.signal.aborted) {
        let errorMessage = `An error occurred. ${errorResponseMessage}`
        if (result.error?.message) {
          errorMessage = result.error.message
        } else if (typeof result.error === 'string') {
          errorMessage = result.error
        }
  
        errorMessage = parseErrorMessage(errorMessage)
  
        let errorChatMsg: ChatMessage = {
          id: uuid(),
          role: ERROR,
          content: errorMessage,
          date: new Date().toISOString()
        }
        let resultConversation
        if (conversationId) {
          resultConversation = appStateContext?.state?.chatHistory?.find(conv => conv.id === conversationId)
          if (!resultConversation) {
            console.error('Conversation not found.')
            setIsLoading(false)
            setShowLoadingMessage(false)
            abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
            return
          }
          resultConversation.messages.push(errorChatMsg)
        } else {
          if (!result.history_metadata) {
            console.error('Error retrieving data.', result)
            let errorChatMsg: ChatMessage = {
              id: uuid(),
              role: ERROR,
              content: errorMessage,
              date: new Date().toISOString()
            }
            setMessages([...messages, userMessage, errorChatMsg])
            setIsLoading(false)
            setShowLoadingMessage(false)
            abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
            return
          }
          resultConversation = {
            id: result.history_metadata.conversation_id,
            title: result.history_metadata.title,
            messages: [userMessage],
            date: result.history_metadata.date
          }
          resultConversation.messages.push(errorChatMsg)
        }
        if (!resultConversation) {
          setIsLoading(false)
          setShowLoadingMessage(false)
          abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
          return
        }
        appStateContext?.dispatch({ type: 'UPDATE_CURRENT_CHAT', payload: resultConversation })
        setMessages([...messages, errorChatMsg])
      } else {
        setMessages([...messages, userMessage])
      }
    } finally {
      setIsLoading(false)
      setShowLoadingMessage(false)
      abortFuncs.current = abortFuncs.current.filter(a => a !== abortController)
      setProcessMessages(messageStatus.Done)
    }
    return abortController.abort()
  }

  const clearChat = async () => {
    setClearingChat(true)
    if (appStateContext?.state.currentChat?.id && appStateContext?.state.isCosmosDBAvailable.cosmosDB) {
      let response = await historyClear(appStateContext?.state.currentChat.id, token, encryptedCurrentUser)
      if (!response.ok) {
        setErrorMsg({
          title: 'Error clearing current chat',
          subtitle: 'Please try again. If the problem persists, please contact the site administrator.'
        })
        toggleErrorDialog()
      } else {
        appStateContext?.dispatch({
          type: 'DELETE_CURRENT_CHAT_MESSAGES',
          payload: appStateContext?.state.currentChat.id
        })
        appStateContext?.dispatch({ type: 'UPDATE_CHAT_HISTORY', payload: appStateContext?.state.currentChat })
        setActiveCitation(undefined)
        setIsCitationPanelOpen(false)
        setIsIntentsPanelOpen(false)
        setMessages([])
      }
    }
    setClearingChat(false)
  }

  const tryGetRaiPrettyError = (errorMessage: string) => {
    try {
      // Using a regex to extract the JSON part that contains "innererror"
      const match = errorMessage.match(/'innererror': ({.*})\}\}/)
      if (match) {
        // Replacing single quotes with double quotes and converting Python-like booleans to JSON booleans
        const fixedJson = match[1]
          .replace(/'/g, '"')
          .replace(/\bTrue\b/g, 'true')
          .replace(/\bFalse\b/g, 'false')
        const innerErrorJson = JSON.parse(fixedJson)
        let reason = ''
        // Check if jailbreak content filter is the reason of the error
        const jailbreak = innerErrorJson.content_filter_result.jailbreak
        if (jailbreak.filtered === true) {
          reason = 'Jailbreak'
        }

        // Returning the prettified error message
        if (reason !== '') {
          return (
            'The prompt was filtered due to triggering Azure OpenAI’s content filtering system.\n' +
            'Reason: This prompt contains content flagged as ' +
            reason +
            '\n\n' +
            'Please modify your prompt and retry. Learn more: https://go.microsoft.com/fwlink/?linkid=2198766'
          )
        }
      }
    } catch (e) {
      console.error('Failed to parse the error:', e)
    }
    return errorMessage
  }

  const parseErrorMessage = (errorMessage: string) => {
    // If this is already a user-friendly message from our error handler, return as-is
    if (typeof errorMessage === 'string' && 
        (errorMessage.includes('Trop de requêtes') || 
         errorMessage.includes('Problème d\'authentification') ||
         errorMessage.includes('Erreur temporaire') ||
         errorMessage.includes('Problème de connexion'))) {
      return errorMessage
    }

    let errorCodeMessage = errorMessage.substring(0, errorMessage.indexOf('-') + 1)
    const innerErrorCue = "{\\'error\\': {\\'message\\': "
    if (errorMessage.includes(innerErrorCue)) {
      try {
        let innerErrorString = errorMessage.substring(errorMessage.indexOf(innerErrorCue))
        if (innerErrorString.endsWith("'}}")) {
          innerErrorString = innerErrorString.substring(0, innerErrorString.length - 3)
        }
        innerErrorString = innerErrorString.replaceAll("\\'", "'")
        let newErrorMessage = errorCodeMessage + ' ' + innerErrorString
        errorMessage = newErrorMessage
      } catch (e) {
        console.error('Error parsing inner error message: ', e)
      }
    }

    return tryGetRaiPrettyError(errorMessage)
  }

  const newChat = () => {
    setProcessMessages(messageStatus.Processing)
    setMessages([])
    setIsCitationPanelOpen(false)
    setIsIntentsPanelOpen(false)
    setActiveCitation(undefined)
    appStateContext?.dispatch({ type: 'UPDATE_CURRENT_CHAT', payload: null })
    setProcessMessages(messageStatus.Done)
  }

  const stopGenerating = () => {
    abortFuncs.current.forEach(a => a.abort())
    setShowLoadingMessage(false)
    setIsLoading(false)
  }

  useEffect(() => {
    if (appStateContext?.state.currentChat) {
      setMessages(appStateContext.state.currentChat.messages)
    } else {
      setMessages([])
    }
  }, [appStateContext?.state.currentChat])

  useLayoutEffect(() => {
    const saveToDB = async (messages: ChatMessage[], id: string) => {
      const response = await historyUpdate(messages, id, token, encryptedCurrentUser)
      return response
    }

    if (appStateContext && appStateContext.state.currentChat && processMessages === messageStatus.Done) {
      if (appStateContext.state.isCosmosDBAvailable.cosmosDB) {
        if (!appStateContext?.state.currentChat?.messages) {
          console.error('Failure fetching current chat state.')
          return
        }
        const noContentError = appStateContext.state.currentChat.messages.find(m => m.role === ERROR)

        if (!noContentError) {
          saveToDB(appStateContext.state.currentChat.messages, appStateContext.state.currentChat.id)
            .then(res => {
              if (!res.ok) {
                let errorMessage =
                  "An error occurred. Answers can't be saved at this time. If the problem persists, please contact the site administrator."
                let errorChatMsg: ChatMessage = {
                  id: uuid(),
                  role: ERROR,
                  content: errorMessage,
                  date: new Date().toISOString()
                }
                if (!appStateContext?.state.currentChat?.messages) {
                  let err: Error = {
                    ...new Error(),
                    message: 'Failure fetching current chat state.'
                  }
                  throw err
                }
                setMessages([...appStateContext?.state.currentChat?.messages, errorChatMsg])
              }
              return res as Response
            })
            .catch(err => {
              console.error('Error: ', err)
              let errRes: Response = {
                ...new Response(),
                ok: false,
                status: 500
              }
              return errRes
            })
        }
      } else {
      }
      appStateContext?.dispatch({ type: 'UPDATE_CHAT_HISTORY', payload: appStateContext.state.currentChat })
      setMessages(appStateContext.state.currentChat.messages)
      setProcessMessages(messageStatus.NotRunning)
    }
  }, [processMessages])


  useLayoutEffect(() => {
    chatMessageStreamEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [showLoadingMessage, processMessages])

  const onShowCitation = (citation: Citation) => {
    setActiveCitation(citation)
    setIsCitationPanelOpen(true)
  }

  const onShowExecResult = (answerId: string) => {
    setIsIntentsPanelOpen(true)
  }

  const onViewSource = (citation: Citation) => {
    if (citation.url && !citation.url.includes('blob.core')) {
      window.open(citation.url, '_blank')
    }
  }

  const parseCitationFromMessage = (message: ChatMessage) => {
    if (message?.role && message?.role === 'tool' && typeof message?.content === "string") {
      try {
        const toolMessage = JSON.parse(message.content) as ToolMessageContent
        return toolMessage.citations
      } catch {
        return []
      }
    }
    return []
  }

  const parsePlotFromMessage = (message: ChatMessage) => {
    if (message?.role && message?.role === "tool" && typeof message?.content === "string") {
      try {
        const execResults = JSON.parse(message.content) as AzureSqlServerExecResults;
        const codeExecResult = execResults.all_exec_results.at(-1)?.code_exec_result;

        if (codeExecResult === undefined) {
          return null;
        }
        return codeExecResult.toString();
      }
      catch {
        return null;
      }
      // const execResults = JSON.parse(message.content) as AzureSqlServerExecResults;
      // return execResults.all_exec_results.at(-1)?.code_exec_result;
    }
    return null;
  }

  const toggleGlobalAutoAudio = () => {
    const newState = !appStateContext?.state.isAutoAudioEnabled
    
    // Mettre à jour l'état global
    appStateContext?.dispatch({
      type: 'TOGGLE_AUTO_AUDIO',
      payload: newState
    })
    
    // Si on ACTIVE l'auto-lecture, déclencher la lecture du dernier message
    if (newState && messages && messages.length > 0) {
      // Trouver le dernier message assistant
      const lastAssistantMessage = [...messages].reverse().find(msg => msg.role === 'assistant')
      
      if (lastAssistantMessage?.content && typeof lastAssistantMessage.content === 'string') {
        // Déclencher le clic sur le bouton audio du dernier message via le DOM
        setTimeout(() => {
          const lastMessageContainer = document.querySelector(`[data-message-id="${lastAssistantMessage.id}"]`)
          if (lastMessageContainer) {
            // Chercher le bouton de lecture dans ce message (pas celui d'arrêt)
            const playButton = lastMessageContainer.querySelector('[aria-label*="playAudio"], [aria-label*="Lire"]')
            if (playButton && playButton instanceof HTMLElement) {
              playButton.click()
            }
          }
        }, 100)
      }
    }
    
    // Si on DÉSACTIVE l'auto-lecture, arrêter toute lecture en cours
    if (!newState) {
      // Arrêter tous les audios sur la page
      const allAudioElements = document.querySelectorAll('audio')
      allAudioElements.forEach(audio => {
        if (!audio.paused) {
          audio.pause()
          audio.currentTime = 0
        }
      })
      
      // Arrêter la synthèse vocale du navigateur
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel()
      }
    }
  }

  const disabledButton = () => {
    return (
      isLoading ||
      (messages && messages.length === 0) ||
      clearingChat ||
      appStateContext?.state.chatHistoryLoadingState === ChatHistoryLoadingState.Loading
    )
  }

  return (
    <div className={styles.container} role="main">
      {showAuthMessage ? (
        <Stack className={styles.chatEmptyState}>
          <ShieldLockRegular
            className={styles.chatIcon}
            style={{ color: 'darkorange', height: '200px', width: '200px' }}
          />
          <h1 className={styles.chatEmptyStateTitle}>{localizedStrings.accesDenied}</h1>
          <h2 className={styles.chatEmptyStateSubtitle} style={{ fontSize: "20px" }}>
              <strong>{localizedStrings.unauthentifiedConnection}</strong>
          </h2>
          <h2 className={styles.chatEmptyStateSubtitle}>{localizedStrings.unauthentifiedConnectionPrecisions}</h2>

        </Stack>
      ) : (
        <Stack horizontal className={styles.chatRoot}>
          <div className={styles.chatContainer}>
          <Snackbar 
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            open={alertWarnTokens} 
            onClose={handleCloseAlert} >
            <Alert severity="warning">
              {localizedStrings.tokenExpirationWarning}
            </Alert>
          </Snackbar>
          <Snackbar 
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            open={alertErrTokens} >
            <Alert severity="error">
              {errAlertMsg}
            </Alert>
          </Snackbar>
            {!messages || messages.length < 1 ? (
              <Stack className={styles.chatEmptyState}>
                <img src={logo} className={styles.chatIcon} aria-hidden="true" />
                <h1 className={styles.chatEmptyStateTitle}>{localizedStrings.uiChatTitle}</h1>
                <h2 className={styles.chatEmptyStateSubtitle}>{localizedStrings.uiChatDescription}</h2>
              </Stack>
            ) : (
              <div className={styles.chatMessageStream} style={{ marginBottom: isLoading ? '40px' : '0px' }} role="log">
                {messages.map((answer, index) => (
                  <>
                    {answer.role === 'user' ? (
                      <div className={styles.chatMessageUser} tabIndex={0}>
                        <div className={styles.chatMessageUserMessage}>
                          {typeof answer.content === "string" && answer.content ? answer.content : Array.isArray(answer.content) ? (
                            <>
                              {answer.content.find((part): part is { type: "text"; text: string } => part.type === "text")?.text}
                              {answer.content.filter((part): part is { type: "image_url"; image_url: { url: string } } => part.type === "image_url").map((imagePart, imgIndex) => (
                                <img key={imgIndex} className={styles.uploadedImageChat} src={imagePart.image_url.url} alt="Uploaded Preview" />
                              ))}
                            </>
                          ) : null}
                        </div>
                      </div>
                    ) : answer.role === 'assistant' ? (
                      <div className={styles.chatMessageGpt}>
                        {typeof answer.content === "string" && <Answer
                          answer={{
                            answer: answer.content,
                            citations: parseCitationFromMessage(messages[index - 1]),
                            generated_chart: parsePlotFromMessage(messages[index - 1]),
                            message_id: answer.id,
                            feedback: answer.feedback,
                            exec_results: execResults
                          }}
                          onCitationClicked={c => onShowCitation(c)}
                          onExectResultClicked={() => onShowExecResult(answerId)}
                          language={localizedStrings.getLanguage()}
                          pauseVoiceRecognition={pauseVoiceRecognition}
                          resumeVoiceRecognition={resumeVoiceRecognition}
                          isStreaming={isLoading}
                        />}
                      </div>
                    ) : answer.role === ERROR ? (
                      <div className={styles.chatMessageError}>
                        <Stack horizontal className={styles.chatMessageErrorContent}>
                          <ErrorCircleRegular className={styles.errorIcon} style={{ color: 'rgba(182, 52, 67, 1)' }} />
                          <span>Error</span>
                        </Stack>
                        <span className={styles.chatMessageErrorContent}>{typeof answer.content === "string" && answer.content}</span>
                      </div>
                    ) : null}
                  </>
                ))}
                {showLoadingMessage && (
                  <>
                    <div className={styles.chatMessageGpt}>
                      <Answer
                        answer={{
                          answer: localizedStrings.answerGenerationText,
                          citations: [],
                          generated_chart: null
                        }}
                        onCitationClicked={() => null}
                        onExectResultClicked={() => null}
                        language={localizedStrings.getLanguage()}
                        pauseVoiceRecognition={pauseVoiceRecognition}
                        resumeVoiceRecognition={resumeVoiceRecognition}
                        isStreaming={true}
                      />
                    </div>
                  </>
                )}
                <div ref={chatMessageStreamEnd} />
              </div>
            )}
            { shouldDisplayInput && (
            <Stack horizontal className={styles.chatInput}>
              {isLoading && messages.length > 0 && (
                <Stack
                  horizontal
                  className={styles.stopGeneratingContainer}
                  role="button"
                  aria-label="Interrompre"
                  tabIndex={0}
                  onClick={stopGenerating}
                  onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? stopGenerating() : null)}>
                  <SquareRegular className={styles.stopGeneratingIcon} aria-hidden="true" />
                  <span className={styles.stopGeneratingText} aria-hidden="true">{localizedStrings.stopGenerationButton}</span>
                </Stack>
              )}
              <Stack>
                {appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured && (
                  <CommandBarButton
                    role="button"
                    styles={{
                      icon: {
                        color: '#FFFFFF'
                      },
                      iconDisabled: {
                        color: '#BDBDBD !important'
                      },
                      root: {
                        color: '#FFFFFF',
                        background:
                          'radial-gradient(109.81% 107.82% at 100.1% 90.19%, #0F6CBD 33.63%, #2D87C3 70.31%, #8DDDD8 100%)'
                      },
                      rootDisabled: {
                        background: '#F0F0F0'
                      }
                    }}
                    className={styles.newChatIcon}
                    iconProps={{ iconName: 'Add' }}
                    onClick={newChat}
                    disabled={disabledButton()}
                    aria-label="start a new chat button"
                  />
                )}
                <CommandBarButton
                  role="button"
                  styles={{
                    icon: {
                      color: '#FFFFFF'
                    },
                    iconDisabled: {
                      color: '#BDBDBD !important'
                    },
                    root: {
                      color: '#FFFFFF',
                      background:
                        'radial-gradient(109.81% 107.82% at 100.1% 90.19%, #0F6CBD 33.63%, #2D87C3 70.31%, #8DDDD8 100%)'
                    },
                    rootDisabled: {
                      background: '#F0F0F0'
                    }
                  }}
                  className={
                    appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured
                      ? styles.clearChatBroom
                      : styles.clearChatBroomNoCosmos
                  }
                  iconProps={{ iconName: 'Broom' }}
                  onClick={
                    appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured
                      ? clearChat
                      : newChat
                  }
                  disabled={disabledButton()}
                  aria-label="clear chat button"
                />
                <Dialog
                  hidden={hideErrorDialog}
                  onDismiss={handleErrorDialogClose}
                  dialogContentProps={errorDialogContentProps}
                  modalProps={modalProps}></Dialog>
              </Stack>
              <QuestionInput
                clearOnSend
                placeholder={localizedStrings.yourQuestionPlaceholder}
                disabled={isLoading}
                onSend={(question, id) => {
                  appStateContext?.state.isCosmosDBAvailable?.cosmosDB
                    ? makeApiRequestWithCosmosDB(question, id)
                    : makeApiRequestWithoutCosmosDB(question, id)
                }}
                conversationId={
                  appStateContext?.state.currentChat?.id ? appStateContext?.state.currentChat?.id : undefined
                }
                onVoiceRecognitionReady={handleVoiceRecognitionReady}
              />
            </Stack>
            )}
          </div>
          {/* Citation Panel */}
          {messages && messages.length > 0 && isCitationPanelOpen && activeCitation && (
            <Stack.Item className={styles.citationPanel} tabIndex={0} role="tabpanel" aria-label="Citations Panel">
              <Stack
                aria-label="Citations Panel Header Container"
                horizontal
                className={styles.citationPanelHeaderContainer}
                horizontalAlign="space-between"
                verticalAlign="center">
                <span aria-label="Citations" className={styles.citationPanelHeader}>
                  Citations
                </span>
                <IconButton
                  iconProps={{ iconName: 'Cancel' }}
                  aria-label="Close citations panel"
                  onClick={() => setIsCitationPanelOpen(false)}
                />
              </Stack>
              <h5
                className={styles.citationPanelTitle}
                tabIndex={0}
                title={
                  activeCitation.url && !activeCitation.url.includes('blob.core')
                    ? activeCitation.url
                    : activeCitation.title ?? ''
                }
                onClick={() => onViewSource(activeCitation)}>
                {activeCitation.title}
              </h5>
              <div tabIndex={0}>
                <ReactMarkdown
                  linkTarget="_blank"
                  className={styles.citationPanelContent}
                  children={DOMPurify.sanitize(activeCitation.content, { ALLOWED_TAGS: XSSAllowTags })}
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                />
              </div>
            </Stack.Item>
          )}
          {messages && messages.length > 0 && isIntentsPanelOpen && (
            <Stack.Item className={styles.citationPanel} tabIndex={0} role="tabpanel" aria-label="Intents Panel">
              <Stack
                aria-label="Intents Panel Header Container"
                horizontal
                className={styles.citationPanelHeaderContainer}
                horizontalAlign="space-between"
                verticalAlign="center">
                <span aria-label="Intents" className={styles.citationPanelHeader}>
                  Intents
                </span>
                <IconButton
                  iconProps={{ iconName: 'Cancel' }}
                  aria-label="Close intents panel"
                  onClick={() => setIsIntentsPanelOpen(false)}
                />
              </Stack>
              <Stack horizontalAlign="space-between">
                {appStateContext?.state?.answerExecResult[answerId]?.map((execResult: ExecResults, index) => (
                  <Stack className={styles.exectResultList} verticalAlign="space-between">
                    <><span>Intent:</span> <p>{execResult.intent}</p></>
                    {execResult.search_query && <><span>Search Query:</span>
                      <SyntaxHighlighter
                        style={nord}
                        wrapLines={true}
                        lineProps={{ style: { wordBreak: 'break-all', whiteSpace: 'pre-wrap' } }}
                        language="sql"
                        PreTag="p">
                        {execResult.search_query}
                      </SyntaxHighlighter></>}
                    {execResult.search_result && <><span>Search Result:</span> <p>{execResult.search_result}</p></>}
                    {execResult.code_generated && <><span>Code Generated:</span>
                      <SyntaxHighlighter
                        style={nord}
                        wrapLines={true}
                        lineProps={{ style: { wordBreak: 'break-all', whiteSpace: 'pre-wrap' } }}
                        language="python"
                        PreTag="p">
                        {execResult.code_generated}
                      </SyntaxHighlighter>
                    </>}
                  </Stack>
                ))}
              </Stack>
            </Stack.Item>
          )}
          {appStateContext?.state.isChatHistoryOpen &&
            appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured && <ChatHistoryPanel />}
        </Stack>
      )}
    </div>
  )
}


let localizedStrings = new LocalizedStrings({
  FR: {
      tokensExpired : "Votre solde de tokens AskMe est expiré. Rapprochez-vous de votre administrateur pour pouvoir utiliser AskMe à nouveau.",
      tokenRetrievalError : "Erreur lors de la récupération du solde de tokens. Merci de vous rapprocher d'un adminsitrateur.",
      tokenExpirationWarning : "Votre solde de tokens AskMe est sur le point d'expirer. Rapprochez-vous de votre administrateur pour pouvoir continuer à utiliser AskMe.",
      yourQuestionPlaceholder: "Votre question ...",
      stopGenerationButton : "Interrompre",
      answerGenerationText : "Génération de la réponse...",
      unauthentifiedConnection : "Votre connexion n'est pas authentifiée. Accès interdit.",
      unauthentifiedConnectionPrecisions : "Si vous pensez que ceci est une erreur, merci de prendre contact avec votre administrateur.",
      uiChatTitle : "Commençons à discuter !",
      uiChatDescription : "Cet assistant est configuré pour répondre à vos questions.",
      accesDenied : "Accès refusé",
  },
  EN:{
      tokensExpired : "Your AskMe token balance has expired. Please contact your administrator to be able to use AskMe again.",
      tokenRetrievalError : "Error retrieving token balance. Please contact an administrator.",
      tokenExpirationWarning : "Your AskMe token balance is about to expire. Please contact your administrator to continue using AskMe.",
      yourQuestionPlaceholder: "Your question ...",
      stopGenerationButton : "Stop generation",
      answerGenerationText : "Answer generation...",
      unauthentifiedConnection : "Your connection is not authenticated. Access denied.",
      unauthentifiedConnectionPrecisions : "If you believe this is an error, please contact your administrator.",
      uiChatTitle : "Let's chat !",
      uiChatDescription : "This assistant is configured to answer your questions.",
      accesDenied : "Acces denied",

  }
  
 });

 
export default Chat
