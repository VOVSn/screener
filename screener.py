# screener.py

import tkinter as tk
from tkinter import scrolledtext, messagebox, font as tkFont
import threading
# Removed: io, base64, json, re (now in utils)
from functools import partial
import platform
import time # Keep for main app logic if needed (e.g., sleep)

# --- Third-Party Imports ---
# Removed: pyautogui (now in capture.py)
from PIL import Image # Keep for type hinting if needed, or remove if only used in utils
# Removed: PIL.ImageDraw (now in ui_utils.py)
from pynput import keyboard # Using GlobalHotKeys below
# Removed: requests (now in ollama_utils.py)

# --- Local Imports ---
try:
    import settings
    # Validate DEFAULT_MANUAL_ACTION exists
    if settings.DEFAULT_MANUAL_ACTION not in settings.HOTKEY_ACTIONS:
        raise ImportError(
            f"DEFAULT_MANUAL_ACTION '{settings.DEFAULT_MANUAL_ACTION}' "
            f"not found in HOTKEY_ACTIONS keys in settings.py"
        )
    # Import the new utility modules/classes
    import ollama_utils
    from ollama_utils import (
        OllamaError, OllamaConnectionError, OllamaTimeoutError, OllamaRequestError
    )
    from capture import ScreenshotCapturer # Import the class
    import ui_utils # Import the module

except ImportError as e:
    # Enhanced error message to potentially include missing utils
    module_name = "unknown module"
    if 'ollama_utils' in str(e): module_name = 'ollama_utils.py'
    elif 'capture' in str(e): module_name = 'capture.py'
    elif 'ui_utils' in str(e): module_name = 'ui_utils.py'
    elif 'settings' in str(e): module_name = 'settings.py'

    base_msg = f'FATAL ERROR: {e}'
    if module_name != "unknown module" and module_name != 'settings.py':
        base_msg += f"\n\nPlease ensure '{module_name}' is in the same directory as 'screener.py'."
    elif module_name == 'settings.py':
         base_msg = f'FATAL ERROR in settings: {e}'

    print(base_msg)

    try: # Attempt to show GUI error if possible
        root = tk.Tk(); root.withdraw()
        err_title = settings.DIALOG_SETTINGS_ERROR_TITLE if module_name == 'settings.py' else "Import Error"
        err_msg = settings.DIALOG_SETTINGS_ERROR_MSG.format(error=e) if module_name == 'settings.py' else base_msg
        messagebox.showerror(err_title, err_msg)
        root.destroy()
    except Exception: pass # Ignore if Tk fails early
    exit()

# --- System Tray Support (Optional) ---
try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    print('Info: pystray library not found. System tray icon disabled.')
    PYSTRAY_AVAILABLE = False


