# settings.py
import json
import os
import sys
import logging # Add logging import

# --- Import and Setup Logging ---
try:
    from . import logging_config # Use relative import if logging_config is in the same package
except ImportError: # Fallback for direct script run or simpler structures
    import logging_config


# --- Helper functions for path resolution ---
def get_bundle_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        # In development, if settings.py is in 'screener/', this returns 'screener/'
        return os.path.dirname(os.path.abspath(__file__))

_BUNDLE_DIR = get_bundle_dir()
_APP_DIR = get_app_dir() # In dev, this is typically 'screener/' if settings.py is there.

# --- Setup Logging EARLY ---
# Determine where logs should go.
# For both bundled app and dev, we want a 'logs' subdirectory within _APP_DIR.
# _APP_DIR is the location of the executable (frozen) or the script's directory (dev, e.g., 'screener/').
prospective_log_dir = os.path.join(_APP_DIR, 'logs')
final_log_dir = prospective_log_dir # Assume this will be the path

# Try to create the 'logs' subdirectory.
# Note: logging is not fully configured yet, so use print for these initial messages.
if not os.path.exists(prospective_log_dir):
    try:
        os.makedirs(prospective_log_dir)
        print(f"INFO: Log directory created: {prospective_log_dir}")
    except OSError as e:
        # If creating 'logs' subdirectory fails, fall back to logging directly in _APP_DIR.
        print(f"WARNING: Failed to create log directory {prospective_log_dir}: {e}. "
              f"Falling back to logging in {_APP_DIR}")
        final_log_dir = _APP_DIR # _APP_DIR itself should exist.

# Now, call setup_logging with the determined and (hopefully) existing path.
# logging_config.setup_logging will configure the root logger and add handlers.
logging_config.setup_logging(app_dir_path=final_log_dir, level=logging.INFO) # Or logging.DEBUG for more verbose logs

# Now that logging is configured, we can get a logger for this module.
logger = logging.getLogger(__name__)

logger.info("settings.py: _BUNDLE_DIR = %s", _BUNDLE_DIR)
logger.info("settings.py: _APP_DIR = %s", _APP_DIR)
logger.info("settings.py: Log directory used for application logs = %s", final_log_dir)


# --- Project Root ---
# This definition of project_root is specific to settings.py's location.
# If settings.py is in 'screener/', project_root is 'screener/'.
project_root = os.path.dirname(os.path.abspath(__file__))

# --- Load Application Settings from JSON ---
SETTINGS_FILE_PATH = os.path.join(_APP_DIR, 'settings.json')

_DEFAULT_CORE_SETTINGS = {
    "OLLAMA_URL": "http://localhost:11434/api/generate",
    "OLLAMA_MODEL": "gemma3:4b",
    "OLLAMA_TIMEOUT_SECONDS": 180,
    "DEFAULT_LANGUAGE": "en",
    "DEFAULT_THEME": "dark",
    "DEFAULT_FONT_SIZE": 13,
    "ICON_FILENAME_PNG": "icon.png"
}
_app_config = _DEFAULT_CORE_SETTINGS.copy()

