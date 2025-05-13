# settings.py
import json
import os

# --- Language Configuration ---
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'ru': 'Русский'
}
DEFAULT_LANGUAGE = 'en' # Default language if no preference is set
LANGUAGE = DEFAULT_LANGUAGE # Current active language (can be changed at runtime)

# --- Ollama Configuration ---
OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'gemma3:12b'
OLLAMA_TIMEOUT_SECONDS = 120
OLLAMA_DEFAULT_ERROR_MSG_KEY = 'ollama_no_response_content'

# --- Hotkey Configuration ---
HOTKEYS_CONFIG_FILE = 'hotkeys.json'
HOTKEY_ACTIONS = {} # Populated by load_hotkey_actions()
DEFAULT_MANUAL_ACTION = 'describe'
CUSTOM_PROMPT_IDENTIFIER = "CUSTOM_PROMPT_PLACEHOLDER"

# --- UI Text Configuration ---
UI_TEXTS_FILE = 'ui_texts.json' # New constant for the UI texts file
UI_TEXTS = {} # Will be populated by load_ui_texts()

def load_ui_texts():
    """Loads UI texts from the JSON file."""
    global UI_TEXTS
    UI_TEXTS = {} # Clear previous texts, if any
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        texts_path = os.path.join(base_dir, UI_TEXTS_FILE)

        with open(texts_path, 'r', encoding='utf-8') as f:
            loaded_texts = json.load(f)

        # Basic validation
        if DEFAULT_LANGUAGE not in loaded_texts:
            raise ValueError(f"Default language '{DEFAULT_LANGUAGE}' not found in '{texts_path}'.")
        for lang_code in SUPPORTED_LANGUAGES.keys():
            if lang_code not in loaded_texts:
                # This is a warning, not a fatal error, as fallbacks will occur.
                print(f"Warning: Supported language '{lang_code}' not found in '{texts_path}'. Missing translations will fallback to default.")
        
        UI_TEXTS = loaded_texts
        # print(f"UI texts loaded from '{texts_path}'.") # Optional: for debugging

    except FileNotFoundError:
        # This is a critical error for application startup.
        raise FileNotFoundError(f"UI texts file '{texts_path}' not found. Application cannot load UI strings.")
    except json.JSONDecodeError as e:
        # Critical error, malformed JSON.
        raise ValueError(f"Error decoding JSON from '{texts_path}': {e}. Check the file for syntax errors.")
    except Exception as e:
        # Catch-all for other unexpected errors during loading.
        raise Exception(f"An unexpected error occurred while loading UI texts from '{texts_path}': {e}")


def set_language(new_lang):
    """Sets the application language and reloads language-dependent settings."""
    global LANGUAGE
    if new_lang in SUPPORTED_LANGUAGES:
        LANGUAGE = new_lang
        print(f"Application language changed to: {LANGUAGE} ({SUPPORTED_LANGUAGES[new_lang]})")
        try:
            # UI_TEXTS are already loaded; T() function handles language switching dynamically.
            # Reload hotkeys as their prompts/descriptions are localized during their load.
            load_hotkey_actions(LANGUAGE) 
            return True
        except Exception as e:
            print(f"Error reloading hotkey actions after language change: {e}")
            return False # Indicate failure
    print(f"Warning: Attempted to set unsupported language '{new_lang}'.")
    return False

def load_hotkey_actions(lang=None):
    """Loads hotkey actions from the JSON file and localizes them."""
    global HOTKEY_ACTIONS
    current_lang = lang if lang else LANGUAGE 

    HOTKEY_ACTIONS = {} 
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, HOTKEYS_CONFIG_FILE)

        with open(config_path, 'r', encoding='utf-8') as f:
            raw_actions = json.load(f)

        for action_name, details in raw_actions.items():
            localized_prompt = details['prompt']
            if isinstance(localized_prompt, dict):
                localized_prompt = localized_prompt.get(current_lang, localized_prompt.get(DEFAULT_LANGUAGE, f"Missing prompt for {action_name}"))
            
            localized_description = details['description']
            if isinstance(localized_description, dict):
                localized_description = localized_description.get(current_lang, localized_description.get(DEFAULT_LANGUAGE, action_name))

            HOTKEY_ACTIONS[action_name] = {
                'hotkey': details['hotkey'],
                'prompt': localized_prompt,
                'description': localized_description
            }
        # print(f"Hotkey actions loaded/reloaded and localized for '{current_lang}'.") # Optional

        if DEFAULT_MANUAL_ACTION not in HOTKEY_ACTIONS:
            raise ValueError(
                f"DEFAULT_MANUAL_ACTION '{DEFAULT_MANUAL_ACTION}' "
                f"not found in loaded HOTKEY_ACTIONS keys from '{config_path}' for language '{current_lang}'."
            )

    except FileNotFoundError:
        raise FileNotFoundError(f"Hotkey configuration file '{config_path}' not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from '{config_path}': {e}")
    except Exception as e: 
        raise Exception(f"Error loading hotkey actions from '{config_path}': {e}")


