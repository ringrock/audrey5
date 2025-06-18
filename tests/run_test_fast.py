#!/usr/bin/env python3
"""
Runner de tests rapide pour l'application AskMe (sans E2E).

Ce script exécute seulement les tests fonctionnels et unitaires pour 
un développement rapide et des rapports détaillés.
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.run_test import TestRunner, SUPPORTED_LLMS, FUNCTIONAL_MARKERS

def main():
    """Point d'entrée pour tests rapides."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Runner de tests rapide AskMe (sans E2E)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation rapide:
  python tests/run_test_fast.py --llm CLAUDE
  python tests/run_test_fast.py --markers language,search
  python tests/run_test_fast.py --html-report --verbose
        """
    )
    
    parser.add_argument(
        "--llm",
        choices=SUPPORTED_LLMS,
        action="append",
        help="LLM spécifique à tester (peut être répété)"
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
        "--html-report",
        action="store_true",
        help="Générer un rapport HTML enrichi"
    )
    
    parser.add_argument(
        "--exit-on-fail", "-x",
        action="store_true",
        help="Arrêter sur le premier échec"
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Configurer l'environnement
    if not runner.setup_test_environment():
        print("❌ Échec de la configuration de l'environnement de test")
        return 1
    
    # Parser les markers
    markers = None
    if args.markers:
        markers = [m.strip() for m in args.markers.split(",")]
    
    print("🚀 Exécution des tests RAPIDES (fonctionnels + unitaires seulement)")
    print(f"🎯 LLM: {args.llm or 'TOUS'}")
    print(f"🏷️  Markers: {markers or 'TOUS'}")
    
    # Exécuter les tests fonctionnels SANS E2E
    success = runner.run_tests(
        test_type="functional",
        llm_providers=args.llm,
        markers=markers,
        verbose=args.verbose,
        html_report=args.html_report,
        exit_on_fail=args.exit_on_fail
    )
    
    if success:
        print("✅ Tous les tests rapides ont réussi !")
        if args.html_report:
            print("📊 Rapport HTML disponible: tests/reports/report.html")
    else:
        print("❌ Certains tests ont échoué")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())