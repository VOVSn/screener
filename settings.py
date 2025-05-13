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

def set_language(new_lang):
    """Sets the application language and reloads language-dependent settings."""
    global LANGUAGE
    if new_lang in SUPPORTED_LANGUAGES:
        LANGUAGE = new_lang
        print(f"Application language changed to: {LANGUAGE} ({SUPPORTED_LANGUAGES[new_lang]})")
        try:
            load_hotkey_actions(LANGUAGE) # Reload hotkeys with new language prompts
            return True
        except Exception as e:
            print(f"Error reloading hotkey actions after language change: {e}")
            # Potentially revert language change or handle error more gracefully
            return False # Indicate failure
    print(f"Warning: Attempted to set unsupported language '{new_lang}'.")
    return False

def load_hotkey_actions(lang=None):
    """Loads hotkey actions from the JSON file and localizes them."""
    global HOTKEY_ACTIONS
    current_lang = lang if lang else LANGUAGE # Use provided lang or current global LANGUAGE

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
        # print(f"Hotkey actions loaded/reloaded and localized for '{current_lang}'.")

        if DEFAULT_MANUAL_ACTION not in HOTKEY_ACTIONS:
            # This check is important. If it fails, the app might not work correctly.
            # Raise an error that can be caught by the main app for a user message.
            raise ValueError(
                f"DEFAULT_MANUAL_ACTION '{DEFAULT_MANUAL_ACTION}' "
                f"not found in loaded HOTKEY_ACTIONS keys from '{config_path}' for language '{current_lang}'."
            )

    except FileNotFoundError:
        raise FileNotFoundError(f"Hotkey configuration file '{config_path}' not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from '{config_path}': {e}")
    except Exception as e: # Catch any other exception during loading
        raise Exception(f"Error loading hotkey actions from '{config_path}': {e}")


