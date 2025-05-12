# ollama_utils.py

import requests
import base64
import json
import io
from PIL import Image

# Import necessary settings
try:
    import settings
except ImportError:
    # Define fallbacks if settings cannot be imported (e.g., testing utils standalone)
    print("Warning: Could not import settings. Using default Ollama config.")
    class settings: # Simple fallback class
        OLLAMA_URL = 'http://localhost:11434/api/generate'
        OLLAMA_MODEL = 'gemma3:12b' # A common default, adjust if needed
        OLLAMA_TIMEOUT_SECONDS = 120
        OLLAMA_DEFAULT_ERROR_MSG = 'No response content found in JSON.'
        SCREENSHOT_FORMAT = 'PNG'

# --- Custom Exceptions ---

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
    """Raised for non-successful HTTP responses or API errors."""
    def __init__(self, message, status_code=None, detail=""):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail

    def __str__(self):
        s = super().__str__()
        if self.status_code:
            s += f" (Status Code: {self.status_code})"
        if self.detail:
            s += f" - Detail: {self.detail}"
        return s


# --- Ollama API Interaction ---

def request_ollama_analysis(image: Image.Image, prompt: str) -> str:
    """
    Sends an image and prompt to the Ollama API for analysis.

    Args:
        image: A PIL Image object of the screenshot.
        prompt: The text prompt to send along with the image.

    Returns:
        The response text from Ollama.

    Raises:
        OllamaConnectionError: If connection to the Ollama server fails.
        OllamaTimeoutError: If the request times out.
        OllamaRequestError: For other request-related errors (e.g., bad status code,
                           API error messages).
        OllamaError: For unexpected errors during the process.
        ValueError: If the image format is invalid.
    """
    try:
        # 1. Prepare Image Data
        buffered = io.BytesIO()
        image.save(buffered, format=settings.SCREENSHOT_FORMAT)
        img_byte = buffered.getvalue()
        img_base64 = base64.b64encode(img_byte).decode('utf-8')

    except Exception as e:
        raise ValueError(f"Failed to encode image: {e}") from e

    # 2. Construct Payload
    payload = {
        'model': settings.OLLAMA_MODEL,
        'prompt': prompt,
        'images': [img_base64],
        'stream': False
    }

    # 3. Send Request and Handle Response/Errors
    try:
        print(f'Sending request to: {settings.OLLAMA_URL}')
        print(f'Using model: {settings.OLLAMA_MODEL}')
        print(f"Using prompt: '{prompt[:60]}...'")

        response = requests.post(
            settings.OLLAMA_URL,
            json=payload,
            timeout=settings.OLLAMA_TIMEOUT_SECONDS
        )

        # Check for HTTP errors first
        response.raise_for_status()

        # Parse JSON response
        response_data = response.json()
        ollama_response_text = response_data.get('response')

        # Check if the 'response' key exists and is not empty
        if ollama_response_text is None:
             # Check if Ollama returned an error message instead
             ollama_error = response_data.get('error')
             if ollama_error:
                 raise OllamaRequestError(
                     f"Ollama API returned an error", detail=ollama_error
                 )
             else:
                 # No 'response' and no 'error', use default message
                 raise OllamaRequestError(
                     settings.OLLAMA_DEFAULT_ERROR_MSG,
                     status_code=response.status_code
                 )

        print('Ollama processing complete.')
        return ollama_response_text

    except requests.exceptions.ConnectionError as e:
        raise OllamaConnectionError(f"Connection failed: {e}") from e
    except requests.exceptions.Timeout as e:
        raise OllamaTimeoutError(f"Request timed out: {e}") from e
    except requests.exceptions.RequestException as e:
        # Handle HTTP errors (like 4xx, 5xx) caught by raise_for_status
        # or other requests library issues
        detail = ""
        status_code = e.response.status_code if e.response is not None else None
        try:
            if e.response is not None:
                detail = e.response.json().get('error', str(e))
        except (json.JSONDecodeError, AttributeError):
             detail = str(e.response.text) if e.response is not None else str(e)

        raise OllamaRequestError(
            f"Request failed: {e}", status_code=status_code, detail=detail
        ) from e
    except json.JSONDecodeError as e:
        raise OllamaError(f"Failed to decode Ollama response JSON: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors during the process
        raise OllamaError(f"An unexpected error occurred: {e}") from e