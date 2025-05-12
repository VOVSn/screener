# settings.py

# --- Ollama Configuration ---
OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'gemma3:12b'
OLLAMA_TIMEOUT_SECONDS = 120 # Timeout for the request
OLLAMA_DEFAULT_ERROR_MSG = 'No response content found in JSON.'

# --- Hotkey Actions Configuration ---
HOTKEY_ACTIONS = {
    'solve': {
        'hotkey': '<ctrl>+<alt>+s',
        'prompt': (
            'Analyze the image. If it presents a problem (mathematical, '
            'logical, or technical), provide a step-by-step solution or '
            'explanation. If not, describe the image.'
        )
    },
    'describe': {
        'hotkey': '<ctrl>+<alt>+d',
        'prompt': (
            'Describe the contents of this image in detail, focusing on '
            'the main subject, text, and any notable elements.'
        )
    },
    'code': {
        'hotkey': '<ctrl>+<alt>+c',
        'prompt': (
            'Analyze the image. If it describes a programming problem or '
            'task, generate relevant code (preferably Python) to address '
            'it. Explain the code briefly. If not a coding task, '
            'describe the image.'
        )
    }
}
DEFAULT_MANUAL_ACTION = 'describe' # Must be a key from HOTKEY_ACTIONS

# --- UI Text ---
APP_TITLE = 'Screenshot to Ollama'
MAIN_LABEL_TEXT = 'Screenshot Capture & Analysis'
CAPTURE_BUTTON_TEXT = 'Capture Region Manually'
EXIT_BUTTON_TEXT = 'Exit'
EXIT_BUTTON_TEXT_TRAY = 'Exit Completely' # Used when tray is available
INITIAL_STATUS_TEXT = 'Initializing...'
PROCESSING_STATUS_TEXT = 'Processing with Ollama...'
READY_STATUS_TEXT_NO_TRAY = 'Ready. Hotkeys active.'
READY_STATUS_TEXT_TRAY = 'Ready. Hotkeys active or use tray.'
RESPONSE_WINDOW_TITLE = 'Ollama Analysis'
COPY_BUTTON_TEXT = 'Copy Response'
COPIED_BUTTON_TEXT = 'Copied!'
CLOSE_BUTTON_TEXT = 'Close'
FONT_SIZE_LABEL_FORMAT = 'Size: {size}pt' # Use .format(size=...)
ERROR_PREPARING_IMAGE_STATUS = 'Error preparing image.'
OLLAMA_CONN_FAILED_STATUS = 'Ollama connection failed.'
OLLAMA_TIMEOUT_STATUS = 'Ollama request timed out.'
OLLAMA_REQUEST_FAILED_STATUS = 'Ollama request failed.'
UNEXPECTED_ERROR_STATUS = 'Unexpected error.'
HOTKEY_FAILED_STATUS = 'Hotkey listener failed!'
ICON_LOAD_FAIL_STATUS = "Tray icon failed to load." # Added for clarity
WINDOW_HIDDEN_STATUS = 'Window hidden to system tray.'
WINDOW_RESTORED_STATUS = 'Window restored from system tray.'
EXITING_APP_STATUS = 'Exiting application...'
STOPPING_HOTKEYS_STATUS = 'Stopping hotkey listener...'
STOPPING_TRAY_STATUS = 'Stopping system tray icon...'
APP_EXIT_COMPLETE_STATUS = 'Application exit sequence complete.'
APP_FINISHED_STATUS = 'Screenshot Tool finished.'

