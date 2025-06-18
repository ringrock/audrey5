#!/bin/bash
# Script Linux/Mac pour tester Claude uniquement (sans E2E)
#
# Usage:
#   bash tests/test_claude_only.sh
#   bash tests/test_claude_only.sh verbose
#   bash tests/test_claude_only.sh exit-on-fail

echo
echo "================================================================="
echo "🧠 Tests AskMe - CLAUDE Provider Uniquement"
echo "📊 Rapport détaillé avec métriques enrichies"  
echo "⚡ Sans tests E2E (rapide)"
echo "================================================================="
echo

# Variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_EXE="$ROOT_DIR/test_env/bin/python"
VERBOSE=""
EXIT_ON_FAIL=""

# Traiter les arguments
if [[ "$1" == "verbose" ]] || [[ "$2" == "verbose" ]]; then
    VERBOSE="--verbose"
fi

if [[ "$1" == "exit-on-fail" ]] || [[ "$2" == "exit-on-fail" ]]; then
    EXIT_ON_FAIL="--exit-on-fail"
fi

echo "🎯 Provider testé: CLAUDE"
echo "📁 Tests: Fonctionnels (language, search, response_length, document_count, image)"
echo "📈 Rapport HTML: tests/reports/report.html"
if [[ -n "$VERBOSE" ]]; then
    echo "🔧 Mode verbose: ✅"
else
    echo "🔧 Mode verbose: ❌"
fi
if [[ -n "$EXIT_ON_FAIL" ]]; then
    echo "🛑 Arrêt sur échec: ✅"
else
    echo "🛑 Arrêt sur échec: ❌"
fi
echo
echo "⏳ Démarrage des tests..."
echo "-----------------------------------------------------------------"

# Variables d'environnement
export SKIP_E2E=true
export PYTEST_CURRENT_TEST=true

# Exécuter les tests
cd "$ROOT_DIR"
"$PYTHON_EXE" tests/run_test.py --type functional --llm CLAUDE --skip-e2e --html-report $VERBOSE $EXIT_ON_FAIL
RESULT=$?

# Vérifier le résultat
echo
echo "================================================================="
if [[ $RESULT -eq 0 ]]; then
    echo "✅ SUCCÈS - Tous les tests Claude ont réussi !"
    echo
    echo "📊 Rapport HTML disponible:"
    echo "   📁 $ROOT_DIR/tests/reports/report.html"
    echo
    echo "🔍 Métriques disponibles dans le rapport:"
    echo "   • Questions posées → Réponses obtenues"
    echo "   • Longueurs mesurées (short/medium/long)"
    echo "   • Nombres de documents (2/6/12) → Citations"
    echo "   • Descriptions d'images complètes"
    echo "   • Validations avec termes trouvés"
else
    echo "❌ ÉCHEC - Certains tests ont échoué"
    echo
    echo "🔍 Vérifiez le rapport HTML pour les détails:"
    echo "   📁 $ROOT_DIR/tests/reports/report.html"
    echo
    echo "💡 Solutions possibles:"
    echo "   • Vérifiez la configuration CLAUDE dans .env"
    echo "   • Vérifiez la clé API CLAUDE"
    echo "   • Lancez avec exit-on-fail pour plus de détails"
fi
echo "================================================================="

exit $RESULT