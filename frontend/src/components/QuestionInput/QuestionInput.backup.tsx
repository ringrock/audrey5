import { useContext, useState, useEffect, useRef } from 'react'
import { FontIcon, Stack, TextField } from '@fluentui/react'
import { SendRegular, Mic20Regular, MicOff20Regular } from '@fluentui/react-icons'

import Send from '../../assets/Send.svg'

import styles from './QuestionInput.module.css'
import { ChatMessage } from '../../api'
import { AppStateContext } from '../../state/AppProvider'
// import { resizeImage } from '../../utils/resizeImage' // Plus utilisé - redimensionnement côté backend
import { uploadDocument, DocumentUploadResponse } from '../../api/api'

// Extract key terms from document for search enhancement
const extractKeywordsFromDocument = (text: string, maxKeywords: number = 8): string[] => {
  // Clean and normalize text
  const cleanText = text.toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  
  const words = cleanText.split(' ')
  
  // Common stop words to filter out
  const stopWords = new Set([
    'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'mais', 'donc', 'car',
    'ce', 'cette', 'ces', 'il', 'elle', 'ils', 'elles', 'je', 'tu', 'nous', 'vous',
    'que', 'qui', 'quoi', 'comment', 'pourquoi', 'où', 'quand', 'dans', 'sur', 'avec',
    'par', 'pour', 'sans', 'sous', 'entre', 'vers', 'chez', 'depuis', 'pendant',
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after'
  ])
  
  // Keep words that are longer than 2 chars and not stop words
  const keywords = words
    .filter(word => word.length > 2 && !stopWords.has(word))
    .slice(0, maxKeywords * 2) // Take more initially
  
  // Remove duplicates and limit count
  const uniqueKeywords = Array.from(new Set(keywords)).slice(0, maxKeywords)
  
  return uniqueKeywords
}

interface Props {
  onSend: (question: ChatMessage['content'], id?: string) => void
  disabled: boolean
  placeholder?: string
  clearOnSend?: boolean
  conversationId?: string
}

