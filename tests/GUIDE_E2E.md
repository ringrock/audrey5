# 🚀 Guide Tests E2E - Configuration et Skip

## 🎯 Options pour Gérer les Tests E2E

### **Option 1 : Skipper Automatiquement les E2E** ⚡

```bash
# Skipper tous les tests E2E (le plus simple)
test_env/bin/python tests/run_test.py --skip-e2e --html-report --verbose

# Tests fonctionnels seulement
test_env/bin/python tests/run_test.py --type functional --html-report --verbose

# Tests avec un LLM spécifique, sans E2E
test_env/bin/python tests/run_test.py --llm CLAUDE --skip-e2e --html-report --verbose
```

### **Option 2 : Démarrer les Services pour E2E** 🔧

**Terminal 1 - Frontend :**
```bash
cd frontend
npm install
npm run dev
# Attendre que le serveur démarre sur http://localhost:5173
```

**Terminal 2 - Backend :**
```bash
python -m uvicorn app:app --port 50505 --reload
# Attendre que l'API démarre sur http://localhost:50505
```

**Terminal 3 - Tests E2E :**
```bash
# Tous les tests E2E (avec services démarrés)
test_env/bin/python tests/run_test.py --type e2e --html-report --verbose

# Tests E2E d'images seulement
test_env/bin/python tests/run_test.py --markers e2e_image --html-report --verbose
```

### **Option 3 : Skip Intelligent (Recommandé)** 🧠

```bash
# Les tests E2E se skipperont automatiquement si les services ne sont pas disponibles
test_env/bin/python tests/run_test.py --html-report --verbose

# Désactiver la vérification des services (forcer l'exécution E2E)
test_env/bin/python tests/run_test.py --no-service-check --html-report --verbose
```

## 🔧 Variables d'Environnement

```bash
# Skipper complètement les tests E2E
export SKIP_E2E=true

# Désactiver la vérification des services
export E2E_CHECK_SERVICES=false

# URLs personnalisées
export E2E_BASE_URL="http://localhost:3000"      # Si frontend sur port différent
export E2E_BACKEND_URL="http://localhost:8000"   # Si backend sur port différent

# Authentification E2E (valeurs par défaut incluses)
export E2E_AUTH_TOKEN="c9970318e1153220772cc670c6db6ce1c8dc49900573eae48060fa240c07eaae"
export E2E_AUTH_LANGUAGE="FR"
export E2E_AUTH_USER="rnegrier@avanteam.fr"

# Mode visible (pour debug)
export HEADLESS=false
```

## ⚡ Commandes Rapides

### **Développement Rapide (Sans E2E)**
```bash
# Tests fonctionnels avec rapport détaillé
test_env/bin/python tests/run_test.py --type functional --html-report --verbose

# Tests de langue seulement (très rapide)
test_env/bin/python tests/run_test.py --markers language --skip-e2e --html-report --verbose

# Tests d'images seulement (sans E2E)
test_env/bin/python tests/run_test.py --markers "image and not e2e" --html-report --verbose
```

### **Test Complet (Avec E2E)**
```bash
# 1. Démarrer les services (voir Option 2)
# 2. Configurer l'authentification (optionnel, valeurs par défaut incluses)
export E2E_AUTH_TOKEN="votre_token_si_different"
export E2E_AUTH_USER="votre_email@domain.com"

# 3. Lancer tous les tests
test_env/bin/python tests/run_test.py --html-report --verbose

# Ou forcer même si services non disponibles
test_env/bin/python tests/run_test.py --no-service-check --html-report --verbose
```

## 📊 Résultats Attendus

### **Services Non Disponibles (Skip Automatique)**
```
tests/e2e/test_chat_interactions_e2e.py SSSSSSSSSSSSSS     [12%] (15 skipped)
tests/e2e/test_image_upload_e2e.py SSSSSSSSSSSSSS           [24%] (15 skipped)

Raison: "Frontend non disponible sur http://localhost:5173. Démarrez 'npm run dev' dans /frontend"
```

### **Services Disponibles (Tests Passent)**
```
tests/e2e/test_chat_interactions_e2e.py .............      [12%] (15 passed)
tests/e2e/test_image_upload_e2e.py .............           [24%] (15 passed)
```

### **Skip Forcé**
```bash
test_env/bin/python tests/run_test.py --skip-e2e --verbose

tests/e2e/ (entièrement ignoré)
tests/functional_tests/ ........................             [100%] (tous passent)
```

## 🎭 Messages d'Aide

Les tests E2E afficheront des messages clairs :

```
SKIPPED [1] conftest.py:45: Frontend non disponible sur http://localhost:5173. 
Démarrez 'npm run dev' dans /frontend

SKIPPED [1] conftest.py:45: Backend non disponible sur http://localhost:50505. 
Démarrez 'python -m uvicorn app:app --port 50505'

SKIPPED [1] conftest.py:45: Tests E2E désactivés via SKIP_E2E=true
```

## 🎯 Recommandations

### **Pour le Développement Quotidien**
```bash
# Rapide et efficace
test_env/bin/python tests/run_test.py --skip-e2e --html-report --verbose
```

### **Pour les Tests Complets (CI/CD)**
```bash
# 1. Démarrer automatiquement les services
# 2. Lancer tous les tests
test_env/bin/python tests/run_test.py --html-report --verbose
```

### **Pour Débugger les E2E**
```bash
# Mode visible + logs détaillés
HEADLESS=false test_env/bin/python tests/run_test.py --type e2e --verbose --exit-on-fail
```

## 🔐 Authentification E2E

Les tests E2E injectent automatiquement un token d'authentification au chargement de chaque page :

### **Configuration par Défaut**
```javascript
// Token injecté automatiquement
window.postMessage({
    AuthToken: "c9970318e1153220772cc670c6db6ce1c8dc49900573eae48060fa240c07eaae",
    Language: "FR",
    UserNameDN: "rnegrier@avanteam.fr"
}, '*');
```

### **Personnalisation du Token**
```bash
# Utiliser un token différent
export E2E_AUTH_TOKEN="votre_nouveau_token_ici"

# Changer l'utilisateur
export E2E_AUTH_USER="votre_email@domain.com"

# Changer la langue
export E2E_AUTH_LANGUAGE="EN"

# Puis lancer les tests
test_env/bin/python tests/run_test.py --type e2e --verbose
```

### **Debug de l'Authentification**
```bash
# Mode visible pour voir les logs d'auth dans la console
HEADLESS=false test_env/bin/python tests/run_test.py --type e2e --verbose

# Les logs console afficheront:
# 🔐 Injection du token d'authentification E2E...
# ✅ Token d'authentification envoyé
```

Maintenant vous pouvez facilement choisir d'inclure ou exclure les tests E2E selon vos besoins ! 🚀