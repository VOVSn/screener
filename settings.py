# settings.py
import json
import os
from dotenv import load_dotenv

# --- Load Environment Variables ---
# Load variables from .env file in the project root
# It's good practice to place this early.
project_root = os.path.dirname(os.path.abspath(__file__)) # Assumes settings.py is in root
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print("Info: .env file not found. Using default configurations or hardcoded fallbacks.")

# --- App Instance (for callbacks like theme update) ---
app_instance = None

# --- Language Configuration ---
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'ru': 'Русский'
}
# Load from .env or use hardcoded default
DEFAULT_LANGUAGE_ENV = os.getenv('DEFAULT_LANGUAGE', 'en').lower()
DEFAULT_LANGUAGE = DEFAULT_LANGUAGE_ENV if DEFAULT_LANGUAGE_ENV in SUPPORTED_LANGUAGES else 'en'
LANGUAGE = DEFAULT_LANGUAGE

# --- Theme Configuration ---
# Load from .env or use hardcoded default
DEFAULT_THEME_ENV = os.getenv('DEFAULT_THEME', 'light').lower()
DEFAULT_THEME = DEFAULT_THEME_ENV if DEFAULT_THEME_ENV in ['light', 'dark'] else 'light'
CURRENT_THEME = DEFAULT_THEME

THEME_COLORS = { # Unchanged, but ensure keys exist for md_* and python_*
    'light': {
        'app_bg': '#F0F0F0', 'app_fg': '#000000', 'text_bg': '#FFFFFF', 'text_fg': '#000000',
        'text_disabled_bg': '#F0F0F0', 'button_bg': '#E1E1E1', 'button_fg': '#000000',
        'button_active_bg': '#ECECEC', 'entry_bg': '#FFFFFF', 'entry_fg': '#000000',
        'entry_select_bg': '#0078D7', 'entry_select_fg': '#FFFFFF', 'label_fg': '#000000',
        'disabled_fg': '#A3A3A3', 'status_default_fg': 'gray', 'status_ready_fg': 'blue',
        'status_processing_fg': 'darkorange', 'status_error_fg': 'red',
        'code_block_bg': '#F5F5F5', 'code_block_fg': '#000000', 'code_block_border': '#DDDDDD',
        'frame_bg': '#F0F0F0', 'scrollbar_bg': '#F0F0F0', 'scrollbar_trough': '#E0E0E0',
        'scale_trough': '#D3D3D3', 'separator_color': '#CCCCCC',
        'md_h1_fg': '#000080', 'md_h2_fg': '#00008B', 'md_list_item_fg': '#228B22',
        'md_inline_code_bg': '#E0E0E0', 'md_inline_code_fg': '#C7254E',
        'python_keyword_fg': '#0000FF', 'python_string_fg': '#008000',
        'python_comment_fg': '#808080', 'python_number_fg': '#A52A2A',
        'python_function_fg': '#800080', 'python_builtin_fg': '#800080',
    },
    'dark': {
        'app_bg': '#2B2B2B', 'app_fg': '#BBBBBB', 'text_bg': '#1E1E1E', 'text_fg': '#D4D4D4',
        'text_disabled_bg': '#252525', 'button_bg': '#3E3E3E', 'button_fg': '#E0E0E0',
        'button_active_bg': '#4F4F4F', 'entry_bg': '#3C3C3C', 'entry_fg': '#D4D4D4',
        'entry_select_bg': '#007ACC', 'entry_select_fg': '#FFFFFF', 'label_fg': '#E0E0E0',
        'disabled_fg': '#7A7A7A', 'status_default_fg': '#999999', 'status_ready_fg': '#569CD6',
        'status_processing_fg': '#CE9178', 'status_error_fg': '#F44747',
        'code_block_bg': '#252525', 'code_block_fg': '#D4D4D4', 'code_block_border': '#444444',
        'frame_bg': '#2B2B2B', 'scrollbar_bg': '#3E3E3E', 'scrollbar_trough': '#2B2B2B',
        'scale_trough': '#4A4A4A', 'separator_color': '#444444',
        'md_h1_fg': '#569CD6', 'md_h2_fg': '#4EC9B0', 'md_list_item_fg': '#B5CEA8',
        'md_inline_code_bg': '#3A3A3A', 'md_inline_code_fg': '#D69D85',
        'python_keyword_fg': '#569CD6', 'python_string_fg': '#CE9178',
        'python_comment_fg': '#6A9955', 'python_number_fg': '#B5CEA8',
        'python_function_fg': '#DCDCAA', 'python_builtin_fg': '#DCDCAA',
    }
}


