# ollama_utils.py
import logging
import requests
import base64
import json
import io
from PIL import Image

# Initialize logger for this module
logger = logging.getLogger(__name__)

# Import necessary settings and T function
try:
    import screener.settings as settings # Assuming settings.py initializes logging
    T = settings.T
except ImportError:
    # This fallback is primarily for standalone testing of this module,
    # or if settings.py fails very early before logging is set up.
    # In a normal app run, settings.py should handle logging setup.
    logger.warning("Could not import 'settings' in ollama_utils.py. Using fallback Ollama config and English text.")
    
    class settings_fallback: # Minimal fallback for core Ollama settings
        OLLAMA_URL = 'http://localhost:11434/api/generate'
        OLLAMA_MODEL = 'gemma3:4b' # Ensure this matches a model you have
        OLLAMA_TIMEOUT_SECONDS = 120
        OLLAMA_DEFAULT_ERROR_MSG_KEY = 'ollama_no_response_content'
        SCREENSHOT_FORMAT = 'PNG'
        LANGUAGE = 'en'
        UI_TEXTS = {'en': {'ollama_no_response_content': 'No response content found in JSON.'}}
    settings = settings_fallback()

    def T_fallback(key, lang='en'):
        return settings.UI_TEXTS.get(lang, settings.UI_TEXTS['en']).get(key, f"<{key} (ollama_utils fallback)>")
    T = T_fallback
    logger.info("ollama_utils.py: Using fallback settings and T function.")


class OllamaError(Exception):
    """Base exception for Ollama interactions."""
    pass

class OllamaConnectionError(OllamaError):
    """Raised when connection to Ollama server fails."""
    pass

class OllamaTimeoutError(OllamaError):
    """Raised when the request to Ollama times out."""
    pass

class OllamaRequestError(OllamaError):
    """Raised for non-connection/timeout errors from Ollama, including API errors."""
    def __init__(self, message, status_code=None, detail=""):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail

    def __str__(self):
        s = super().__str__()
        if self.status_code: s += f" (Status Code: {self.status_code})"
        if self.detail: s += f" - Detail: {self.detail}"
        return s

