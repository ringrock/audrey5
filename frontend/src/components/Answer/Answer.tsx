import { FormEvent, useContext, useEffect, useMemo, useState, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { nord } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Checkbox, DefaultButton, Dialog, FontIcon, Stack, Text } from '@fluentui/react'
import { useBoolean } from '@fluentui/react-hooks'
import { ThumbDislike20Filled, ThumbLike20Filled, Copy20Regular, Speaker120Regular, SpeakerOff20Regular } from '@fluentui/react-icons'
import DOMPurify from 'dompurify'
import remarkGfm from 'remark-gfm'
import supersub from 'remark-supersub'
import { AskResponse, Citation, Feedback, historyMessageFeedback, azureSpeechSynthesize } from '../../api'
import { XSSAllowTags, XSSAllowAttributes } from '../../constants/sanatizeAllowables'
import { AppStateContext } from '../../state/AppProvider'

import { parseAnswer } from './AnswerParser'

import styles from './Answer.module.css'

import LocalizedStrings from 'react-localization';
import rehypeRaw from 'rehype-raw'

import logoDocument from '../../assets/logoDocument.png'
import logoUrl from '../../assets/logoUrl.png'
import logoEye from '../../assets/logoEye.png'
interface Props {
  answer: AskResponse
  onCitationClicked: (citedDocument: Citation) => void
  onExectResultClicked: (answerId: string) => void
  language: string;
  pauseVoiceRecognition?: () => void
  resumeVoiceRecognition?: () => void
  isStreaming?: boolean
  questionImage?: string // Image base64 de la question précédente (optionnelle)
  messageDate?: string // Date de création du message (optionnelle)
}