# --- UI Text (Internationalized) ---
UI_TEXTS = {
    'en': {
        'app_title': 'Screenshot to Ollama',
        'main_label_text': 'Screenshot Capture & Analysis',
        'capture_button_text': 'Capture Region Manually',
        'custom_prompt_label': 'Custom Prompt:',
        'hotkeys_list_label': 'Active Hotkeys:',
        'exit_button_text': 'Exit',
        'exit_button_text_tray': 'Exit Completely',
        'initial_status_text': 'Initializing...',
        'processing_status_text': 'Processing with Ollama...',
        'ready_status_text_no_tray': 'Ready. Hotkeys active.',
        'ready_status_text_tray': 'Ready. Hotkeys active or use tray.',
        'response_window_title': 'Ollama Analysis',
        'copy_button_text': 'Copy Response',
        'copied_button_text': 'Copied!',
        'close_button_text': 'Close',
        'font_size_label_format': 'Size: {size}pt',
        'error_preparing_image_status': 'Error preparing image.',
        'ollama_conn_failed_status': 'Ollama connection failed.',
        'ollama_timeout_status': 'Ollama request timed out.',
        'ollama_request_failed_status': 'Ollama request failed.',
        'ollama_no_response_content': 'No response content found in JSON.',
        'unexpected_error_status': 'Unexpected error.',
        'hotkey_failed_status': 'Hotkey listener failed!',
        'icon_load_fail_status': "Tray icon failed to load.",
        'window_hidden_status': 'Window hidden to system tray.',
        'window_restored_status': 'Window restored from system tray.',
        'exiting_app_status': 'Exiting application...',
        'stopping_hotkeys_status': 'Stopping hotkey listener...',
        'stopping_tray_status': 'Stopping system tray icon...',
        'app_exit_complete_status': 'Application exit sequence complete.',
        'app_finished_status': 'Screenshot Tool finished.',
        'dialog_settings_error_title': 'Settings Error',
        'dialog_settings_error_msg': 'Error loading settings.py or related files:\n{error}',
        'dialog_hotkey_json_error_title': 'Hotkey Config Error',
        'dialog_hotkey_json_error_msg': "Error loading or parsing '{file}':\n{error}",
        'dialog_screenshot_error_title': 'Screenshot Error',
        'dialog_internal_error_title': 'Internal Error',
        'dialog_internal_error_msg': 'Capture prompt was lost or invalid.',
        'dialog_processing_error_title': 'Processing Error',
        'dialog_ollama_conn_error_title': 'Ollama Connection Error',
        'dialog_ollama_conn_error_msg': ('Connection Error: Could not connect to Ollama at '
                                         '{url}. Is it running?'),
        'dialog_ollama_timeout_title': 'Ollama Timeout',
        'dialog_ollama_timeout_msg': ('Timeout: Ollama at {url} took too long.'),
        'dialog_ollama_error_title': 'Ollama Error',
        'dialog_unexpected_error_title': 'Unexpected Error',
        'dialog_hotkey_error_title': 'Hotkey Error',
        'dialog_hotkey_error_msg': (
            'Failed to set up hotkey listener: {error}\n\nCommon causes:\n'
            '- Incorrect hotkey format in hotkeys.json.\n'
            '- Accessibility/Input permissions missing (macOS/Linux).\n'
            '- Another app using the same hotkey.'
        ),
        'dialog_icon_warning_title': 'Icon Warning',
        'dialog_icon_warning_msg': ("Tray icon file '{path}' not found.\n"
                                  "A default icon will be used. Continue?"),
        'dialog_icon_error_title': 'Icon Error',
        'dialog_icon_error_msg': ("Error loading tray icon '{path}': {error}\n"
                                 "A default icon will be used. Continue?"),
        'tray_show_window_text': 'Show Window',
        'tray_capture_text': 'Capture Region',
        'tray_exit_text': 'Exit',
        'tray_language_text': 'Language', # New
        'custom_prompt_empty_warning': 'Custom prompt field is empty. Please enter a prompt.',
        'dialog_warning_title': 'Warning',
        'status_lang_changed_to': 'Language changed to {lang_name}.', # New
    },
    'ru': {
        'app_title': 'Скриншот в Ollama',
        'main_label_text': 'Захват и анализ скриншотов',
        'capture_button_text': 'Захватить область вручную',
        'custom_prompt_label': 'Свой запрос:',
        'hotkeys_list_label': 'Активные горячие клавиши:',
        'exit_button_text': 'Выход',
        'exit_button_text_tray': 'Выйти полностью',
        'initial_status_text': 'Инициализация...',
        'processing_status_text': 'Обработка с Ollama...',
        'ready_status_text_no_tray': 'Готово. Горячие клавиши активны.',
        'ready_status_text_tray': 'Готово. Клавиши активны / меню трея.',
        'response_window_title': 'Анализ от Ollama',
        'copy_button_text': 'Копировать ответ',
        'copied_button_text': 'Скопировано!',
        'close_button_text': 'Закрыть',
        'font_size_label_format': 'Размер: {size}pt',
        'error_preparing_image_status': 'Ошибка подготовки изображения.',
        'ollama_conn_failed_status': 'Ошибка подключения к Ollama.',
        'ollama_timeout_status': 'Тайм-аут запроса к Ollama.',
        'ollama_request_failed_status': 'Ошибка запроса к Ollama.',
        'ollama_no_response_content': 'Содержимое ответа не найдено в JSON.',
        'unexpected_error_status': 'Непредвиденная ошибка.',
        'hotkey_failed_status': 'Ошибка слушателя горячих клавиш!',
        'icon_load_fail_status': "Ошибка загрузки иконки трея.",
        'window_hidden_status': 'Окно скрыто в системный трей.',
        'window_restored_status': 'Окно восстановлено из трея.',
        'exiting_app_status': 'Завершение приложения...',
        'stopping_hotkeys_status': 'Остановка слушателя горячих клавиш...',
        'stopping_tray_status': 'Остановка иконки системного трея...',
        'app_exit_complete_status': 'Последовательность выхода из приложения завершена.',
        'app_finished_status': 'Инструмент Скриншот закончил работу.',
        'dialog_settings_error_title': 'Ошибка настроек',
        'dialog_settings_error_msg': 'Ошибка загрузки settings.py или связанных файлов:\n{error}',
        'dialog_hotkey_json_error_title': 'Ошибка конфиг. горячих клавиш',
        'dialog_hotkey_json_error_msg': "Ошибка загрузки или парсинга '{file}':\n{error}",
        'dialog_screenshot_error_title': 'Ошибка скриншота',
        'dialog_internal_error_title': 'Внутренняя ошибка',
        'dialog_internal_error_msg': 'Запрос для захвата был утерян или недействителен.',
        'dialog_processing_error_title': 'Ошибка обработки',
        'dialog_ollama_conn_error_title': 'Ошибка подключения Ollama',
        'dialog_ollama_conn_error_msg': ('Ошибка подключения: Не удалось подключиться к Ollama по адресу '
                                         '{url}. Он запущен?'),
        'dialog_ollama_timeout_title': 'Тайм-аут Ollama',
        'dialog_ollama_timeout_msg': ('Тайм-аут: Ollama по адресу {url} отвечал слишком долго.'),
        'dialog_ollama_error_title': 'Ошибка Ollama',
        'dialog_unexpected_error_title': 'Непредвиденная ошибка',
        'dialog_hotkey_error_title': 'Ошибка горячих клавиш',
        'dialog_hotkey_error_msg': (
            'Не удалось настроить слушатель горячих клавиш: {error}\n\nВозможные причины:\n'
            '- Неверный формат горячей клавиши в hotkeys.json.\n'
            '- Отсутствуют права доступа (macOS/Linux).\n'
            '- Другое приложение использует ту же горячую клавишу.'
        ),
        'dialog_icon_warning_title': 'Предупреждение об иконке',
        'dialog_icon_warning_msg': ("Файл иконки трея '{path}' не найден.\n"
                                  "Будет использована иконка по умолчанию. Продолжить?"),
        'dialog_icon_error_title': 'Ошибка иконки',
        'dialog_icon_error_msg': ("Ошибка загрузки иконки трея '{path}': {error}\n"
                                 "Будет использована иконка по умолчанию. Продолжить?"),
        'tray_show_window_text': 'Показать окно',
        'tray_capture_text': 'Захватить область',
        'tray_exit_text': 'Выход',
        'tray_language_text': 'Язык', # New
        'custom_prompt_empty_warning': 'Поле для своего запроса пусто. Пожалуйста, введите запрос.',
        'dialog_warning_title': 'Предупреждение',
        'status_lang_changed_to': 'Язык изменен на {lang_name}.', # New
    }
}

