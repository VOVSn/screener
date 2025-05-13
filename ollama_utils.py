# ollama_utils.py

import requests
import base64
import json
import io
from PIL import Image

# Import necessary settings and T function
try:
    import settings
    T = settings.T
except ImportError:
    print("Warning: Could not import settings in ollama_utils.py. Using default Ollama config and English text.")
    class settings_fallback:
        OLLAMA_URL = 'http://localhost:11434/api/generate'
        OLLAMA_MODEL = 'gemma3:4b'
        OLLAMA_TIMEOUT_SECONDS = 120
        OLLAMA_DEFAULT_ERROR_MSG_KEY = 'ollama_no_response_content'
        SCREENSHOT_FORMAT = 'PNG'
        LANGUAGE = 'en'
        UI_TEXTS = {'en': {'ollama_no_response_content': 'No response content found in JSON.'}}
    settings = settings_fallback()
    def T_fallback(key, lang='en'): return settings.UI_TEXTS.get(lang, settings.UI_TEXTS['en']).get(key, f"<{key}>")
    T = T_fallback


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
    try:
        buffered = io.BytesIO()
        image.save(buffered, format=settings.SCREENSHOT_FORMAT)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        raise ValueError(f"Failed to encode image: {e}") from e

    payload = {'model': settings.OLLAMA_MODEL, 'prompt': prompt, 'images': [img_base64], 'stream': False}

    try:
        print(f'Sending request to: {settings.OLLAMA_URL} with model: {settings.OLLAMA_MODEL}')
        print(f"Using prompt: '{prompt[:60]}...'")
        response = requests.post(settings.OLLAMA_URL, json=payload, timeout=settings.OLLAMA_TIMEOUT_SECONDS)
        response.raise_for_status()
        response_data = response.json()
        ollama_response_text = response_data.get('response')

        if ollama_response_text is None:
             ollama_error = response_data.get('error')
             if ollama_error:
                 raise OllamaRequestError("Ollama API returned an error", detail=ollama_error)
             else:
                 default_msg = T(settings.OLLAMA_DEFAULT_ERROR_MSG_KEY)
                 raise OllamaRequestError(default_msg, status_code=response.status_code)
        return ollama_response_text
    except requests.exceptions.ConnectionError as e:
        raise OllamaConnectionError(f"Connection failed: {e}") from e
    except requests.exceptions.Timeout as e:
        raise OllamaTimeoutError(f"Request timed out: {e}") from e
    except requests.exceptions.RequestException as e:
        detail = ""
        status_code = e.response.status_code if e.response is not None else None
        try:
            if e.response is not None: detail = e.response.json().get('error', str(e.response.text))
        except (json.JSONDecodeError, AttributeError):
             detail = str(e.response.text) if e.response is not None else str(e)
        raise OllamaRequestError(f"Request failed: {e}", status_code=status_code, detail=detail) from e
    except json.JSONDecodeError as e:
        raise OllamaError(f"Failed to decode Ollama response JSON: {e}") from e
    except Exception as e:
        raise OllamaError(f"An unexpected error occurred: {e}") from e