"""
Configuration pytest pour les tests End-to-End avec Playwright.
"""
import pytest
import asyncio
import os
import time
import requests
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Configuration des URLs et timeouts
BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:5173")  # Frontend dev server
BACKEND_URL = os.getenv("E2E_BACKEND_URL", "http://localhost:50505")  # Backend server
DEFAULT_TIMEOUT = 30000  # 30 secondes
SLOW_TIMEOUT = 60000    # 60 secondes pour les réponses LLM

# Variables pour skipper les tests E2E
SKIP_E2E = os.getenv("SKIP_E2E", "false").lower() == "true"
E2E_CHECK_SERVICES = os.getenv("E2E_CHECK_SERVICES", "true").lower() == "true"

# Configuration d'authentification E2E
E2E_AUTH_TOKEN = os.getenv("E2E_AUTH_TOKEN", "c9970318e1153220772cc670c6db6ce1c8dc49900573eae48060fa240c07eaae")
E2E_AUTH_LANGUAGE = os.getenv("E2E_AUTH_LANGUAGE", "FR")
E2E_AUTH_USER = os.getenv("E2E_AUTH_USER", "rnegrier@avanteam.fr")

def check_service_availability(url: str, timeout: int = 5) -> bool:
    """Vérifier si un service est disponible."""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code < 500
    except Exception:
        return False

def should_skip_e2e() -> str:
    """Déterminer si les tests E2E doivent être skippés et pourquoi."""
    if SKIP_E2E:
        return "Tests E2E désactivés via SKIP_E2E=true"
    
    if not E2E_CHECK_SERVICES:
        return ""  # Ne pas vérifier les services
    
    # Vérifier la disponibilité des services
    if not check_service_availability(BASE_URL):
        return f"Frontend non disponible sur {BASE_URL}. Démarrez 'npm run dev' dans /frontend"
    
    if not check_service_availability(f"{BACKEND_URL}/frontend_settings"):
        return f"Backend non disponible sur {BACKEND_URL}. Démarrez 'python -m uvicorn app:app --port 50505'"
    
    return ""  # Tous les services sont disponibles


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def browser():
    """Launch browser instance for the session."""
    skip_reason = should_skip_e2e()
    if skip_reason:
        pytest.skip(skip_reason)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            args=[
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-dev-shm-usage",
                "--no-sandbox"
            ]
        )
        yield browser
        await browser.close()


@pytest.fixture(scope="function")
async def context(browser: Browser):
    """Create a new browser context for each test."""
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="fr-FR",
        permissions=["clipboard-read", "clipboard-write"]
    )
    yield context
    await context.close()


@pytest.fixture(scope="function")
async def page(context: BrowserContext):
    """Create a new page for each test."""
    page = await context.new_page()
    
    # Set default timeouts
    page.set_default_timeout(DEFAULT_TIMEOUT)
    page.set_default_navigation_timeout(DEFAULT_TIMEOUT)
    
    # Navigate to the application
    try:
        await page.goto(BASE_URL, wait_until="networkidle", timeout=10000)
        
        # Wait for page to be fully loaded
        await page.wait_for_load_state("domcontentloaded")
        
    except Exception as e:
        pytest.skip(f"Frontend non disponible sur {BASE_URL}: {e}")
    
    yield page
    
    await page.close()


@pytest.fixture
def image_test_paths():
    """Paths to test images."""
    test_dir = Path(__file__).parent.parent / "functional_tests" / "img"
    return {
        "broken_bottle": test_dir / "test1.jpg",
        "engine_fire": test_dir / "test2.jpg"
    }


@pytest.fixture
async def authenticated_page(page: Page):
    """Page with authentication token injected."""
    # Inject authentication token via postMessage
    auth_script = f"""
    () => {{
        console.log('🔐 Injection du token d\'authentification E2E...');
        
        // Inject authentication token
        window.postMessage({{
            AuthToken: "{E2E_AUTH_TOKEN}",
            Language: "{E2E_AUTH_LANGUAGE}",
            UserNameDN: "{E2E_AUTH_USER}"
        }}, '*');
        
        console.log('✅ Token d\'authentification envoyé');
        
        // Wait a bit for the auth to be processed
        return new Promise(resolve => setTimeout(resolve, 1000));
    }}
    """
    
    # Execute the authentication script
    await page.evaluate(auth_script)
    
    # Wait for potential auth processing
    await page.wait_for_timeout(2000)
    
    # Check if authentication was successful
    try:
        # Look for any auth error messages
        auth_error = await page.wait_for_selector("[data-testid='auth-error']", timeout=2000)
        if auth_error:
            error_text = await auth_error.inner_text()
            pytest.skip(f"Authentication failed: {error_text}")
    except:
        # No auth error, continue
        pass
    
    yield page


