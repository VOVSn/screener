# settings.py
import json
import os

# --- App Instance (for callbacks like theme update) ---
# This will be set by ScreenshotApp instance
app_instance = None

# --- Language Configuration ---
SUPPORTED_LANGUAGES = { # Unchanged
    'en': 'English',
    'ru': 'Русский'
}
DEFAULT_LANGUAGE = 'en'
LANGUAGE = DEFAULT_LANGUAGE

# --- Theme Configuration ---
DEFAULT_THEME = 'light'
CURRENT_THEME = DEFAULT_THEME # Can be 'light' or 'dark'

THEME_COLORS = {
    'light': {
        'app_bg': '#F0F0F0',
        'app_fg': '#000000',
        'text_bg': '#FFFFFF',
        'text_fg': '#000000',
        'text_disabled_bg': '#F0F0F0', # For disabled Text widget background
        'button_bg': '#E1E1E1',
        'button_fg': '#000000',
        'button_active_bg': '#ECECEC',
        'entry_bg': '#FFFFFF',
        'entry_fg': '#000000',
        'entry_select_bg': '#0078D7',
        'entry_select_fg': '#FFFFFF',
        'label_fg': '#000000',
        'disabled_fg': '#A3A3A3',
        'status_default_fg': 'gray',
        'status_ready_fg': 'blue',
        'status_processing_fg': 'darkorange',
        'status_error_fg': 'red',
        'code_block_bg': '#F5F5F5', # Slightly different from app_bg for visibility
        'code_block_fg': '#000000',
        'code_block_border': '#DDDDDD',
        'frame_bg': '#F0F0F0',
        'scrollbar_bg': '#F0F0F0', # Used for tk.Scrollbar
        'scrollbar_trough': '#E0E0E0', # Used for tk.Scrollbar
        'scale_trough': '#D3D3D3', # For ttk.Scale trough
        'separator_color': '#CCCCCC',
        'md_h1_fg': '#000080', # Navy for H1
        'md_h2_fg': '#00008B', # DarkBlue for H2
        'md_list_item_fg': '#228B22', # ForestGreen for list items
        'md_inline_code_bg': '#E0E0E0',
        'md_inline_code_fg': '#C7254E', # Similar to Bootstrap's code color
        'python_keyword_fg': '#0000FF', # Blue for keywords
        'python_string_fg': '#008000',  # Green for strings
        'python_comment_fg': '#808080', # Gray for comments
        'python_number_fg': '#A52A2A',  # Brown for numbers
        'python_function_fg': '#800080', # Purple for function names (basic) # For ttk.Separator
    },
    'dark': {
        'app_bg': '#2B2B2B',
        'app_fg': '#BBBBBB',
        'text_bg': '#1E1E1E',
        'text_fg': '#D4D4D4',
        'text_disabled_bg': '#252525', # For disabled Text widget background
        'button_bg': '#3E3E3E',
        'button_fg': '#E0E0E0',
        'button_active_bg': '#4F4F4F',
        'entry_bg': '#3C3C3C',
        'entry_fg': '#D4D4D4',
        'entry_select_bg': '#007ACC',
        'entry_select_fg': '#FFFFFF',
        'label_fg': '#E0E0E0',
        'disabled_fg': '#7A7A7A',
        'status_default_fg': '#999999',
        'status_ready_fg': '#569CD6',
        'status_processing_fg': '#CE9178',
        'status_error_fg': '#F44747',
        'code_block_bg': '#252525', # Slightly different from app_bg
        'code_block_fg': '#D4D4D4',
        'code_block_border': '#444444',
        'frame_bg': '#2B2B2B',
        'scrollbar_bg': '#3E3E3E', # Used for tk.Scrollbar
        'scrollbar_trough': '#2B2B2B', # Used for tk.Scrollbar
        'scale_trough': '#4A4A4A', # For ttk.Scale trough
        'separator_color': '#444444', # For ttk.Separator
        'md_h1_fg': '#569CD6',
        'md_h2_fg': '#4EC9B0',
        'md_list_item_fg': '#B5CEA8',
        'md_inline_code_bg': '#3A3A3A',
        'md_inline_code_fg': '#D69D85',
        'python_keyword_fg': '#569CD6', # Light blue
        'python_string_fg': '#CE9178',  # Light orange/brown
        'python_comment_fg': '#6A9955', # Darker green
        'python_number_fg': '#B5CEA8',  # Light green/blue
        'python_function_fg': '#DCDCAA', # Light yellow for function names
    }
}

def get_theme_color(key, theme=None):
    """Gets a color value for the given key from the current/specified theme."""
    current_theme_name = theme if theme else CURRENT_THEME
    # Fallback to default theme if current theme or key is missing
    color = THEME_COLORS.get(current_theme_name, THEME_COLORS[DEFAULT_THEME]).get(key)
    if color is None:
        color = THEME_COLORS[DEFAULT_THEME].get(key, '#FF00FF') # Magenta for missing key
        # print(f"Warning: Color key '{key}' not found in theme '{current_theme_name}' or default. Using fallback.")
    return color

