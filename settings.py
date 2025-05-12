# settings.py

# --- Ollama Configuration ---
OLLAMA_URL = 'http://localhost:11434/api/generate'
# The multimodal model to use. Using Gemma 3 12B as requested!
# Make sure the model is installed in Ollama: `ollama pull gemma3:12b`
OLLAMA_MODEL = 'gemma3:12b' # Updated model!

# --- Hotkey Actions Configuration ---
# Maps an action name to its hotkey combination and the prompt to use.
# Hotkey format follows pynput specification. Ensure hotkeys are unique!
HOTKEY_ACTIONS = {
    'solve': {
        'hotkey': '<ctrl>+<alt>+s', # Use this format for GlobalHotKeys
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

# Action to use when triggering capture via the UI Button or Tray Menu
# Must be one of the keys in HOTKEY_ACTIONS ('solve', 'describe', 'code')
DEFAULT_MANUAL_ACTION = 'describe'

# --- UI / File Paths ---
# Path to the system tray icon image (e.g., .png, .ico).
ICON_PATH = 'icon.png'

# --- Font Configuration for Response Window ---
DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 10
MAX_FONT_SIZE = 16
# Preferred monospace font for code blocks. Falls back if not found.
CODE_FONT_FAMILY = 'Courier New'

# --- Capture Settings ---
MIN_SELECTION_WIDTH = 10
MIN_SELECTION_HEIGHT = 10
# Delay (seconds) after closing overlay before taking screenshot.
CAPTURE_DELAY = 0.2