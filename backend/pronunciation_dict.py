"""
Dictionnaire de prononciation pour la synthèse vocale
"""

# Dictionnaire des corrections de prononciation
# Format: "mot_original": "prononciation_phonétique"
PRONUNCIATION_DICT = {
    # Noms de société et produits
    "Avanteam": "avantime",
    "AskMe": "askmi", 
    "QualitySaaS": "quality sasse",
    "QualitySaas": "quality sasse",  # Variation de casse
    "qualitysaas": "quality sasse",  # Minuscules
    
    # Termes techniques courants (exemples)
    "SaaS": "sasse",
    "API": "A P I",
    "URL": "U R L",
    "HTTP": "H T T P",
    "HTTPS": "H T T P S",
    "SQL": "S Q L",
    "JSON": "jason",
    "XML": "X M L",
    "CSS": "C S S",
    "HTML": "H T M L",
    
    # Autres mots spécifiques à votre domaine
    # Ajoutez ici vos propres corrections...
}

def apply_pronunciation_corrections(text: str) -> str:
    """
    Applique les corrections de prononciation au texte
    
    Args:
        text: Texte à corriger
        
    Returns:
        Texte avec les corrections de prononciation appliquées
    """
    import re
    
    # Appliquer chaque correction du dictionnaire
    for original, phonetic in PRONUNCIATION_DICT.items():
        # Utiliser une regex pour remplacer le mot en respectant les limites de mots
        # \b assure qu'on remplace uniquement les mots complets
        pattern = r'\b' + re.escape(original) + r'\b'
        text = re.sub(pattern, phonetic, text, flags=re.IGNORECASE)
    
    return text


def add_pronunciation(original: str, phonetic: str) -> None:
    """
    Ajoute une nouvelle correction de prononciation
    
    Args:
        original: Mot original
        phonetic: Prononciation phonétique
    """
    PRONUNCIATION_DICT[original] = phonetic


def remove_pronunciation(original: str) -> bool:
    """
    Supprime une correction de prononciation
    
    Args:
        original: Mot original à supprimer
        
    Returns:
        True si supprimé, False si le mot n'existait pas
    """
    if original in PRONUNCIATION_DICT:
        del PRONUNCIATION_DICT[original]
        return True
    return False


def get_pronunciation_dict() -> dict:
    """
    Retourne le dictionnaire complet des prononciations
    
    Returns:
        Dictionnaire des corrections de prononciation
    """
    return PRONUNCIATION_DICT.copy()


def load_pronunciation_from_file(file_path: str) -> None:
    """
    Charge les prononciations depuis un fichier JSON
    
    Args:
        file_path: Chemin vers le fichier JSON
    """
    import json
    import os
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                custom_dict = json.load(f)
                PRONUNCIATION_DICT.update(custom_dict)
        except Exception as e:
            print(f"Erreur lors du chargement du fichier de prononciation: {e}")


def save_pronunciation_to_file(file_path: str) -> None:
    """
    Sauvegarde les prononciations dans un fichier JSON
    
    Args:
        file_path: Chemin vers le fichier JSON
    """
    import json
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(PRONUNCIATION_DICT, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erreur lors de la sauvegarde du fichier de prononciation: {e}")