# --- Main Application Class ---
class ScreenshotApp:
    """Main application class handling UI, events, and coordination."""

    def __init__(self):
        self.root = tk.Tk()
        default_font = tkFont.nametofont('TkDefaultFont')
        default_font.configure(size=settings.DEFAULT_FONT_SIZE)
        self.root.option_add('*Font', default_font)

        # Instantiate the capturer, passing self (the app instance)
        self.capturer = ScreenshotCapturer(self) # Now from capture.py

        self.running = True
        self.hotkey_listener = None # Uses GlobalHotKeys
        self.listener_thread = None
        self.response_window = None
        self.tray_icon = None
        self.tray_thread = None
        self.icon_image = None # Will be loaded or created

        # --- Load Icon ---
        # Moved icon loading logic here for better flow after root exists
        if PYSTRAY_AVAILABLE:
            try:
                self.icon_image = Image.open(settings.ICON_PATH)
                print(f"Icon '{settings.ICON_PATH}' loaded.")
            except FileNotFoundError:
                print(f"Warning: Icon '{settings.ICON_PATH}' not found. Using default.")
                self.icon_image = ui_utils.create_default_icon() # Use ui_utils
            except Exception as e:
                print(f"Warning: Error loading icon '{settings.ICON_PATH}': {e}. Using default.")
                self.icon_image = ui_utils.create_default_icon() # Use ui_utils
                # Status update can happen later in run() or _setup_ui

        self._setup_ui() # Setup UI after loading icon (or fallback)


    def _setup_ui(self):
        """Configures the main Tkinter window using settings."""
        self.root.title(settings.APP_TITLE)
        self.root.geometry(settings.MAIN_WINDOW_GEOMETRY)
        self.root.resizable(
            settings.WINDOW_RESIZABLE_WIDTH,
            settings.WINDOW_RESIZABLE_HEIGHT
        )

        label = tk.Label(self.root, text=settings.MAIN_LABEL_TEXT)
        label.pack(pady=settings.PADDING_LARGE)

        self.status_label = tk.Label(
            self.root,
            text=settings.INITIAL_STATUS_TEXT,
            fg=settings.STATUS_COLOR_DEFAULT
        )
        self.status_label.pack(pady=settings.PADDING_SMALL)

        # Button uses the default action/prompt from settings
        default_prompt = settings.HOTKEY_ACTIONS[
            settings.DEFAULT_MANUAL_ACTION]['prompt']
        tk.Button(
            self.root, text=settings.CAPTURE_BUTTON_TEXT,
            # Trigger capture using the capturer instance
            command=partial(self._trigger_capture, prompt=default_prompt)
        ).pack(pady=settings.PADDING_LARGE)

        exit_text = (settings.EXIT_BUTTON_TEXT_TRAY if PYSTRAY_AVAILABLE
                     else settings.EXIT_BUTTON_TEXT)
        tk.Button(self.root, text=exit_text, command=self.on_exit).pack(pady=settings.PADDING_SMALL)

        close_action = self.hide_to_tray if PYSTRAY_AVAILABLE else self.on_exit
        self.root.protocol('WM_DELETE_WINDOW', close_action)

    def _trigger_capture(self, prompt):
        """Safely triggers capture via the ScreenshotCapturer instance."""
        print(f"Triggering capture via ScreenshotCapturer for prompt: '{prompt[:30]}...'")
        # Call the method on the capturer instance
        # It handles thread safety internally now
        self.capturer.capture_region(prompt)

    # --- Ollama Interaction (Coordination) ---
    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str):
        """
        Callback function called by ScreenshotCapturer.
        Starts Ollama request in a background thread using ollama_utils.
        """
        self.update_status(
            settings.PROCESSING_STATUS_TEXT, settings.STATUS_COLOR_PROCESSING
        )
        # Start the worker thread
        threading.Thread(
            target=self._ollama_request_worker,
            args=(screenshot, prompt),
            daemon=True
        ).start()

    def _ollama_request_worker(self, screenshot: Image.Image, prompt: str):
        """
        Worker function (runs in background thread) to call ollama_utils
        and handle results/exceptions, scheduling UI updates.
        (No changes needed in this method itself)
        """
        try:
            # Call the utility function
            response_text = ollama_utils.request_ollama_analysis(screenshot, prompt)
            # Schedule success UI update on main thread
            self.root.after(0, self.display_ollama_response, response_text)

        # --- Handle specific Ollama errors ---
        except OllamaConnectionError as e:
            error_msg = settings.DIALOG_OLLAMA_CONN_ERROR_MSG.format(url=settings.OLLAMA_URL)
            print(f"Ollama Error: {error_msg} - Details: {e}")
            self.root.after(
                0, messagebox.showerror,
                settings.DIALOG_OLLAMA_CONN_ERROR_TITLE, error_msg
            )
            self.root.after(
                0, self.update_status,
                settings.OLLAMA_CONN_FAILED_STATUS, settings.STATUS_COLOR_ERROR
            )
        except OllamaTimeoutError as e:
            error_msg = settings.DIALOG_OLLAMA_TIMEOUT_MSG.format(url=settings.OLLAMA_URL)
            print(f"Ollama Error: {error_msg} - Details: {e}")
            self.root.after(
                0, messagebox.showerror,
                settings.DIALOG_OLLAMA_TIMEOUT_TITLE, error_msg
            )
            self.root.after(
                0, self.update_status,
                settings.OLLAMA_TIMEOUT_STATUS, settings.STATUS_COLOR_ERROR
            )
        except OllamaRequestError as e:
            error_msg = f"Ollama API Error: {e.detail or str(e)}"
            print(f"Ollama Error: {error_msg}")
            self.root.after(
                0, messagebox.showerror,
                settings.DIALOG_OLLAMA_ERROR_TITLE, error_msg
            )
            self.root.after(
                0, self.update_status,
                settings.OLLAMA_REQUEST_FAILED_STATUS, settings.STATUS_COLOR_ERROR
            )
        except ValueError as e: # Catch image encoding errors from ollama_utils
             error_msg = f"Image Error: {e}"
             print(error_msg)
             self.root.after(
                 0, messagebox.showerror,
                 settings.DIALOG_PROCESSING_ERROR_TITLE, error_msg
             )
             self.root.after(
                 0, self.update_status,
                 settings.ERROR_PREPARING_IMAGE_STATUS, settings.STATUS_COLOR_ERROR
             )
        except (OllamaError, Exception) as e: # Catch other Ollama errors or unexpected ones
            error_msg = f'Unexpected error during Ollama processing: {e}'
            print(error_msg)
            self.root.after(
                0, messagebox.showerror,
                settings.DIALOG_UNEXPECTED_ERROR_TITLE, error_msg
            )
            self.root.after(
                0, self.update_status,
                settings.UNEXPECTED_ERROR_STATUS, settings.STATUS_COLOR_ERROR
            )


    # --- Response Window ---
    def display_ollama_response(self, response_text):
        """Displays the Ollama response in a formatted Toplevel window."""
        if self.response_window and self.response_window.winfo_exists():
            self.response_window.destroy()

        self.response_window = tk.Toplevel(self.root)
        self.response_window.title(settings.RESPONSE_WINDOW_TITLE)
        self.response_window.geometry(settings.RESPONSE_WINDOW_GEOMETRY)

        text_frame = tk.Frame(self.response_window)
        text_frame.pack(
            padx=settings.RESPONSE_TEXT_PADDING_X,
            pady=settings.RESPONSE_TEXT_PADDING_Y_TOP,
            fill=tk.BOTH, expand=True
        )

        txt_area = scrolledtext.ScrolledText(
            text_frame, wrap=tk.WORD, relief=tk.FLAT, bd=0,
            font=('TkDefaultFont', settings.DEFAULT_FONT_SIZE) # Base font
        )
        txt_area.pack(fill=tk.BOTH, expand=True)

        control_frame = tk.Frame(self.response_window)
        control_frame.pack(
            padx=settings.RESPONSE_CONTROL_PADDING_X,
            pady=settings.RESPONSE_CONTROL_PADDING_Y,
            fill=tk.X
        )

        # --- Slider Callback ---
        def update_font_size(value):
            try:
                new_size = int(float(value))
                if not (settings.MIN_FONT_SIZE <= new_size <= settings.MAX_FONT_SIZE):
                    return # Ignore invalid values

                # Update base font for the text area *itself*
                base_font_obj = tkFont.Font(font=txt_area['font'])
                base_font_obj.configure(size=new_size)
                txt_area.configure(font=base_font_obj) # Apply base size change

                # Re-apply tags which recalculates tag fonts based on the *new* base size
                # Need the original response text to reapply formatting correctly
                # Store it temporarily or re-fetch if needed. Here, assume we refetch/reapply:
                current_content = txt_area.get("1.0", tk.END) # Get current content
                ui_utils.apply_formatting_tags(txt_area, current_content, new_size) # Reapply with new size

                size_label.config(text=settings.FONT_SIZE_LABEL_FORMAT.format(size=new_size))
            except Exception as e:
                print(f'Error updating font size: {e}')

        # --- Slider ---
        font_slider = tk.Scale(
            control_frame, from_=settings.MIN_FONT_SIZE,
            to=settings.MAX_FONT_SIZE, orient=tk.HORIZONTAL, resolution=1,
            showvalue=0,
            command=update_font_size
        )
        font_slider.set(settings.DEFAULT_FONT_SIZE)
        font_slider.pack(
            side=tk.LEFT, fill=tk.X, expand=True,
            padx=(0, settings.PADDING_LARGE)
        )

        size_label = tk.Label(
            control_frame,
            text=settings.FONT_SIZE_LABEL_FORMAT.format(size=settings.DEFAULT_FONT_SIZE),
            width=settings.FONT_SIZE_LABEL_WIDTH
        )
        size_label.pack(side=tk.LEFT)

        # --- Apply Initial Formatting ---
        # Use the utility function from ui_utils
        ui_utils.apply_formatting_tags(
            txt_area, response_text, settings.DEFAULT_FONT_SIZE
        )

        # --- Button Frame ---
        button_frame = tk.Frame(self.response_window)
        button_frame.pack(
            pady=settings.RESPONSE_BUTTON_PADDING_Y,
            fill=tk.X,
            padx=settings.RESPONSE_BUTTON_PADDING_X
        )

        def copy_to_clipboard():
            # Get raw text content
            raw_text = txt_area.get('1.0', tk.END).strip()
            # Clear and append to the response window's clipboard
            self.response_window.clipboard_clear()
            self.response_window.clipboard_append(raw_text)
            copy_button.config(text=settings.COPIED_BUTTON_TEXT, relief=tk.SUNKEN)
            self.response_window.after(
                settings.COPY_BUTTON_RESET_DELAY_MS,
                lambda: copy_button.config(text=settings.COPY_BUTTON_TEXT, relief=tk.RAISED)
            )

        copy_button = tk.Button(
            button_frame, text=settings.COPY_BUTTON_TEXT, command=copy_to_clipboard
        )
        copy_button.pack(side=tk.LEFT, padx=settings.PADDING_SMALL)

        close_button = tk.Button(
            button_frame, text=settings.CLOSE_BUTTON_TEXT,
            command=self.response_window.destroy
        )
        close_button.pack(side=tk.RIGHT, padx=settings.PADDING_SMALL)

        # --- Window Behavior ---
        self.response_window.transient(self.root)
        self.response_window.grab_set()
        self.response_window.focus_force()
        # Update status after response is successfully displayed
        ready_status = (settings.READY_STATUS_TEXT_TRAY if PYSTRAY_AVAILABLE
                        else settings.READY_STATUS_TEXT_NO_TRAY)
        self.update_status(ready_status, settings.STATUS_COLOR_READY)


    # --- Hotkey Listener ---
    def start_hotkey_listener(self):
        """Sets up and starts the global hotkey listener using GlobalHotKeys."""
        print('Registering hotkeys:')
        hotkey_map = {}
        try:
            for action_name, details in settings.HOTKEY_ACTIONS.items():
                hotkey_str = details['hotkey']
                prompt = details['prompt']
                # Use _trigger_capture which now calls the capturer instance
                callback = partial(self._trigger_capture, prompt=prompt)
                hotkey_map[hotkey_str] = callback
                print(f'  - {hotkey_str} -> Action: {action_name}')

            # Create GlobalHotKeys listener
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)

            # Run listener in its own daemon thread
            self.listener_thread = threading.Thread(
                target=self.hotkey_listener.run, daemon=True
            )
            self.listener_thread.start()
            print('Hotkey listener thread started.')

        except Exception as e:
            error_msg = settings.DIALOG_HOTKEY_ERROR_MSG.format(error=e)
            print(f'Error setting up hotkey listener: {e}')
            if self.root and self.root.winfo_exists():
                 self.root.after(
                    0, messagebox.showerror,
                    settings.DIALOG_HOTKEY_ERROR_TITLE, error_msg
                 )
            self.update_status(settings.HOTKEY_FAILED_STATUS, settings.STATUS_COLOR_ERROR)

    # --- Status Update Method ---
    def update_status(self, message, color=settings.STATUS_COLOR_DEFAULT):
        """Updates the status label in the main window (thread-safe)."""
        # (No change needed)
        def _update():
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.config(text=message, fg=color)
            else:
                print(f'Status Update (UI not ready): {message}')

        if self.root and self.root.winfo_exists():
             self.root.after(0, _update) # Schedule on main thread
        else:
             print(f'Status Update (No UI): {message}')

    # --- System Tray Methods ---
    def setup_tray_icon(self):
        """Creates and runs the system tray icon using settings."""
        if not PYSTRAY_AVAILABLE or not self.icon_image:
            print('Info: System tray icon setup skipped.')
            return

        default_prompt = settings.HOTKEY_ACTIONS[
            settings.DEFAULT_MANUAL_ACTION]['prompt']
        menu = (
            pystray.MenuItem(
                settings.TRAY_SHOW_WINDOW_TEXT,
                self.show_window, default=True,
                visible=lambda item: not self.root.winfo_viewable()
                         if self.root and self.root.winfo_exists() else False
            ),
            pystray.MenuItem(
                settings.TRAY_CAPTURE_TEXT,
                # Use _trigger_capture which calls the capturer instance
                partial(self._trigger_capture, prompt=default_prompt)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(settings.TRAY_EXIT_TEXT, self.on_exit)
        )

        self.tray_icon = pystray.Icon(
            settings.TRAY_ICON_NAME,
            self.icon_image, # Use the loaded/created icon
            settings.TRAY_TOOLTIP,
            menu
        )
        self.tray_thread = threading.Thread(
            target=self.tray_icon.run, daemon=True
        )
        self.tray_thread.start()
        print('System tray icon thread started.')

    def hide_to_tray(self):
        """Hides the main application window."""
        # (No change needed)
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
            if self.tray_icon:
                self.tray_icon.update_menu()
            print(settings.WINDOW_HIDDEN_STATUS)

    def show_window(self):
        """Shows the main application window from the system tray."""
        # (No change needed)
        def _show():
            if self.root and self.root.winfo_exists():
                 self.root.deiconify(); self.root.lift(); self.root.focus_force()
                 if self.tray_icon:
                     self.tray_icon.update_menu()
                 print(settings.WINDOW_RESTORED_STATUS)
            else:
                 print('Cannot show window, root does not exist.')
        if self.root:
             self.root.after(0, _show)


    # --- Exit Method ---
    def on_exit(self):
        """Performs cleanup and exits the application."""
        # (No change needed)
        if not self.running: return
        print(settings.EXITING_APP_STATUS)
        self.running = False

        if self.hotkey_listener:
            print(settings.STOPPING_HOTKEYS_STATUS)
            try: self.hotkey_listener.stop()
            except Exception as e: print(f'Error stopping hotkey listener: {e}')
        if self.listener_thread and self.listener_thread.is_alive():
            print('Waiting for listener thread to join...')
            self.listener_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS)

        if self.tray_icon:
            print(settings.STOPPING_TRAY_STATUS)
            self.tray_icon.stop()
        if self.tray_thread and self.tray_thread.is_alive():
             print('Waiting for tray thread to join...')
             self.tray_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS)

        if self.root and self.root.winfo_exists():
            print('Destroying main window...')
            self.root.destroy()

        print(settings.APP_EXIT_COMPLETE_STATUS)

    # --- Main Application Execution ---
    def run(self):
        """Starts listeners, tray icon, and the main Tkinter event loop."""
        self.start_hotkey_listener() # Start after UI is set up
        self.setup_tray_icon() # Start after icon is loaded

        status_msg = (settings.READY_STATUS_TEXT_TRAY if PYSTRAY_AVAILABLE
                      else settings.READY_STATUS_TEXT_NO_TRAY)
        self.update_status(status_msg, settings.STATUS_COLOR_READY)

        print('Starting main application loop (Tkinter)...')
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print('KeyboardInterrupt received, initiating exit...')
            self.on_exit()

        # Ensure cleanup if mainloop exits unexpectedly
        if self.running:
             self.on_exit()
        print(settings.APP_FINISHED_STATUS)