@pytest.fixture
def llm_providers():
    """Available LLM providers for E2E testing."""
    return ["CLAUDE", "GEMINI", "OPENAI_DIRECT"]


@pytest.fixture
def image_supported_providers():
    """LLM providers that support image upload."""
    return ["CLAUDE", "GEMINI", "OPENAI_DIRECT"]


class E2EHelpers:
    """Helper class for common E2E operations."""
    
    @staticmethod
    async def wait_for_response(page: Page, timeout: int = SLOW_TIMEOUT):
        """Wait for LLM response to complete."""
        # Wait for loading indicator to disappear
        try:
            await page.wait_for_selector("[data-testid='answer-loading']", timeout=5000)
            await page.wait_for_selector("[data-testid='answer-loading']", state="detached", timeout=timeout)
        except:
            # Loading indicator might not appear for fast responses
            pass
        
        # Wait a bit more for content to stabilize
        await page.wait_for_timeout(1000)
    
    @staticmethod
    async def select_llm_provider(page: Page, provider: str):
        """Select a specific LLM provider in the UI."""
        # This assumes there's a dropdown or selection UI for LLM providers
        # Adapt based on your actual UI implementation
        try:
            # Look for provider selector
            provider_selector = await page.wait_for_selector("[data-testid='llm-provider-selector']", timeout=5000)
            await provider_selector.click()
            
            # Select the specific provider
            await page.click(f"[data-testid='llm-provider-{provider}']")
            
            # Wait for selection to be applied
            await page.wait_for_timeout(1000)
        except:
            # Provider selector might not be available or provider already selected
            pass
    
    @staticmethod
    async def upload_image(page: Page, image_path: Path):
        """Upload an image file through the UI."""
        # Look for file input or upload button
        file_input = await page.wait_for_selector("input[type='file']", timeout=10000)
        
        # Upload the file
        await file_input.set_input_files(str(image_path))
        
        # Wait for upload to complete
        await page.wait_for_timeout(2000)
    
    @staticmethod
    async def send_message(page: Page, message: str):
        """Send a text message through the chat interface."""
        # Find message input
        message_input = await page.wait_for_selector("[data-testid='question-input']", timeout=10000)
        
        # Type the message
        await message_input.fill(message)
        
        # Send the message (look for send button)
        send_button = await page.wait_for_selector("[data-testid='send-button']", timeout=10000)
        await send_button.click()
    
    @staticmethod
    async def get_last_response(page: Page) -> str:
        """Get the text content of the last response."""
        # Wait for response to appear
        await E2EHelpers.wait_for_response(page)
        
        # Get all response elements
        responses = await page.query_selector_all("[data-testid='chat-response']")
        if responses:
            last_response = responses[-1]
            return await last_response.inner_text()
        
        return ""
    
    @staticmethod
    async def clear_chat(page: Page):
        """Clear the current chat session."""
        try:
            clear_button = await page.wait_for_selector("[data-testid='clear-chat']", timeout=5000)
            await clear_button.click()
            
            # Confirm if there's a confirmation dialog
            try:
                confirm_button = await page.wait_for_selector("[data-testid='confirm-clear']", timeout=2000)
                await confirm_button.click()
            except:
                pass
                
            await page.wait_for_timeout(1000)
        except:
            # Clear button might not be available
            pass


@pytest.fixture
def e2e_helpers():
    """Provide E2E helper methods."""
    return E2EHelpers


def pytest_configure(config):
    """Configure pytest for E2E tests."""
    config.addinivalue_line(
        "markers", "e2e: End-to-End tests with Playwright"
    )
    config.addinivalue_line(
        "markers", "e2e_image: E2E tests for image upload functionality"
    )
    config.addinivalue_line(
        "markers", "e2e_chat: E2E tests for chat interactions"
    )
    config.addinivalue_line(
        "markers", "e2e_slow: Slow E2E tests that may take longer"
    )