#!/usr/bin/env python3
"""
Script de test rapide pour Claude uniquement (sans E2E).

Ce script lance tous les tests fonctionnels avec le provider Claude seulement,
génère un rapport HTML détaillé avec toutes les métriques enrichies.

Usage:
    python tests/test_claude_only.py
    python tests/test_claude_only.py --verbose
    python tests/test_claude_only.py --exit-on-fail
"""
import sys
import os
import subprocess
from pathlib import Path

def main():
    """Lancer les tests Claude uniquement."""
    
    # Configuration
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent
    test_env = root_dir / "test_env"
    python_exe = test_env / "bin" / "python"
    
    if os.name == 'nt':  # Windows
        python_exe = test_env / "Scripts" / "python.exe"
    
    # Arguments par défaut
    verbose = "--verbose" if "--verbose" in sys.argv or "-v" in sys.argv else ""
    exit_on_fail = "--exit-on-fail" if "--exit-on-fail" in sys.argv or "-x" in sys.argv else ""
    
    # Commande de test optimisée pour Claude
    cmd = [
        str(python_exe),
        "tests/run_test.py",
        "--type", "functional",        # Tests fonctionnels seulement
        "--llm", "CLAUDE",            # Claude uniquement
        "--skip-e2e",                 # Pas de tests E2E
        "--html-report",              # Rapport HTML enrichi
    ]
    
    # Ajouter les options
    if verbose:
        cmd.append("--verbose")
    if exit_on_fail:
        cmd.append("--exit-on-fail")
    
    # Informations d'exécution
    print("🚀 " + "="*60)
    print("🧠 Tests AskMe - CLAUDE Provider Uniquement")
    print("📊 Rapport détaillé avec métriques enrichies")
    print("⚡ Sans tests E2E (rapide)")
    print("="*64)
    print()
    print(f"🎯 Provider testé: CLAUDE")
    print(f"📁 Tests: Fonctionnels (language, search, response_length, document_count, image)")
    print(f"📈 Rapport HTML: tests/reports/report.html")
    print(f"🔧 Mode verbose: {'✅' if verbose else '❌'}")
    print(f"🛑 Arrêt sur échec: {'✅' if exit_on_fail else '❌'}")
    print()
    print("⏳ Démarrage des tests...")
    print("-" * 64)
    
    # Variables d'environnement
    env = os.environ.copy()
    env["SKIP_E2E"] = "true"
    env["PYTEST_CURRENT_TEST"] = "true"
    
    # Exécuter la commande
    try:
        result = subprocess.run(
            cmd, 
            cwd=root_dir,
            env=env,
            text=True
        )
        
        print()
        print("="*64)
        
        if result.returncode == 0:
            print("✅ SUCCÈS - Tous les tests Claude ont réussi !")
            print()
            print("📊 Rapport HTML disponible:")
            print(f"   📁 {root_dir}/tests/reports/report.html")
            print()
            print("🔍 Métriques disponibles dans le rapport:")
            print("   • Questions posées → Réponses obtenues")
            print("   • Longueurs mesurées (short/medium/long)")
            print("   • Nombres de documents (2/6/12) → Citations")
            print("   • Descriptions d'images complètes")
            print("   • Validations avec termes trouvés")
            
        else:
            print("❌ ÉCHEC - Certains tests ont échoué")
            print()
            print("🔍 Vérifiez le rapport HTML pour les détails:")
            print(f"   📁 {root_dir}/tests/reports/report.html")
            print()
            print("💡 Solutions possibles:")
            print("   • Vérifiez la configuration CLAUDE dans .env")
            print("   • Vérifiez la clé API CLAUDE")
            print("   • Lancez avec --exit-on-fail pour plus de détails")
        
        print("="*64)
        return result.returncode
        
    except KeyboardInterrupt:
        print()
        print("🛑 Tests interrompus par l'utilisateur")
        return 1
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())