try:
    with open(SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
        loaded_json_config = json.load(f)
        _app_config.update(loaded_json_config)
    logger.info("Successfully loaded configurations from '%s'.", SETTINGS_FILE_PATH)
except FileNotFoundError:
    logger.info("Settings file '%s' not found. Using default configurations.", SETTINGS_FILE_PATH)
except json.JSONDecodeError as e:
    logger.warning("Error decoding JSON from '%s': %s. Using default configurations.", SETTINGS_FILE_PATH, e, exc_info=False)
except Exception as e:
    logger.error("An unexpected error occurred while loading '%s': %s. Using default configurations.", SETTINGS_FILE_PATH, e, exc_info=True)

# --- App Instance ---
app_instance = None

# --- Language Configuration ---
SUPPORTED_LANGUAGES = {'en': 'English', 'ru': 'Русский'}
_default_lang_from_config = _app_config.get('DEFAULT_LANGUAGE', _DEFAULT_CORE_SETTINGS['DEFAULT_LANGUAGE']).lower()
DEFAULT_LANGUAGE = _default_lang_from_config if _default_lang_from_config in SUPPORTED_LANGUAGES else _DEFAULT_CORE_SETTINGS['DEFAULT_LANGUAGE']
LANGUAGE = DEFAULT_LANGUAGE
logger.debug("Initial language set to: %s", LANGUAGE)

# --- Theme Configuration ---
_default_theme_from_config = _app_config.get('DEFAULT_THEME', _DEFAULT_CORE_SETTINGS['DEFAULT_THEME']).lower()
DEFAULT_THEME = _default_theme_from_config if _default_theme_from_config in ['light', 'dark'] else _DEFAULT_CORE_SETTINGS['DEFAULT_THEME']
CURRENT_THEME = DEFAULT_THEME
logger.debug("Initial theme set to: %s", CURRENT_THEME)

THEME_COLORS = {
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


def get_theme_color(key, theme=None):
    current_theme_name = theme if theme else CURRENT_THEME
    color = THEME_COLORS.get(current_theme_name, THEME_COLORS[DEFAULT_THEME]).get(key)
    if color is None:
        logger.warning("Theme color key '%s' not found for theme '%s' or default. Falling back to magenta.", key, current_theme_name)
        color = THEME_COLORS[DEFAULT_THEME].get(key, '#FF00FF') # Fallback to default then magenta
    return color

def set_theme(new_theme):
    global CURRENT_THEME
    if new_theme in THEME_COLORS:
        if CURRENT_THEME == new_theme: return True
        CURRENT_THEME = new_theme
        logger.info("Application theme changed to: %s", CURRENT_THEME)
        if app_instance and hasattr(app_instance, 'apply_theme_globally'):
            app_instance.apply_theme_globally()
            theme_name_localized = T(f'tray_theme_{new_theme}_text')
            if app_instance and hasattr(app_instance, 'update_status'):
                app_instance.update_status(
                    T('status_theme_changed_to').format(theme_name=theme_name_localized),
                    get_theme_color('status_ready_fg')
                )
        return True
    logger.warning("Attempted to set unsupported theme '%s'.", new_theme)
    return False

# --- Ollama Configuration ---
OLLAMA_URL = _app_config.get('OLLAMA_URL', _DEFAULT_CORE_SETTINGS['OLLAMA_URL'])
OLLAMA_MODEL = _app_config.get('OLLAMA_MODEL', _DEFAULT_CORE_SETTINGS['OLLAMA_MODEL'])
OLLAMA_TIMEOUT_SECONDS = int(_app_config.get('OLLAMA_TIMEOUT_SECONDS', _DEFAULT_CORE_SETTINGS['OLLAMA_TIMEOUT_SECONDS']))
OLLAMA_DEFAULT_ERROR_MSG_KEY = 'ollama_no_response_content'


# --- Hotkey Configuration ---
HOTKEYS_CONFIG_FILE_NAME = 'hotkeys.json'
_HOTKEYS_FULL_PATH = os.path.join(_BUNDLE_DIR, HOTKEYS_CONFIG_FILE_NAME)
HOTKEY_ACTIONS = {}
DEFAULT_MANUAL_ACTION = 'describe'
CUSTOM_PROMPT_IDENTIFIER = "CUSTOM_PROMPT_PLACEHOLDER"

# --- UI Text Configuration ---
UI_TEXTS_FILE_NAME = 'ui_texts.json'
_UI_TEXTS_FULL_PATH = os.path.join(_BUNDLE_DIR, UI_TEXTS_FILE_NAME)
UI_TEXTS = {}

def load_ui_texts():
    global UI_TEXTS
    UI_TEXTS = {}
    try:
        texts_path = _UI_TEXTS_FULL_PATH
        with open(texts_path, 'r', encoding='utf-8') as f:
            loaded_texts = json.load(f)
        if DEFAULT_LANGUAGE not in loaded_texts:
            msg = f"Default language '{DEFAULT_LANGUAGE}' not found in '{texts_path}'."
            logger.error(msg)
            raise ValueError(msg)
        UI_TEXTS = loaded_texts
        logger.debug("UI texts loaded successfully from %s", texts_path)
    except FileNotFoundError:
        logger.error("UI texts file '%s' not found.", texts_path, exc_info=False)
        raise
    except json.JSONDecodeError as e:
        logger.error("Error decoding JSON from UI texts file '%s': %s", texts_path, e, exc_info=False)
        raise
    except Exception as e:
        logger.error("Unexpected error loading UI texts from '%s': %s", texts_path, e, exc_info=True)
        raise

def set_language(new_lang):
    global LANGUAGE
    if new_lang in SUPPORTED_LANGUAGES:
        LANGUAGE = new_lang
        logger.info("Application language changed to: %s (%s)", LANGUAGE, SUPPORTED_LANGUAGES[new_lang])
        try:
            load_hotkey_actions(LANGUAGE)
            if app_instance and hasattr(app_instance, 'apply_theme_globally'):
                 app_instance.apply_theme_globally(language_changed=True)
            return True
        except Exception as e:
            logger.error("Error reloading after language change to %s: %s", new_lang, e, exc_info=True)
            return False
    logger.warning("Attempted to set unsupported language '%s'.", new_lang)
    return False

def load_hotkey_actions(lang=None):
    global HOTKEY_ACTIONS
    current_lang = lang if lang else LANGUAGE
    HOTKEY_ACTIONS = {}
    try:
        config_path = _HOTKEYS_FULL_PATH
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
            msg = f"DEFAULT_MANUAL_ACTION '{DEFAULT_MANUAL_ACTION}' not found in '{config_path}'."
            logger.error(msg)
            raise ValueError(msg)
        logger.debug("Hotkey actions loaded successfully from %s for language %s", config_path, current_lang)
    except FileNotFoundError:
        logger.error("Hotkey configuration file '%s' not found.", config_path, exc_info=False)
        raise
    except json.JSONDecodeError as e:
        logger.error("Error decoding JSON from hotkey file '%s': %s", config_path, e, exc_info=False)
        raise
    except Exception as e:
        logger.error("Error loading hotkey actions from '%s': %s", config_path, e, exc_info=True)
        raise


def T(key, lang=None):
    current_lang_code = lang if lang else LANGUAGE
    if not UI_TEXTS:
        logger.warning("T function called but UI_TEXTS is uninitialized (key: %s).", key)
        return f"<{key} (UI_TEXTS_UNINITIALIZED)>"
    lang_texts = UI_TEXTS.get(current_lang_code)
    if lang_texts:
        text_value = lang_texts.get(key)
        if text_value is not None: return text_value
    if current_lang_code != DEFAULT_LANGUAGE:
        default_lang_texts = UI_TEXTS.get(DEFAULT_LANGUAGE)
        if default_lang_texts:
            text_value = default_lang_texts.get(key)
            if text_value is not None: return text_value
    logger.warning("UI text key '%s' not found for language '%s' or default language.", key, current_lang_code)
    return f"<{key}>"


# --- UI Style Constants ---
MAIN_WINDOW_GEOMETRY = '450x350'
WINDOW_RESIZABLE_WIDTH = False
WINDOW_RESIZABLE_HEIGHT = False
PADDING_SMALL = 5
PADDING_LARGE = 10
RESPONSE_WINDOW_MIN_WIDTH = 400
RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES = 5
ESTIMATED_CONTROL_FRAME_HEIGHT_PX = 60
ESTIMATED_BUTTON_FRAME_HEIGHT_PX = 50
ESTIMATED_PADDING_PX = 20
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
OVERLAY_BG_COLOR = 'gray'
SELECTION_RECT_COLOR = 'red'
SELECTION_RECT_WIDTH = 2
DEFAULT_FONT_SIZE = int(_app_config.get('DEFAULT_FONT_SIZE', _DEFAULT_CORE_SETTINGS['DEFAULT_FONT_SIZE']))
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 17
CODE_FONT_FAMILY = 'Courier New'
MIN_SELECTION_WIDTH = 10
MIN_SELECTION_HEIGHT = 10
CAPTURE_DELAY = 0.2
SCREENSHOT_FORMAT = 'PNG'
_icon_filename_from_config = _app_config.get('ICON_FILENAME_PNG', _DEFAULT_CORE_SETTINGS['ICON_FILENAME_PNG'])
ICON_PATH = os.path.join(_BUNDLE_DIR, _icon_filename_from_config)
TRAY_ICON_NAME = 'screener_ollama_app'
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


# --- Initialize configurations ---
_initialization_errors = []
logger.info("Starting initialization of UI texts and hotkey actions...")
try: load_ui_texts()
except Exception as e:
    err_msg = f"UI texts ({UI_TEXTS_FILE_NAME}): {e}"
    logger.critical("CRITICAL: Failed to load UI texts: %s", err_msg, exc_info=False)
    _initialization_errors.append(err_msg)

try: load_hotkey_actions(LANGUAGE)
except Exception as e:
    err_msg = f"Hotkey actions ({HOTKEYS_CONFIG_FILE_NAME}): {e}"
    logger.critical("CRITICAL: Failed to load hotkey actions: %s", err_msg, exc_info=False)
    _initialization_errors.append(err_msg)

if _initialization_errors:
    logger.error("="*30 + " SETTINGS INITIALIZATION ERRORS " + "="*30)
    for _err in _initialization_errors: logger.error(" - %s", _err)
    logger.error("="* (60 + len(" SETTINGS INITIALIZATION ERRORS ") +2)) # Corrected length
else:
    logger.info("UI texts and hotkey actions initialized successfully.")