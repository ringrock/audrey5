import { useContext, useState, useEffect, useRef, useCallback } from 'react'
import { FontIcon, Stack, TextField } from '@fluentui/react'
import { SendRegular, Mic20Regular, MicOff20Regular, Speaker220Regular, SpeakerOff20Regular } from '@fluentui/react-icons'

import Send from '../../assets/Send.svg'

import styles from './QuestionInput.module.css'
import { ChatMessage } from '../../api'
import { AppStateContext } from '../../state/AppProvider'
import { useVoiceRecognition } from '../../hooks/useVoiceRecognition'

interface Props {
  onSend: (question: ChatMessage['content'], id?: string) => void
  disabled: boolean
  placeholder?: string
  clearOnSend?: boolean
  conversationId?: string
  onVoiceRecognitionReady?: (pause: () => void, resume: () => void) => void
}

export const QuestionInput = ({ onSend, disabled, placeholder, clearOnSend, conversationId, onVoiceRecognitionReady }: Props) => {
  const [base64Image, setBase64Image] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [userTypedQuestion, setUserTypedQuestion] = useState<string>('')
  const [isInitialQuestionSet, setIsInitialQuestionSet] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  
  // History management for arrow key navigation
  const [history, setHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState<number>(-1)
  const [tempQuestion, setTempQuestion] = useState<string>('')
  
  // Drag & drop state
  const [isDragging, setIsDragging] = useState<boolean>(false)
  
  const autoSendTimeoutRef = useRef<number | null>(null)

  const appStateContext = useContext(AppStateContext)
  
  // Configuration vocale depuis les paramètres
  const voiceInputEnabled = appStateContext?.state.frontendSettings?.voice_input_enabled ?? true
  const canUseWakeWord = appStateContext?.state.frontendSettings?.wake_word_enabled ?? true
  const wakeWordEnabled = appStateContext?.state.frontendSettings?.wake_word_enabled ?? true
  const wakeWordPhrases = appStateContext?.state.frontendSettings?.wake_word_phrases ?? ['asmi', 'askme', 'askmi', 'asqmi']
  const wakeWordVariants = appStateContext?.state.frontendSettings?.wake_word_variants ?? {}
  
  // Configuration pour les images
  const imageMaxSizeMb = appStateContext?.state.frontendSettings?.image_max_size_mb ?? 10.0
  
  // Use voice recognition hook
  const voiceRecognition = useVoiceRecognition({
    voiceInputEnabled,
    canUseWakeWord,
    wakeWordEnabled,
    wakeWordPhrases,
    wakeWordVariants
  })

  // Sync question state with voice recognition
  const [question, setQuestion] = useState<string>('')
  
  useEffect(() => {
    if (voiceRecognition.question !== question) {
      setQuestion(voiceRecognition.question)
    }
  }, [voiceRecognition.question])

  useEffect(() => {
    if (question !== voiceRecognition.question) {
      voiceRecognition.setQuestion(question)
    }
  }, [question])

  // Expose voice recognition functions to parent
  useEffect(() => {
    if (onVoiceRecognitionReady) {
      onVoiceRecognitionReady(
        voiceRecognition.pauseVoiceRecognition,
        voiceRecognition.resumeVoiceRecognition
      )
    }
  }, [onVoiceRecognitionReady, voiceRecognition.pauseVoiceRecognition, voiceRecognition.resumeVoiceRecognition])
  
  // Auto-audio functionality
  const toggleGlobalAutoAudio = () => {
    const newState = !appStateContext?.state.isAutoAudioEnabled
    
    appStateContext?.dispatch({
      type: 'TOGGLE_AUTO_AUDIO',
      payload: newState
    })
    
    // Si on DÉSACTIVE l'auto-lecture, arrêter la lecture en cours
    if (!newState) {
      const allAudioElements = document.querySelectorAll('audio')
      allAudioElements.forEach((audio) => {
        if (!audio.paused) {
          audio.pause()
          audio.currentTime = 0
          audio.src = ''
        }
      })
      
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel()
      }
    }
    // Si on ACTIVE l'auto-lecture, ne rien faire - laisse l'auto-lecture se déclencher naturellement sur le prochain nouveau message
  }
  
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

  const OYD_ENABLED = appStateContext?.state.frontendSettings?.oyd_enabled || false
  const currentProvider = appStateContext?.state.customizationPreferences?.llmProvider || 'AZURE_OPENAI'
  
  // Seuls Claude, Gemini et OpenAI Direct supportent les images
  const supportsImages = ['CLAUDE', 'GEMINI', 'OPENAI_DIRECT'].includes(currentProvider)

  // Nettoyer l'image quand on change vers un provider qui ne supporte pas les images
  useEffect(() => {
    if (!supportsImages && base64Image) {
      console.log('Clearing image because provider', currentProvider, 'does not support images')
      setBase64Image(null)
    }
  }, [currentProvider, supportsImages, base64Image])
  
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
          
          // Utiliser la même logique que pour l'upload de fichier
          convertToBase64(file)
            .then(() => {
              console.log('Image du presse-papier traitée avec succès')
            })
            .catch((error) => {
              console.error('Erreur lors du traitement de l\'image du presse-papier:', error)
              if (error instanceof Error) {
                setErrorMessage(error.message)
              }
            })
        }
        
        return // Sortir de la boucle une fois qu'une image est trouvée
      }
    }
  }

  // Auto-populate question if provided in URL params
  useEffect(() => {
    if (!isInitialQuestionSet) {
      const urlParams = new URLSearchParams(window.location.search)
      const questionParam = urlParams.get('question')
      if (questionParam) {
        setQuestion(decodeURIComponent(questionParam))
        setIsInitialQuestionSet(true)
      } else {
        setIsInitialQuestionSet(true)
      }
    }
  }, [isInitialQuestionSet])

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    
    try {
      if (file) {
        console.log('File selected:', file.name, file.type, file.size)
        
        // Vérifier si le provider actuel supporte les images
        if (!supportsImages) {
          alert(`Les images ne sont pas supportées par ${currentProvider}. Veuillez changer de fournisseur pour utiliser cette fonctionnalité.`)
          event.target.value = ''
          return
        }
        
        // Réinitialiser les états précédents
        setBase64Image(null)
        
        // Seules les images sont autorisées
        if (file.type.startsWith('image/')) {
          console.log('Processing image file...')
          try {
            await convertToBase64(file)
            console.log('Image processing completed successfully')
          } catch (conversionError) {
            console.error('Image conversion failed:', conversionError)
            if (conversionError instanceof Error) {
              setErrorMessage(conversionError.message)
            } else {
              setErrorMessage('Erreur lors du traitement de l\'image. Veuillez réessayer.')
            }
          }
        } else {
          console.log('Non-image file selected, skipping...')
          alert('Seules les images sont supportées.')
        }
        
        // Reset file input value pour permettre de sélectionner le même fichier
        event.target.value = ''
      }
    } catch (error) {
      console.error('Error in handleFileUpload:', error)
      if (error instanceof Error) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('Erreur lors du téléchargement du fichier. Veuillez réessayer.')
      }
    }
  }

  // Gestionnaires pour le drag & drop d'images
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    // Vérifier si les images sont supportées par le provider actuel
    if (!supportsImages) {
      return
    }
    
    // Vérifier si l'élément glissé contient des fichiers
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    // Ne désactiver le dragging que si on quitte vraiment la zone (pas un élément enfant)
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragging(false)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    
    // Vérifier si les images sont supportées par le provider actuel
    if (!supportsImages) {
      alert(`Les images ne sont pas supportées par ${currentProvider}. Veuillez changer de fournisseur pour utiliser cette fonctionnalité.`)
      return
    }
    
    const files = Array.from(e.dataTransfer.files)
    if (files.length === 0) return
    
    const file = files[0] // Prendre seulement le premier fichier
    
    try {
      console.log('File dropped:', file.name, file.type, file.size)
      
      // Réinitialiser les états précédents
      setBase64Image(null)
      
      // Seules les images sont autorisées
      if (file.type.startsWith('image/')) {
        console.log('Processing dropped image file...')
        try {
          await convertToBase64(file)
          console.log('Dropped image processing completed successfully')
        } catch (conversionError) {
          console.error('Dropped image conversion failed:', conversionError)
          if (conversionError instanceof Error) {
            setErrorMessage(conversionError.message)
          } else {
            setErrorMessage('Erreur lors du traitement de l\'image. Veuillez réessayer.')
          }
        }
      } else {
        console.log('Non-image file dropped, rejecting...')
        alert('Seules les images sont supportées.')
      }
    } catch (error) {
      console.error('Error in handleDrop:', error)
      if (error instanceof Error) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('Erreur lors du traitement du fichier. Veuillez réessayer.')
      }
    }
  }

  const convertToBase64 = async (file: Blob) => {
    return new Promise<void>((resolve, reject) => {
      try {
        console.log('convertToBase64 called with file:', file.size, 'bytes')
        
        // Vérification de la taille d'image selon la configuration backend
        const maxSizeBytes = imageMaxSizeMb * 1024 * 1024
        if (file.size > maxSizeBytes) {
          console.error('File too large:', file.size, 'bytes, limit:', maxSizeBytes)
          const errorMsg = `Image trop volumineuse (limite ${imageMaxSizeMb}MB). Veuillez utiliser une image plus petite.`
          setErrorMessage(errorMsg)
          reject(new Error(errorMsg))
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

  const sendQuestion = useCallback(() => {
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
  }, [disabled, question, base64Image, history, conversationId, onSend, clearOnSend])

  // Auto-send effect for voice input
  useEffect(() => {
    if (voiceRecognition.voiceInputComplete && question.trim() && !disabled) {
      // Délai de 2 secondes avant l'envoi automatique
      autoSendTimeoutRef.current = setTimeout(() => {
        if (question.trim() && !disabled) {
          sendQuestion()
          voiceRecognition.resetVoiceInput()
        }
        autoSendTimeoutRef.current = null
      }, 2000)
    }
    
    return () => {
      if (autoSendTimeoutRef.current) {
        clearTimeout(autoSendTimeoutRef.current)
        autoSendTimeoutRef.current = null
      }
    }
  }, [voiceRecognition.voiceInputComplete, question, disabled, sendQuestion, voiceRecognition.resetVoiceInput])

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
    } else if (ev.key === 'ArrowDown' && historyIndex >= 0) {
      ev.preventDefault()
      
      if (historyIndex === 0) {
        // Return to original question
        setHistoryIndex(-1)
        setQuestion(tempQuestion)
        setTempQuestion('')
      } else {
        // Go to more recent question
        const newIndex = historyIndex - 1
        setHistoryIndex(newIndex)
        setQuestion(history[newIndex])
      }
    }
  }



  const disableRequiredAccessControl = false

  return (
    <Stack 
      horizontal 
      className={`${styles.questionInputContainer} ${isDragging ? styles.dragging : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <TextField
        className={styles.questionInputTextArea}
        placeholder={placeholder}
        multiline
        resizable={false}
        borderless
        value={question}
        onChange={(_ev, newValue) => {
          setQuestion(newValue || '')
          setUserTypedQuestion(newValue || '')
        }}
        onKeyDown={onEnterPress}
        onPaste={onPaste}
      />
      {isDragging && supportsImages && (
        <div className={styles.dragOverlay}>
          <div className={styles.dragMessage}>
            📷 Déposez votre image ici
          </div>
        </div>
      )}
      <div className={styles.fileInputContainer}>
        <input
          type="file"
          id="fileInput"
          onChange={handleFileUpload}
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
      {/* Auto-audio toggle button */}
      <div className={styles.autoAudioContainer}>
        <button
          type="button"
          className={`${styles.voiceButton} ${appStateContext?.state.isAutoAudioEnabled ? styles.autoAudioActive : ''}`}
          onClick={toggleGlobalAutoAudio}
          aria-label={appStateContext?.state.isAutoAudioEnabled ? "Désactiver la lecture automatique" : "Activer la lecture automatique"}
          title={appStateContext?.state.isAutoAudioEnabled ? "Désactiver la lecture automatique" : "Activer la lecture automatique"}
        >
          {appStateContext?.state.isAutoAudioEnabled ? (
            <Speaker220Regular className={styles.voiceIcon} />
          ) : (
            <SpeakerOff20Regular className={styles.voiceIcon} />
          )}
        </button>
      </div>
      {voiceInputEnabled && voiceRecognition.speechSupported && (
        <div className={styles.voiceInputContainer}>
          <button
            type="button"
            className={`${styles.voiceButton} ${!voiceRecognition.speechSupported ? styles.disabled : ''} ${voiceRecognition.isListening ? styles.listening : ''} ${voiceRecognition.isWakeWordListening && !voiceRecognition.isListening ? styles.wakeWordListening : ''}`}
            onClick={voiceRecognition.toggleWakeWord}
            disabled={!voiceRecognition.speechSupported}
            aria-label={
              voiceRecognition.isWakeWordListening 
                ? "Mode écoute active (double-clic pour désactiver)" 
                : voiceRecognition.isListening 
                  ? "Reconnaissance vocale en cours..." 
                  : "Clic simple: reconnaissance vocale / Double-clic: mode écoute"
            }
            title={
              voiceRecognition.isWakeWordListening 
                ? "Mode écoute active (double-clic pour désactiver)" 
                : voiceRecognition.isListening 
                  ? "Reconnaissance vocale en cours..." 
                  : "Clic simple: reconnaissance vocale / Double-clic: mode écoute"
            }
          >
            {voiceRecognition.isListening ? (
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
        {disabled ? (
          <SendRegular className={styles.questionInputSendButtonDisabled} />
        ) : (
          <img src={Send} className={styles.questionInputSendButton} alt="Send Button" />
        )}
      </div>
      {errorMessage && (
        <div className={styles.errorContainer}>
          <div className={styles.errorMessage}>
            <FontIcon iconName="ErrorBadge" className={styles.errorIcon} />
            <span>{errorMessage}</span>
            <button 
              className={styles.errorCloseButton}
              onClick={() => setErrorMessage(null)}
              aria-label="Fermer le message d'erreur"
              title="Fermer"
            >
              <FontIcon iconName="Cancel" />
            </button>
          </div>
        </div>
      )}
      <div className={styles.questionInputBottomBorder} />
    </Stack>
  )
}