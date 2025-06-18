#!/usr/bin/env python3
"""
Runner de tests pour l'application AskMe avec support multi-LLM.

Ce script permet d'exécuter différents types de tests :
- Tests unitaires
- Tests d'intégration  
- Tests fonctionnels

Il supporte également la sélection de LLM spécifiques et différents niveaux de tests.

Usage:
    python tests/run_test.py --help
    python tests/run_test.py --type functional --llm AZURE_OPENAI
    python tests/run_test.py --type all --llm-skip GEMINI
    python tests/run_test.py --type functional --markers language,search
"""

import argparse
import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Répertoire racine du projet
ROOT_DIR = Path(__file__).parent.parent
TESTS_DIR = ROOT_DIR / "tests"
TEST_ENV_DIR = ROOT_DIR / "test_env"

# LLM supportés
SUPPORTED_LLMS = ["AZURE_OPENAI", "CLAUDE", "OPENAI_DIRECT", "MISTRAL", "GEMINI"]

# Types de tests disponibles
TEST_TYPES = {
    "unit": "tests/unit_tests",
    "integration": "tests/integration_tests", 
    "functional": "tests/functional_tests",
    "e2e": "tests/e2e",
    "all": "tests"
}

# Markers de tests fonctionnels
FUNCTIONAL_MARKERS = {
    "language": "Tests de langue et localisation",
    "search": "Tests Azure AI Search avec citations", 
    "response_length": "Tests de longueur de réponse",
    "document_count": "Tests de nombre de documents",
    "image": "Tests d'analyse d'images",
    "e2e": "Tests End-to-End avec Playwright",
    "e2e_image": "Tests E2E pour upload d'images",
    "e2e_chat": "Tests E2E pour interactions chat",
    "e2e_slow": "Tests E2E lents",
    "slow": "Tests lents (peuvent prendre du temps)"
}