# --- UI Style ---
# Main Window
MAIN_WINDOW_GEOMETRY = '350x200'
WINDOW_RESIZABLE_WIDTH = False
WINDOW_RESIZABLE_HEIGHT = False
PADDING_SMALL = 5
PADDING_LARGE = 10
# Response Window
RESPONSE_WINDOW_GEOMETRY = '700x800'
RESPONSE_TEXT_PADDING_X = 10
RESPONSE_TEXT_PADDING_Y_TOP = (10, 0)
RESPONSE_CONTROL_PADDING_X = 10
RESPONSE_CONTROL_PADDING_Y = 5
RESPONSE_BUTTON_PADDING_Y = (5, 10)
RESPONSE_BUTTON_PADDING_X = 5
FONT_SIZE_LABEL_WIDTH = 10
# Colors
STATUS_COLOR_DEFAULT = 'gray' # For initial state
STATUS_COLOR_READY = 'blue'
STATUS_COLOR_PROCESSING = 'darkorange'
STATUS_COLOR_ERROR = 'red'
# Font settings already exist (DEFAULT_FONT_SIZE etc.)
# Code Block Formatting
CODE_BLOCK_BG_COLOR = '#f0f0f0'
CODE_BLOCK_MARGIN = 10 # Used for lmargin1 and lmargin2
CODE_FONT_SIZE_OFFSET = -1 # Code font size relative to normal text size
# Capture Overlay
OVERLAY_ALPHA = 0.4 # Transparency (0.0 to 1.0)
OVERLAY_CURSOR = 'cross'
OVERLAY_BG_COLOR = 'gray' # Background of the overlay canvas
SELECTION_RECT_COLOR = 'red'
SELECTION_RECT_WIDTH = 2

# --- Font Configuration ---
DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 10
MAX_FONT_SIZE = 16
CODE_FONT_FAMILY = 'Courier New'

# --- Capture Settings ---
MIN_SELECTION_WIDTH = 10
MIN_SELECTION_HEIGHT = 10
CAPTURE_DELAY = 0.2 # Seconds after overlay closes
SCREENSHOT_FORMAT = 'PNG' # Format for saving screenshot in memory

# --- System Tray / Icon ---
ICON_PATH = 'icon.png'
TRAY_ICON_NAME = 'screenshot_ollama' # Internal name for pystray
TRAY_TOOLTIP = APP_TITLE # Reuse app title for tooltip
TRAY_SHOW_WINDOW_TEXT = 'Show Window'
TRAY_CAPTURE_TEXT = 'Capture Region' # Uses DEFAULT_MANUAL_ACTION
TRAY_EXIT_TEXT = 'Exit'
# Default Icon Generation (if ICON_PATH fails)
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

# --- Behavior / Timings ---
COPY_BUTTON_RESET_DELAY_MS = 2000 # How long "Copied!" message shows
THREAD_JOIN_TIMEOUT_SECONDS = 1.0 # Max wait for threads on exit

# --- Error Handling ---
# Dialog titles/messages can be added here if needed for configuration/localization
DIALOG_SETTINGS_ERROR_TITLE = 'Settings Error'
DIALOG_SETTINGS_ERROR_MSG = 'Error loading settings.py:\n{error}'
DIALOG_SCREENSHOT_ERROR_TITLE = 'Screenshot Error'
DIALOG_INTERNAL_ERROR_TITLE = 'Internal Error'
DIALOG_INTERNAL_ERROR_MSG = 'Capture prompt was lost.'
DIALOG_PROCESSING_ERROR_TITLE = 'Processing Error'
DIALOG_OLLAMA_CONN_ERROR_TITLE = 'Ollama Connection Error'
DIALOG_OLLAMA_CONN_ERROR_MSG = ('Connection Error: Could not connect to Ollama at '
                                '{url}. Is it running?')
DIALOG_OLLAMA_TIMEOUT_TITLE = 'Ollama Timeout'
DIALOG_OLLAMA_TIMEOUT_MSG = ('Timeout: Ollama at {url} took too long.')
DIALOG_OLLAMA_ERROR_TITLE = 'Ollama Error'
DIALOG_UNEXPECTED_ERROR_TITLE = 'Unexpected Error'
DIALOG_HOTKEY_ERROR_TITLE = 'Hotkey Error'
DIALOG_HOTKEY_ERROR_MSG = (
    'Failed to set up hotkey listener: {error}\n\nCommon causes:\n'
    '- Incorrect hotkey format in settings.py.\n'
    '- Accessibility/Input permissions missing (macOS/Linux).\n'
    '- Another app using the same hotkey.'
)
DIALOG_ICON_WARNING_TITLE = 'Icon Warning'
DIALOG_ICON_WARNING_MSG = ("Tray icon file '{path}' not found.\n"
                          "A default icon will be used. Continue?")
DIALOG_ICON_ERROR_TITLE = 'Icon Error'
DIALOG_ICON_ERROR_MSG = ("Error loading tray icon '{path}': {error}\n"
                         "A default icon will be used. Continue?")