def T(key, lang=None):
    """
    Fetches a localized string. Uses current global LANGUAGE if lang is None.
    Fallbacks: Current Lang -> Default Lang -> "<key_name_missing>"
    """
    current_lang_code = lang if lang else LANGUAGE
    
    # Check if UI_TEXTS has been populated. This should always be true after module init.
    if not UI_TEXTS:
        # This situation implies a severe failure during settings.py initialization.
        # Error should have been caught and logged by the initial loading sequence.
        # screener.py's import error handling for settings.py would likely trigger its own fallback T function.
        print(f"CRITICAL WARNING: T() called, but UI_TEXTS is empty. Key: '{key}'. Settings initialization likely failed.")
        return f"<{key} (UI_TEXTS_UNINITIALIZED)>"

    # Try fetching from the specified or current language
    lang_texts = UI_TEXTS.get(current_lang_code)
    if lang_texts:
        text_value = lang_texts.get(key)
        if text_value is not None:
            return text_value

    # If not found in current language, try fallback to default language
    if current_lang_code != DEFAULT_LANGUAGE: # Avoid re-checking if current is already default
        default_lang_texts = UI_TEXTS.get(DEFAULT_LANGUAGE)
        if default_lang_texts:
            text_value = default_lang_texts.get(key)
            if text_value is not None:
                # Optional: Log that a fallback to default language occurred.
                # print(f"Info: UI text key '{key}' not found for lang '{current_lang_code}', used default '{DEFAULT_LANGUAGE}'.")
                return text_value
            
    # If key is not found in either current or default language, return the key itself as a placeholder.
    # This indicates a missing translation string in ui_texts.json for the given key.
    # print(f"Warning: UI text key '{key}' not found for language '{current_lang_code}' or default '{DEFAULT_LANGUAGE}'.")
    return f"<{key}>"


# --- UI Style --- (Constants remain unchanged)
MAIN_WINDOW_GEOMETRY = '450x350'
WINDOW_RESIZABLE_WIDTH = False
WINDOW_RESIZABLE_HEIGHT = False
PADDING_SMALL = 5
PADDING_LARGE = 10
RESPONSE_WINDOW_GEOMETRY = '700x800'
RESPONSE_TEXT_PADDING_X = 10
RESPONSE_TEXT_PADDING_Y_TOP = (10, 0)
RESPONSE_CONTROL_PADDING_X = 10
RESPONSE_CONTROL_PADDING_Y = 5
RESPONSE_BUTTON_PADDING_Y = (5, 10)
RESPONSE_BUTTON_PADDING_X = 5
FONT_SIZE_LABEL_WIDTH = 10
STATUS_COLOR_DEFAULT = 'gray'
STATUS_COLOR_READY = 'blue'
STATUS_COLOR_PROCESSING = 'darkorange'
STATUS_COLOR_ERROR = 'red'
CODE_BLOCK_BG_COLOR = '#f0f0f0'
CODE_BLOCK_MARGIN = 10
CODE_FONT_SIZE_OFFSET = -1
OVERLAY_ALPHA = 0.4
OVERLAY_CURSOR = 'cross'
OVERLAY_BG_COLOR = 'gray'
SELECTION_RECT_COLOR = 'red'
SELECTION_RECT_WIDTH = 2
DEFAULT_FONT_SIZE = 12
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 17
CODE_FONT_FAMILY = 'Courier New'
MIN_SELECTION_WIDTH = 10
MIN_SELECTION_HEIGHT = 10
CAPTURE_DELAY = 0.2
SCREENSHOT_FORMAT = 'PNG'
ICON_PATH = 'icon.png'
TRAY_ICON_NAME = 'screenshot_ollama'
DEFAULT_ICON_WIDTH = 64
DEFAULT_ICON_HEIGHT = 64
DEFAULT_ICON_BG_COLOR = 'dimgray'
DEFAULT_ICON_RECT_COLOR = 'dodgerblue'
DEFAULT_ICON_RECT_WIDTH = 4
DEFAULT_ICON_FONT_FAMILY = 'Arial'
DEFAULT_ICON_FONT_SIZE = 30
DEFAULT_ICON_FONT_WEIGHT = 'bold'
DEFAULT_ICON_TEXT = 'S'
DEFAULT_ICON_TEXT_COLOR = 'white'
COPY_BUTTON_RESET_DELAY_MS = 2000
THREAD_JOIN_TIMEOUT_SECONDS = 1.0

# --- Initialize configurations at module load time ---
# These must be populated before other modules (like screener.py) try to access them.
# Errors here are critical and should be handled by the main application entry point (screener.py).

_initialization_errors = [] # Use a leading underscore to suggest it's for internal module use

try:
    load_ui_texts() # Load UI texts first, as T() might be used implicitly or explicitly soon.
except Exception as e:
    err_msg = f"CRITICAL ERROR during initial settings.load_ui_texts: {e}"
    print(err_msg)
    _initialization_errors.append(err_msg)
    # UI_TEXTS will remain empty or partially filled if an error occurs within load_ui_texts
    # The T() function has a safeguard for empty UI_TEXTS.
    # screener.py's import error handling for settings.py is the primary mechanism for user notification.

try:
    # LANGUAGE should be its default value here unless set otherwise prior to this script execution (e.g. env var)
    load_hotkey_actions(LANGUAGE)
except Exception as e:
    err_msg = f"CRITICAL ERROR during initial settings.load_hotkey_actions: {e}"
    print(err_msg)
    _initialization_errors.append(err_msg)
    # HOTKEY_ACTIONS will be empty or partially filled.
    # screener.py checks for issues like DEFAULT_MANUAL_ACTION missing.

if _initialization_errors:
    print("\n" + "="*30 + " SETTINGS INITIALIZATION ERRORS " + "="*30)
    for _err in _initialization_errors:
        print(f" - {_err}")
    print("="* (60 + len(" SETTINGS INITIALIZATION ERRORS ")) )
    print("Application may not function correctly or will exit if screener.py cannot handle these errors.\n")
    # It's generally better to let these errors propagate if they are critical,
    # so that screener.py's try-except block around 'import settings' can catch them
    # and display a user-friendly error message.
    # If load_ui_texts or load_hotkey_actions raises an unhandled exception (like FileNotFoundError),
    # the import of settings.py itself will fail.