class TestRunner:
    """Gestionnaire d'exécution des tests."""
    
    def __init__(self):
        self.root_dir = ROOT_DIR
        self.test_env_dir = TEST_ENV_DIR
        self.python_exe = self._get_python_executable()
    
    def _get_python_executable(self) -> str:
        """Obtenir l'exécutable Python du virtual environment."""
        if os.name == 'nt':  # Windows
            python_exe = self.test_env_dir / "Scripts" / "python.exe"
        else:  # Unix/Linux
            python_exe = self.test_env_dir / "bin" / "python"
        
        if python_exe.exists():
            return str(python_exe)
        else:
            logger.warning(f"Virtual environment not found at {self.test_env_dir}")
            return sys.executable
    
    def setup_test_environment(self) -> bool:
        """Configurer l'environnement de test."""
        logger.info("Configuration de l'environnement de test...")
        
        # Créer le virtual environment s'il n'existe pas
        if not self.test_env_dir.exists():
            logger.info("Création du virtual environment...")
            result = subprocess.run([
                sys.executable, "-m", "venv", str(self.test_env_dir)
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Erreur lors de la création du venv: {result.stderr}")
                return False
        
        # Installer les dépendances de test
        logger.info("Installation des dépendances de test...")
        pip_exe = self.test_env_dir / ("Scripts/pip.exe" if os.name == 'nt' else "bin/pip")
        
        # Installer d'abord les packages problématiques avec wheels
        problematic_packages = ["tiktoken"]
        for package in problematic_packages:
            logger.info(f"Installation de {package} avec wheel précompilé...")
            result = subprocess.run([
                str(pip_exe), "install", package, "--only-binary=all"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"Échec installation {package} avec wheel, on continue...")
        
        # Installer les requirements principaux
        requirements_files = [
            self.root_dir / "requirements.txt",
            self.root_dir / "requirements-dev.txt"
        ]
        
        for req_file in requirements_files:
            if req_file.exists():
                logger.info(f"Installation des dépendances depuis {req_file.name}...")
                result = subprocess.run([
                    str(pip_exe), "install", "-r", str(req_file), "--only-binary=all"
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    # Essayer sans --only-binary si ça échoue
                    logger.warning(f"Échec avec --only-binary, essai sans restriction...")
                    result = subprocess.run([
                        str(pip_exe), "install", "-r", str(req_file)
                    ], capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        logger.error(f"Erreur lors de l'installation de {req_file}: {result.stderr}")
                        return False
        
        # Installer pytest et dépendances de test si pas déjà installées
        test_packages = ["pytest", "pytest-asyncio", "pytest-html", "pytest-cov"]
        result = subprocess.run([
            str(pip_exe), "install"
        ] + test_packages, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Erreur lors de l'installation des packages de test: {result.stderr}")
            return False
        
        logger.info("✓ Environnement de test configuré")
        return True
    
    def run_tests(self, 
                  test_type: str = "all",
                  llm_providers: Optional[List[str]] = None,
                  llm_skip: Optional[List[str]] = None,
                  markers: Optional[List[str]] = None,
                  verbose: bool = False,
                  coverage: bool = False,
                  html_report: bool = False,
                  exit_on_fail: bool = False,
                  skip_e2e: bool = False,
                  no_service_check: bool = False) -> bool:
        """
        Exécuter les tests selon les paramètres spécifiés.
        
        Args:
            test_type: Type de tests à exécuter ("unit", "integration", "functional", "all")
            llm_providers: Liste des LLM à tester (None = tous)
            llm_skip: Liste des LLM à ignorer
            markers: Liste des markers pytest à utiliser
            verbose: Mode verbose
            coverage: Générer un rapport de couverture
            html_report: Générer un rapport HTML
            exit_on_fail: Arrêter sur le premier échec
        
        Returns:
            True si tous les tests passent, False sinon
        """
        logger.info(f"Exécution des tests {test_type}...")
        
        # Construire la commande pytest
        pytest_cmd = [self.python_exe, "-m", "pytest"]
        
        # Répertoire de tests
        if test_type in TEST_TYPES:
            test_dir = self.root_dir / TEST_TYPES[test_type]
            pytest_cmd.append(str(test_dir))
        else:
            logger.error(f"Type de test inconnu: {test_type}")
            return False
        
        # Options de verbosité
        if verbose:
            pytest_cmd.extend(["-v", "-s"])
        
        # Arrêt sur échec
        if exit_on_fail:
            pytest_cmd.append("-x")
        
        # Markers
        if markers:
            for marker in markers:
                pytest_cmd.extend(["-m", marker])
        
        # Filtrage par LLM
        # Construire les filtres
        filter_parts = []
        
        # Filtrage par LLM (par nom de test)
        if llm_providers:
            # Chercher les tests qui contiennent le nom du provider
            provider_filter = " or ".join([llm for llm in llm_providers])
            filter_parts.append(f"({provider_filter})")
        elif llm_skip:
            # Exclure les tests qui contiennent le nom du provider
            skip_filter = " and ".join([f"not {llm}" for llm in llm_skip])
            filter_parts.append(skip_filter)
        
        # Filtrage E2E
        if skip_e2e:
            filter_parts.append("not e2e")
        
        # Appliquer les filtres
        if filter_parts:
            combined_filter = " and ".join([f"({part})" for part in filter_parts])
            pytest_cmd.extend(["-k", combined_filter])
        
        # Couverture de code
        if coverage:
            pytest_cmd.extend([
                "--cov=backend",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov"
            ])
        
        # Rapport HTML enrichi
        if html_report:
            reports_dir = self.root_dir / "tests" / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            pytest_cmd.extend([
                "--html=tests/reports/report.html",
                "--self-contained-html",
                "--capture=no",  # Capture tous les logs
                "--tb=long"      # Tracebacks longs
            ])
        
        # Variables d'environnement pour les tests
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.root_dir)
        # Activer logging détaillé pour les rapports
        env["PYTEST_CURRENT_TEST"] = "true"
        
        # Configuration pour les tests E2E
        if skip_e2e:
            env["SKIP_E2E"] = "true"
        if no_service_check:
            env["E2E_CHECK_SERVICES"] = "false"
        
        # Exécuter pytest
        logger.info(f"Commande: {' '.join(pytest_cmd)}")
        result = subprocess.run(pytest_cmd, cwd=self.root_dir, env=env)
        
        success = result.returncode == 0
        if success:
            logger.info("✓ Tous les tests sont passés")
        else:
            logger.error("✗ Certains tests ont échoué")
        
        return success
    
    def list_available_tests(self):
        """Lister les tests disponibles."""
        logger.info("Tests disponibles:")
        
        for test_type, path in TEST_TYPES.items():
            logger.info(f"\n{test_type.upper()}:")
            test_path = self.root_dir / path
            if test_path.exists():
                for test_file in test_path.rglob("test_*.py"):
                    relative_path = test_file.relative_to(self.root_dir)
                    logger.info(f"  {relative_path}")
        
        logger.info(f"\nLLM supportés: {', '.join(SUPPORTED_LLMS)}")
        logger.info(f"\nMarkers fonctionnels disponibles:")
        for marker, description in FUNCTIONAL_MARKERS.items():
            logger.info(f"  {marker}: {description}")


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Runner de tests pour l'application AskMe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  python tests/run_test.py --type functional --llm AZURE_OPENAI
  python tests/run_test.py --type all --llm-skip GEMINI
  python tests/run_test.py --type functional --markers language,search
  python tests/run_test.py --list
  python tests/run_test.py --setup-only
        """
    )
    
    parser.add_argument(
        "--type", 
        choices=list(TEST_TYPES.keys()), 
        default="all",
        help="Type de tests à exécuter (default: all)"
    )
    
    parser.add_argument(
        "--llm",
        choices=SUPPORTED_LLMS,
        action="append",
        help="LLM spécifique à tester (peut être répété)"
    )
    
    parser.add_argument(
        "--llm-skip",
        choices=SUPPORTED_LLMS,
        action="append", 
        help="LLM à ignorer (peut être répété)"
    )
    
    parser.add_argument(
        "--markers",
        help="Markers pytest séparés par des virgules (ex: language,search)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mode verbose"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Générer un rapport de couverture"
    )
    
    parser.add_argument(
        "--html-report",
        action="store_true",
        help="Générer un rapport HTML"
    )
    
    parser.add_argument(
        "--exit-on-fail", "-x",
        action="store_true",
        help="Arrêter sur le premier échec"
    )
    
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Seulement configurer l'environnement de test"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lister les tests disponibles"
    )
    
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Skipper les tests E2E (End-to-End)"
    )
    
    parser.add_argument(
        "--no-service-check",
        action="store_true",
        help="Ne pas vérifier la disponibilité des services pour les tests E2E"
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Lister les tests disponibles
    if args.list:
        runner.list_available_tests()
        return 0
    
    # Configurer l'environnement
    if not runner.setup_test_environment():
        logger.error("Échec de la configuration de l'environnement de test")
        return 1
    
    # Si setup seulement
    if args.setup_only:
        logger.info("Environnement de test configuré avec succès")
        return 0
    
    # Valider les arguments
    if args.llm and args.llm_skip:
        llm_conflict = set(args.llm).intersection(set(args.llm_skip))
        if llm_conflict:
            logger.error(f"Conflit: LLM spécifiés à la fois dans --llm et --llm-skip: {llm_conflict}")
            return 1
    
    # Parser les markers
    markers = None
    if args.markers:
        markers = [m.strip() for m in args.markers.split(",")]
        # Valider les markers pour les tests fonctionnels
        if args.type == "functional":
            invalid_markers = set(markers) - set(FUNCTIONAL_MARKERS.keys())
            if invalid_markers:
                logger.error(f"Markers invalides pour les tests fonctionnels: {invalid_markers}")
                logger.error(f"Markers disponibles: {list(FUNCTIONAL_MARKERS.keys())}")
                return 1
    
    # Exécuter les tests
    success = runner.run_tests(
        test_type=args.type,
        llm_providers=args.llm,
        llm_skip=args.llm_skip,
        markers=markers,
        verbose=args.verbose,
        coverage=args.coverage,
        html_report=args.html_report,
        exit_on_fail=args.exit_on_fail,
        skip_e2e=args.skip_e2e,
        no_service_check=args.no_service_check
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())