export const Answer = ({ answer, onCitationClicked, onExectResultClicked, language, pauseVoiceRecognition, resumeVoiceRecognition, isStreaming, questionImage, messageDate}: Props) => {
  const appStateContext = useContext(AppStateContext)
  const initializeAnswerFeedback = (answer: AskResponse) => {
    if (answer.message_id == undefined) return undefined
    if (answer.feedback == undefined) return undefined
    if (answer.feedback.split(',').length > 1) return Feedback.Negative
    if (Object.values(Feedback).includes(answer.feedback)) return answer.feedback
    return Feedback.Neutral
  }

  localizedStrings.setLanguage(language);

  // Fonction pour générer le disclaimer avec la date de création du message
  const generateDisclaimer = () => {
    // Utiliser la date du message si disponible, sinon la date actuelle
    const date = messageDate ? new Date(messageDate) : new Date();
    if (language === 'FR') {
      const dateString = date.toLocaleDateString('fr-FR', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
      return `Les réponses générées par l'IA peuvent être incorrectes - ${dateString}`;
    } else {
      const dateString = date.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
      return `AI-generated content may be incorrect - ${dateString}`;
    }
  };

  const [isRefAccordionOpen, { toggle: toggleIsRefAccordionOpen }] = useBoolean(false)
  const filePathTruncationLimit = 50

  const parsedAnswer = useMemo(() => parseAnswer(answer), [answer])
  const [chevronIsExpanded, setChevronIsExpanded] = useState(isRefAccordionOpen)
  const [feedbackState, setFeedbackState] = useState(initializeAnswerFeedback(answer))
  const [isFeedbackDialogOpen, setIsFeedbackDialogOpen] = useState(false)
  const [showReportInappropriateFeedback, setShowReportInappropriateFeedback] = useState(false)
  const [negativeFeedbackList, setNegativeFeedbackList] = useState<Feedback[]>([])
  const [copySuccess, setCopySuccess] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [speechSynthesis, setSpeechSynthesis] = useState<SpeechSynthesisUtterance | null>(null)
  const autoPlayTriggeredRef = useRef<string | null>(null)
  const audioElementsRef = useRef<HTMLAudioElement[]>([])
  const abortControllerRef = useRef<AbortController | null>(null)
  const isManualStopRef = useRef<boolean>(false)
  const FEEDBACK_ENABLED =
    appStateContext?.state.frontendSettings?.feedback_enabled && appStateContext?.state.isCosmosDBAvailable?.cosmosDB
  const SANITIZE_ANSWER = appStateContext?.state.frontendSettings?.sanitize_answer

  const ui = appStateContext?.state.frontendSettings?.ui;

  const handleChevronClick = () => {
    setChevronIsExpanded(!chevronIsExpanded)
    toggleIsRefAccordionOpen()
  }

  useEffect(() => {
    setChevronIsExpanded(isRefAccordionOpen)
  }, [isRefAccordionOpen])

  // Auto-lecture audio si activée - UNIQUEMENT pour le dernier message assistant
  useEffect(() => {
    // Déclencher SEULEMENT si c'est un nouveau message ET que l'auto-lecture est activée ET que c'est le dernier message assistant
    if (appStateContext?.state.isAutoAudioEnabled && 
        parsedAnswer?.markdownFormatText && 
        answer.message_id !== undefined &&
        !isStreaming &&
        !isPlaying &&
        autoPlayTriggeredRef.current !== answer.message_id) {
      
      console.log('🔍 Vérification auto-lecture pour message:', answer.message_id)
      
      // Attendre un peu que le DOM soit à jour
      const timeoutId = setTimeout(() => {
        // Vérifier que ce message est bien le dernier message assistant de la page
        const allAssistantMessages = document.querySelectorAll('[data-message-role="assistant"]')
        const currentMessageElement = document.querySelector(`[data-message-id="${answer.message_id}"]`)
        
        console.log('🔍 Messages assistant trouvés:', allAssistantMessages.length)
        console.log('🔍 Élément actuel trouvé:', !!currentMessageElement)
        
        if (allAssistantMessages.length > 0) {
          const lastAssistantMessage = allAssistantMessages[allAssistantMessages.length - 1]
          const lastMessageId = lastAssistantMessage.getAttribute('data-message-id')
          console.log('🔍 Dernier message ID:', lastMessageId, '| Message actuel ID:', answer.message_id)
          
          // Seulement déclencher si c'est le dernier message assistant
          if (currentMessageElement && currentMessageElement === lastAssistantMessage) {
            
            // Marquer immédiatement pour éviter les re-triggers
            autoPlayTriggeredRef.current = answer.message_id || null
            
            // Vérifier les conditions audio avant de déclencher
            const anyAudioPlaying = Array.from(document.querySelectorAll('audio')).some(audio => !audio.paused)
            const browserSpeechPlaying = window.speechSynthesis.speaking
            
            if (appStateContext?.state.isAutoAudioEnabled && 
                !isPlaying && 
                !anyAudioPlaying &&
                !browserSpeechPlaying &&
                autoPlayTriggeredRef.current === answer.message_id) {
              
              console.log('🔊 Auto-lecture déclenchée pour le dernier message:', answer.message_id)
              playAudio()
            }
          } else {
            console.log('🔍 Ce message n\'est pas le dernier - pas d\'auto-lecture')
          }
        }
      }, 100) // Délai très réduit pour un lancement rapide
      
      return () => clearTimeout(timeoutId)
    }
  }, [parsedAnswer?.markdownFormatText, answer.message_id, isStreaming])
  // IMPORTANT: Ne pas inclure isPlaying ni isAutoAudioEnabled dans les dépendances pour éviter les re-triggers

  useEffect(() => {
    if (answer.message_id == undefined) return

    let currentFeedbackState
    if (appStateContext?.state.feedbackState && appStateContext?.state.feedbackState[answer.message_id]) {
      currentFeedbackState = appStateContext?.state.feedbackState[answer.message_id]
    } else {
      currentFeedbackState = initializeAnswerFeedback(answer)
    }
    setFeedbackState(currentFeedbackState)
  }, [appStateContext?.state.feedbackState, feedbackState, answer.message_id])

  const createCitationFilepath = (citation: Citation, index: number, truncate: boolean = false) => {
    let citationFilename = ''

    // Does the citation have a title ?
    if (citation.title) {
      const part_i = citation.part_index ?? (citation.chunk_id ? parseInt(citation.chunk_id) + 1 : '')
      if (truncate && citation.title.length > filePathTruncationLimit) {
        const citationLength = citation.title.length
        citationFilename = `${citation.title.substring(0, 20)}...${citation.title.substring(citationLength - 20)} - Part ${part_i}`
      } else {
        citationFilename = `${citation.title} - Part ${part_i}`
      }
    } else if (citation.title && citation.reindex_id) {
      citationFilename = `${citation.title} - Part ${citation.reindex_id}`
    } else {
      // else, use filepath
      if (citation.filepath) {
        const part_i = citation.part_index ?? (citation.chunk_id ? parseInt(citation.chunk_id) + 1 : '')
        if (truncate && citation.filepath.length > filePathTruncationLimit) {
          const citationLength = citation.filepath.length
          citationFilename = `${citation.filepath.substring(0, 20)}...${citation.filepath.substring(citationLength - 20)} - Part ${part_i}`
        } else {
          citationFilename = `${citation.filepath} - Part ${part_i}`
        }
      } else if (citation.filepath && citation.reindex_id) {
        citationFilename = `${citation.filepath} - Part ${citation.reindex_id}`
      } else {
        citationFilename = `Citation ${index}`
      }
    }
    return citationFilename
  }

  const onLikeResponseClicked = async () => {
    if (answer.message_id == undefined) return;
    if (appStateContext?.state.authToken == undefined || appStateContext?.state.authToken == "") return;
    let newFeedbackState = feedbackState
    // Set or unset the thumbs up state
    if (feedbackState == Feedback.Positive) {
      newFeedbackState = Feedback.Neutral
    } else {
      newFeedbackState = Feedback.Positive
    }
    appStateContext?.dispatch({
      type: 'SET_FEEDBACK_STATE',
      payload: { answerId: answer.message_id, feedback: newFeedbackState }
    })
    setFeedbackState(newFeedbackState)

    // Update message feedback in db
    await historyMessageFeedback(answer.message_id, newFeedbackState, appStateContext?.state.authToken, appStateContext?.state.encryptedUsername)
  }

  const onDislikeResponseClicked = async () => {
    if (answer.message_id == undefined) return;
    if (appStateContext?.state.authToken == undefined || appStateContext?.state.authToken == "") return;

    let newFeedbackState = feedbackState
    if (feedbackState === undefined || feedbackState === Feedback.Neutral || feedbackState === Feedback.Positive) {
      newFeedbackState = Feedback.Negative
      setFeedbackState(newFeedbackState)
      setIsFeedbackDialogOpen(true)
    } else {
      // Reset negative feedback to neutral
      newFeedbackState = Feedback.Neutral
      setFeedbackState(newFeedbackState)
      await historyMessageFeedback(answer.message_id, Feedback.Neutral, appStateContext?.state.authToken, appStateContext?.state.encryptedUsername)
    }
    appStateContext?.dispatch({
      type: 'SET_FEEDBACK_STATE',
      payload: { answerId: answer.message_id, feedback: newFeedbackState }
    })
  }

  const updateFeedbackList = (ev?: FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
    if (answer.message_id == undefined) return
    const selectedFeedback = (ev?.target as HTMLInputElement)?.id as Feedback

    let feedbackList = negativeFeedbackList.slice()
    if (checked) {
      feedbackList.push(selectedFeedback)
    } else {
      feedbackList = feedbackList.filter(f => f !== selectedFeedback)
    }

    setNegativeFeedbackList(feedbackList)
  }

  const onSubmitNegativeFeedback = async () => {
    if (answer.message_id == undefined) return;
    if (appStateContext?.state.authToken == undefined || appStateContext?.state.authToken == "") return;
    
    await historyMessageFeedback(answer.message_id, negativeFeedbackList.join(','), appStateContext?.state.authToken, appStateContext?.state.encryptedUsername)
    resetFeedbackDialog()
  }

  const resetFeedbackDialog = () => {
    setIsFeedbackDialogOpen(false)
    setShowReportInappropriateFeedback(false)
    setNegativeFeedbackList([])
  }

  const onCopyResponseClicked = async () => {
    if (!parsedAnswer?.markdownFormatText) return;
    
    try {
      // Copier le texte sans les balises HTML
      const textContent = parsedAnswer.markdownFormatText.replace(/<[^>]*>/g, '');
      await navigator.clipboard.writeText(textContent);
      setCopySuccess(true);
      
      // Réinitialiser l'état après 2 secondes
      setTimeout(() => {
        setCopySuccess(false);
      }, 2000);
    } catch (err) {
      console.error('Erreur lors de la copie:', err);
    }
  }

  const playAudio = async () => {
    // Réinitialiser le flag d'arrêt manuel au début de toute nouvelle lecture
    isManualStopRef.current = false
    
    if (!parsedAnswer?.markdownFormatText) return
    
    if (isPlaying) {
      stopAudio()
      return
    }
    
    // Suspendre l'écoute vocale pour éviter que le système s'entende parler
    pauseVoiceRecognition?.()
    
    // IMPORTANT: Arrêter SEULEMENT les audios qui jouent actuellement
    // Cela évite que des lectures précédentes reprennent en parallèle
    // mais n'interfère pas avec l'auto-lecture des autres composants
    const allAudioElements = document.querySelectorAll('audio')
    allAudioElements.forEach((audio, index) => {
      if (!audio.paused) {
        audio.pause()
        audio.currentTime = 0
        audio.src = '' // Force cleanup seulement pour les audios en cours
      }
    })
    
    // Stopper toute lecture en cours au niveau système (browser speech)
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel()
    }
    
    // Envoyer le texte markdown brut au backend - tout le nettoyage sera fait côté backend
    const textToSynthesize = parsedAnswer.markdownFormatText
    
    if (!textToSynthesize) return
    
    // Vérifier si Azure Speech Services est activé
    const azureSpeechEnabled = appStateContext?.state.frontendSettings?.azure_speech_enabled
    
    if (azureSpeechEnabled) {
      await playAudioWithAzure(textToSynthesize)
    } else {
      await playAudioWithBrowser(textToSynthesize)
    }
  }

  const playAudioWithAzure = async (text: string) => {
    try {
      setIsPlaying(true)
      
      const result = await azureSpeechSynthesize(text, language)
      
      if (!result?.success) {
        console.error('Azure Speech error:', result?.error)
        // Reprendre l'écoute en cas d'erreur avant de basculer vers le navigateur
        resumeVoiceRecognition?.()
        await playAudioWithBrowser(text)
        return
      }
      
      // Vérifier s'il s'agit de segments multiples ou d'un seul audio
      if (result.audio_segments && result.audio_segments.length > 1 && result.content_type) {
        // Lecture séquentielle des segments
        await playAudioSegments(result.audio_segments, result.content_type)
      } else {
        // Lecture simple d'un seul audio
        const audioData = result.audio_data 
          ? `data:${result.content_type || 'audio/mpeg'};base64,${result.audio_data}`
          : result.audio_segments && result.audio_segments[0]
            ? `data:${result.content_type || 'audio/mpeg'};base64,${result.audio_segments[0]}`
            : null
        
        if (!audioData) {
          playAudioWithBrowser(text)
          return
        }
        
        const audio = new Audio(audioData)
        
        // IMPORTANT: Ajouter l'élément audio à la référence pour pouvoir l'arrêter
        audioElementsRef.current = [audio]
        
        audio.onended = () => {
          setIsPlaying(false)
          setSpeechSynthesis(null)
          // Nettoyer les éléments audio après lecture
          audioElementsRef.current = []
          // Nettoyer la référence d'auto-play après lecture complète
          autoPlayTriggeredRef.current = null
          // Réinitialiser le flag d'arrêt manuel
          isManualStopRef.current = false
          // Reprendre l'écoute vocale après la lecture
          resumeVoiceRecognition?.()
        }
        
        audio.onerror = async (event) => {
          setIsPlaying(false)
          setSpeechSynthesis(null)
          // Nettoyer les éléments audio en cas d'erreur
          audioElementsRef.current = []
          // Nettoyer la référence d'auto-play en cas d'erreur
          autoPlayTriggeredRef.current = null
          
          // Reprendre l'écoute vocale en cas d'erreur
          resumeVoiceRecognition?.()
          
          // Seulement faire le fallback si ce n'est pas un arrêt manuel
          if (!isManualStopRef.current) {
            await playAudioWithBrowser(text)
          } else {
            isManualStopRef.current = false // Reset for next time
          }
        }
        
        await audio.play()
      }
      
    } catch (err) {
      console.error('Azure Speech synthesis error:', err)
      setIsPlaying(false)
      setSpeechSynthesis(null)
      // Nettoyer les éléments audio en cas d'erreur
      audioElementsRef.current = []
      // Nettoyer la référence d'auto-play en cas d'erreur
      autoPlayTriggeredRef.current = null
      // Reprendre l'écoute vocale en cas d'erreur
      resumeVoiceRecognition?.()
      await playAudioWithBrowser(text)
    }
  }
  
  const playAudioSegments = async (segments: string[], contentType: string) => {
    try {
      // Créer un nouveau AbortController pour cette lecture
      abortControllerRef.current = new AbortController()
      const signal = abortControllerRef.current.signal
      
      // Nettoyer les éléments audio précédents
      audioElementsRef.current = []
      
      for (let i = 0; i < segments.length; i++) {
        // Vérifier si l'arrêt a été demandé
        if (signal.aborted) {
          throw new Error('Playback aborted')
        }
        
        const audioData = `data:${contentType};base64,${segments[i]}`
        const audio = new Audio(audioData)
        audioElementsRef.current.push(audio)
        
        // Attendre que ce segment soit fini avant de passer au suivant
        await new Promise<void>((resolve, reject) => {
          const onAbort = () => {
            audio.pause()
            audio.currentTime = 0
            reject(new Error('Playback aborted'))
          }
          
          signal.addEventListener('abort', onAbort)
          
          audio.onended = () => {
            signal.removeEventListener('abort', onAbort)
            resolve()
          }
          audio.onerror = (event) => {
            signal.removeEventListener('abort', onAbort)
            console.error(`Error playing segment ${i + 1}:`, event)
            reject(new Error(`Error playing segment ${i}`))
          }
          
          audio.play().catch(reject)
        })
        
        // Pause minimale entre les segments pour fluidité
        if (i < segments.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 50))
        }
      }
      
      setIsPlaying(false)
      setSpeechSynthesis(null)
      audioElementsRef.current = []
      abortControllerRef.current = null
      // Nettoyer la référence d'auto-play après lecture complète
      autoPlayTriggeredRef.current = null
      // Reprendre l'écoute vocale après tous les segments
      resumeVoiceRecognition?.()
      
    } catch (err) {
      if (err instanceof Error && err.message === 'Playback aborted') {
        // Playback stopped by user
      } else {
        console.error('Error playing audio segments:', err)
      }
      setIsPlaying(false)
      setSpeechSynthesis(null)
      audioElementsRef.current = []
      abortControllerRef.current = null
      // Nettoyer la référence d'auto-play en cas d'erreur
      autoPlayTriggeredRef.current = null
      // Reprendre l'écoute vocale en cas d'erreur
      resumeVoiceRecognition?.()
    }
  }

  const playAudioWithBrowser = async (text: string) => {
    try {
      // Double vérification avant de démarrer
      if (isPlaying) {
        return
      }
      
      // Nettoyer le texte côté backend même pour le navigateur
      const response = await fetch('/speech/clean', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text })
      })
      
      let cleanedText = text
      if (response.ok) {
        const result = await response.json()
        if (result.success && result.cleaned_text) {
          cleanedText = result.cleaned_text
        }
      }
      
      const utterance = new SpeechSynthesisUtterance(cleanedText)
      
      // Configuration
      utterance.lang = language === 'FR' ? 'fr-FR' : 'en-US'
      utterance.rate = 1.15
      utterance.pitch = 0.7
      utterance.volume = 1
      
      // Sélection de voix simple
      const voices = window.speechSynthesis.getVoices()
      const targetLang = language === 'FR' ? 'fr' : 'en'
      const bestVoice = voices.find(voice => voice.lang.includes(targetLang))
      
      if (bestVoice) {
        utterance.voice = bestVoice
      }
      
      utterance.onstart = () => {
        setIsPlaying(true)
      }
      utterance.onend = () => {
        setIsPlaying(false)
        setSpeechSynthesis(null)
        // Nettoyer la référence d'auto-play après lecture complète
        autoPlayTriggeredRef.current = null
        // Reprendre l'écoute vocale après la lecture navigateur
        resumeVoiceRecognition?.()
      }
      utterance.onerror = (event) => {
        console.error('Browser speech error:', event)
        setIsPlaying(false)
        setSpeechSynthesis(null)
        // Nettoyer la référence d'auto-play en cas d'erreur
        autoPlayTriggeredRef.current = null
        // Reprendre l'écoute vocale en cas d'erreur
        resumeVoiceRecognition?.()
      }
      
      setSpeechSynthesis(utterance)
      setIsPlaying(true)
      window.speechSynthesis.speak(utterance)
    } catch (err) {
      console.error('Browser speech error:', err)
      setIsPlaying(false)
      setSpeechSynthesis(null)
      // Nettoyer la référence d'auto-play en cas d'erreur
      autoPlayTriggeredRef.current = null
      // Reprendre l'écoute vocale en cas d'erreur
      resumeVoiceRecognition?.()
    }
  }

  const stopAudio = () => {
    // Marquer que c'est un arrêt manuel pour éviter le fallback
    isManualStopRef.current = true
    
    // Arrêter TOUS les audios de la page pour éviter les reprises parallèles
    const allAudioElements = document.querySelectorAll('audio')
    allAudioElements.forEach((audio) => {
      if (!audio.paused) {
        audio.pause()
        audio.currentTime = 0
        audio.src = '' // Force cleanup
      }
    })
    
    // Arrêter la synthèse vocale du navigateur
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel()
    }
    
    // Arrêter tous les éléments audio Azure Speech de ce composant
    audioElementsRef.current.forEach((audio, index) => {
      try {
        audio.pause()
        audio.currentTime = 0
        audio.src = '' // Force cleanup pour empêcher la reprise
        // Supprimer l'élément audio du DOM pour éviter qu'il reprenne plus tard
        if (audio.parentNode) {
          audio.parentNode.removeChild(audio)
        }
      } catch (err) {
        console.error(`Error stopping audio segment ${index + 1}:`, err)
      }
    })
    
    // Annuler la lecture en cours via AbortController
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    
    // Nettoyer les états
    setIsPlaying(false)
    setSpeechSynthesis(null)
    audioElementsRef.current = []
    
    // Réinitialiser la référence d'auto-play pour permettre une nouvelle lecture
    if (answer.message_id && autoPlayTriggeredRef.current === answer.message_id) {
      autoPlayTriggeredRef.current = null
    }
    
    // Reprendre l'écoute vocale si arrêt manuel
    resumeVoiceRecognition?.()
  }

  const toggleAudio = () => {
    if (isPlaying) {
      stopAudio()
    } else {
      playAudio()
    }
  }


  const shouldDisplayCitationLink = (citation : Citation) => {
    
    try{
      
      return (
        citation.url
        && (
          citation.url?.includes("iddoc_") == true 
          || citation.url?.includes("blob.core") == true 
          || decodeBase64String(citation.url).includes("blob.core") == true
        )
      );
    } catch (e) {
      return false;
    }
  }

  const shouldDisplayAttachmentLink = (citation : Citation) => {
    
    try{

      return (
       citation.url
        && (
          citation.url?.includes("blob.core") == true 
          || decodeBase64String(citation.url).includes("blob.core") == true
        )
      );
    } catch (e) {
      return false;
    }
  }
  

  const decodeBase64String = (encodedString : string)  => {
    // Supprimer le dernier caractère de la chaîne encodée
    var encodedStringWithoutTrailingCharacter = encodedString.slice(0, -1);
    
    // Décoder la chaîne Base64URL
    var encodedBytes = atob(encodedStringWithoutTrailingCharacter.replace(/-/g, '+').replace(/_/g, '/'));
    
    // Décoder les octets en chaîne de caractères
    var decodedString = decodeURIComponent(escape(encodedBytes));
    
    return decodedString;
}

  const handleOpenDocumentById = (id : string, action : string) => {

    const message = {
      action: action,
      idDoc: id,
    };
    
    // Envoi du message au parent
    window.parent.postMessage(message, "*");
  }


  const postCreateRecord = (description : string) => {

    const message: any = {
      action: "CreateRecord",
      description: description,
    };
    
    // Ajouter l'image si elle est disponible
    if (questionImage) {
      message.image = questionImage;
      console.log('📷 Image ajoutée au CreateRecord:', questionImage.substring(0, 50) + '...')
    } else {
      console.log('📷 Aucune image disponible pour le CreateRecord')
    }
    
    // Envoi du message au parent
    window.parent.postMessage(message, "*");
  }

  
  const handleOpenDocument = (citation: Citation, action: string) => {
    if (citation.url != null) {
      var idDoc = '-';
  
      if (citation.url.startsWith("iddoc_")) {
        idDoc = citation.url.slice(6);
      } else {
        const regex = /\/([^\/]+)\/[^\/]+$/;
        var fileUrl = citation.url.includes("http") ? citation.url : decodeBase64String(citation.url);
  
        const match = fileUrl.match(regex);
        if (match && match.length > 1) {
          idDoc = match[1]; 
        } else {
          console.log("Aucun code trouvé dans l'URL.");
        }
      }
  
      if (idDoc != '-') {
        // Préparer un extrait de texte significatif pour la recherche
        // Prendre 40-50 caractères maximum pour éviter les problèmes de formatage
        let searchText = '';
        if (citation.content) {
          searchText = citation.content.replace(/\s+/g, ' ').trim();
          //searchText = searchText.substring(0, Math.min(50, searchText.length));
        }
  
        const message = {
          action: action,
          idDoc: idDoc,
          citationText: searchText
        };
        
        // Envoi du message au parent
        window.parent.postMessage(message, "*");
      } else {
        console.error("Impossible de déterminer l'id du document depuis l'URL de la citation.");
        console.error(citation);
      }
    }
  }

  const UnhelpfulFeedbackContent = () => {
    return (
      <>
        <div>{localizedStrings.labelWhy}</div>
        <Stack tokens={{ childrenGap: 4 }}>
          <Checkbox
            label={localizedStrings.feedbackMissingCitations}
            id={Feedback.MissingCitation}
            defaultChecked={negativeFeedbackList.includes(Feedback.MissingCitation)}
            onChange={updateFeedbackList}></Checkbox>
          <Checkbox
            label={localizedStrings.feedbackWrongCitation}
            id={Feedback.WrongCitation}
            defaultChecked={negativeFeedbackList.includes(Feedback.WrongCitation)}
            onChange={updateFeedbackList}></Checkbox>
          <Checkbox
            label={localizedStrings.feedbackOutOfScope}
            id={Feedback.OutOfScope}
            defaultChecked={negativeFeedbackList.includes(Feedback.OutOfScope)}
            onChange={updateFeedbackList}></Checkbox>
          <Checkbox
            label={localizedStrings.feedbackInaccurateOrIrrelevant}
            id={Feedback.InaccurateOrIrrelevant}
            defaultChecked={negativeFeedbackList.includes(Feedback.InaccurateOrIrrelevant)}
            onChange={updateFeedbackList}></Checkbox>
          <Checkbox
            label={localizedStrings.feedbackOtherUnhelpful}
            id={Feedback.OtherUnhelpful}
            defaultChecked={negativeFeedbackList.includes(Feedback.OtherUnhelpful)}
            onChange={updateFeedbackList}></Checkbox>
        </Stack>
        <div onClick={() => setShowReportInappropriateFeedback(true)} style={{ color: '#115EA3', cursor: 'pointer' }}>
          {localizedStrings.reportInappropriateContent}
        </div>
      </>
    )
  }

  const ReportInappropriateFeedbackContent = () => {
    return (
      <>
        <div>
          {localizedStrings.feedbackInappropriateLabel}
        </div>
        <Stack tokens={{ childrenGap: 4 }}>
          <Checkbox
            label={localizedStrings.feedbackInappropriateHate}
            id={Feedback.HateSpeech}
            defaultChecked={negativeFeedbackList.includes(Feedback.HateSpeech)}
            onChange={updateFeedbackList}></Checkbox>
          <Checkbox
            label={localizedStrings.feedbackInappropriateViolent}
            id={Feedback.Violent}
            defaultChecked={negativeFeedbackList.includes(Feedback.Violent)}
            onChange={updateFeedbackList}></Checkbox>
          <Checkbox
            label={localizedStrings.feedbackInappropriateSexual}
            id={Feedback.Sexual}
            defaultChecked={negativeFeedbackList.includes(Feedback.Sexual)}
            onChange={updateFeedbackList}></Checkbox>
          <Checkbox
            label={localizedStrings.feedbackInappropriateManipulative}
            defaultChecked={negativeFeedbackList.includes(Feedback.Manipulative)}
            id={Feedback.Manipulative}
            onChange={updateFeedbackList}></Checkbox>
          <Checkbox
            label={localizedStrings.feedbackInappropriateOther}
            id={Feedback.OtherHarmful}
            defaultChecked={negativeFeedbackList.includes(Feedback.OtherHarmful)}
            onChange={updateFeedbackList}></Checkbox>
        </Stack>
      </>
    )
  }

  const components = {
    code({ node, ...props }: { node: any;[key: string]: any }) {
      let language
      if (props.className) {
        const match = props.className.match(/language-(\w+)/)
        language = match ? match[1] : undefined
      }
      const codeString = node.children[0].value ?? ''
      return (
        <SyntaxHighlighter style={nord} language={language} PreTag="div" {...props}>
          {codeString}
        </SyntaxHighlighter>
      )
    },
    // Gestion des éléments personnalisés créés via le parser
    span({ className, children, ...props }: { className?: string; children: React.ReactNode; [key: string]: any }) {
      
      if (className === 'iddoc-link') {
        const id = props['data-id'];
        const ref = props['data-ref'];
        return (
          <span
            {...props}
            onClick={() => handleOpenDocumentById(id, 'OpenIdDoc')}
            style={{ color: 'blue', cursor: 'pointer', textDecoration: 'underline'  }}
          >
            {children} {/* Affiche le texte du lien */}
          </span>
        );
      }
  
      if (className === 'create-record-link') {
        const description = props['data-description'];
        return (
          <span
            {...props}
            onClick={() => postCreateRecord(description)}
            style={{ color: 'blue', cursor: 'pointer', textDecoration: 'underline' }}
          >
            {children} {/* Affiche le texte du lien */}
          </span>
        );
      }
  
      return <span {...props}>{children}</span>; // Si aucune des classes ne correspond
    },
  }

  return (
    <>
      <Stack 
        className={styles.answerContainer} 
        tabIndex={0}
        data-message-role="assistant"
        data-message-id={answer.message_id}
      >
        <Stack.Item>
          <Stack horizontal grow>
            <Stack.Item grow>
              {parsedAnswer && <ReactMarkdown
                linkTarget="_blank"
                remarkPlugins={[remarkGfm, supersub]}
                rehypePlugins={[rehypeRaw]}
                /* Utilisation de sanitize, comme on utilise rehypeRax pour autoriser l'exécution des balises */
                children={
                    DOMPurify.sanitize(
                      parsedAnswer?.markdownFormatText, { 
                        ALLOWED_TAGS: XSSAllowTags
                        , ALLOWED_ATTR: XSSAllowAttributes }
                    )

                }
                className={styles.answerText}
                components={components}
              />}
            </Stack.Item>
            <Stack.Item className={styles.answerHeader}>
              {(FEEDBACK_ENABLED && answer.message_id !== undefined) || (!FEEDBACK_ENABLED && answer.message_id !== undefined) ? (
                <Stack horizontal horizontalAlign="space-between">
                  {isPlaying ? (
                    <SpeakerOff20Regular
                      aria-hidden="false"
                      aria-label={localizedStrings.stopAudio}
                      onClick={stopAudio}
                      style={{ color: '#d13438', cursor: 'pointer' }}
                    />
                  ) : (
                    <Speaker120Regular
                      aria-hidden="false"
                      aria-label={localizedStrings.playAudio}
                      onClick={playAudio}
                      style={{ color: 'slategray', cursor: 'pointer' }}
                    />
                  )}
                  <Copy20Regular
                    aria-hidden="false"
                    aria-label={copySuccess ? localizedStrings.copied : localizedStrings.copyResponse}
                    onClick={() => onCopyResponseClicked()}
                    style={
                      copySuccess
                        ? { color: 'darkgreen', cursor: 'pointer' }
                        : { color: 'slategray', cursor: 'pointer' }
                    }
                  />
                  {FEEDBACK_ENABLED && (
                    <>
                      <ThumbLike20Filled
                        aria-hidden="false"
                        aria-label="Like this response"
                        onClick={() => onLikeResponseClicked()}
                        style={
                          feedbackState === Feedback.Positive ||
                            appStateContext?.state.feedbackState[answer.message_id] === Feedback.Positive
                            ? { color: 'darkgreen', cursor: 'pointer' }
                            : { color: 'slategray', cursor: 'pointer' }
                        }
                      />
                      <ThumbDislike20Filled
                        aria-hidden="false"
                        aria-label="Dislike this response"
                        onClick={() => onDislikeResponseClicked()}
                        style={
                          feedbackState !== Feedback.Positive &&
                            feedbackState !== Feedback.Neutral &&
                            feedbackState !== undefined
                            ? { color: 'darkred', cursor: 'pointer' }
                            : { color: 'slategray', cursor: 'pointer' }
                        }
                      />
                    </>
                  )}
                </Stack>
              ) : null}
            </Stack.Item>
          </Stack>
        </Stack.Item>
        {parsedAnswer?.generated_chart !== null && (
          <Stack className={styles.answerContainer}>
            <Stack.Item grow>
              <img src={`data:image/png;base64, ${parsedAnswer?.generated_chart}`} />
            </Stack.Item>
          </Stack>
        )}
        <Stack horizontal className={styles.answerFooter}>
          {!!parsedAnswer?.citations.length && (
            <Stack.Item onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? toggleIsRefAccordionOpen() : null)}>
              <Stack style={{ width: '100%' }}>
                <Stack horizontal horizontalAlign="start" verticalAlign="center">
                  <Text
                    className={styles.accordionTitle}
                    onClick={toggleIsRefAccordionOpen}
                    aria-label="Open references"
                    tabIndex={0}
                    role="button">
                    <span>
                      {parsedAnswer.citations.length > 1
                        ? parsedAnswer.citations.length + ' references'
                        : '1 reference'}
                    </span>
                  </Text>
                  <FontIcon
                    className={styles.accordionIcon}
                    onClick={handleChevronClick}
                    iconName={chevronIsExpanded ? 'ChevronDown' : 'ChevronRight'}
                  />
                </Stack>
              </Stack>
            </Stack.Item>
          )}
          <Stack.Item className={styles.answerDisclaimerContainer}>
            <span className={styles.answerDisclaimer}>{generateDisclaimer()}</span>
          </Stack.Item>
          {!!answer.exec_results?.length && (
            <Stack.Item onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? toggleIsRefAccordionOpen() : null)}>
              <Stack style={{ width: '100%' }}>
                <Stack horizontal horizontalAlign="start" verticalAlign="center">
                  <Text
                    className={styles.accordionTitle}
                    onClick={() => onExectResultClicked(answer.message_id ?? '')}
                    aria-label="Open Intents"
                    tabIndex={0}
                    role="button">
                    <span>
                      Show Intents
                    </span>
                  </Text>
                  <FontIcon
                    className={styles.accordionIcon}
                    onClick={handleChevronClick}
                    iconName={'ChevronRight'}
                  />
                </Stack>
              </Stack>
            </Stack.Item>
          )}
        </Stack>
        {chevronIsExpanded && (
          <div className={styles.citationWrapper}>
            {parsedAnswer?.citations.map((citation, idx) => {
              
              var shouldDisplayLink = shouldDisplayCitationLink(citation);
              var shouldDisplayAttLink = shouldDisplayAttachmentLink(citation);

              return (
                <div className={styles.citationOverlapDiv}>
                <span
                  title={createCitationFilepath(citation, ++idx)}
                  tabIndex={0}
                  role="link"
                  key={idx}
                  onClick={() => onCitationClicked(citation)}
                  onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? onCitationClicked(citation) : null)}
                  className={styles.citationContainer}
                  aria-label={createCitationFilepath(citation, idx)}>
                  <div className={styles.citation}>{idx}</div>
                  {createCitationFilepath(citation, idx, true)}
                </span>
                { (shouldDisplayLink) &&
                  
                  <div className={styles.referencesContainer}>
                    {/* Exemple pour une seule référence */}
                    <div className={styles.referenceItem}>
                      <div className={styles.dropdown}>
                        <button className={styles.dropdownButton}>
                          <img src={logoEye} height="20px" width="20px" alt="Document" />
                          <span className={styles.arrow}>▼</span>
                        </button>
                        <div className={styles.dropdownMenu}>
                          <span
                            onClick={() => handleOpenDocument(citation, "OpenIdDoc")}
                            role="button" // Ceci améliore l'accessibilité
                            tabIndex={0}  // Pour le rendre focusable, accessible au clavier
                            className={styles.dropdownLink}
                          >
                            <img src={logoDocument} height="16px" width="16px" alt="Ouvrir" />
                            <span className={styles.hideOnSmall}>{localizedStrings.openDocument}</span>
                          </span>
                          {
                            (shouldDisplayAttLink) && 
                            <span
                              onClick={() => handleOpenDocument(citation, "OpenAttachmentsIdDoc")}
                              role="button" // Ceci améliore l'accessibilité
                              tabIndex={0}  // Pour le rendre focusable, accessible au clavier
                              className={styles.dropdownLink}
                            >
                              <img src={logoUrl} height="16px" width="16px" alt="Prévisualiser" />
                              <span className={styles.hideOnSmall}>{localizedStrings.openAttachment}</span>
                            </span>
                          }
                        </div>
                      </div>
                    </div>
                  </div>

                
                
                }    
                </div>
              )
            })}
          </div>
        )}
      </Stack>
      <Dialog
        onDismiss={() => {
          resetFeedbackDialog()
          setFeedbackState(Feedback.Neutral)
        }}
        hidden={!isFeedbackDialogOpen}
        styles={{
          main: [
            {
              selectors: {
                ['@media (min-width: 480px)']: {
                  maxWidth: '600px',
                  background: '#FFFFFF',
                  boxShadow: '0px 14px 28.8px rgba(0, 0, 0, 0.24), 0px 0px 8px rgba(0, 0, 0, 0.2)',
                  borderRadius: '8px',
                  maxHeight: '600px',
                  minHeight: '100px'
                }
              }
            }
          ]
        }}
        dialogContentProps={{
          title: localizedStrings.submitFeedbakc,
          showCloseButton: true
        }}>
        <Stack tokens={{ childrenGap: 4 }}>
          <div>{localizedStrings.feedbackHelps}</div>

          {!showReportInappropriateFeedback ? <UnhelpfulFeedbackContent /> : <ReportInappropriateFeedbackContent />}

          <div>{localizedStrings.feedbackWillBVisible}</div>

          <DefaultButton disabled={negativeFeedbackList.length < 1} onClick={onSubmitNegativeFeedback}>
            {localizedStrings.submit}
          </DefaultButton>
        </Stack>
      </Dialog>
    </>
  )
}



