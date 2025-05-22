# settings.py
import json
import os
import sys
import logging

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
prospective_log_dir = os.path.join(_APP_DIR, 'logs')
final_log_dir = prospective_log_dir

if not os.path.exists(prospective_log_dir):
    try:
        os.makedirs(prospective_log_dir, exist_ok=True)
        # print(f"INFO: Log directory created: {prospective_log_dir}") # Logger not fully ready for file here
    except OSError as e:
        # print(f"WARNING: Failed to create log directory {prospective_log_dir}: {e}. Falling back to logging in {_APP_DIR}")
        final_log_dir = _APP_DIR

logging_config.setup_logging(app_dir_path=final_log_dir, level=logging.INFO)
logger = logging.getLogger(__name__) # Now logger is configured

logger.info("settings.py: _BUNDLE_DIR = %s", _BUNDLE_DIR)
logger.info("settings.py: _APP_DIR = %s", _APP_DIR)
logger.info("settings.py: Log directory used for application logs = %s", final_log_dir)


# --- Configuration Loading and Saving ---
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
_app_config = {} # Will be populated by load_app_config

def save_app_config():
    """Saves the current _app_config to settings.json."""
    global _app_config
    try:
        # Ensure the directory for settings.json exists (it's _APP_DIR)
        settings_file_dir = os.path.dirname(SETTINGS_FILE_PATH)
        if not os.path.exists(settings_file_dir):
             os.makedirs(settings_file_dir, exist_ok=True)
             logger.info(f"Created directory for settings file: {settings_file_dir}")

        with open(SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(_app_config, f, indent=4, ensure_ascii=False)
        logger.info("Application configuration saved to '%s'.", SETTINGS_FILE_PATH)
    except Exception as e:
        logger.error("Failed to save application configuration to '%s': %s", SETTINGS_FILE_PATH, e, exc_info=True)

def load_app_config():
    """Loads configuration from settings.json, falling back to defaults and creating/repairing the file if necessary."""
    global _app_config
    base_defaults = _DEFAULT_CORE_SETTINGS.copy()
    
    try:
        with open(SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
            loaded_json_config = json.load(f)
        
        _app_config = base_defaults # Start with base defaults
        _app_config.update(loaded_json_config) # Override with loaded values
        
        logger.info("Successfully loaded configurations from '%s'.", SETTINGS_FILE_PATH)
        
        resave_needed = False
        for key, default_value in _DEFAULT_CORE_SETTINGS.items():
            if key not in loaded_json_config:
                _app_config[key] = default_value # Ensure default is in current config if missing from file
                resave_needed = True
                logger.info("Key '%s' was missing from settings.json, added from defaults.", key)
        
        if resave_needed:
            logger.info("Settings file structure updated (e.g., missing keys added). Resaving canonical configuration.")
            save_app_config()

    except FileNotFoundError:
        logger.info("Settings file '%s' not found. Using default configurations and creating the file.", SETTINGS_FILE_PATH)
        _app_config = base_defaults.copy()
        save_app_config() 
    except json.JSONDecodeError as e:
        logger.warning("Error decoding JSON from '%s': %s. File is corrupt. Resetting to default configurations and recreating the file.", SETTINGS_FILE_PATH, e, exc_info=False)
        _app_config = base_defaults.copy()
        save_app_config() 
    except Exception as e:
        logger.error("An unexpected error occurred while loading '%s': %s. Using default configurations and attempting to recreate the file.", SETTINGS_FILE_PATH, e, exc_info=True)
        _app_config = base_defaults.copy()
        save_app_config()

load_app_config() # Load configuration early

# --- Populate global settings variables from _app_config ---
OLLAMA_URL = _app_config['OLLAMA_URL']
OLLAMA_MODEL = _app_config['OLLAMA_MODEL']
OLLAMA_TIMEOUT_SECONDS = int(_app_config['OLLAMA_TIMEOUT_SECONDS'])
DEFAULT_FONT_SIZE = int(_app_config['DEFAULT_FONT_SIZE'])
_icon_filename_from_config = _app_config['ICON_FILENAME_PNG']

# --- Language Configuration ---
SUPPORTED_LANGUAGES = {'en': 'English', 'ru': 'Русский'}
LANGUAGE = _app_config.get('DEFAULT_LANGUAGE', _DEFAULT_CORE_SETTINGS['DEFAULT_LANGUAGE']).lower()
if LANGUAGE not in SUPPORTED_LANGUAGES:
    logger.warning("Invalid language '%s' in settings. Resetting to '%s' and saving.", LANGUAGE, _DEFAULT_CORE_SETTINGS['DEFAULT_LANGUAGE'])
    LANGUAGE = _DEFAULT_CORE_SETTINGS['DEFAULT_LANGUAGE']
    _app_config['DEFAULT_LANGUAGE'] = LANGUAGE
    save_app_config()
logger.debug("Initial language set to: %s (from effective config)", LANGUAGE)

# --- Theme Configuration ---
CURRENT_THEME = _app_config.get('DEFAULT_THEME', _DEFAULT_CORE_SETTINGS['DEFAULT_THEME']).lower()
THEME_OPTIONS = ['light', 'dark']
if CURRENT_THEME not in THEME_OPTIONS:
    logger.warning("Invalid theme '%s' in settings. Resetting to '%s' and saving.", CURRENT_THEME, _DEFAULT_CORE_SETTINGS['DEFAULT_THEME'])
    CURRENT_THEME = _DEFAULT_CORE_SETTINGS['DEFAULT_THEME']
    _app_config['DEFAULT_THEME'] = CURRENT_THEME
    save_app_config()
logger.debug("Initial theme set to: %s (from effective config)", CURRENT_THEME)

THEME_COLORS = {
    'light': {
        'app_bg': '#F0F0F0', 'app_fg': '#000000', 'text_bg': '#FFFFFF', 'text_fg': '#000000',
        'text_disabled_bg': '#F0F0F0', 'button_bg': '#E1E1E1', 'button_fg': '#000000',
        'button_active_bg': '#ECECEC', 
        'button_exit_bg': '#B0B0B0', 'button_exit_fg': '#000000', # Darker for light theme
        'button_exit_active_bg': '#C8C8C8', # Slightly lighter active for exit button
        'entry_bg': '#FFFFFF', 'entry_fg': '#000000',
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
        'button_active_bg': '#4F4F4F', 
        'button_exit_bg': '#2F2F2F', 'button_exit_fg': '#C0C0C0', # Darker for dark theme
        'button_exit_active_bg': '#3A3A3A', # Slightly lighter active for exit button
        'entry_bg': '#3C3C3C', 'entry_fg': '#D4D4D4',
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
    global CURRENT_THEME
    ultimate_fallback_theme_name = _DEFAULT_CORE_SETTINGS['DEFAULT_THEME']
    current_theme_name_to_use = theme if theme else CURRENT_THEME

    if current_theme_name_to_use not in THEME_COLORS:
        logger.warning(f"get_theme_color: Invalid theme name '{current_theme_name_to_use}'. Using ultimate fallback '{ultimate_fallback_theme_name}'.")
        current_theme_name_to_use = ultimate_fallback_theme_name
    
    theme_dict = THEME_COLORS[current_theme_name_to_use]
    color = theme_dict.get(key)
    
    if color is None:
        logger.warning("Theme color key '%s' not found for theme '%s'. Trying ultimate fallback theme '%s' for this key.", key, current_theme_name_to_use, ultimate_fallback_theme_name)
        color = THEME_COLORS[ultimate_fallback_theme_name].get(key, '#FF00FF') # Magenta if key totally missing
        if color == '#FF00FF':
            logger.error("CRITICAL: Theme color key '%s' is missing from ALL themes, including fallback. Defaulting to Magenta.", key)
    return color

def set_theme(new_theme):
    global CURRENT_THEME, _app_config
    new_theme_lower = new_theme.lower()
    if new_theme_lower in THEME_OPTIONS:
        if CURRENT_THEME == new_theme_lower and _app_config.get('DEFAULT_THEME') == new_theme_lower:
            logger.debug("Theme '%s' is already active and saved.", new_theme_lower)
            return True

        CURRENT_THEME = new_theme_lower
        _app_config['DEFAULT_THEME'] = new_theme_lower
        save_app_config()
        logger.info("Application theme changed to: %s and saved.", CURRENT_THEME)
        return True
    logger.warning("Attempted to set unsupported theme '%s'. Valid themes: %s", new_theme, THEME_OPTIONS)
    return False

OLLAMA_DEFAULT_ERROR_MSG_KEY = 'ollama_no_response_content'

HOTKEYS_CONFIG_FILE_NAME = 'hotkeys.json'
_HOTKEYS_FULL_PATH = os.path.join(_BUNDLE_DIR, HOTKEYS_CONFIG_FILE_NAME)
HOTKEY_ACTIONS = {}
DEFAULT_MANUAL_ACTION = 'describe'
CUSTOM_PROMPT_IDENTIFIER = "CUSTOM_PROMPT_PLACEHOLDER"

UI_TEXTS_FILE_NAME = 'ui_texts.json'
_UI_TEXTS_FULL_PATH = os.path.join(_BUNDLE_DIR, UI_TEXTS_FILE_NAME)
UI_TEXTS = {}

def load_ui_texts():
    global UI_TEXTS, LANGUAGE
    UI_TEXTS = {}
    try:
        texts_path = _UI_TEXTS_FULL_PATH
        with open(texts_path, 'r', encoding='utf-8') as f:
            loaded_texts = json.load(f)
        
        core_default_lang = _DEFAULT_CORE_SETTINGS['DEFAULT_LANGUAGE']
        if LANGUAGE not in loaded_texts and core_default_lang not in loaded_texts:
            msg = (f"Critical: Neither current language '{LANGUAGE}' nor core default language "
                   f"'{core_default_lang}' found in UI texts file '{texts_path}'.")
            logger.error(msg)
            raise ValueError(msg)
        elif LANGUAGE not in loaded_texts:
             logger.warning(f"Current language '{LANGUAGE}' not found in UI texts file. Using core default '{core_default_lang}'.")
        
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
    global LANGUAGE, _app_config
    new_lang_lower = new_lang.lower()
    if new_lang_lower in SUPPORTED_LANGUAGES:
        if LANGUAGE == new_lang_lower and _app_config.get('DEFAULT_LANGUAGE') == new_lang_lower:
            logger.debug("Language '%s' is already active and saved.", new_lang_lower)
            return True

        LANGUAGE = new_lang_lower
        _app_config['DEFAULT_LANGUAGE'] = new_lang_lower
        save_app_config()
        logger.info("Application language changed to: %s (%s) and saved.", LANGUAGE, SUPPORTED_LANGUAGES[LANGUAGE])
        try:
            load_hotkey_actions(LANGUAGE)
            return True
        except Exception as e:
            logger.error("Error reloading hotkey actions after language change to %s: %s", new_lang_lower, e, exc_info=True)
            return False
    logger.warning("Attempted to set unsupported language '%s'. Supported: %s", new_lang, list(SUPPORTED_LANGUAGES.keys()))
    return False

def load_hotkey_actions(lang_code_to_use=None):
    global HOTKEY_ACTIONS, LANGUAGE
    current_lang_for_hotkeys = lang_code_to_use if lang_code_to_use else LANGUAGE
    core_default_lang = _DEFAULT_CORE_SETTINGS['DEFAULT_LANGUAGE']
    
    HOTKEY_ACTIONS = {}
    try:
        config_path = _HOTKEYS_FULL_PATH
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_actions = json.load(f)

        for action_name, details in raw_actions.items():
            prompt_data = details.get('prompt')
            desc_data = details.get('description')
            hotkey_val = details.get('hotkey')

            if not hotkey_val:
                logger.warning(f"Hotkey value missing for action '{action_name}'. Skipping.")
                continue

            if isinstance(prompt_data, dict):
                localized_prompt = prompt_data.get(current_lang_for_hotkeys, prompt_data.get(core_default_lang))
                if localized_prompt is None: localized_prompt = f"Prompt missing for {action_name}"
            elif isinstance(prompt_data, str): localized_prompt = prompt_data
            else: localized_prompt = f"Invalid/Missing prompt for {action_name}"

            if isinstance(desc_data, dict):
                localized_description = desc_data.get(current_lang_for_hotkeys, desc_data.get(core_default_lang))
                if localized_description is None: localized_description = action_name
            elif isinstance(desc_data, str): localized_description = desc_data
            else: localized_description = action_name

            HOTKEY_ACTIONS[action_name] = {
                'hotkey': hotkey_val,
                'prompt': localized_prompt,
                'description': localized_description
            }
        
        if DEFAULT_MANUAL_ACTION not in HOTKEY_ACTIONS:
            # Check if custom prompt placeholder can be a fallback, though not ideal for this key
            custom_action_key = None
            for k, v in HOTKEY_ACTIONS.items():
                if v.get('prompt') == CUSTOM_PROMPT_IDENTIFIER:
                    custom_action_key = k
                    break
            
            if not custom_action_key and 'describe' not in HOTKEY_ACTIONS: # Last resort before error
                msg = (f"Critical: DEFAULT_MANUAL_ACTION '{DEFAULT_MANUAL_ACTION}' not found "
                       f"after localizing for '{current_lang_for_hotkeys}', and no 'describe' or custom prompt action available. Check '{config_path}'.")
                logger.error(msg)
                raise ValueError(msg)
            elif DEFAULT_MANUAL_ACTION not in HOTKEY_ACTIONS:
                 logger.warning(f"DEFAULT_MANUAL_ACTION '{DEFAULT_MANUAL_ACTION}' not found. Tray/UI may use 'describe' or custom prompt as fallback if available.")


        logger.debug("Hotkey actions loaded for language %s", current_lang_for_hotkeys)

    except FileNotFoundError:
        logger.error("Hotkey file '%s' not found.", config_path, exc_info=False); raise
    except json.JSONDecodeError as e:
        logger.error("Error decoding hotkey file '%s': %s", config_path, e, exc_info=False); raise
    except Exception as e:
        logger.error("Error loading hotkey actions from '%s': %s", config_path, e, exc_info=True); raise

def T(key, lang=None):
    global LANGUAGE, UI_TEXTS
    target_lang = lang if lang else LANGUAGE
    core_default_lang = _DEFAULT_CORE_SETTINGS['DEFAULT_LANGUAGE']

    if not UI_TEXTS:
        logger.warning("T(key='%s'): UI_TEXTS uninitialized. Fallback.", key)
        return f"<{key} (UI_TEXTS_UNINIT)>"

    if target_lang in UI_TEXTS and key in UI_TEXTS[target_lang]:
        return UI_TEXTS[target_lang][key]
    if target_lang != core_default_lang and core_default_lang in UI_TEXTS and key in UI_TEXTS[core_default_lang]:
        logger.debug("T(key='%s'): Used core default lang '%s'.", key, core_default_lang)
        return UI_TEXTS[core_default_lang][key]
    logger.warning("T(key='%s'): Not found for lang '%s' or core default. Placeholder.", key, target_lang)
    return f"<{key}>"

# --- Constants (Application specific, not typically in settings.json) ---
MAIN_WINDOW_GEOMETRY = '280x500'
WINDOW_RESIZABLE_WIDTH = False
WINDOW_RESIZABLE_HEIGHT = False # Consider True if single column buttons make it too tall
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
FONT_SIZE_LABEL_WIDTH = 11
CODE_FONT_SIZE_OFFSET = -1
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 17
CODE_FONT_FAMILY = 'Courier New'
MIN_SELECTION_WIDTH = 10
MIN_SELECTION_HEIGHT = 10
CAPTURE_DELAY = 0.2
SCREENSHOT_FORMAT = 'PNG'
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

# --- Overlay Specific Constants (Used by capture.py) ---
OVERLAY_ALPHA = 0.4
OVERLAY_CURSOR = 'cross'
OVERLAY_BG_COLOR = 'gray'
SELECTION_RECT_COLOR = 'red'
SELECTION_RECT_WIDTH = 2
# MIN_SELECTION_WIDTH and MIN_SELECTION_HEIGHT are already defined above, they are shared.
# CAPTURE_DELAY is also already defined above.


# --- Initial Load of Language-Dependent Resources ---
_initialization_errors = []
logger.info("Starting initial load of UI texts and hotkey actions using LANGUAGE: %s", LANGUAGE)

try: load_ui_texts()
except Exception as e:
    err_msg = f"Failed to load UI texts ({UI_TEXTS_FILE_NAME}): {type(e).__name__} - {e}"
    logger.critical(err_msg, exc_info=False)
    _initialization_errors.append(err_msg)

try: load_hotkey_actions()
except Exception as e:
    err_msg = f"Failed to load hotkey actions ({HOTKEYS_CONFIG_FILE_NAME}): {type(e).__name__} - {e}"
    logger.critical(err_msg, exc_info=False)
    _initialization_errors.append(err_msg)

if _initialization_errors:
    logger.error("="*30 + " CRITICAL SETTINGS INITIALIZATION ERRORS " + "="*30)
    for _err in _initialization_errors: logger.error(" - %s", _err)
    logger.error("="* (60 + len(" CRITICAL SETTINGS INITIALIZATION ERRORS ") +2))
else:
    logger.info("UI texts and hotkey actions initialized successfully for language: %s.", LANGUAGE)