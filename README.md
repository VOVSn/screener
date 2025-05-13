# Screener: Screenshot Analysis with Ollama

Screener is a desktop application that allows you to capture regions of your screen and send them to a local Ollama instance for analysis, description, code generation, translation, or custom tasks. It features global hotkeys for quick captures and a system tray icon for easy access.

## Features

*   **Region Capture:** Manually select any part of your screen for analysis.
*   **Ollama Integration:** Utilizes a local Ollama instance for powerful image-to-text processing.
    *   Configurable Ollama URL and model.
*   **Predefined Actions via Hotkeys:**
    *   **Solve/Describe:** Analyze mathematical, logical, or technical problems, or describe the image if it's not a problem.
    *   **Describe Image:** Provide a detailed description of the image content.
    *   **Generate Code:** If the image describes a programming task, generate relevant Python code and an explanation.
    *   **Translate to Russian:** Translate text within the image to Russian, or describe the image in Russian.
*   **Custom Prompts:**
    *   Use a dedicated hotkey to capture with a custom prompt entered in the main application window.
    *   Manually trigger capture from the UI with a custom prompt.
*   **Global Hotkeys:** Customizable hotkeys for all predefined actions (configurable in `hotkeys.json`).
*   **System Tray Integration:**
    *   Show/Hide the main application window.
    *   Quick capture action.
    *   Language selection.
    *   Theme selection (Light/Dark).
    *   Exit application.
*   **Internationalization (i18n):**
    *   Supports English (en) and Russian (ru).
    *   UI text and hotkey descriptions are localized.
    *   Language can be changed at runtime via the tray menu.
*   **Theming:**
    *   Light and Dark themes available, switchable from the tray menu.
*   **Formatted Responses:**
    *   Ollama's responses are displayed in a separate window with basic Markdown rendering (bold, italic, headers, lists, code blocks).
    *   Python syntax highlighting within ` ```python ... ``` ` code blocks.
    *   Adjustable font size for the response text.
    *   Copy response to clipboard.
*   **Cross-Platform (Conceptual):** Built with Python and Tkinter, aiming for cross-platform compatibility (Windows, macOS, Linux), though pynput (for global hotkeys) and pystray might have platform-specific dependencies or setup requirements.

## Prerequisites

*   **Python 3.8+**
*   **Ollama:** A running local instance of [Ollama](https://ollama.ai/).
    *   Ensure the model specified in `settings.py` (default: `gemma3:12b`) is downloaded and available in your Ollama instance (e.g., `ollama pull gemma3:12b`).
*   **Tcl/Tk:** Usually comes with Python, but ensure it's a version that supports ttk themes well (Tk 8.6+ recommended).

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd screener
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: On Linux, you might need to install additional packages for `pynput` to function correctly (e.g., `python3-dev`, `libudev-dev`, `libx11-dev`, `xorg-dev` or similar, depending on your distribution and whether you are using X11 or Wayland).*
    *For `pystray` on Linux, you might need `libappindicator3-dev` or `libayatana-appindicator3-dev` and related components for system tray icons to work best.*

## Configuration

Most settings are managed in `settings.py`:

*   `OLLAMA_URL`: URL of your Ollama API endpoint (default: `http://localhost:11434/api/generate`).
*   `OLLAMA_MODEL`: The Ollama model to use (default: `gemma3:12b`).
*   `DEFAULT_LANGUAGE`: Default application language ('en' or 'ru').
*   `DEFAULT_THEME`: Default theme ('light' or 'dark').

Hotkeys are defined in `hotkeys.json`:

*   You can change the key combinations and default prompts/descriptions here.
*   Ensure hotkey combinations are valid for `pynput`.

UI text and translations are in `ui_texts.json`.

## Usage

1.  **Ensure Ollama is running.**
2.  **Run the Application:**
    ```bash
    python screener.py
    ```
3.  **Using Hotkeys:**
    *   Press the configured hotkey for the desired action (e.g., `Ctrl+Alt+S` to "Solve/Describe").
    *   Your cursor will change to a crosshair. Click and drag to select a screen region.
    *   Release the mouse button to capture.
    *   The image will be sent to Ollama, and the response will appear in a new window.
4.  **Using the Main Window:**
    *   Enter a custom prompt in the input field if you want to use the "Custom Prompt" hotkey or trigger manually.
    *   Click "Capture Region Manually" to trigger a capture with the default "describe" action (or a custom prompt if the "describe" action is set to use `CUSTOM_PROMPT_PLACEHOLDER` and you've filled the field).
5.  **Using the System Tray Icon:**
    *   Right-click the tray icon for options: Show/Hide window, Capture, Language, Theme, Exit.

## Troubleshooting

*   **Ollama Connection Errors:**
    *   Verify Ollama is running and accessible at the configured `OLLAMA_URL`.
    *   Check if the specified `OLLAMA_MODEL` is available in your Ollama instance.
    *   Firewall might be blocking the connection.
*   **Hotkey Issues:**
    *   Ensure no other application is using the same global hotkeys.
    *   On macOS, you might need to grant accessibility permissions to your terminal or Python interpreter.
    *   On Linux (especially Wayland), global hotkey support can be tricky. `pynput` might require specific environment variables or X11 compatibility layers.
*   **Tray Icon Not Appearing:**
    *   `pystray` might require specific libraries (e.g., `libappindicator` on Linux).
    *   Some desktop environments might not fully support legacy tray icons.
*   **"Unknown option -bordercolor" TclError:** Your Tcl/Tk version is older than 8.6.11. The application should still work, but code block borders might not have custom colors.

## Files

*   `screener.py`: Main application logic and UI.
*   `settings.py`: Application settings, theme colors, language configuration.
*   `ollama_utils.py`: Handles communication with the Ollama API.
*   `capture.py`: Manages the screen capture overlay and process.
*   `ui_utils.py`: UI helper functions, including Markdown/syntax formatting.
*   `hotkeys.json`: Hotkey definitions and associated prompts.
*   `ui_texts.json`: Internationalized UI string definitions.
*   `requirements.txt`: Python package dependencies.
*   `icon.png`: Application icon for the tray and window.
*   `.gitignore`: Specifies intentionally untracked files for Git.

## Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit a pull request.

## License

This project is open-source. Please add a license file (e.g., MIT, Apache 2.0) if you intend to distribute it widely. (Currently Unlicensed)