let localizedStrings = new LocalizedStrings({
  FR: {
      openDocument : "Ouvrir le document",
      openAttachment : "Ouvrir la pièce-jointe",
      copyResponse: "Copier la réponse",
      copied: "Copié!",
      playAudio: "Lire la réponse",
      stopAudio: "Arrêter la lecture",
      enableAutoAudio: "Activer la lecture automatique",
      disableAutoAudio: "Désactiver la lecture automatique",
      submitFeedbakc: "Soumette un avis",
      feedbackHelps: "Votre feedback nous permet d'améliorer votre expérience.",
      feedbackWillBVisible: "En validant, votre retour sera rendu visible pour les administrateurs de l'application.",
      submit: "Soumettre",
      aiDisclaimer: "Les réponses générées par l'IA peuvent être incorrectes",
      // Unhelpful
      labelWhy: "Pourquoi cette réponse n'était pas adaptée ?",
      feedbackMissingCitations: "Manque de citations",
      feedbackWrongCitation: "Les citations ne sont pas bonnes",
      feedbackOutOfScope: "La réponse ne s'appuie pas sur mes données",
      feedbackInaccurateOrIrrelevant: "Imprécis ou non pertinent",
      feedbackOtherUnhelpful: "Autres",
      reportInappropriateContent:"Signaler un contenu inaproprié",
      // inapropriate
      feedbackInappropriateLabel:"Le contenu est :",
      feedbackInappropriateHate:"Discours de haine, stéréotypes, humiliations",
      feedbackInappropriateViolent:"Violent : glorification de la violence ou automutilation",
      feedbackInappropriateSexual:"Sexuel : contenu explicite, déplacé",
      feedbackInappropriateManipulative:"Manipulateur : sournois, émotif, autoritaire, intimidant",
      feedbackInappropriateOther:"Autres"
  },
  EN:{
      openDocument : "Open document", 
      openAttachment : "Open attachment",
      copyResponse: "Copy response",
      copied: "Copied!",
      playAudio: "Play audio",
      stopAudio: "Stop audio",
      enableAutoAudio: "Enable auto audio",
      disableAutoAudio: "Disable auto audio",
      submitFeedbakc: "Submit Feedback",
      feedbackHelps: "Your feedback will improve this experience.",
      feedbackWillBVisible: "By pressing submit, your feedback will be visible to the application owner.",
      submit: "Submit",
      aiDisclaimer: "AI-generated content may be incorrect",
      // Unhelpful
      labelWhy: "Why wasn't this response helpful ?",
      feedbackMissingCitations: "Citations are missing",
      feedbackWrongCitation: "Citations are wrong",
      feedbackOutOfScope: "The response is not from my data",
      feedbackInaccurateOrIrrelevant: "Inaccurate or irrelevant",
      feedbackOtherUnhelpful: "Other",
      reportInappropriateContent:"Report inappropriate content",
      // inapropriate
      feedbackInappropriateLabel:"The content is :",
      feedbackInappropriateHate:"Hate speech, stereotyping, demeaning",
      feedbackInappropriateViolent:"Violent: glorification of violence, self-harm",
      feedbackInappropriateSexual:"Sexual: explicit content, grooming",
      feedbackInappropriateManipulative:"Manipulative: devious, emotional, pushy, bullying",
      feedbackInappropriateOther:"Other"


  }
    
    });