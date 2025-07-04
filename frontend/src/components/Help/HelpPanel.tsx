import React, { useContext, useEffect, useState, useRef } from 'react'
import {
  Icon,
  Text,
  MessageBar,
  MessageBarType,
  SearchBox,
  Pivot,
  PivotItem,
  FocusZone,
  List,
  Spinner,
  SpinnerSize
} from '@fluentui/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AppStateContext } from '../../state/AppProvider'

// Importation des fichiers de style
import styles from './HelpPanel.module.css'

// Types pour le contenu d'aide
interface Translation {
  [key: string]: string;
}

interface Translations {
  [lang: string]: Translation;
}

interface Category {
  key: string;
  name: { [lang: string]: string };
  icon: string;
}

interface GuideSection {
  id: string;
  title: { [lang: string]: string };
  content: { [lang: string]: string };
  icon: string;
}

interface PredefinedPrompt {
  id: number;
  categories: string[];
  title: { [lang: string]: string };
  description: { [lang: string]: string };
  prompt: { [lang: string]: string };
}

interface HelpContent {
  translations: Translations;
  categories: Category[];
  guideContent: GuideSection[];
  predefinedPrompts: PredefinedPrompt[];
}

export function HelpPanel() {
  const appStateContext = useContext(AppStateContext)
  const [isVisible, setIsVisible] = useState(false)
  const [showToast, setShowToast] = useState(false)
  const [toastMessage, setToastMessage] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [filteredPrompts, setFilteredPrompts] = useState<PredefinedPrompt[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [currentLanguage, setCurrentLanguage] = useState('FR')
  const [selectedGuideSection, setSelectedGuideSection] = useState<string>('getting-started')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [helpContent, setHelpContent] = useState<HelpContent | null>(null)
  
  const panelRef = useRef<HTMLDivElement>(null)
  const guideSectionRefs = useRef<{[key: string]: React.RefObject<HTMLDivElement>}>({})
  
  // Fonction pour récupérer une traduction
  const getTranslation = (key: string): string => {
    if (!helpContent) return key;
    const translations = helpContent.translations[currentLanguage] || {};
    return translations[key] || key;
  };
  
  // Charger le contenu d'aide depuis l'API
  useEffect(() => {
    const fetchHelpContent = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const language = appStateContext?.state.userLanguage || 'FR';
        const response = await fetch(`/help_content?lang=${language}`);
        
        if (!response.ok) {
          throw new Error(`Error ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        setHelpContent(data);
        
        // Initialiser les références pour chaque section du guide
        if (data.guideContent) {
          data.guideContent.forEach((section: GuideSection) => {
            guideSectionRefs.current[section.id] = React.createRef<HTMLDivElement>();
          });
        }
        
        // Initialiser les prompts filtrés
        if (data.predefinedPrompts) {
          setFilteredPrompts(data.predefinedPrompts);
        }
        
      } catch (err) {
        console.error('Error fetching help content:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchHelpContent();
  }, [appStateContext?.state.userLanguage]);
  
  // Fermeture du panneau d'aide
  const handleCloseHelp = () => {
    setIsVisible(false)
    // Délai avant de réellement masquer le panneau (pour permettre l'animation)
    setTimeout(() => {
      appStateContext?.dispatch({ type: 'TOGGLE_HELP_PANEL' })
    }, 300)
  }
  
  // Gestion du clic sur l'overlay (fond semi-transparent)
  const handleOverlayClick = (e: React.MouseEvent) => {
    // S'assurer que le clic était bien sur l'overlay et pas sur le panneau
    if (e.target === e.currentTarget) {
      handleCloseHelp()
    }
  }
  
  // Fonction pour copier un exemple de prompt dans le presse-papiers
  const copyPromptExample = (text: string) => {
    navigator.clipboard.writeText(text)
      .then(() => {
        // Afficher la notification toast
        setToastMessage(getTranslation('promptCopied'))
        setShowToast(true)
        
        // Masquer après 3 secondes
        setTimeout(() => {
          setShowToast(false)
        }, 3000)
      })
      .catch(err => {
        console.error('Erreur lors de la copie: ', err)
        // Notification d'erreur
        setToastMessage(getTranslation('copyError'))
        setShowToast(true)
        setTimeout(() => {
          setShowToast(false)
        }, 3000)
      })
  }

  // Fonction pour filtrer les prompts en fonction de la recherche et de la catégorie
  const filterPrompts = () => {
    if (!helpContent?.predefinedPrompts) return;
    
    let filtered = helpContent.predefinedPrompts;
    
    // Filtrer par catégorie si une catégorie est sélectionnée
    if (selectedCategory) {
      filtered = filtered.filter(prompt => prompt.categories.includes(selectedCategory));
    }
    
    // Filtrer par recherche si une recherche est effectuée
    if (searchQuery.trim() !== '') {
      const lowerCaseQuery = searchQuery.toLowerCase();
      filtered = filtered.filter(prompt => {
        const title = prompt.title[currentLanguage].toLowerCase();
        const description = prompt.description[currentLanguage].toLowerCase();
        const promptText = prompt.prompt[currentLanguage].toLowerCase();
        
        return (
          title.includes(lowerCaseQuery) || 
          description.includes(lowerCaseQuery) || 
          promptText.includes(lowerCaseQuery)
        );
      });
    }
    
    setFilteredPrompts(filtered);
  }

  // Fonction pour faire défiler vers une section du guide
  const scrollToGuideSection = (sectionId: string) => {
    setSelectedGuideSection(sectionId);
    
    const sectionRef = guideSectionRefs.current[sectionId];
    if (sectionRef && sectionRef.current) {
      sectionRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Mettre à jour les filtres lorsque la recherche ou la catégorie change
  useEffect(() => {
    filterPrompts();
  }, [searchQuery, selectedCategory, helpContent]);

  useEffect(() => {
    // Définir l'animation d'apparition après montage du composant
    setTimeout(() => {
      setIsVisible(true)
    }, 50)
    
    // Déterminer la langue en fonction du contexte de l'application
    const userLang = appStateContext?.state.userLanguage || 'FR';
    setCurrentLanguage(userLang);
    
    // Ajouter l'écouteur pour la touche Escape
    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleCloseHelp()
      }
    }
    
    document.addEventListener('keydown', handleEscapeKey)
    
    // Nettoyage lors du démontage
    return () => {
      document.removeEventListener('keydown', handleEscapeKey)
    }
  }, [appStateContext?.state.userLanguage])

  // Rendu des badges de catégories pour un prompt
  const renderCategoryBadges = (categories: string[]) => {
    if (!helpContent) return null;
    
    // Trouver les objets de catégorie correspondants
    const categoryObjects = categories.map(categoryKey => 
      helpContent.categories.find(cat => cat.key === categoryKey)
    ).filter(Boolean) as Category[];
    
    return (
      <div className={styles.categoryBadgesContainer}>
        {categoryObjects.map((category, index) => (
          <span key={index} className={styles.promptCardCategory}>
            <Icon iconName={category.icon} className={styles.promptCardCategoryIcon} />
            {category.name[currentLanguage]}
          </span>
        ))}
      </div>
    );
  };

  // Rendu d'un élément de prompt
  const renderPromptItem = (item?: PredefinedPrompt) => {
    if (!item || !helpContent) return null;
    
    return (
      <div className={styles.promptCard} onClick={() => copyPromptExample(item.prompt[currentLanguage])}>
        <div className={styles.promptCardHeader}>
          <Icon 
            iconName={
              helpContent.categories.find(cat => cat.key === item.categories[0])?.icon || 'Tag'
            } 
            className={styles.promptCardIcon} 
          />
          <div className={styles.promptCardTitle}>{item.title[currentLanguage]}</div>
        </div>
        <div className={styles.promptCardDescription}>{item.description[currentLanguage]}</div>
        <div className={styles.promptCardPrompt}>
          <div className={styles.promptLabel}>{getTranslation('promptLabel')}</div>
          <div className={styles.promptText}>
            <Icon iconName="Copy" className={styles.copyIcon} />
            {item.prompt[currentLanguage]}
          </div>
        </div>
        {renderCategoryBadges(item.categories)}
      </div>
    );
  };

  // Rendu d'une section du guide
  const renderGuideSection = (section: GuideSection) => {
    return (
      <div 
        key={section.id} 
        ref={guideSectionRefs.current[section.id]}
        className={styles.sectionContainer}
        id={`guide-section-${section.id}`}
      >
        <h3 className={styles.sectionTitle}>
          <Icon iconName={section.icon} />
          {section.title[currentLanguage]}
        </h3>
        
        <div className={styles.markdownContent}>
          <ReactMarkdown
            children={section.content[currentLanguage]}
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({node, ...props}) => <p className={styles.markdownParagraph} {...props} />,
              ul: ({node, ...props}) => <ul className={styles.markdownList} {...props} />,
              ol: ({node, ...props}) => <ol className={styles.markdownList} {...props} />,
              li: ({node, ...props}) => <li className={styles.markdownListItem} {...props} />,
              strong: ({node, ...props}) => <strong className={styles.markdownBold} {...props} />
            }}
          />
        </div>
      </div>
    );
  };

  // Afficher un spinner pendant le chargement
  if (isLoading) {
    return (
      <div className={`${styles.container} ${isVisible ? styles.visible : ''}`}>
        <div className={styles.helpHeader}>
          <h2 className={styles.helpTitle}>
            <Icon iconName="Lifesaver" className={styles.titleIcon} />
            Chargement...
          </h2>
          <button 
            className={styles.closeButton} 
            onClick={handleCloseHelp}
            aria-label="Fermer"
          >
            <Icon iconName="Cancel" />
          </button>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '70vh' }}>
          <Spinner size={SpinnerSize.large} label="Chargement du contenu d'aide..." />
        </div>
      </div>
    );
  }

  // Afficher un message d'erreur si le chargement a échoué
  if (error) {
    return (
      <div className={`${styles.container} ${isVisible ? styles.visible : ''}`}>
        <div className={styles.helpHeader}>
          <h2 className={styles.helpTitle}>
            <Icon iconName="Error" className={styles.titleIcon} style={{ color: '#d13438' }} />
            Erreur
          </h2>
          <button 
            className={styles.closeButton} 
            onClick={handleCloseHelp}
            aria-label="Fermer"
          >
            <Icon iconName="Cancel" />
          </button>
        </div>
        <div style={{ padding: '20px' }}>
          <MessageBar
            messageBarType={MessageBarType.error}
            isMultiline={true}
          >
            Une erreur s'est produite lors du chargement du contenu d'aide: {error}
            <br/>
            Veuillez réessayer plus tard ou contacter votre administrateur.
          </MessageBar>
        </div>
      </div>
    );
  }

  // Si aucun contenu d'aide n'est disponible
  if (!helpContent) {
    return (
      <div className={`${styles.container} ${isVisible ? styles.visible : ''}`}>
        <div className={styles.helpHeader}>
          <h2 className={styles.helpTitle}>
            <Icon iconName="Lifesaver" className={styles.titleIcon} />
            Centre d'aide
          </h2>
          <button 
            className={styles.closeButton} 
            onClick={handleCloseHelp}
            aria-label="Fermer"
          >
            <Icon iconName="Cancel" />
          </button>
        </div>
        <div style={{ padding: '20px' }}>
          <MessageBar
            messageBarType={MessageBarType.warning}
            isMultiline={true}
          >
            Aucun contenu d'aide n'est disponible pour le moment.
          </MessageBar>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Overlay semi-transparent */}
      <div 
        className={`${styles.overlay} ${isVisible ? styles.overlayVisible : ''}`}
        onClick={handleOverlayClick}
        aria-hidden="true"
      />
      
      {/* Panneau d'aide */}
      <div 
        ref={panelRef}
        className={`${styles.container} ${isVisible ? styles.visible : ''}`} 
        aria-label="panneau d'aide"
      >
        {/* Toast de notification */}
        {showToast && (
          <div className={styles.toastContainer}>
            <MessageBar
              className={styles.toast}
              messageBarType={MessageBarType.success}
              isMultiline={false}
              onDismiss={() => setShowToast(false)}
              dismissButtonAriaLabel={getTranslation('dismiss')}
            >
              {toastMessage}
            </MessageBar>
          </div>
        )}
        
        <div className={styles.helpHeader}>
          <h2 className={styles.helpTitle}>
            <Icon iconName="Lifesaver" className={styles.titleIcon} />
            {getTranslation('helpPanelTitle')}
          </h2>
          <button 
            className={styles.closeButton} 
            onClick={handleCloseHelp}
            aria-label={getTranslation('hide')}
          >
            <Icon iconName="Cancel" />
          </button>
        </div>
        
        <div className={styles.helpContent}>
          {/* Système d'onglets */}
          <Pivot aria-label="Options d'aide">

            <PivotItem 
              headerText={getTranslation('promptsTab')} 
              headerButtonProps={{
                'data-order': 1,
                'data-title': 'Requests'
              }}
              itemIcon="BulletedList"
            >
              <div className={styles.tabContent}>
                <div className={styles.promptsHeader}>
                  <h3 className={styles.promptsTitle}>{getTranslation('promptsTabTitle')}</h3>
                  
                  {/* Barre de recherche */}
                  <div className={styles.searchContainer}>
                    <SearchBox 
                      placeholder={getTranslation('searchPrompts')} 
                      onChange={(_, newValue) => setSearchQuery(newValue || '')}
                      className={styles.searchBox}
                      iconProps={{ iconName: 'Search' }}
                    />
                  </div>
                </div>
                
                {/* Filtres par catégorie */}
                <div className={styles.categoryFilters}>
                  <button 
                    className={`${styles.categoryButton} ${selectedCategory === null ? styles.categoryButtonActive : ''}`}
                    onClick={() => setSelectedCategory(null)}
                  >
                    <Icon iconName="AllApps" className={styles.categoryButtonIcon} />
                    {getTranslation('allCategories')}
                  </button>
                  
                  {helpContent.categories.map(category => (
                    <button 
                      key={category.key}
                      className={`${styles.categoryButton} ${selectedCategory === category.key ? styles.categoryButtonActive : ''}`}
                      onClick={() => setSelectedCategory(category.key)}
                    >
                      <Icon iconName={category.icon} className={styles.categoryButtonIcon} />
                      {category.name[currentLanguage]}
                    </button>
                  ))}
                </div>
                
                {/* Liste des prompts */}
                <div className={styles.promptsList}>
                  {filteredPrompts.length === 0 ? (
                    <div className={styles.noResults}>
                      <Icon iconName="SearchIssue" className={styles.noResultsIcon} />
                      <div className={styles.noResultsText}>
                        {getTranslation('noPromptResults')}
                      </div>
                    </div>
                  ) : (
                    <FocusZone>
                      <List
                        items={filteredPrompts}
                        onRenderCell={renderPromptItem}
                      />
                    </FocusZone>
                  )}
                </div>
              </div>
            </PivotItem>
            
            <PivotItem 
              headerText={getTranslation('guideTab')} 
              headerButtonProps={{
                'data-order': 2,
                'data-title': 'Guide'
              }}
              itemIcon="ReadingMode"
            >
              <div className={styles.tabContent}>
                {/* Navigation du guide */}
                <div className={styles.guideNavigation}>
                  {helpContent.guideContent.map(section => (
                    <button
                      key={section.id}
                      className={`${styles.guideNavButton} ${selectedGuideSection === section.id ? styles.guideNavButtonActive : ''}`}
                      onClick={() => scrollToGuideSection(section.id)}
                    >
                      <Icon iconName={section.icon} className={styles.guideNavButtonIcon} />
                      {section.title[currentLanguage]}
                    </button>
                  ))}
                </div>
                
                {/* Contenu du guide */}
                <div style={{ overflow: 'auto' }}>
                  {helpContent.guideContent.map(section => renderGuideSection(section))}
                </div>
              </div>
            </PivotItem>
            
          </Pivot>
        </div>
      </div>
    </>
  )
}