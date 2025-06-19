import { useContext, useState, useEffect } from 'react'
import { FontIcon, Stack, TextField } from '@fluentui/react'
import { SendRegular } from '@fluentui/react-icons'

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

  const appStateContext = useContext(AppStateContext)
  
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