def get_theme_color(key, theme=None): # Unchanged
    current_theme_name = theme if theme else CURRENT_THEME
    color = THEME_COLORS.get(current_theme_name, THEME_COLORS[DEFAULT_THEME]).get(key)
    if color is None:
        color = THEME_COLORS[DEFAULT_THEME].get(key, '#FF00FF') 
    return color

def set_theme(new_theme): # Unchanged
    global CURRENT_THEME
    if new_theme in THEME_COLORS:
        if CURRENT_THEME == new_theme: return True
        CURRENT_THEME = new_theme
        print(f"Application theme changed to: {CURRENT_THEME}")
        if app_instance and hasattr(app_instance, 'apply_theme_globally'):
            app_instance.apply_theme_globally()
            theme_name_localized = T(f'tray_theme_{new_theme}_text')
            if app_instance and hasattr(app_instance, 'update_status'):
                app_instance.update_status(
                    T('status_theme_changed_to').format(theme_name=theme_name_localized),
                    get_theme_color('status_ready_fg')
                )
        return True
    print(f"Warning: Attempted to set unsupported theme '{new_theme}'.")
    return False

# --- Ollama Configuration ---
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434/api/generate')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma3:12b') # Example: llama3:8b, llava, etc.
OLLAMA_TIMEOUT_SECONDS = int(os.getenv('OLLAMA_TIMEOUT_SECONDS', '120')) # Ensure it's an int
OLLAMA_DEFAULT_ERROR_MSG_KEY = 'ollama_no_response_content'


# --- Hotkey Configuration --- (Unchanged, loaded from JSON)
HOTKEYS_CONFIG_FILE = 'hotkeys.json'
HOTKEY_ACTIONS = {}
DEFAULT_MANUAL_ACTION = 'describe'
CUSTOM_PROMPT_IDENTIFIER = "CUSTOM_PROMPT_PLACEHOLDER"

# --- UI Text Configuration --- (Unchanged, loaded from JSON)
UI_TEXTS_FILE = 'ui_texts.json'
UI_TEXTS = {}

def load_ui_texts(): # Unchanged logic
    global UI_TEXTS
    UI_TEXTS = {}
    try:
        # Ensure base_dir is correct if settings.py is not in project root
        # base_dir = os.path.dirname(os.path.abspath(__file__))
        texts_path = os.path.join(project_root, UI_TEXTS_FILE) # Use project_root
        with open(texts_path, 'r', encoding='utf-8') as f:
            loaded_texts = json.load(f)
        if DEFAULT_LANGUAGE not in loaded_texts:
            raise ValueError(f"Default language '{DEFAULT_LANGUAGE}' not found in '{texts_path}'.")
        UI_TEXTS = loaded_texts
    except FileNotFoundError:
        raise FileNotFoundError(f"UI texts file '{texts_path}' not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from '{texts_path}': {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred while loading UI texts from '{texts_path}': {e}")

def set_language(new_lang): # Unchanged logic
    global LANGUAGE
    if new_lang in SUPPORTED_LANGUAGES:
        LANGUAGE = new_lang
        print(f"Application language changed to: {LANGUAGE} ({SUPPORTED_LANGUAGES[new_lang]})")
        try:
            load_hotkey_actions(LANGUAGE)
            if app_instance and hasattr(app_instance, 'apply_theme_globally'):
                 app_instance.apply_theme_globally(language_changed=True)
            return True
        except Exception as e:
            print(f"Error reloading after language change: {e}")
            return False
    print(f"Warning: Attempted to set unsupported language '{new_lang}'.")
    return False

def load_hotkey_actions(lang=None): # Unchanged logic
    global HOTKEY_ACTIONS
    current_lang = lang if lang else LANGUAGE
    HOTKEY_ACTIONS = {}
    try:
        # base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(project_root, HOTKEYS_CONFIG_FILE) # Use project_root
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
        if DEFAULT_MANUAL_ACTION not in HOTKEY_ACTIONS:
            raise ValueError(f"DEFAULT_MANUAL_ACTION '{DEFAULT_MANUAL_ACTION}' not found.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Hotkey configuration file '{config_path}' not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from '{config_path}': {e}")
    except Exception as e:
        raise Exception(f"Error loading hotkey actions from '{config_path}': {e}")