# --- Main Execution Guard ---
def main():
    """Main function to initialize and run the application."""
    # (No change needed, initial icon check remains useful)
    print('Screenshot to Ollama Tool Starting...')
    print(f'Platform: {platform.system()} {platform.release()}')

    # Settings are checked during import now
    if PYSTRAY_AVAILABLE:
        try:
            with Image.open(settings.ICON_PATH) as img:
                print(f"Tray icon '{settings.ICON_PATH}' check successful.")
        except FileNotFoundError:
             # Use askokcancel which requires Tkinter, show before main app window
             root_check = tk.Tk(); root_check.withdraw()
             proceed = messagebox.askokcancel(
                 settings.DIALOG_ICON_WARNING_TITLE,
                 settings.DIALOG_ICON_WARNING_MSG.format(path=settings.ICON_PATH)
                )
             root_check.destroy()
             if not proceed: return
        except Exception as e:
             root_check = tk.Tk(); root_check.withdraw()
             proceed = messagebox.askokcancel(
                 settings.DIALOG_ICON_ERROR_TITLE,
                 settings.DIALOG_ICON_ERROR_MSG.format(path=settings.ICON_PATH, error=e)
                )
             root_check.destroy()
             if not proceed: return

    app = ScreenshotApp()
    app.run()


if __name__ == '__main__':
    main()