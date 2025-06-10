import { useContext, useState, useEffect } from 'react'
import { FontIcon, Stack, TextField } from '@fluentui/react'
import { SendRegular } from '@fluentui/react-icons'

import Send from '../../assets/Send.svg'

import styles from './QuestionInput.module.css'
import { ChatMessage } from '../../api'
import { AppStateContext } from '../../state/AppProvider'
import { resizeImage } from '../../utils/resizeImage'

interface Props {
  onSend: (question: ChatMessage['content'], id?: string) => void
  disabled: boolean
  placeholder?: string
  clearOnSend?: boolean
  conversationId?: string
}

export const QuestionInput = ({ onSend, disabled, placeholder, clearOnSend, conversationId }: Props) => {
  const [question, setQuestion] = useState<string>('')
  const [base64Image, setBase64Image] = useState<string | null>(null);

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

  const handleImageUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];

    if (file) {
      await convertToBase64(file);
    }
  };

  const convertToBase64 = async (file: Blob) => {
    try {
      const resizedBase64 = await resizeImage(file, 800, 800);
      setBase64Image(resizedBase64);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const sendQuestion = () => {
    if (disabled || !question.trim()) {
      return
    }

    const questionText = question.trim()
    const questionTest: ChatMessage["content"] = base64Image ? [{ type: "text", text: questionText }, { type: "image_url", image_url: { url: base64Image } }] : questionText;

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
      />
      {!OYD_ENABLED && (
        <div className={styles.fileInputContainer}>
          <input
            type="file"
            id="fileInput"
            onChange={(event) => handleImageUpload(event)}
            accept="image/*"
            className={styles.fileInput}
          />
          <label htmlFor="fileInput" className={styles.fileLabel} aria-label='Upload Image'>
            <FontIcon
              className={styles.fileIcon}
              iconName={'PhotoCollection'}
              aria-label='Upload Image'
            />
          </label>
        </div>)}
      {base64Image && <img className={styles.uploadedImage} src={base64Image} alt="Uploaded Preview" />}
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