def T(key, lang=None):
    """Fetches a localized string. Uses current LANGUAGE if lang is None."""
    current_lang_code = lang if lang else LANGUAGE
    # Fallback to DEFAULT_LANGUAGE if current_lang_code's texts are missing, then to key itself
    primary_texts = UI_TEXTS.get(current_lang_code, UI_TEXTS.get(DEFAULT_LANGUAGE, {}))
    default_texts = UI_TEXTS.get(DEFAULT_LANGUAGE, {})
    
    text_value = primary_texts.get(key)
    if text_value is None: # If key not in primary or primary texts missing
        text_value = default_texts.get(key, f"<{key}>") # Fallback to default lang then key
    return text_value


# --- UI Style --- (No changes from previous version)
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
DEFAULT_FONT_SIZE = 14
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

# --- Initialize hotkeys with the default language at module load time ---
# This is crucial so that HOTKEY_ACTIONS is populated before screener.py (or other modules)
# might try to access it during their own import/initialization phase.
try:
    load_hotkey_actions(LANGUAGE)
except Exception as e:
    print(f"CRITICAL ERROR during initial settings.load_hotkey_actions: {e}")
    print("Application may not function correctly or will exit if screener.py cannot handle this.")
    # HOTKEY_ACTIONS will be empty or partially filled. screener.py's error handling
    # for settings import should catch this scenario if it relies on HOTKEY_ACTIONS.