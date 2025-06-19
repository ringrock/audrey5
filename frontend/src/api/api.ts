import { chatHistorySampleData } from '../constants/chatHistory'

import { ChatMessage, Conversation, ConversationRequest, CosmosDBHealth, CosmosDBStatus, UserInfo } from './models'

export async function conversationApi(
  options: ConversationRequest, 
  abortSignal: AbortSignal, 
  token: string, 
  username: string, 
  userFullDefinition: string,
  customizationPreferences?: any
): Promise<Response> {
  // Debug logging pour vérifier la transmission du provider et des paramètres
  console.log('🤖 LLM Provider utilisé:', customizationPreferences?.llmProvider || 'DEFAULT (AZURE_OPENAI)');
  console.log('📊 Paramètres envoyés:', {
    provider: customizationPreferences?.llmProvider,
    responseSize: customizationPreferences?.responseSize,
    documentsCount: customizationPreferences?.documentsCount
  });
  
  const response = await fetch('/conversation', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      "AuthToken": token
    },
    body: JSON.stringify({
      messages: options.messages,
      currentUser: username,
      userFullDefinition: userFullDefinition,
      customizationPreferences: customizationPreferences,
      provider: customizationPreferences?.llmProvider
    }),
    signal: abortSignal
  })

  return response
}

export async function authenticate(authToken:string): Promise<boolean> {
  const response = await fetch("/authenticate", {
      method: "POST",
      headers: {
          "Content-Type": "application/json",
          "AuthToken":authToken
      }
  })
  var resJson = await response.json();
  return ("status" in resJson && resJson.status == "ok")
  
}

export async function getTokenStatus(): Promise<string> {
  const response = await fetch("/check-tokens", {
      method: "POST",
      headers: {
          "Content-Type": "application/json"
      }
  })
  var resJson = await response.json();
  if ("details" in resJson){
      console.log("Erreur lors de la récupération des tokens restants : " + resJson.details);
  }
  return ("status" in resJson) ? resJson.status : "ERR";
  
}


export async function getUserInfo(): Promise<UserInfo[]> {
  const response = await fetch('/.auth/me')
  if (!response.ok) {
    console.log('No identity provider found. Access to chat will be blocked.')
    return []
  }

  const payload = await response.json()
  return payload
}

// export const fetchChatHistoryInit = async (): Promise<Conversation[] | null> => {
export const fetchChatHistoryInit = (): Conversation[] | null => {
  // Make initial API call here

  return chatHistorySampleData
}

export const historyList = async (offset = 0, authToken:string, encryptedUsername:string): Promise<Conversation[] | null> => {
  const response = await fetch(`/history/list?offset=${offset}`, {
    method: 'GET',
    headers: {
      "AuthToken":authToken,
      "EncodedUsername":encryptedUsername
    },
  })
    .then(async res => {
      const payload = await res.json()
      if (!Array.isArray(payload)) {
        console.error('There was an issue fetching your data.')
        return null
      }
      const conversations: Conversation[] = await Promise.all(
        payload.map(async (conv: any) => {
          let convMessages: ChatMessage[] = []
          convMessages = await historyRead(conv.id, authToken, encryptedUsername)
            .then(res => {
              return res
            })
            .catch(err => {
              console.error('error fetching messages: ', err)
              return []
            })
          const conversation: Conversation = {
            id: conv.id,
            title: conv.title,
            date: conv.createdAt,
            messages: convMessages
          }
          return conversation
        })
      )
      return conversations
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      return null
    })

  return response
}

export const historyRead = async (convId: string, authToken: string, encryptedUsername:string): Promise<ChatMessage[]> => {
  const response = await fetch('/history/read', {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: convId
    }),
    headers: {
      'Content-Type': 'application/json',
      "AuthToken":authToken,
      "EncodedUsername":encryptedUsername
    }
  })
    .then(async res => {
      if (!res) {
        return []
      }
      const payload = await res.json()
      const messages: ChatMessage[] = []
      if (payload?.messages) {
        payload.messages.forEach((msg: any) => {
          const message: ChatMessage = {
            id: msg.id,
            role: msg.role,
            date: msg.createdAt,
            content: msg.content,
            feedback: msg.feedback ?? undefined
          }
          messages.push(message)
        })
      }
      return messages
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      return []
    })
  return response
}

export const historyGenerate = async (
  authToken:string,
  encryptedUsername: string,
  options: ConversationRequest,
  abortSignal: AbortSignal,
  userFullDefinition: string,
  customizationPreferences?: any,
  convId?: string,
): Promise<Response> => {
  let body
  // Debug logging pour vérifier la transmission du provider et des paramètres
  console.log('🤖 LLM Provider utilisé (historique):', customizationPreferences?.llmProvider || 'DEFAULT (AZURE_OPENAI)');
  console.log('📊 Paramètres envoyés (historique):', {
    provider: customizationPreferences?.llmProvider,
    responseSize: customizationPreferences?.responseSize,
    documentsCount: customizationPreferences?.documentsCount
  });
  
  if (convId) {
    body = JSON.stringify({
      conversation_id: convId,
      messages: options.messages,
      userFullDefinition: userFullDefinition,
      customizationPreferences: customizationPreferences,
      provider: customizationPreferences?.llmProvider
    })
  } else {
    body = JSON.stringify({
      messages: options.messages,
      userFullDefinition: userFullDefinition,
      customizationPreferences: customizationPreferences,
      provider: customizationPreferences?.llmProvider
    })
  }
  const response = await fetch('/history/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      "AuthToken":authToken,
      "EncodedUsername":encryptedUsername
    },
    body: body,
    signal: abortSignal
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      return new Response()
    })
  return response
}

