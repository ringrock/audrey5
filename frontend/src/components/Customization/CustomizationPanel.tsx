import React, { useContext, useEffect, useState, useRef } from 'react'
import {
  Icon,
  Text,
  Stack,
  Slider,
  ChoiceGroup,
  IChoiceGroupOption,
  MessageBar,
  MessageBarType,
  DefaultButton
} from '@fluentui/react'
import { AppStateContext } from '../../state/AppProvider'

// Importation des fichiers de style
import styles from './CustomizationPanel.module.css'

// Types pour les préférences de personnalisation
export interface CustomizationPreferences {
  responseSize: 'veryShort' | 'medium' | 'comprehensive';
  documentsCount: number;
  llmProvider: string;
}

// Fonction utilitaire pour charger les préférences depuis localStorage (définie en dehors du composant)
const loadPreferencesFromStorage = (): CustomizationPreferences | null => {
  try {
    const saved = localStorage.getItem('userCustomizationPreferences')
    if (saved) {
      const parsed = JSON.parse(saved)
      // Validation des données pour éviter les erreurs
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

export function CustomizationPanel() {
  const appStateContext = useContext(AppStateContext)
  const [isVisible, setIsVisible] = useState(false)
  const [showToast, setShowToast] = useState(false)
  const [toastMessage, setToastMessage] = useState('')
  const [currentLanguage, setCurrentLanguage] = useState('FR')
  
  // États pour les préférences utilisateur - initialisés avec les valeurs sauvegardées ou par défaut
  const getInitialPreferences = () => {
    const saved = loadPreferencesFromStorage()
    return saved || {
      responseSize: appStateContext?.state.customizationPreferences?.responseSize || 'medium',
      documentsCount: appStateContext?.state.customizationPreferences?.documentsCount || 5,
      llmProvider: appStateContext?.state.customizationPreferences?.llmProvider || 'AZURE_OPENAI'
    }
  }

  const initialPrefs = getInitialPreferences()
  
  const [responseSize, setResponseSize] = useState<'veryShort' | 'medium' | 'comprehensive'>(
    initialPrefs.responseSize as 'veryShort' | 'medium' | 'comprehensive'
  )
  
  const [documentsCount, setDocumentsCount] = useState<number>(
    initialPrefs.documentsCount
  )
  
  const [llmProvider, setLlmProvider] = useState<string>(
    initialPrefs.llmProvider || 'AZURE_OPENAI'
  )
  
  const panelRef = useRef<HTMLDivElement>(null)
  
  // Options pour le choix de la taille de réponse
  const responseSizeOptions: IChoiceGroupOption[] = [
    { key: 'veryShort', text: currentLanguage === 'FR' ? 'Très courte' : 'Very short' },
    { key: 'medium', text: currentLanguage === 'FR' ? 'Moyenne' : 'Medium' },
    { key: 'comprehensive', text: currentLanguage === 'FR' ? 'Très complète' : 'Comprehensive' }
  ]
  
  // Récupérer la liste des providers disponibles depuis les settings frontend
  const availableProviders = appStateContext?.state.frontendSettings?.available_llm_providers || ['AZURE_OPENAI']
  
  // Options pour le choix du provider LLM (basées sur la configuration backend)
  const llmProviderOptions: IChoiceGroupOption[] = availableProviders.map(provider => ({
    key: provider,
    text: provider
  }))
  
  
  // Fonction pour sauvegarder les préférences dans localStorage
  const savePreferencesToStorage = (preferences: CustomizationPreferences) => {
    try {
      localStorage.setItem('userCustomizationPreferences', JSON.stringify(preferences))
    } catch (error) {
      console.warn('Failed to save customization preferences to localStorage:', error)
    }
  }


  // Fonction pour mettre à jour les préférences
  const updatePreferences = (newResponseSize?: 'veryShort' | 'medium' | 'comprehensive', newDocumentsCount?: number, newLlmProvider?: string) => {
    const updatedPreferences: CustomizationPreferences = {
      responseSize: newResponseSize || responseSize,
      documentsCount: newDocumentsCount !== undefined ? newDocumentsCount : documentsCount,
      llmProvider: newLlmProvider || llmProvider
    }
    
    // Sauvegarder dans localStorage
    savePreferencesToStorage(updatedPreferences)
    
    // Mise à jour des préférences dans le contexte global sans afficher de toast
    appStateContext?.dispatch({ type: 'UPDATE_CUSTOMIZATION_PREFERENCES', payload: updatedPreferences })
  }
  
  // Gestionnaires d'événements pour les changements
  const handleResponseSizeChange = (_: React.FormEvent<HTMLElement | HTMLInputElement> | undefined, option?: IChoiceGroupOption) => {
    if (option) {
      const newValue = option.key as 'veryShort' | 'medium' | 'comprehensive'
      setResponseSize(newValue)
      updatePreferences(newValue, undefined, undefined)
    }
  }
  
  const handleDocumentsCountChange = (value: number) => {
    setDocumentsCount(value)
    updatePreferences(undefined, value, undefined)
  }
  
  const handleLlmProviderChange = (_: React.FormEvent<HTMLElement | HTMLInputElement> | undefined, option?: IChoiceGroupOption) => {
    if (option) {
      const newValue = option.key as string
      setLlmProvider(newValue)
      updatePreferences(undefined, undefined, newValue)
    }
  }
  
  // Fermeture du panneau de personnalisation
  const handleCloseCustomization = () => {
    // Animer la fermeture du panneau
    setIsVisible(false)
    
    // Délai avant de réellement masquer le panneau (pour permettre l'animation)
    setTimeout(() => {
      appStateContext?.dispatch({ type: 'TOGGLE_CUSTOMIZATION_PANEL' })
    }, 300)
  }
  
  // Gestion du clic sur l'overlay (fond semi-transparent)
  const handleOverlayClick = (e: React.MouseEvent) => {
    // S'assurer que le clic était bien sur l'overlay et pas sur le panneau
    if (e.target === e.currentTarget) {
      handleCloseCustomization()
    }
  }
  
  // Réinitialiser les paramètres par défaut
  const resetToDefaults = () => {
    const defaultProvider = availableProviders[0] || 'AZURE_OPENAI'
    const defaultPreferences: CustomizationPreferences = {
      responseSize: 'medium',
      documentsCount: 5,
      llmProvider: defaultProvider
    }
    
    // Mettre à jour l'état local
    setResponseSize('medium')
    setDocumentsCount(5)
    setLlmProvider(defaultProvider)
    
    // Supprimer les préférences du localStorage
    try {
      localStorage.removeItem('userCustomizationPreferences')
    } catch (error) {
      console.warn('Failed to remove customization preferences from localStorage:', error)
    }
    
    // Mettre à jour l'état global
    appStateContext?.dispatch({ type: 'UPDATE_CUSTOMIZATION_PREFERENCES', payload: defaultPreferences })
    
    // Afficher un toast de confirmation
    setToastMessage(currentLanguage === 'FR' ? 'Préférences réinitialisées' : 'Preferences reset to defaults')
    setShowToast(true)
    
    // Masquer après 2 secondes
    setTimeout(() => {
      setShowToast(false)
    }, 2000)
  }

  // useEffect pour charger les préférences sauvegardées au démarrage
  useEffect(() => {
    // Charger les préférences depuis localStorage
    const savedPreferences = loadPreferencesFromStorage()
    if (savedPreferences) {
      // Mettre à jour l'état local
      setResponseSize(savedPreferences.responseSize)
      setDocumentsCount(savedPreferences.documentsCount)
      setLlmProvider(savedPreferences.llmProvider || 'AZURE_OPENAI')
      
      // Mettre à jour l'état global
      appStateContext?.dispatch({ type: 'UPDATE_CUSTOMIZATION_PREFERENCES', payload: savedPreferences })
    }
  }, []) // Se déclenche seulement au montage du composant

  useEffect(() => {
    // Définir l'animation d'apparition après montage du composant
    setTimeout(() => {
      setIsVisible(true)
    }, 50)
    
    // Déterminer la langue en fonction du contexte de l'application
    const userLang = appStateContext?.state.userLanguage || 'FR';
    setCurrentLanguage(userLang);
    
    // Synchroniser l'état local avec les préférences globales à chaque ouverture du panneau
    if (appStateContext?.state.customizationPreferences) {
      setResponseSize(appStateContext.state.customizationPreferences.responseSize);
      setDocumentsCount(appStateContext.state.customizationPreferences.documentsCount);
      setLlmProvider(appStateContext.state.customizationPreferences.llmProvider);
    }
    
    // Ajouter l'écouteur pour la touche Escape
    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleCloseCustomization()
      }
    }
    
    document.addEventListener('keydown', handleEscapeKey)
    
    // Nettoyage lors du démontage
    return () => {
      document.removeEventListener('keydown', handleEscapeKey)
    }
  }, [appStateContext?.state.userLanguage, appStateContext?.state.customizationPreferences])

  return (
    <>
      {/* Overlay semi-transparent */}
      <div 
        className={`${styles.overlay} ${isVisible ? styles.overlayVisible : ''}`}
        onClick={handleOverlayClick}
        aria-hidden="true"
      />
      
      {/* Panneau de personnalisation */}
      <div 
        ref={panelRef}
        className={`${styles.container} ${isVisible ? styles.visible : ''}`} 
        aria-label="panneau de personnalisation"
      >
        {/* Toast de notification */}
        {showToast && (
          <div className={styles.toastContainer}>
            <MessageBar
              className={styles.toast}
              messageBarType={MessageBarType.success}
              isMultiline={false}
              onDismiss={() => setShowToast(false)}
              dismissButtonAriaLabel={currentLanguage === 'FR' ? 'Fermer' : 'Dismiss'}
              aria-live="polite"
            >
              {toastMessage}
            </MessageBar>
          </div>
        )}
        
        <div className={styles.customizationHeader}>
          <h2 className={styles.customizationTitle}>
            <Icon iconName="Settings" className={styles.titleIcon} />
            {currentLanguage === 'FR' ? 'Personnalisation' : 'Customization'}
          </h2>
          <button 
            className={styles.closeButton} 
            onClick={handleCloseCustomization}
            aria-label={currentLanguage === 'FR' ? 'Fermer' : 'Close'}
          >
            <Icon iconName="Cancel" />
          </button>
        </div>
        
        <div className={styles.customizationContent}>
          {/* Section de la taille de réponse */}
          <div className={styles.settingSection}>
            <h3 className={styles.settingTitle}>
              <Icon iconName="TextDocument" className={styles.settingIcon} />
              {currentLanguage === 'FR' ? 'Taille de la réponse' : 'Response Size'}
            </h3>
            <p className={styles.settingDescription}>
              {currentLanguage === 'FR' 
                ? 'Choisissez la longueur des réponses générées par l\'assistant.' 
                : 'Choose the length of responses generated by the assistant.'}
            </p>
            
            <ChoiceGroup 
              selectedKey={responseSize}
              options={responseSizeOptions}
              onChange={handleResponseSizeChange}
              className={styles.choiceGroup}
            />
          </div>
          
          {/* Section du nombre de documents */}
          <div className={styles.settingSection}>
            <h3 className={styles.settingTitle}>
              <Icon iconName="DocumentSearch" className={styles.settingIcon} />
              {currentLanguage === 'FR' ? 'Nombre de documents' : 'Number of Documents'}
            </h3>
            <p className={styles.settingDescription}>
              {currentLanguage === 'FR' 
                ? 'Définissez combien de documents l\'assistant doit consulter pour répondre à vos questions.' 
                : 'Set how many documents the assistant should consult to answer your questions.'}
            </p>
            
            <div className={styles.sliderContainer}>
              <Slider
                label={`${documentsCount} ${currentLanguage === 'FR' ? 'documents' : 'documents'}`}
                min={3}
                max={20}
                step={1}
                value={documentsCount}
                onChange={handleDocumentsCountChange}
                showValue={false}
                className={styles.slider}
              />
              <div className={styles.sliderLegend}>
                <span className={styles.sliderMin}>3</span>
                <span className={styles.sliderMax}>20</span>
              </div>
            </div>
            
            <MessageBar 
              className={styles.warningMessage}
              messageBarType={MessageBarType.warning}
            >
              {currentLanguage === 'FR' 
                ? 'Attention : Un nombre élevé de documents peut diminuer la précision des réponses et augmenter le temps de traitement.'
                : 'Warning: A higher number of documents may decrease answer precision and increase processing time.'}
            </MessageBar>
          </div>
          
          {/* Section du choix du provider LLM - seulement si plusieurs providers disponibles */}
          {availableProviders.length > 1 && (
            <div className={styles.settingSection}>
              <h3 className={styles.settingTitle}>
                <Icon iconName="Robot" className={styles.settingIcon} />
                {currentLanguage === 'FR' ? 'Modèle de langage' : 'Language Model'}
              </h3>
              <p className={styles.settingDescription}>
                {currentLanguage === 'FR' 
                  ? 'Choisissez le modèle de langage à utiliser pour générer les réponses.' 
                  : 'Choose the language model to use for generating responses.'}
              </p>
              
              <ChoiceGroup 
                selectedKey={llmProvider}
                options={llmProviderOptions}
                onChange={handleLlmProviderChange}
                className={styles.choiceGroup}
              />
            </div>
          )}
          
          {/* Bouton de réinitialisation uniquement */}
          <div className={styles.actionButtons}>
            <DefaultButton
              className={styles.resetButton}
              onClick={resetToDefaults}
              iconProps={{ iconName: 'Refresh', className: styles.buttonIcon }}
              text={currentLanguage === 'FR' ? 'Rétablir les paramètres par défaut' : 'Reset to defaults'}
            />
          </div>

          {/* Note informative */}
          <MessageBar className={styles.infoMessage}>
            {currentLanguage === 'FR' 
              ? 'Vos préférences sont automatiquement appliquées lorsque vous les modifiez.'
              : 'Your preferences are automatically applied when you change them.'}
          </MessageBar>
        </div>
      </div>
    </>
  )
}