def request_ollama_analysis(image: Image.Image, prompt: str) -> str:
    """
    Sends an image and a prompt to the Ollama API for analysis.

    Args:
        image: A PIL.Image.Image object of the screenshot.
        prompt: The text prompt for Ollama.

    Returns:
        The response text from Ollama.

    Raises:
        ValueError: If image encoding fails.
        OllamaConnectionError: If connection to Ollama server fails.
        OllamaTimeoutError: If the request to Ollama times out.
        OllamaRequestError: For other request-related errors or API errors.
        OllamaError: For unexpected issues during the process.
    """
    logger.debug("Attempting to encode image for Ollama request.")
    try:
        buffered = io.BytesIO()
        image.save(buffered, format=settings.SCREENSHOT_FORMAT)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        logger.debug("Image successfully encoded to base64. Length: %d", len(img_base64))
    except Exception as e:
        logger.error("Failed to encode image for Ollama request.", exc_info=True)
        raise ValueError(f"Failed to encode image: {e}") from e

    payload = {
        'model': settings.OLLAMA_MODEL,
        'prompt': prompt,
        'images': [img_base64],
        'stream': False # We are expecting a single JSON response
    }

    headers = {'Content-Type': 'application/json'}

    try:
        logger.info("Sending request to Ollama: URL=%s, Model=%s, Timeout=%ss, Prompt='%.60s...'",
                    settings.OLLAMA_URL, settings.OLLAMA_MODEL, settings.OLLAMA_TIMEOUT_SECONDS, prompt)
        
        response = requests.post(
            settings.OLLAMA_URL,
            json=payload,
            headers=headers,
            timeout=settings.OLLAMA_TIMEOUT_SECONDS
        )
        logger.debug("Ollama request sent. Response status code: %s", response.status_code)
        response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
        
        response_data = response.json()
        ollama_response_text = response_data.get('response')
        
        if ollama_response_text is not None:
            logger.info("Received successful response from Ollama. Response length: %d", len(ollama_response_text))
            logger.debug("Ollama response preview: %.100s...", ollama_response_text)
            return ollama_response_text
        else:
            # Check for an 'error' field if 'response' is missing
            ollama_api_error = response_data.get('error')
            if ollama_api_error:
                logger.error("Ollama API returned an error in JSON response: %s. Full response: %s", ollama_api_error, response_data)
                raise OllamaRequestError("Ollama API returned an error", status_code=response.status_code, detail=ollama_api_error)
            else:
                # This case should be rare if the API behaves as expected
                logger.error("Ollama response JSON did not contain 'response' or 'error' field. Status: %s, Full response: %s", response.status_code, response_data)
                default_msg = T(settings.OLLAMA_DEFAULT_ERROR_MSG_KEY) # "No response content found in JSON."
                raise OllamaRequestError(default_msg, status_code=response.status_code, detail="Response JSON malformed or missing expected fields.")

    except requests.exceptions.ConnectionError as e:
        logger.error("Ollama connection failed for URL: %s. Error: %s", settings.OLLAMA_URL, e, exc_info=False)
        raise OllamaConnectionError(f"Connection to Ollama at {settings.OLLAMA_URL} failed: {e}") from e
    except requests.exceptions.Timeout as e:
        logger.error("Ollama request timed out after %s seconds for URL: %s. Error: %s", settings.OLLAMA_TIMEOUT_SECONDS, settings.OLLAMA_URL, e, exc_info=False)
        raise OllamaTimeoutError(f"Request to Ollama at {settings.OLLAMA_URL} timed out: {e}") from e
    except requests.exceptions.RequestException as e: # Catches HTTPError from raise_for_status too
        # This is a broader category for other request issues (e.g., DNS failure, too many redirects, HTTP errors)
        error_detail = "N/A"
        status_code = e.response.status_code if e.response is not None else "N/A"
        if e.response is not None:
            try:
                error_detail = e.response.json().get('error', e.response.text) # Try to get 'error' field from JSON
            except json.JSONDecodeError:
                error_detail = e.response.text # Fallback to raw text if not JSON
        
        logger.error("Ollama request failed. Status: %s, URL: %s, Detail: %.200s, OriginalErrorType: %s",
                     status_code, settings.OLLAMA_URL, error_detail, type(e).__name__, exc_info=False) # exc_info=False if e is enough
        raise OllamaRequestError(f"Ollama request failed: {e}", status_code=status_code, detail=error_detail) from e
    except json.JSONDecodeError as e: # If response.json() fails on a 200 OK response (unlikely but possible)
        response_text_preview = response.text[:200] if hasattr(response, 'text') else "N/A"
        logger.error("Failed to decode Ollama response JSON despite a successful HTTP status. Response text preview: %s", response_text_preview, exc_info=True)
        raise OllamaError(f"Failed to decode Ollama response JSON: {e}. Response text: {response_text_preview}") from e
    except Exception as e: # Catch-all for other unexpected errors within this function
        logger.error("An unexpected error occurred during Ollama request processing.", exc_info=True)
        raise OllamaError(f"An unexpected error occurred during Ollama interaction: {e}") from e

if __name__ == '__main__':
    # Basic test for ollama_utils.py
    # This requires a running Ollama instance and a model that can handle images.
    # Also, you'd need a dummy image.

    # Setup basic logging for standalone test if not already configured
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logger.info("Running ollama_utils.py standalone test...")
    
    # Create a dummy image for testing
    try:
        dummy_image = Image.new('RGB', (100, 100), color = 'red')
        logger.debug("Created dummy image for testing.")

        # Test prompt (ensure your model can handle a generic prompt with an image)
        test_prompt = "Describe this image."
        
        logger.info("Sending test request to Ollama...")
        response = request_ollama_analysis(dummy_image, test_prompt)
        logger.info("Test request successful. Ollama response:")
        logger.info(response)

    except OllamaConnectionError:
        logger.error("TEST FAILED: Could not connect to Ollama. Is Ollama running and accessible at %s?", settings.OLLAMA_URL)
    except OllamaError as oe:
        logger.error("TEST FAILED: An Ollama error occurred: %s", oe, exc_info=True)
    except Exception as ex:
        logger.error("TEST FAILED: An unexpected error occurred: %s", ex, exc_info=True)