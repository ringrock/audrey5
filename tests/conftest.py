"""
Configuration pytest pour tous les tests.

Ce module configure les fixtures communes pour :
- Logging détaillé
- Configuration LLM providers  
- Setup des tests fonctionnels et E2E
- Variables d'environnement de test
"""
import pytest
import logging
import sys
import os
from pathlib import Path

# Créer le répertoire de rapports si nécessaire
reports_dir = Path("tests/reports")
reports_dir.mkdir(exist_ok=True)

# Configuration du logging pour captures dans les rapports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(reports_dir / 'test.log', mode='w')
    ]
)

def pytest_configure(config):
    """Configuration globale pytest."""
    # Créer le répertoire de rapports
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(exist_ok=True)
    
    # Configurer le logging pour pytest-html
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

def pytest_html_report_title(report):
    """Titre personnalisé pour le rapport HTML."""
    report.title = "Rapport de Tests AskMe - Multi-LLM"

def pytest_html_results_summary(prefix, summary, postfix):
    """Résumé personnalisé pour le rapport HTML."""
    prefix.extend([
        "<h2>Tests fonctionnels AskMe avec support multi-LLM</h2>",
        "<p>Ce rapport contient les détails complets des tests incluant :</p>",
        "<ul>",
        "<li>Questions posées et réponses obtenues</li>",
        "<li>Métriques de longueur (short/medium/long)</li>", 
        "<li>Nombres de documents testés (2/6/12)</li>",
        "<li>Descriptions détaillées des images analysées</li>",
        "<li>Validations des citations Azure AI Search</li>",
        "<li>Tests End-to-End complets avec Playwright</li>",
        "</ul>"
    ])

def pytest_runtest_logstart(nodeid, location):
    """Log au début de chaque test."""
    logging.info(f"\n{'='*80}")
    logging.info(f"DÉBUT DU TEST: {nodeid}")
    logging.info(f"Localisation: {location}")
    logging.info(f"{'='*80}")

def pytest_runtest_logfinish(nodeid, location):
    """Log à la fin de chaque test."""
    logging.info(f"{'='*80}")
    logging.info(f"FIN DU TEST: {nodeid}")
    logging.info(f"{'='*80}\n")

def pytest_addoption(parser):
    parser.addoption(
        "--use-keyvault-secrets",
        help='Get secrets from a keyvault instead of the environment.',
        action='store_true', default=False
    )

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup global pour tous les tests."""
    # Configurer l'environnement de test
    os.environ["TESTING"] = "true"
    os.environ["LOG_LEVEL"] = "INFO"
    
    # S'assurer que le répertoire de logs existe
    log_dir = Path("tests/reports")
    log_dir.mkdir(exist_ok=True)
    
    yield
    
    # Cleanup si nécessaire
    logging.info("Nettoyage de l'environnement de test terminé")

@pytest.fixture(scope="session")
def use_keyvault_secrets(request) -> str:
    return request.config.getoption("use_keyvault_secrets")

# Import des fixtures spécifiques depuis les modules de tests
try:
    from tests.functional_tests.conftest import *
except ImportError:
    pass

try:
    from tests.e2e.conftest import *
except ImportError:
    pass