export const QuestionInput = ({ onSend, disabled, placeholder, clearOnSend, conversationId }: Props) => {
  const [question, setQuestion] = useState<string>('')
  const [base64Image, setBase64Image] = useState<string | null>(null)
  const [documentText, setDocumentText] = useState<string | null>(null)
  const [documentInfo, setDocumentInfo] = useState<{name: string, type?: string} | null>(null)
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [userTypedQuestion, setUserTypedQuestion] = useState<string>('')

  const [isInitialQuestionSet, setIsInitialQuestionSet] = useState(false);
  
  // History management for arrow key navigation
  const [history, setHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState<number>(-1)
  const [tempQuestion, setTempQuestion] = useState<string>('')

  // Voice recognition states
  const [isListening, setIsListening] = useState<boolean>(false)
  const [speechSupported, setSpeechSupported] = useState<boolean>(false)
  const [voiceInputComplete, setVoiceInputComplete] = useState<boolean>(false)
  const [isWakeWordListening, setIsWakeWordListening] = useState<boolean>(false)
  const [wakeWordEnabled, setWakeWordEnabled] = useState<boolean>(false)
  const recognitionRef = useRef<any>(null)
  const wakeWordRecognitionRef = useRef<any>(null)
  const autoSendTimeoutRef = useRef<number | null>(null)
  const lastClickTimeRef = useRef<number>(0)
  const singleClickTimeoutRef = useRef<number | null>(null)

  const appStateContext = useContext(AppStateContext)
  
  // Configuration vocale depuis les paramètres
  const voiceInputEnabled = appStateContext?.state.frontendSettings?.voice_input_enabled ?? true;
  const canUseWakeWord = appStateContext?.state.frontendSettings?.wake_word_enabled ?? true;
  const wakeWordPhrases = appStateContext?.state.frontendSettings?.wake_word_phrases ?? ['asmi', 'askme', 'askmi', 'asqmi'];
  
  // Load history from localStorage on component mount
  useEffect(() => {
    const savedHistory = localStorage.getItem('questionHistory')
    if (savedHistory) {
      try {
        const parsedHistory = JSON.parse(savedHistory)
        if (Array.isArray(parsedHistory)) {
          setHistory(parsedHistory.slice(0, 50)) // Limit to 50 items
        }
      } catch (error) {
        console.warn('Failed to parse question history from localStorage:', error)
      }
    }
  }, [])

  // Initialize speech recognition
  useEffect(() => {
    if (!voiceInputEnabled) {
      setSpeechSupported(false)
      return
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    
    if (SpeechRecognition) {
      setSpeechSupported(true)
      
      // Recognition principale pour les questions
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = true
      recognition.lang = 'fr-FR'
      
      recognition.onstart = () => {
        setIsListening(true)
        console.log('Speech recognition started')
      }
      
      recognition.onresult = (event: any) => {
        let transcript = ''
        let isFinal = false
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript
          if (event.results[i].isFinal) {
            isFinal = true
          }
        }
        
        setQuestion(transcript)
        
        if (autoSendTimeoutRef.current) {
          clearTimeout(autoSendTimeoutRef.current)
          autoSendTimeoutRef.current = null
        }
        
        if (isFinal && transcript.trim()) {
          setIsListening(false)
          setVoiceInputComplete(true)
        }
      }
      
      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
        
        let errorMessage = 'Erreur de reconnaissance vocale'
        switch (event.error) {
          case 'no-speech':
            errorMessage = 'Aucune parole détectée. Veuillez réessayer.'
            break
          case 'audio-capture':
            errorMessage = 'Microphone non accessible. Vérifiez les autorisations.'
            break
          case 'not-allowed':
            errorMessage = 'Permission microphone refusée. Activez-la dans les paramètres du navigateur.'
            break
          case 'network':
            errorMessage = 'Erreur réseau. Vérifiez votre connexion internet.'
            break
        }
        console.warn(errorMessage)
      }
      
      recognition.onend = () => {
        setIsListening(false)
        console.log('Speech recognition ended')
        
        // Redémarrer le wake word si il était actif
        if (wakeWordEnabled && canUseWakeWord) {
          console.log('Redémarrage du wake word après reconnaissance...')
          setTimeout(() => startWakeWordListeningForced(), 2000)
        }
      }
      
      recognitionRef.current = recognition
      
      // Recognition pour le wake word
      if (canUseWakeWord) {
        const wakeWordRecognition = new SpeechRecognition()
        wakeWordRecognition.continuous = true
        wakeWordRecognition.interimResults = true  // Pour une détection plus rapide
        wakeWordRecognition.lang = 'fr-FR'
        
        wakeWordRecognition.onstart = () => {
          setIsWakeWordListening(true)
          console.log('Wake word listening started')
        }
        
        wakeWordRecognition.onresult = (event: any) => {
          // Vérifier tous les résultats, y compris les intérimaires pour une détection plus rapide
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript.toLowerCase().trim()
            console.log('Wake word detection:', transcript, '(final:', event.results[i].isFinal, ')')
            
            // Détection flexible du wake word avec les phrases configurées
            const detected = wakeWordPhrases.some((phrase: string) => 
              transcript.includes(phrase.toLowerCase())
            )
            
            if (detected && event.results[i].isFinal) {
              console.log('Wake word detected! Using full transcript as question...')
              
              // Arrêter le wake word listening
              wakeWordRecognition.stop()
              setIsWakeWordListening(false)
              
              // Extraire la partie après le wake word (supprimer tout jusqu'au mot-clé inclus)
              let questionPart = ''
              for (const phrase of wakeWordPhrases) {
                const index = transcript.indexOf(phrase.toLowerCase())
                if (index !== -1) {
                  // Prendre tout ce qui suit le mot-clé détecté
                  questionPart = transcript.substring(index + phrase.length).trim()
                  console.log(`Mot-clé "${phrase}" détecté, partie extraite:`, questionPart)
                  break
                }
              }
              
              console.log('Question extraite:', questionPart)
              
              if (questionPart && questionPart.length > 0) {
                // Utiliser directement la question détectée et déclencher l'envoi
                setQuestion(questionPart)
                setVoiceInputComplete(true)
              } else {
                // Si rien après le wake word, démarrer une reconnaissance normale
                console.log('Wake word detected but no question following, starting normal voice input...')
                setQuestion('')
                setTimeout(() => {
                  if (recognitionRef.current && !isListening) {
                    try {
                      setIsListening(true)
                      recognitionRef.current.start()
                    } catch (error) {
                      console.error('Failed to start speech recognition after wake word:', error)
                      setIsListening(false)
                    }
                  }
                }, 500) // Délai plus long pour éviter les conflits
              }
              
              break // Sortir de la boucle une fois détecté
            }
          }
        }
        
        wakeWordRecognition.onerror = (event: any) => {
          console.error('Wake word recognition error:', event.error)
          setIsWakeWordListening(false)
          
          // Redémarrer automatiquement selon le type d'erreur
          if (wakeWordEnabled && speechSupported) {
            let restartDelay = 2000
            
            switch (event.error) {
              case 'no-speech':
                // Erreur courante - redémarrer rapidement
                restartDelay = 500
                console.log('No speech detected, restarting wake word listening...')
                break
              case 'aborted':
                // Reconnaissance annulée - redémarrer normalement 
                restartDelay = 1000
                break
              case 'not-allowed':
              case 'audio-capture':
                // Erreurs de permission - ne pas redémarrer
                console.error('Permission denied or audio capture failed')
                return
              case 'network':
                // Erreur réseau - délai plus long
                restartDelay = 5000
                break
              default:
                restartDelay = 2000
            }
            
            setTimeout(() => {
              if (wakeWordRecognitionRef.current && speechSupported && wakeWordEnabled && !isWakeWordListening && !isListening) {
                try {
                  setIsWakeWordListening(true)
                  wakeWordRecognitionRef.current.start()
                  console.log('Wake word listening restarted after error:', event.error)
                } catch (error) {
                  console.error('Failed to restart wake word recognition:', error)
                  setIsWakeWordListening(false)
                }
              }
            }, restartDelay)
          }
        }
        
        wakeWordRecognition.onend = () => {
          setIsWakeWordListening(false)
          console.log('Wake word recognition ended')
          
          // Redémarrer automatiquement le wake word listening si activé et aucune autre reconnaissance en cours
          if (wakeWordEnabled && speechSupported && !isListening && !isWakeWordListening) {
            console.log('Restarting wake word listening after normal end...')
            setTimeout(() => {
              if (wakeWordRecognitionRef.current && speechSupported && wakeWordEnabled && !isWakeWordListening && !isListening) {
                try {
                  setIsWakeWordListening(true)
                  wakeWordRecognitionRef.current.start()
                  console.log('Wake word listening restarted after normal end')
                } catch (error) {
                  console.error('Failed to restart wake word recognition:', error)
                  setIsWakeWordListening(false)
                }
              }
            }, 1000)
          }
        }
        
        wakeWordRecognitionRef.current = wakeWordRecognition
      }
      
    } else {
      setSpeechSupported(false)
      console.warn('Speech recognition not supported in this browser')
    }
    
    // Cleanup function
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
      if (wakeWordRecognitionRef.current) {
        wakeWordRecognitionRef.current.stop()
      }
      if (autoSendTimeoutRef.current) {
        clearTimeout(autoSendTimeoutRef.current)
        autoSendTimeoutRef.current = null
      }
      if (singleClickTimeoutRef.current) {
        clearTimeout(singleClickTimeoutRef.current)
        singleClickTimeoutRef.current = null
      }
    }
  }, [voiceInputEnabled, canUseWakeWord, wakeWordPhrases])

  // Auto-send effect for voice input
  useEffect(() => {
    if (voiceInputComplete && question.trim() && !disabled) {
      // Délai de 2 secondes avant l'envoi automatique
      autoSendTimeoutRef.current = setTimeout(() => {
        if (question.trim() && !disabled) {
          sendQuestion()
          
          // Redémarrer automatiquement le wake word listening après l'envoi si activé
          if (wakeWordEnabled && speechSupported && canUseWakeWord) {
            console.log('Redémarrage automatique du wake word listening après envoi...')
            setTimeout(() => {
              if (wakeWordRecognitionRef.current && !isWakeWordListening && !isListening) {
                try {
                  setIsWakeWordListening(true)
                  wakeWordRecognitionRef.current.start()
                } catch (error) {
                  console.error('Failed to restart wake word listening after send:', error)
                  setIsWakeWordListening(false)
                }
              }
            }, 1000) // Délai pour laisser le temps à la réponse de commencer
          }
        }
        setVoiceInputComplete(false)
        autoSendTimeoutRef.current = null
      }, 2000)
    }
    
    return () => {
      if (autoSendTimeoutRef.current) {
        clearTimeout(autoSendTimeoutRef.current)
        autoSendTimeoutRef.current = null
      }
    }
  }, [voiceInputComplete, question, disabled, wakeWordEnabled, speechSupported, canUseWakeWord, isWakeWordListening, isListening])

  const OYD_ENABLED = appStateContext?.state.frontendSettings?.oyd_enabled || false;
  const currentProvider = appStateContext?.state.customizationPreferences?.llmProvider || 'AZURE_OPENAI';
  
  // Seuls Claude, Gemini et OpenAI Direct supportent les images
  const supportsImages = ['CLAUDE', 'GEMINI', 'OPENAI_DIRECT'].includes(currentProvider);
  
  // Messages d'info bulle par provider
  const getImageTooltip = () => {
    if (supportsImages) {
      return "Télécharger une image"
    }
    
    switch (currentProvider) {
      case 'MISTRAL':
        return "Les images ne sont pas supportées par Mistral"
      case 'AZURE_OPENAI':
        return "Les images ne sont pas supportées par ce provider Azure OpenAI"
      default:
        return "Les images ne sont pas supportées par ce provider"
    }
  }

  const startWakeWordListening = () => {
    if (!canUseWakeWord || !wakeWordEnabled || isListening || !speechSupported) {
      console.log('Cannot start wake word:', { canUseWakeWord, wakeWordEnabled, isListening, speechSupported })
      return
    }

    // Créer la reconnaissance wake word si elle n'existe pas
    if (!wakeWordRecognitionRef.current) {
      console.log('Creating wake word recognition...')
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      
      if (!SpeechRecognition) {
        console.error('Speech recognition not available')
        return
      }

      const wakeWordRecognition = new SpeechRecognition()
      wakeWordRecognition.continuous = true
      wakeWordRecognition.interimResults = true  // Pour une détection plus rapide
      wakeWordRecognition.lang = 'fr-FR'
      
      wakeWordRecognition.onstart = () => {
        setIsWakeWordListening(true)
        console.log('Wake word listening started')
      }
      
      wakeWordRecognition.onresult = (event: any) => {
        // Vérifier tous les résultats, y compris les intérimaires pour une détection plus rapide
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript.toLowerCase().trim()
          console.log('Wake word detection:', transcript, '(final:', event.results[i].isFinal, ')')
          
          // Détection flexible du wake word avec les phrases configurées
          const detected = wakeWordPhrases.some((phrase: string) => 
            transcript.includes(phrase.toLowerCase())
          )
          
          if (detected) {
            console.log('Wake word detected! Using full transcript as question...')
            
            // Arrêter le wake word listening
            wakeWordRecognition.stop()
            setIsWakeWordListening(false)
            
            // Extraire la partie après le wake word (supprimer tout jusqu'au mot-clé inclus)
            let questionPart = ''
            for (const phrase of wakeWordPhrases) {
              const index = transcript.indexOf(phrase.toLowerCase())
              if (index !== -1) {
                // Prendre tout ce qui suit le mot-clé détecté
                questionPart = transcript.substring(index + phrase.length).trim()
                console.log(`Mot-clé "${phrase}" détecté, partie extraite:`, questionPart)
                break
              }
            }
            
            console.log('Question extraite:', questionPart)
            
            if (questionPart && questionPart.length > 0) {
              // Utiliser directement la question détectée et déclencher l'envoi
              setQuestion(questionPart)
              setVoiceInputComplete(true)
            } else {
              // Si rien après le wake word, démarrer l'écoute pour la question
              setQuestion('')
              setTimeout(() => {
                if (recognitionRef.current && !isListening) {
                  try {
                    recognitionRef.current.start()
                  } catch (error) {
                    console.error('Failed to start speech recognition after wake word:', error)
                  }
                }
              }, 100)
            }
            
            break // Sortir de la boucle une fois détecté
          }
        }
      }
      
      wakeWordRecognition.onerror = (event: any) => {
        console.error('Wake word recognition error:', event.error)
        setIsWakeWordListening(false)
        
        // Redémarrer automatiquement le wake word listening sauf si permission refusée
        if (event.error !== 'not-allowed' && event.error !== 'audio-capture' && wakeWordEnabled) {
          setTimeout(() => {
            if (wakeWordRecognitionRef.current && speechSupported) {
              try {
                wakeWordRecognitionRef.current.start()
              } catch (error) {
                console.error('Failed to restart wake word recognition:', error)
              }
            }
          }, 2000)
        }
      }
      
      wakeWordRecognition.onend = () => {
        setIsWakeWordListening(false)
        console.log('Wake word recognition ended')
        
        // Redémarrer automatiquement le wake word listening si activé
        if (wakeWordEnabled && !isListening) {
          setTimeout(() => {
            if (wakeWordRecognitionRef.current && speechSupported) {
              try {
                wakeWordRecognitionRef.current.start()
              } catch (error) {
                console.error('Failed to restart wake word recognition:', error)
              }
            }
          }, 1000)
        }
      }
      
      wakeWordRecognitionRef.current = wakeWordRecognition
    }

    // Démarrer l'écoute
    try {
      console.log('Starting wake word recognition...')
      wakeWordRecognitionRef.current.start()
    } catch (error) {
      console.error('Failed to start wake word recognition:', error)
    }
  }

  const stopWakeWordListening = () => {
    if (wakeWordRecognitionRef.current && isWakeWordListening) {
      try {
        wakeWordRecognitionRef.current.stop()
        setIsWakeWordListening(false)
      } catch (error) {
        console.error('Failed to stop wake word recognition:', error)
      }
    }
  }

  const toggleWakeWordMode = () => {
    const newState = !wakeWordEnabled
    setWakeWordEnabled(newState)
    
    console.log(`Wake word mode ${newState ? 'activé' : 'désactivé'}`)
    
    if (newState) {
      // Activer le wake word - appeler directement sans attendre l'état
      console.log('Démarrage immédiat du wake word...')
      startWakeWordListeningForced()
    } else {
      // Désactiver le wake word
      stopWakeWordListening()
    }
  }

  // Version qui force le démarrage sans vérifier wakeWordEnabled
  const startWakeWordListeningForced = () => {
    if (!canUseWakeWord || isListening || !speechSupported) {
      console.log('Cannot start wake word (forced):', { canUseWakeWord, isListening, speechSupported })
      return
    }

    // Créer la reconnaissance wake word si elle n'existe pas
    if (!wakeWordRecognitionRef.current) {
      console.log('Creating wake word recognition...')
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      
      if (!SpeechRecognition) {
        console.error('Speech recognition not available')
        return
      }

      const wakeWordRecognition = new SpeechRecognition()
      wakeWordRecognition.continuous = true
      wakeWordRecognition.interimResults = true  // Pour une détection plus rapide
      wakeWordRecognition.lang = 'fr-FR'
      
      wakeWordRecognition.onstart = () => {
        setIsWakeWordListening(true)
        console.log('Wake word listening started')
      }
      
      wakeWordRecognition.onresult = (event: any) => {
        // Vérifier tous les résultats, y compris les intérimaires pour une détection plus rapide
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript.toLowerCase().trim()
          console.log('Wake word detection:', transcript, '(final:', event.results[i].isFinal, ')')
          
          // Détection flexible du wake word avec les phrases configurées
          const detected = wakeWordPhrases.some((phrase: string) => 
            transcript.includes(phrase.toLowerCase())
          )
          
          if (detected) {
            console.log('Wake word detected! Using full transcript as question...')
            
            // Arrêter le wake word listening
            wakeWordRecognition.stop()
            setIsWakeWordListening(false)
            
            // Extraire la partie après le wake word (supprimer tout jusqu'au mot-clé inclus)
            let questionPart = ''
            for (const phrase of wakeWordPhrases) {
              const index = transcript.indexOf(phrase.toLowerCase())
              if (index !== -1) {
                // Prendre tout ce qui suit le mot-clé détecté
                questionPart = transcript.substring(index + phrase.length).trim()
                console.log(`Mot-clé "${phrase}" détecté, partie extraite:`, questionPart)
                break
              }
            }
            
            console.log('Question extraite:', questionPart)
            
            if (questionPart && questionPart.length > 0) {
              // Utiliser directement la question détectée et déclencher l'envoi
              setQuestion(questionPart)
              setVoiceInputComplete(true)
            } else {
              // Si rien après le wake word, démarrer l'écoute pour la question
              setQuestion('')
              setTimeout(() => {
                if (recognitionRef.current && !isListening) {
                  try {
                    recognitionRef.current.start()
                  } catch (error) {
                    console.error('Failed to start speech recognition after wake word:', error)
                  }
                }
              }, 100)
            }
            
            break // Sortir de la boucle une fois détecté
          }
        }
      }
      
      wakeWordRecognition.onerror = (event: any) => {
        console.error('Wake word recognition error:', event.error)
        setIsWakeWordListening(false)
        
        // Redémarrer automatiquement le wake word listening sauf si permission refusée
        if (event.error !== 'not-allowed' && event.error !== 'audio-capture') {
          setTimeout(() => {
            if (wakeWordRecognitionRef.current && speechSupported && wakeWordEnabled) {
              try {
                wakeWordRecognitionRef.current.start()
              } catch (error) {
                console.error('Failed to restart wake word recognition:', error)
              }
            }
          }, 2000)
        }
      }
      
      wakeWordRecognition.onend = () => {
        setIsWakeWordListening(false)
        console.log('Wake word recognition ended')
        
        // Redémarrer automatiquement le wake word listening si activé
        setTimeout(() => {
          if (wakeWordRecognitionRef.current && speechSupported && wakeWordEnabled && !isListening) {
            try {
              wakeWordRecognitionRef.current.start()
            } catch (error) {
              console.error('Failed to restart wake word recognition:', error)
            }
          }
        }, 1000)
      }
      
      wakeWordRecognitionRef.current = wakeWordRecognition
    }

    // Démarrer l'écoute
    try {
      console.log('Starting wake word recognition...')
      wakeWordRecognitionRef.current.start()
    } catch (error) {
      console.error('Failed to start wake word recognition:', error)
    }
  }

  const handleSingleClick = () => {
    if (isListening) {
      // Si on est en train d'écouter, arrêter immédiatement
      recognitionRef.current.stop()
      setIsListening(false)
      setVoiceInputComplete(false)
      
      if (autoSendTimeoutRef.current) {
        clearTimeout(autoSendTimeoutRef.current)
        autoSendTimeoutRef.current = null
      }
    } else {
      // Arrêter le wake word temporairement
      if (isWakeWordListening) {
        stopWakeWordListening()
      }
      
      // Commencer l'écoute manuelle
      try {
        recognitionRef.current.start()
      } catch (error) {
        console.error('Failed to start speech recognition:', error)
        setIsListening(false)
      }
    }
  }

  const toggleVoiceRecognition = () => {
    if (!voiceInputEnabled || !speechSupported || !recognitionRef.current) {
      return
    }

    const currentTime = Date.now()
    const timeSinceLastClick = currentTime - lastClickTimeRef.current
    
    // Annuler le timeout du simple clic s'il existe
    if (singleClickTimeoutRef.current) {
      clearTimeout(singleClickTimeoutRef.current)
      singleClickTimeoutRef.current = null
    }
    
    // Détection du double-clic (moins de 300ms entre les clics)
    if (timeSinceLastClick < 300 && timeSinceLastClick > 0) {
      // Double-clic : toggle wake word mode
      console.log('Double-clic détecté : toggle wake word mode')
      toggleWakeWordMode()
      lastClickTimeRef.current = 0 // Reset pour éviter les triples clics
      return
    }
    
    lastClickTimeRef.current = currentTime

    // Programmer l'action du simple clic avec un délai
    singleClickTimeoutRef.current = setTimeout(() => {
      handleSingleClick()
      singleClickTimeoutRef.current = null
    }, 300) // Délai pour détecter un éventuel double-clic
  }

  const getVoiceTooltip = () => {
    if (!voiceInputEnabled) {
      return "Reconnaissance vocale désactivée"
    }
    
    if (!speechSupported) {
      return "Reconnaissance vocale non supportée par ce navigateur"
    }
    
    if (isWakeWordListening && !isListening) {
      return `En écoute des mots-clés: ${wakeWordPhrases.join(', ')} - Clic: dictée manuelle, Double-clic: désactiver`
    }
    
    if (wakeWordEnabled && canUseWakeWord && !isListening && !isWakeWordListening) {
      return "Mode wake word activé - Clic: dictée manuelle, Double-clic: désactiver"
    }
    
    return isListening ? "Arrêter l'écoute" : "Clic: dictée vocale, Double-clic: activer wake word"
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    
    try {
      if (file) {
        console.log('File selected:', file.name, file.type, file.size)
        
        // Réinitialiser les états précédents
        setBase64Image(null)
        setDocumentText(null)
        setDocumentInfo(null)
        
        // Seules les images sont autorisées
        if (file.type.startsWith('image/')) {
          console.log('Processing image file...')
          try {
            await convertToBase64(file)
            console.log('Image processing completed successfully')
          } catch (conversionError) {
            console.error('Image conversion failed:', conversionError)
            // Optionnel : afficher l'erreur à l'utilisateur
            if (conversionError instanceof Error) {
              alert(conversionError.message)
            }
          }
        } else {
          console.log('File rejected: not an image')
        }
      } else {
        console.log('No file selected')
      }
    } catch (error) {
      console.error('Error in handleFileUpload:', error)
    } finally {
      // IMPORTANT: Toujours réinitialiser l'input pour permettre la re-sélection du même fichier
      event.target.value = ''
    }
  }


  const convertToBase64 = async (file: Blob) => {
    return new Promise<void>((resolve, reject) => {
      try {
        console.log('convertToBase64 called with file:', file.size, 'bytes')
        
        // Limite de sécurité : 20MB (limite générale raisonnable)
        if (file.size > 20 * 1024 * 1024) {
          console.error('File too large:', file.size)
          reject(new Error('Image trop volumineuse (limite 20MB). Veuillez utiliser une image plus petite.'))
          return
        }
        
        console.log(`${currentProvider} provider: converting image to base64`)
        
        // Conversion directe sans redimensionnement - le backend s'occupe de tout
        const reader = new FileReader()
        
        reader.onloadend = () => {
          try {
            const originalBase64 = reader.result as string
            if (!originalBase64) {
              console.error('FileReader returned null result')
              reject(new Error('Erreur lors de la lecture du fichier'))
              return
            }
            
            console.log(`Base64 conversion successful, length:`, originalBase64.length)
            console.log(`File details:`, {
              name: (file as File).name || 'unknown',
              size: file.size,
              type: file.type
            })
            
            setBase64Image(originalBase64)
            console.log('Image state updated successfully')
            resolve()
          } catch (error) {
            console.error('Error in reader.onloadend:', error)
            reject(error)
          }
        }
        
        reader.onerror = (error) => {
          console.error('FileReader error:', error)
          reject(new Error('Erreur lors de la lecture du fichier'))
        }
        
        reader.onabort = () => {
          console.error('FileReader aborted')
          reject(new Error('Lecture du fichier interrompue'))
        }
        
        console.log('Starting FileReader.readAsDataURL...')
        reader.readAsDataURL(file)
        
      } catch (error) {
        console.error('Error in convertToBase64:', error)
        reject(error)
      }
    })
  }

  const sendQuestion = () => {
    if (disabled || !question.trim()) {
      return
    }

    const questionText = question.trim()
    
    // Build the content for the message - images only for now
    const questionTest: ChatMessage["content"] = base64Image ? 
      [
        { type: "text" as const, text: questionText },
        { type: "image_url" as const, image_url: { url: base64Image } }
      ] : 
      questionText
    
    // DEBUG: Log what we're sending
    console.log('DEBUG: questionTest content:', questionTest)
    if (Array.isArray(questionTest)) {
      console.log('DEBUG: multimodal message with', questionTest.length, 'parts')
      questionTest.forEach((part, i) => {
        console.log(`DEBUG: Part ${i}:`, part.type)
        if (part.type === 'image_url') {
          console.log(`DEBUG: Image URL length:`, part.image_url.url.length)
          console.log(`DEBUG: Image URL preview:`, part.image_url.url.substring(0, 50))
        }
      })
    } else {
      console.log('DEBUG: text-only message')
    }

    // Add to history or move to top if it already exists
    if (questionText) {
      // Remove from existing position if it exists
      const filteredHistory = history.filter(item => item !== questionText)
      // Add to beginning
      const newHistory = [questionText, ...filteredHistory].slice(0, 50) // Keep last 50 questions
      setHistory(newHistory)
      
      // Save to localStorage
      try {
        localStorage.setItem('questionHistory', JSON.stringify(newHistory))
      } catch (error) {
        console.warn('Failed to save question history to localStorage:', error)
      }
    }
    
    // Reset history navigation
    setHistoryIndex(-1)
    setTempQuestion('')

    if (conversationId && questionTest !== undefined) {
      onSend(questionTest, conversationId)
      setBase64Image(null)
    } else {
      onSend(questionTest)
      setBase64Image(null)
    }

    if (clearOnSend) {
      setQuestion('')
    }
  }

  const onEnterPress = (ev: React.KeyboardEvent<Element>) => {
    if (ev.key === 'Enter' && !ev.shiftKey && !(ev.nativeEvent?.isComposing === true)) {
      ev.preventDefault()
      sendQuestion()
    } else if (ev.key === 'ArrowUp' && history.length > 0) {
      ev.preventDefault()
      
      // First time navigating up: save current question
      if (historyIndex === -1) {
        setTempQuestion(question)
      }
      
      const newIndex = Math.min(historyIndex + 1, history.length - 1)
      setHistoryIndex(newIndex)
      setQuestion(history[newIndex])
    } else if (ev.key === 'ArrowDown') {
      ev.preventDefault()
      
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1
        setHistoryIndex(newIndex)
        setQuestion(history[newIndex])
      } else if (historyIndex === 0) {
        // Return to original/temp question
        setHistoryIndex(-1)
        setQuestion(tempQuestion)
      }
    }
  }

  const onPaste = (ev: React.ClipboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    // Vérifier si les images sont supportées par le provider actuel
    if (!supportsImages) {
      return
    }

    const clipboardData = ev.clipboardData
    if (!clipboardData || !clipboardData.items) {
      return
    }

    // Rechercher une image dans le presse-papier
    for (let i = 0; i < clipboardData.items.length; i++) {
      const item = clipboardData.items[i]
      
      if (item.type.startsWith('image/')) {
        ev.preventDefault() // Empêcher le comportement par défaut du collage
        
        console.log('Image détectée dans le presse-papier:', item.type)
        
        // Récupérer le fichier depuis le presse-papier
        const file = item.getAsFile()
        if (file) {
          console.log('Fichier image récupéré du presse-papier:', file.name || 'clipboard-image', file.type, file.size)
          
          // Réinitialiser les états précédents
          setBase64Image(null)
          setDocumentText(null)
          setDocumentInfo(null)
          
          // Utiliser la même logique que pour l'upload de fichier
          convertToBase64(file)
            .then(() => {
              console.log('Image du presse-papier traitée avec succès')
            })
            .catch((error) => {
              console.error('Erreur lors du traitement de l\'image du presse-papier:', error)
              if (error instanceof Error) {
                alert(error.message)
              }
            })
        }
        break // Sortir de la boucle après avoir trouvé la première image
      }
    }
  }

  const onQuestionChange = (_ev: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, newValue?: string) => {
    setQuestion(newValue || '')
    
    // Reset history navigation if user is typing
    if (historyIndex !== -1) {
      setHistoryIndex(-1)
      setTempQuestion('')
    }
    
    // Annuler l'envoi automatique si l'utilisateur modifie manuellement le texte
    if (autoSendTimeoutRef.current) {
      clearTimeout(autoSendTimeoutRef.current)
      autoSendTimeoutRef.current = null
    }
    
    // Annuler le timeout du single clic si l'utilisateur tape
    if (singleClickTimeoutRef.current) {
      clearTimeout(singleClickTimeoutRef.current)
      singleClickTimeoutRef.current = null
    }
    
    setVoiceInputComplete(false)
  }

  var sendQuestionDisabled = disabled || !question.trim()

  useEffect(() => {
    if (isInitialQuestionSet && question.trim() && !disabled) {
      sendQuestion();
      setIsInitialQuestionSet(false);
      /* remise à vide de la question initiale */
      appStateContext?.dispatch({ type: 'SET_INITIAL_QUESTION', payload: "" });
    }
  }, [question, disabled, isInitialQuestionSet]);

  useEffect(() => {
    if (appStateContext?.state.initialQuestion) {
      setQuestion(appStateContext.state.initialQuestion);
      setIsInitialQuestionSet(true);
    }
  }, [appStateContext?.state.initialQuestion]);

  // Nettoyer l'image quand on change vers un provider qui ne supporte pas les images
  useEffect(() => {
    if (!supportsImages && base64Image) {
      console.log('Clearing image because provider', currentProvider, 'does not support images')
      setBase64Image(null)
    }
  }, [currentProvider, supportsImages, base64Image]);

  return (
    <Stack horizontal className={styles.questionInputContainer}>
      <TextField
        className={styles.questionInputTextArea}
        placeholder={placeholder}
        multiline
        resizable={false}
        borderless
        value={question}
        onChange={onQuestionChange}
        onKeyDown={onEnterPress}
        onPaste={onPaste}
      />
      <div className={styles.fileInputContainer}>
        <input
          type="file"
          id="fileInput"
          onChange={(event) => handleFileUpload(event)}
          accept="image/*"
          className={styles.fileInput}
          disabled={!supportsImages || isUploading}
        />
        <label 
          htmlFor="fileInput" 
          className={`${styles.fileLabel} ${!supportsImages ? styles.disabled : ''}`}
          aria-label="Upload Image"
          title={getImageTooltip()}
        >
          <FontIcon
            className={supportsImages ? styles.fileIcon : styles.fileIconDisabled}
            iconName={isUploading ? 'ProgressRingDots' : 'Attach'}
            aria-label="Upload Image"
          />
        </label>
      </div>
      {voiceInputEnabled && (
        <div className={styles.voiceInputContainer}>
          <button
            type="button"
            className={`${styles.voiceButton} ${!speechSupported ? styles.disabled : ''} ${isListening ? styles.listening : ''} ${isWakeWordListening && !isListening ? styles.wakeWordListening : ''}`}
            onClick={toggleVoiceRecognition}
            disabled={!speechSupported}
            aria-label={getVoiceTooltip()}
            title={getVoiceTooltip()}
          >
            {isListening ? (
              <MicOff20Regular className={styles.voiceIcon} />
            ) : (
              <Mic20Regular className={styles.voiceIcon} />
            )}
          </button>
        </div>
      )}
      {base64Image && (
        <div className={styles.uploadedImageContainer}>
          <img className={styles.uploadedImage} src={base64Image} alt="Uploaded Preview" />
          <button 
            className={styles.removeImageButton}
            onClick={() => setBase64Image(null)}
            aria-label="Supprimer l'image"
            title="Supprimer l'image"
          >
            <FontIcon iconName="Cancel" />
          </button>
        </div>
      )}
      <div
        className={styles.questionInputSendButtonContainer}
        role="button"
        tabIndex={0}
        aria-label="Ask question button"
        onClick={sendQuestion}
        onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? sendQuestion() : null)}>
        {sendQuestionDisabled ? (
          <SendRegular className={styles.questionInputSendButtonDisabled} />
        ) : (
          <img src={Send} className={styles.questionInputSendButton} alt="Send Button" />
        )}
      </div>
      <div className={styles.questionInputBottomBorder} />
    </Stack>
  )
}