def T(key, lang=None): # Unchanged logic
    current_lang_code = lang if lang else LANGUAGE
    if not UI_TEXTS: return f"<{key} (UI_TEXTS_UNINITIALIZED)>"
    lang_texts = UI_TEXTS.get(current_lang_code)
    if lang_texts:
        text_value = lang_texts.get(key)
        if text_value is not None: return text_value
    if current_lang_code != DEFAULT_LANGUAGE:
        default_lang_texts = UI_TEXTS.get(DEFAULT_LANGUAGE)
        if default_lang_texts:
            text_value = default_lang_texts.get(key)
            if text_value is not None: return text_value
    return f"<{key}>"


# --- UI Style Constants ---
MAIN_WINDOW_GEOMETRY = '450x350'
WINDOW_RESIZABLE_WIDTH = False
WINDOW_RESIZABLE_HEIGHT = False
PADDING_SMALL = 5
PADDING_LARGE = 10

# Constants moved from screener.py
RESPONSE_WINDOW_MIN_WIDTH = 400
RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES = 5 # Min height for the ScrolledText in text lines
ESTIMATED_CONTROL_FRAME_HEIGHT_PX = 60 # Slider + Label + Padding (adjusted)
ESTIMATED_BUTTON_FRAME_HEIGHT_PX = 50  # Buttons + Padding
ESTIMATED_PADDING_PX = 20              # General window padding (top/bottom)

# Other UI constants (some color ones are now theme-dependent)
RESPONSE_WINDOW_GEOMETRY = '700x800'
RESPONSE_TEXT_PADDING_X = 10
RESPONSE_TEXT_PADDING_Y_TOP = (10, 0)
RESPONSE_CONTROL_PADDING_X = 10
RESPONSE_CONTROL_PADDING_Y = 5
RESPONSE_BUTTON_PADDING_Y = (5, 10)
RESPONSE_BUTTON_PADDING_X = 5
FONT_SIZE_LABEL_WIDTH = 10
CODE_FONT_SIZE_OFFSET = -1
OVERLAY_ALPHA = 0.4
OVERLAY_CURSOR = 'cross'
OVERLAY_BG_COLOR = 'gray' # Capture overlay specific, less theme-dependent
SELECTION_RECT_COLOR = 'red' # Capture overlay specific
SELECTION_RECT_WIDTH = 2
DEFAULT_FONT_SIZE = 12
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 17
CODE_FONT_FAMILY = 'Courier New'
MIN_SELECTION_WIDTH = 10
MIN_SELECTION_HEIGHT = 10
CAPTURE_DELAY = 0.2 # seconds
SCREENSHOT_FORMAT = 'PNG'
ICON_PATH = os.getenv('ICON_PATH', os.path.join(project_root, 'icon.png')) # Use project_root
TRAY_ICON_NAME = 'screener_ollama_app' # More unique name
DEFAULT_ICON_WIDTH = 64
DEFAULT_ICON_HEIGHT = 64
DEFAULT_ICON_BG_COLOR = 'dimgray' # Static for default icon generation
DEFAULT_ICON_RECT_COLOR = 'dodgerblue'
DEFAULT_ICON_RECT_WIDTH = 4
DEFAULT_ICON_FONT_FAMILY = 'Arial'
DEFAULT_ICON_FONT_SIZE = 30
DEFAULT_ICON_FONT_WEIGHT = 'bold'
DEFAULT_ICON_TEXT = 'S'
DEFAULT_ICON_TEXT_COLOR = 'white'
COPY_BUTTON_RESET_DELAY_MS = 2000
THREAD_JOIN_TIMEOUT_SECONDS = 1.0 # For threads on exit

# --- Initialize configurations ---
_initialization_errors = []
try: load_ui_texts()
except Exception as e: _initialization_errors.append(f"UI texts: {e}")
try: load_hotkey_actions(LANGUAGE) # Load with current language
except Exception as e: _initialization_errors.append(f"Hotkey actions: {e}")

if _initialization_errors:
    print("="*30 + " SETTINGS INITIALIZATION ERRORS " + "="*30)
    for _err in _initialization_errors: print(f" - {_err}")
    print("="* (60 + len(" SETTINGS INITIALIZATION ERRORS ")))
    # The main screener.py will catch the import error and show a dialog