export const historyUpdate = async (messages: ChatMessage[], convId: string, authToken:string, encryptedUsername:string): Promise<Response> => {
  const response = await fetch('/history/update', {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: convId,
      messages: messages
    }),
    headers: {
      'Content-Type': 'application/json',
      "AuthToken": authToken,
      "EncodedUsername":encryptedUsername
    }
  })
    .then(async res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyDelete = async (convId: string, authToken :string, encryptedUsername:string): Promise<Response> => {
  const response = await fetch('/history/delete', {
    method: 'DELETE',
    body: JSON.stringify({
      conversation_id: convId
    }),
    headers: {
      'Content-Type': 'application/json',
      "AuthToken": authToken,
      "EncodedUsername":encryptedUsername
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyDeleteAll = async (authToken: string, encryptedUsername:string): Promise<Response> => {
  const response = await fetch('/history/delete_all', {
    method: 'DELETE',
    body: JSON.stringify({}),
    headers: {
      'Content-Type': 'application/json',
      "AuthToken": authToken,
      "EncodedUsername":encryptedUsername
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyClear = async (convId: string, authToken: string, encryptedUsername:string): Promise<Response> => {
  const response = await fetch('/history/clear', {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: convId
    }),
    headers: {
      'Content-Type': 'application/json',
      "AuthToken": authToken,
      "EncodedUsername":encryptedUsername
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyRename = async (convId: string, title: string, authToken: string, encryptedUsername:string): Promise<Response> => {
  const response = await fetch('/history/rename', {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: convId,
      title: title
    }),
    headers: {
      'Content-Type': 'application/json',
      "AuthToken": authToken,
      "EncodedUsername":encryptedUsername
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyEnsure = async (token:string): Promise<CosmosDBHealth> => {
  const response = await fetch('/history/ensure', {
    method: 'GET',
    headers: {
      "AuthToken":token
    },
  })
    .then(async res => {
      const respJson = await res.json()
      let formattedResponse
      if (respJson.message) {
        formattedResponse = CosmosDBStatus.Working
      } else {
        if (res.status === 500) {
          formattedResponse = CosmosDBStatus.NotWorking
        } else if (res.status === 401) {
          formattedResponse = CosmosDBStatus.InvalidCredentials
        } else if (res.status === 422) {
          formattedResponse = respJson.error
        } else {
          formattedResponse = CosmosDBStatus.NotConfigured
        }
      }
      if (!res.ok) {
        return {
          cosmosDB: false,
          status: formattedResponse
        }
      } else {
        return {
          cosmosDB: true,
          status: formattedResponse
        }
      }
    })
    .catch(err => {
      console.error('There was an issue fetching your data.')
      return {
        cosmosDB: false,
        status: err
      }
    })
  return response
}

export const frontendSettings = async (): Promise<Response | null> => {
  const response = await fetch('/frontend_settings', {
    method: 'GET'
  })
    .then(res => {
      return res.json()
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      return null
    })

  return response
}
export const historyMessageFeedback = async (messageId: string, feedback: string, authToken: string, encryptedUsername:string): Promise<Response> => {
  const response = await fetch('/history/message_feedback', {
    method: 'POST',
    body: JSON.stringify({
      message_id: messageId,
      message_feedback: feedback
    }),
    headers: {
      'Content-Type': 'application/json',
      "AuthToken":authToken,
      "EncodedUsername":encryptedUsername
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue logging feedback.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const getHelpContent = async (lang: string = "FR"): Promise<any> => {
  const response = await fetch(`/help_content?lang=${lang}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    }
  })

  return await response.json()
}

export interface DocumentUploadResponse {
  success: boolean
  text?: string
  error?: string
  file_info?: {
    name: string
    size: number
    type?: string
    text_length?: number
  }
}

export const uploadDocument = async (file: File): Promise<DocumentUploadResponse> => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/upload-document', {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    const errorData = await response.json()
    throw new Error(errorData.error || `Upload failed with status ${response.status}`)
  }

  return await response.json()
}

export async function azureSpeechSynthesize(text: string, language: string = 'FR'): Promise<{
  success: boolean
  audio_data?: string
  audio_segments?: string[]
  content_type?: string
  voice_used?: string
  segment_count?: number
  error?: string
} | null> {
  try {
    const response = await fetch('/speech/synthesize', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ text, language })
    })

    if (!response.ok) {
      const errorData = await response.json()
      return {
        success: false,
        error: errorData.error || `Speech synthesis failed with status ${response.status}`
      }
    }

    return await response.json()
  } catch (error) {
    console.error('Azure Speech synthesis error:', error)
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    }
  }
}