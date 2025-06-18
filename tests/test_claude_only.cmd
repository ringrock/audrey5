@echo off
REM Script Windows pour tester Claude uniquement (sans E2E)
REM 
REM Usage:
REM   tests\test_claude_only.cmd
REM   tests\test_claude_only.cmd verbose
REM   tests\test_claude_only.cmd exit-on-fail

echo.
echo =================================================================
echo 🧠 Tests AskMe - CLAUDE Provider Uniquement
echo 📊 Rapport détaillé avec métriques enrichies  
echo ⚡ Sans tests E2E (rapide)
echo =================================================================
echo.

REM Définir les variables
set ROOT_DIR=%~dp0..
set PYTHON_EXE=%ROOT_DIR%\test_env\Scripts\python.exe
set VERBOSE=
set EXIT_ON_FAIL=

REM Traiter les arguments
if "%1"=="verbose" set VERBOSE=--verbose
if "%1"=="exit-on-fail" set EXIT_ON_FAIL=--exit-on-fail
if "%2"=="verbose" set VERBOSE=--verbose  
if "%2"=="exit-on-fail" set EXIT_ON_FAIL=--exit-on-fail

echo 🎯 Provider testé: CLAUDE
echo 📁 Tests: Fonctionnels (language, search, response_length, document_count, image)
echo 📈 Rapport HTML: tests\reports\report.html
if defined VERBOSE echo 🔧 Mode verbose: ✅
if not defined VERBOSE echo 🔧 Mode verbose: ❌
if defined EXIT_ON_FAIL echo 🛑 Arrêt sur échec: ✅  
if not defined EXIT_ON_FAIL echo 🛑 Arrêt sur échec: ❌
echo.
echo ⏳ Démarrage des tests...
echo -----------------------------------------------------------------

REM Variables d'environnement
set SKIP_E2E=true
set PYTEST_CURRENT_TEST=true

REM Exécuter les tests
"%PYTHON_EXE%" tests\run_test.py --type functional --llm CLAUDE --skip-e2e --html-report %VERBOSE% %EXIT_ON_FAIL%

REM Vérifier le résultat
if %ERRORLEVEL% == 0 (
    echo.
    echo =================================================================
    echo ✅ SUCCÈS - Tous les tests Claude ont réussi !
    echo.
    echo 📊 Rapport HTML disponible:
    echo    📁 %ROOT_DIR%\tests\reports\report.html
    echo.
    echo 🔍 Métriques disponibles dans le rapport:
    echo    • Questions posées → Réponses obtenues
    echo    • Longueurs mesurées (short/medium/long)
    echo    • Nombres de documents (2/6/12) → Citations
    echo    • Descriptions d'images complètes
    echo    • Validations avec termes trouvés
    echo =================================================================
) else (
    echo.
    echo =================================================================
    echo ❌ ÉCHEC - Certains tests ont échoué
    echo.
    echo 🔍 Vérifiez le rapport HTML pour les détails:
    echo    📁 %ROOT_DIR%\tests\reports\report.html
    echo.
    echo 💡 Solutions possibles:
    echo    • Vérifiez la configuration CLAUDE dans .env
    echo    • Vérifiez la clé API CLAUDE
    echo    • Lancez avec exit-on-fail pour plus de détails
    echo =================================================================
)

pause