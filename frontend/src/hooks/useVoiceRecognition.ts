import { useState, useEffect, useRef, useCallback } from 'react'

interface VoiceRecognitionConfig {
  voiceInputEnabled: boolean
  canUseWakeWord: boolean
  wakeWordEnabled: boolean
  wakeWordPhrases: string[]
  wakeWordVariants: Record<string, string[]>
}

interface VoiceRecognitionState {
  isListening: boolean
  isWakeWordListening: boolean
  speechSupported: boolean
  question: string
  voiceInputComplete: boolean
}

interface VoiceRecognitionActions {
  startListening: () => void
  stopListening: () => void
  toggleWakeWord: () => void
  setQuestion: (question: string) => void
  resetVoiceInput: () => void
  pauseVoiceRecognition: () => void
  resumeVoiceRecognition: () => void
}

export const useVoiceRecognition = (
  config: VoiceRecognitionConfig
): VoiceRecognitionState & VoiceRecognitionActions => {
  const [isListening, setIsListening] = useState<boolean>(false)
  const [isWakeWordListening, setIsWakeWordListening] = useState<boolean>(false)
  const [speechSupported, setSpeechSupported] = useState<boolean>(false)
  const [question, setQuestion] = useState<string>('')
  const [voiceInputComplete, setVoiceInputComplete] = useState<boolean>(false)
  const [wakeWordMode, setWakeWordMode] = useState<boolean>(false)
  
  // État pour mémoriser si l'écoute était active avant la pause audio
  const wasWakeWordActiveBeforePause = useRef<boolean>(false)

  const recognitionRef = useRef<any>(null)
  const wakeWordRecognitionRef = useRef<any>(null)
  const lastClickTimeRef = useRef<number>(0)
  const singleClickTimeoutRef = useRef<number | null>(null)

  const { voiceInputEnabled, canUseWakeWord, wakeWordEnabled, wakeWordPhrases, wakeWordVariants } = config

  // Initialize speech recognition
  useEffect(() => {
    if (!voiceInputEnabled) return

    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      setSpeechSupported(true)
      
      // Initialize main speech recognition
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = true
      recognition.lang = 'fr-FR'

      recognition.onstart = () => {
        console.log('Speech recognition started')
        setIsListening(true)
      }

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript
        setQuestion(transcript)
        
        if (event.results[0].isFinal) {
          setVoiceInputComplete(true)
        }
      }

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
      }

      recognition.onend = () => {
        console.log('Speech recognition ended')
        setIsListening(false)
        // Force a small delay to ensure state is properly synchronized
        setTimeout(() => {
          if (recognitionRef.current) {
            // Ensure recognition is ready for next use
            console.log('Speech recognition ready for next use')
          }
        }, 100)
      }

      recognitionRef.current = recognition

      // Initialize wake word recognition if enabled
      if (canUseWakeWord && wakeWordPhrases.length > 0) {
        const wakeWordRecognition = new SpeechRecognition()
        wakeWordRecognition.continuous = true
        wakeWordRecognition.interimResults = true
        wakeWordRecognition.lang = 'fr-FR'

        wakeWordRecognition.onstart = () => {
          console.log('Wake word listening started')
          setIsWakeWordListening(true)
        }

        wakeWordRecognition.onresult = (event: any) => {
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript.toLowerCase().trim()
            
            // Fonction pour normaliser le texte (enlever les accents)
            const normalizeText = (text: string) => {
              return text.toLowerCase()
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '') // Enlever les accents
                .trim()
            }
            
            const normalizedTranscript = normalizeText(transcript)
            
            // Vérifier la détection avec les variantes phonétiques
            let detectedPhrase = ''
            let detectedVariant = ''
            
            // D'abord vérifier les variantes phonétiques
            for (const [mainPhrase, variants] of Object.entries(wakeWordVariants)) {
              for (const variant of variants) {
                const normalizedVariant = normalizeText(variant)
                if (normalizedTranscript.includes(normalizedVariant)) {
                  detectedPhrase = mainPhrase
                  detectedVariant = variant
                  break
                }
              }
              if (detectedPhrase) break
            }
            
            // Si pas trouvé dans les variantes, vérifier les phrases principales
            if (!detectedPhrase) {
              for (const phrase of wakeWordPhrases) {
                const normalizedPhrase = normalizeText(phrase)
                if (normalizedTranscript.includes(normalizedPhrase)) {
                  detectedPhrase = phrase
                  detectedVariant = phrase
                  break
                }
              }
            }
            
            if (detectedPhrase && event.results[i].isFinal) {
              console.log(`Wake word detected! Phrase: "${detectedPhrase}", Variant: "${detectedVariant}"`)
              console.log('Original transcript:', transcript)
              console.log('Normalized transcript:', normalizedTranscript)
              
              wakeWordRecognition.stop()
              setIsWakeWordListening(false)
              
              // Extract question part after wake word
              let questionPart = ''
              const normalizedVariant = normalizeText(detectedVariant)
              const index = normalizedTranscript.indexOf(normalizedVariant)
              if (index !== -1) {
                // Utiliser l'index dans le transcript original pour préserver la casse
                const originalWords = transcript.split(' ')
                const normalizedWords = normalizedTranscript.split(' ')
                
                let wordCount = 0
                for (let j = 0; j < normalizedWords.length; j++) {
                  if (normalizedTranscript.substring(0, normalizedWords.slice(0, j + 1).join(' ').length).includes(normalizedVariant)) {
                    wordCount = j + 1
                    break
                  }
                }
                
                if (wordCount > 0 && wordCount < originalWords.length) {
                  questionPart = originalWords.slice(wordCount).join(' ').trim()
                } else {
                  // Fallback: utiliser l'approche basique
                  questionPart = transcript.substring(index + normalizedVariant.length).trim()
                }
                
                console.log(`Wake word "${detectedPhrase}" (variant "${detectedVariant}") detected, extracted question:`, questionPart)
              }
              
              console.log('Question extraite:', questionPart)
              
              if (questionPart && questionPart.length > 0) {
                setQuestion(questionPart)
                setVoiceInputComplete(true)
              } else {
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
                }, 500)
              }
              
              break
            }
          }
        }

        wakeWordRecognition.onerror = (event: any) => {
          console.error('Wake word recognition error:', event.error)
          console.log('Wake word error context:', { wakeWordMode, speechSupported, isListening, isWakeWordListening })
          setIsWakeWordListening(false)
          
          // Redémarrer automatiquement le wake word listening sauf si permission refusée - comme dans le backup  
          // Utiliser les valeurs de config au lieu des états internes pour éviter les problèmes de synchronisation
          if (event.error !== 'not-allowed' && event.error !== 'audio-capture' && canUseWakeWord && voiceInputEnabled) {
            let restartDelay = 2000
            
            switch (event.error) {
              case 'no-speech':
                restartDelay = 500
                console.log('No speech detected, restarting wake word listening...')
                break
              case 'aborted':
                restartDelay = 1000
                break
              case 'network':
                restartDelay = 5000
                break
              default:
                restartDelay = 2000
            }
            
            console.log('Scheduling wake word restart in', restartDelay, 'ms...')
            setTimeout(() => {
              console.log('Wake word restart attempt:', { 
                hasRef: !!wakeWordRecognitionRef.current, 
                canUseWakeWord, 
                voiceInputEnabled,
                wakeWordMode, 
                isWakeWordListening, 
                isListening 
              })
              if (wakeWordRecognitionRef.current && canUseWakeWord && voiceInputEnabled && !isWakeWordListening && !isListening) {
                try {
                  setIsWakeWordListening(true)
                  wakeWordRecognitionRef.current.start()
                  console.log('Wake word listening restarted after error:', event.error)
                } catch (error) {
                  console.error('Failed to restart wake word recognition:', error)
                  setIsWakeWordListening(false)
                }
              } else {
                console.log('Wake word restart conditions not met')
              }
            }, restartDelay)
          } else {
            console.log('Wake word not restarting due to conditions:', { 
              errorType: event.error, 
              canUseWakeWord,
              voiceInputEnabled,
              wakeWordMode
            })
          }
        }

        wakeWordRecognition.onend = () => {
          setIsWakeWordListening(false)
          console.log('Wake word recognition ended')
          
          // Redémarrer automatiquement le wake word listening si activé - comme dans le backup
          if (wakeWordMode && canUseWakeWord && voiceInputEnabled && !isListening) {
            console.log('Restarting wake word listening after normal end...')
            setTimeout(() => {
              if (wakeWordRecognitionRef.current && speechSupported && wakeWordMode && !isWakeWordListening && !isListening) {
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
    
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
      if (wakeWordRecognitionRef.current) {
        wakeWordRecognitionRef.current.stop()
      }
      if (singleClickTimeoutRef.current) {
        clearTimeout(singleClickTimeoutRef.current)
        singleClickTimeoutRef.current = null
      }
    }
  }, [voiceInputEnabled, canUseWakeWord, wakeWordPhrases, wakeWordVariants])

  // Start/stop listening functions
  const startListening = useCallback(() => {
    if (recognitionRef.current && !isListening && !isWakeWordListening) {
      try {
        console.log('Starting manual speech recognition...')
        // Ensure we reset any previous state
        setVoiceInputComplete(false)
        setIsListening(true)
        recognitionRef.current.start()
      } catch (error) {
        console.error('Failed to start speech recognition:', error)
        setIsListening(false)
        // If there's an error, wait a bit and ensure state is clean
        setTimeout(() => {
          console.log('Resetting recognition state after error')
        }, 500)
      }
    } else {
      console.log('Cannot start listening:', {
        hasRecognition: !!recognitionRef.current,
        isListening,
        isWakeWordListening
      })
    }
  }, [isListening, isWakeWordListening])

  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
      setVoiceInputComplete(false)
    }
  }, [isListening])

  // Wake word toggle with double-click detection
  const toggleWakeWord = useCallback(() => {
    if (!voiceInputEnabled || !speechSupported) {
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
      
      const newWakeWordMode = !wakeWordMode
      setWakeWordMode(newWakeWordMode)
      
      if (newWakeWordMode) {
        console.log('Wake word mode activé')
        if (wakeWordRecognitionRef.current && speechSupported && canUseWakeWord) {
          console.log('Démarrage immédiat du wake word...')
          setTimeout(() => {
            if (wakeWordRecognitionRef.current && !isWakeWordListening && !isListening) {
              try {
                console.log('Starting wake word recognition...')
                setIsWakeWordListening(true)
                wakeWordRecognitionRef.current.start()
              } catch (error) {
                console.error('Failed to start wake word recognition:', error)
                setIsWakeWordListening(false)
              }
            }
          }, 100)
        }
      } else {
        console.log('Wake word mode désactivé')
        if (wakeWordRecognitionRef.current && isWakeWordListening) {
          wakeWordRecognitionRef.current.stop()
          setIsWakeWordListening(false)
        }
      }
      
      lastClickTimeRef.current = 0 // Reset pour éviter les triples clics
      return
    }
    
    lastClickTimeRef.current = currentTime

    // Programmer l'action du simple clic avec un délai
    singleClickTimeoutRef.current = setTimeout(() => {
      console.log('Single click detected - current state:', { isListening, isWakeWordListening })
      
      // Single click logic - simplified like in backup
      if (isListening) {
        // Si on est en train d'écouter, arrêter immédiatement
        console.log('Stopping current speech recognition...')
        if (recognitionRef.current) {
          recognitionRef.current.stop()
          setIsListening(false)
          setVoiceInputComplete(false)
        }
      } else {
        // Arrêter le wake word temporairement si actif
        if (isWakeWordListening && wakeWordRecognitionRef.current) {
          try {
            console.log('Stopping wake word recognition for manual input...')
            wakeWordRecognitionRef.current.stop()
            setIsWakeWordListening(false)
          } catch (error) {
            console.error('Failed to stop wake word recognition:', error)
          }
        }
        
        // Commencer l'écoute manuelle directement comme dans le backup
        console.log('Starting manual speech recognition from single click...')
        if (recognitionRef.current) {
          try {
            recognitionRef.current.start()
          } catch (error) {
            console.error('Failed to start speech recognition:', error)
            setIsListening(false)
          }
        }
      }
      singleClickTimeoutRef.current = null
    }, 300) // Délai pour détecter un éventuel double-clic
  }, [voiceInputEnabled, speechSupported, wakeWordMode, canUseWakeWord, isWakeWordListening, isListening])

  // Auto-restart wake word after question is sent
  const restartWakeWordAfterSend = useCallback(() => {
    if (wakeWordMode && speechSupported && canUseWakeWord) {
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
      }, 1000)
    }
  }, [wakeWordMode, speechSupported, canUseWakeWord, isWakeWordListening, isListening])

  const resetVoiceInput = useCallback(() => {
    console.log('Resetting voice input state...')
    setVoiceInputComplete(false)
    setIsListening(false) // Ensure listening state is clean
    restartWakeWordAfterSend()
  }, [restartWakeWordAfterSend])

  // Pause l'écoute vocale (pendant la lecture audio par exemple)
  const pauseVoiceRecognition = useCallback(() => {
    console.log('Pausing voice recognition for audio playback')
    
    // Mémoriser l'état actuel du wake word avant de l'arrêter
    wasWakeWordActiveBeforePause.current = isWakeWordListening
    console.log('Wake word was active before pause:', wasWakeWordActiveBeforePause.current)
    
    // Arrêter la reconnaissance manuelle si en cours
    if (recognitionRef.current && isListening) {
      try {
        recognitionRef.current.stop()
      } catch (error) {
        console.error('Error stopping manual recognition:', error)
      }
    }
    
    // Arrêter le wake word si en cours
    if (wakeWordRecognitionRef.current && isWakeWordListening) {
      try {
        wakeWordRecognitionRef.current.stop()
      } catch (error) {
        console.error('Error stopping wake word recognition:', error)
      }
    }
  }, [isListening, isWakeWordListening])

  // Reprendre l'écoute vocale après la lecture audio
  const resumeVoiceRecognition = useCallback(() => {
    console.log('Resuming voice recognition after audio playback')
    
    // Utiliser un délai pour permettre aux états de se synchroniser
    setTimeout(() => {
      console.log('Current state before resume check:', {
        wasWakeWordActiveBeforePause: wasWakeWordActiveBeforePause.current,
        wakeWordMode,
        canUseWakeWord,
        voiceInputEnabled,
        isListening,
        isWakeWordListening,
        hasWakeWordRef: !!wakeWordRecognitionRef.current
      })
      
      // Redémarrer le wake word SEULEMENT s'il était actif avant la pause ET que le mode est toujours activé
      // Ignorer l'état isWakeWordListening car il peut être incohérent après la pause
      if (wasWakeWordActiveBeforePause.current && wakeWordMode && canUseWakeWord && voiceInputEnabled && !isListening) {
        console.log('Conditions met, restarting wake word recognition...')
        if (wakeWordRecognitionRef.current) {
          try {
            // Forcer l'arrêt d'abord pour s'assurer qu'on repart sur une base propre
            if (isWakeWordListening) {
              console.log('Stopping any existing wake word recognition before restart')
              wakeWordRecognitionRef.current.stop()
              setIsWakeWordListening(false)
            }
            
            // Petit délai pour s'assurer que l'arrêt est effectif
            setTimeout(() => {
              try {
                console.log('Starting fresh wake word recognition')
                setIsWakeWordListening(true)
                wakeWordRecognitionRef.current.start()
                console.log('Wake word recognition resumed (was active before)')
              } catch (error) {
                console.error('Error starting fresh wake word recognition:', error)
                setIsWakeWordListening(false)
              }
            }, 100)
          } catch (error) {
            console.error('Error stopping existing wake word recognition:', error)
            setIsWakeWordListening(false)
          }
        }
      } else {
        console.log('Not resuming wake word - conditions not met:', {
          wasActive: wasWakeWordActiveBeforePause.current,
          modeEnabled: wakeWordMode,
          canUse: canUseWakeWord,
          voiceEnabled: voiceInputEnabled,
          notListening: !isListening
        })
      }
      
      // Réinitialiser l'état mémorisé après usage
      wasWakeWordActiveBeforePause.current = false
    }, 800) // Délai principal
  }, [canUseWakeWord, voiceInputEnabled, isListening, isWakeWordListening, wakeWordMode])

  return {
    // State
    isListening,
    isWakeWordListening,
    speechSupported,
    question,
    voiceInputComplete,
    
    // Actions
    startListening,
    stopListening,
    toggleWakeWord,
    setQuestion,
    resetVoiceInput,
    pauseVoiceRecognition,
    resumeVoiceRecognition
  }
}