def set_theme(new_theme):
    """Sets the application theme and triggers UI updates."""
    global CURRENT_THEME
    if new_theme in THEME_COLORS:
        if CURRENT_THEME == new_theme:
            return True # No change needed

        CURRENT_THEME = new_theme
        print(f"Application theme changed to: {CURRENT_THEME}")
        if app_instance and hasattr(app_instance, 'apply_theme_globally'):
            app_instance.apply_theme_globally() # Notify app to update UI
            # Optionally, update status bar or log
            theme_name_localized = T(f'tray_theme_{new_theme}_text')
            if app_instance and hasattr(app_instance, 'update_status'):
                app_instance.update_status(
                    T('status_theme_changed_to').format(theme_name=theme_name_localized),
                    get_theme_color('status_ready_fg')
                )
        return True
    print(f"Warning: Attempted to set unsupported theme '{new_theme}'.")
    return False

# --- Ollama Configuration --- (Unchanged)
OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'gemma3:12b'
OLLAMA_TIMEOUT_SECONDS = 120
OLLAMA_DEFAULT_ERROR_MSG_KEY = 'ollama_no_response_content'

# --- Hotkey Configuration --- (Unchanged)
HOTKEYS_CONFIG_FILE = 'hotkeys.json'
HOTKEY_ACTIONS = {}
DEFAULT_MANUAL_ACTION = 'describe'
CUSTOM_PROMPT_IDENTIFIER = "CUSTOM_PROMPT_PLACEHOLDER"

# --- UI Text Configuration --- (Unchanged, assuming ui_texts.json setup from previous step)
UI_TEXTS_FILE = 'ui_texts.json'
UI_TEXTS = {}

def load_ui_texts(): # Unchanged
    global UI_TEXTS
    UI_TEXTS = {}
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        texts_path = os.path.join(base_dir, UI_TEXTS_FILE)
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

def set_language(new_lang): # Modified to potentially re-apply theme if texts change
    global LANGUAGE
    if new_lang in SUPPORTED_LANGUAGES:
        LANGUAGE = new_lang
        print(f"Application language changed to: {LANGUAGE} ({SUPPORTED_LANGUAGES[new_lang]})")
        try:
            load_hotkey_actions(LANGUAGE)
            if app_instance and hasattr(app_instance, 'apply_theme_globally'):
                 # UI texts might have changed, re-apply to ensure correct display
                 app_instance.apply_theme_globally(language_changed=True)
            return True
        except Exception as e:
            print(f"Error reloading after language change: {e}")
            return False
    print(f"Warning: Attempted to set unsupported language '{new_lang}'.")
    return False

def load_hotkey_actions(lang=None): # Unchanged
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
        if DEFAULT_MANUAL_ACTION not in HOTKEY_ACTIONS:
            raise ValueError(f"DEFAULT_MANUAL_ACTION '{DEFAULT_MANUAL_ACTION}' not found.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Hotkey configuration file '{config_path}' not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from '{config_path}': {e}")
    except Exception as e:
        raise Exception(f"Error loading hotkey actions from '{config_path}': {e}")

def T(key, lang=None): # Unchanged
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


# --- UI Style (Constants for geometry, padding, etc. Some color constants removed/replaced by theme) ---
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
# STATUS_COLOR_DEFAULT, STATUS_COLOR_READY, etc. are now fetched via get_theme_color
# CODE_BLOCK_BG_COLOR, etc. are now fetched via get_theme_color
CODE_FONT_SIZE_OFFSET = -1 # Kept for font logic
OVERLAY_ALPHA = 0.4 # Kept for capture overlay
OVERLAY_CURSOR = 'cross' # Kept
OVERLAY_BG_COLOR = 'gray' # Kept, could be themed if desired but often kept simple
SELECTION_RECT_COLOR = 'red' # Kept
SELECTION_RECT_WIDTH = 2 # Kept
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
DEFAULT_ICON_WIDTH = 64 # Default tray icon visual parameters
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

# --- Initialize configurations --- (Unchanged from previous refactor)
_initialization_errors = []
try: load_ui_texts()
except Exception as e: _initialization_errors.append(f"UI texts: {e}")
try: load_hotkey_actions(LANGUAGE)
except Exception as e: _initialization_errors.append(f"Hotkey actions: {e}")

if _initialization_errors:
    print("="*30 + " SETTINGS INITIALIZATION ERRORS " + "="*30)
    for _err in _initialization_errors: print(f" - {_err}")
    print("="* (60 + len(" SETTINGS INITIALIZATION ERRORS ")))
    # Error propagation will be handled by screener.py on import