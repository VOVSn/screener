# screenshot_ollama.py

import tkinter as tk
from tkinter import scrolledtext, messagebox, font as tkFont
import threading
# import io # No longer needed here for Ollama part
# import base64 # No longer needed here for Ollama part
# import json # No longer needed here for Ollama part
import re
from functools import partial
import platform
import time


# --- Third-Party Imports ---
import pyautogui
from PIL import Image, ImageDraw
from pynput import keyboard # Using GlobalHotKeys below
# import requests # No longer needed here

# --- Local Imports ---
try:
    import settings
    # Validate DEFAULT_MANUAL_ACTION exists
    if settings.DEFAULT_MANUAL_ACTION not in settings.HOTKEY_ACTIONS:
        raise ImportError(
            f"DEFAULT_MANUAL_ACTION '{settings.DEFAULT_MANUAL_ACTION}' "
            f"not found in HOTKEY_ACTIONS keys in settings.py"
        )
    # Import the new utility and its exceptions
    import ollama_utils
    from ollama_utils import (
        OllamaError, OllamaConnectionError, OllamaTimeoutError, OllamaRequestError
    )

except ImportError as e:
    # Enhanced error message to potentially include missing ollama_utils
    base_msg = f'FATAL ERROR: {e}'
    if 'ollama_utils' in str(e):
        base_msg += "\n\nPlease ensure 'ollama_utils.py' is in the same directory as 'screener.py'."
    elif 'settings' in str(e):
         base_msg = f'FATAL ERROR in settings: {e}'
    print(base_msg)

    try: # Attempt to show GUI error if possible
        root = tk.Tk(); root.withdraw()
        err_title = settings.DIALOG_SETTINGS_ERROR_TITLE if 'settings' in str(e) else "Import Error"
        err_msg = settings.DIALOG_SETTINGS_ERROR_MSG.format(error=e) if 'settings' in str(e) else base_msg
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

# --- Screenshot Capturer Class (No changes needed inside this class) ---
class ScreenshotCapturer:
    """Handles the screen region selection overlay and capturing."""

    def __init__(self, app_instance):
        self.selection_window = None
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.capture_root = None # Temporary Tk root for the overlay
        self.app = app_instance # Reference to the main ScreenshotApp
        self.current_prompt = None # Store prompt for the current operation

    def capture_region(self, prompt):
        """Creates a fullscreen transparent window to select a region."""
        # ... (rest of capture_region remains the same) ...
        print(f"Creating selection window for prompt: '{prompt[:30]}...'")
        self.current_prompt = prompt

        if threading.current_thread() != threading.main_thread():
            print('Error: Tried to create Tkinter window from non-main thread.')
            if self.app and self.app.root and self.app.root.winfo_exists():
                 self.app.root.after(0, self.capture_region, prompt)
            else:
                 print('Cannot schedule capture: App root not available.')
            return

        if self.capture_root and self.capture_root.winfo_exists():
            try: self.capture_root.destroy()
            except tk.TclError: pass
        self.reset_state()
        self.current_prompt = prompt # Set again after reset

        self.capture_root = tk.Tk()
        self.capture_root.withdraw()

        self.selection_window = tk.Toplevel(self.capture_root)
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-alpha', settings.OVERLAY_ALPHA) # Transparency
        self.selection_window.attributes('-topmost', True) # Stay on top
        self.selection_window.overrideredirect(True) # No window border/title
        self.selection_window.update_idletasks() # Ensure drawn before use

        canvas = tk.Canvas(
            self.selection_window,
            cursor=settings.OVERLAY_CURSOR,
            bg=settings.OVERLAY_BG_COLOR
        )
        canvas.pack(fill=tk.BOTH, expand=True)

        # --- Event Handlers ---
        def on_button_press(event):
            canvas.focus_set()
            self.start_x = self.selection_window.winfo_pointerx()
            self.start_y = self.selection_window.winfo_pointery()
            canvas_x, canvas_y = event.x, event.y
            self.rect_id = canvas.create_rectangle(
                canvas_x, canvas_y, canvas_x, canvas_y,
                outline=settings.SELECTION_RECT_COLOR,
                width=settings.SELECTION_RECT_WIDTH,
                tags='selection'
            )

        def on_mouse_drag(event):
            if self.rect_id is None: return
            start_canvas_x = self.start_x - self.selection_window.winfo_rootx()
            start_canvas_y = self.start_y - self.selection_window.winfo_rooty()
            cur_canvas_x, cur_canvas_y = event.x, event.y
            canvas.coords(
                self.rect_id, start_canvas_x, start_canvas_y,
                cur_canvas_x, cur_canvas_y
            )

        def on_button_release(event):
            if not self.capture_root or not self.capture_root.winfo_exists():
                print('Capture cancelled: Overlay window closed prematurely.')
                self.reset_state()
                return
            if self.start_x is None or self.start_y is None:
                print('Selection cancelled (no area selected).')
                cancel_capture()
                return

            end_x = self.selection_window.winfo_pointerx()
            end_y = self.selection_window.winfo_pointery()
            x1 = min(self.start_x, end_x); y1 = min(self.start_y, end_y)
            x2 = max(self.start_x, end_x); y2 = max(self.start_y, end_y)
            width = x2 - x1; height = y2 - y1

            print(f'Selected region: ({x1}, {y1}) to ({x2}, {y2})'
                  f' - {width}x{height}')
            region_to_capture = (x1, y1, width, height)
            prompt_for_ollama = self.current_prompt

            # Destroy overlay BEFORE screenshot
            try:
                if self.selection_window and self.selection_window.winfo_exists():
                    self.selection_window.destroy()
                if self.capture_root and self.capture_root.winfo_exists():
                    self.capture_root.destroy()
            except tk.TclError as e:
                print(f'Minor error destroying capture window: {e}')

            self.reset_state() # Reset state including prompt
            time.sleep(settings.CAPTURE_DELAY)

            if (width >= settings.MIN_SELECTION_WIDTH and
                    height >= settings.MIN_SELECTION_HEIGHT):
                if prompt_for_ollama is None:
                    print('Error: Prompt was lost before processing. Aborting.')
                    self.app.root.after(
                        0, messagebox.showerror,
                        settings.DIALOG_INTERNAL_ERROR_TITLE,
                        settings.DIALOG_INTERNAL_ERROR_MSG
                    )
                    return
                try:
                    screenshot = pyautogui.screenshot(region=region_to_capture)
                    print('Screenshot captured. Processing...')
                    # Pass screenshot object (PIL Image) directly
                    self.app.root.after(
                        0, self.app.process_screenshot_with_ollama,
                        screenshot, prompt_for_ollama
                    )
                except Exception as e:
                    error_msg = f'Failed to capture screenshot: {e}'
                    print(f'Screenshot Error: {error_msg}')
                    self.app.root.after(
                        0, messagebox.showerror,
                        settings.DIALOG_SCREENSHOT_ERROR_TITLE, error_msg
                    )
            else:
                print('Selection too small or invalid. Screenshot cancelled.')

        def cancel_capture(event=None):
            """Cancels capture and cleans up overlay windows."""
            print('Capture cancelled by user.')
            try:
                if self.selection_window and self.selection_window.winfo_exists():
                    self.selection_window.destroy()
                if self.capture_root and self.capture_root.winfo_exists():
                    self.capture_root.destroy()
            except tk.TclError: pass # Ignore errors if already gone
            self.reset_state()

        # Bind events
        canvas.bind('<ButtonPress-1>', on_button_press)
        canvas.bind('<B1-Motion>', on_mouse_drag)
        canvas.bind('<ButtonRelease-1>', on_button_release)
        self.selection_window.bind('<Escape>', cancel_capture) # Esc key

        self.selection_window.focus_force()
        canvas.focus_set()

        # Start the temporary event loop for the overlay
        if self.capture_root and self.capture_root.winfo_exists():
             self.capture_root.mainloop()
        else:
             print('Capture setup failed, not running overlay mainloop.')
             self.reset_state()

    def reset_state(self):
        """Resets internal state variables after capture or cancellation."""
        self.selection_window = None
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.capture_root = None
        self.current_prompt = None # Crucial: Reset prompt


# --- Formatting Helper (No changes needed) ---
def apply_formatting_tags(text_widget, text_content, initial_font_size):
    """Applies basic markdown and code block styling using Tkinter tags."""
    # ... (apply_formatting_tags remains the same) ...
    text_widget.configure(state='normal')
    text_widget.delete('1.0', tk.END)
    text_widget.insert('1.0', text_content)

    base_font = tkFont.Font(font=text_widget['font'])
    base_family = base_font.actual()['family']
    code_family = settings.CODE_FONT_FAMILY
    try:
        tkFont.Font(family=code_family, size=initial_font_size)
    except tk.TclError:
        print(f"Warning: Code font '{settings.CODE_FONT_FAMILY}' "
              f"not found, using '{base_family}'.")
        code_family = base_family # Fallback

    # Define tags using initial size
    text_widget.tag_configure(
        'bold', font=(base_family, initial_font_size, 'bold')
    )
    text_widget.tag_configure(
        'italic', font=(base_family, initial_font_size, 'italic')
    )
    # Use offset from settings for code font size calculation
    code_font_size = max(
        settings.MIN_FONT_SIZE,
        initial_font_size + settings.CODE_FONT_SIZE_OFFSET
    )
    text_widget.tag_configure(
        'code', background=settings.CODE_BLOCK_BG_COLOR,
        font=(code_family, code_font_size, 'normal'),
        wrap=tk.WORD,
        lmargin1=settings.CODE_BLOCK_MARGIN,
        lmargin2=settings.CODE_BLOCK_MARGIN
    )

    # Apply code blocks first (multiline)
    code_pattern = re.compile(r'```(\w*)\n(.*?)\n```', re.DOTALL)
    for match in code_pattern.finditer(text_content):
        start_index = text_widget.index(f'1.0 + {match.start()} chars')
        end_index = text_widget.index(f'1.0 + {match.end()} chars')
        text_widget.tag_add('code', start_index, end_index)

    # Apply inline styles (check not inside code)
    inline_patterns = {
        'bold': re.compile(r'\*\*(.*?)\*\*'),
        'italic': re.compile(r'\*(.*?)\*'),
        # Could add inline code `...` here if needed
    }
    for tag_name, pattern in inline_patterns.items():
        for match in pattern.finditer(text_content):
             start_index_tag = text_widget.index(f'1.0 + {match.start()} chars')
             # Check if the tag starts *within* an existing code block
             if 'code' not in text_widget.tag_names(start_index_tag):
                 inner_start = text_widget.index(f'1.0 + {match.start(1)} chars')
                 inner_end = text_widget.index(f'1.0 + {match.end(1)} chars')
                 text_widget.tag_add(tag_name, inner_start, inner_end)

    text_widget.configure(state='disabled') # Make read-only


# --- Main Application Class ---
class ScreenshotApp:
    """Main application class handling UI, events, and Ollama interaction."""

    def __init__(self):
        self.root = tk.Tk()
        default_font = tkFont.nametofont('TkDefaultFont')
        default_font.configure(size=settings.DEFAULT_FONT_SIZE)
        self.root.option_add('*Font', default_font)

        self.capturer = ScreenshotCapturer(self)
        self.running = True
        self.hotkey_listener = None # Uses GlobalHotKeys
        self.listener_thread = None
        self.response_window = None
        self.tray_icon = None
        self.tray_thread = None
        self.icon_image = None

        if PYSTRAY_AVAILABLE:
            try:
                self.icon_image = Image.open(settings.ICON_PATH)
            except FileNotFoundError:
                print(f"Warning: Icon '{settings.ICON_PATH}' not found. "
                      f"Using default.")
                self.icon_image = self.create_default_icon()
            except Exception as e:
                print(f"Warning: Error loading icon '{settings.ICON_PATH}': {e}."
                      f" Using default.")
                self.icon_image = self.create_default_icon()
                # Check if status label exists before updating
                # Note: _setup_ui might not have run yet, handle potential AttributeError
                # self.update_status(settings.ICON_LOAD_FAIL_STATUS, settings.STATUS_COLOR_ERROR)

        self._setup_ui() # Setup UI after loading icon (or fallback)

    def create_default_icon(self):
        """Creates a simple fallback PIL image icon using settings."""
        # ... (create_default_icon remains the same) ...
        width = settings.DEFAULT_ICON_WIDTH
        height = settings.DEFAULT_ICON_HEIGHT
        image = Image.new('RGB', (width, height), color=settings.DEFAULT_ICON_BG_COLOR)
        d = ImageDraw.Draw(image)
        margin = 10 # Keep margin calculation simple for now
        d.rectangle(
            [(margin, margin), (width - margin, height - margin)],
            outline=settings.DEFAULT_ICON_RECT_COLOR,
            width=settings.DEFAULT_ICON_RECT_WIDTH
        )
        try:
            font = tkFont.Font(
                family=settings.DEFAULT_ICON_FONT_FAMILY,
                size=settings.DEFAULT_ICON_FONT_SIZE,
                weight=settings.DEFAULT_ICON_FONT_WEIGHT
            )
        except tk.TclError:
            print(f"Warning: Default icon font '{settings.DEFAULT_ICON_FONT_FAMILY}'"
                  " not found, using Tk default.")
            font = tkFont.Font(
                size=settings.DEFAULT_ICON_FONT_SIZE,
                weight=settings.DEFAULT_ICON_FONT_WEIGHT
            ) # Fallback size/weight
        # Basic text centering approximation
        text_width, text_height = d.textbbox((0, 0), settings.DEFAULT_ICON_TEXT, font=font)[2:4]
        text_x = (width - text_width) / 2
        text_y = (height - text_height) / 2
        d.text(
            (text_x, text_y),
            settings.DEFAULT_ICON_TEXT,
            fill=settings.DEFAULT_ICON_TEXT_COLOR,
            font=font
        )
        return image

    def _setup_ui(self):
        """Configures the main Tkinter window using settings."""
        # ... (_setup_ui remains the same) ...
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
            command=partial(self._trigger_capture, prompt=default_prompt)
        ).pack(pady=settings.PADDING_LARGE)

        exit_text = (settings.EXIT_BUTTON_TEXT_TRAY if PYSTRAY_AVAILABLE
                     else settings.EXIT_BUTTON_TEXT)
        tk.Button(self.root, text=exit_text, command=self.on_exit).pack(pady=settings.PADDING_SMALL)

        close_action = self.hide_to_tray if PYSTRAY_AVAILABLE else self.on_exit
        self.root.protocol('WM_DELETE_WINDOW', close_action)

    def _trigger_capture(self, prompt):
        """Safely triggers capture with a specific prompt on main thread."""
        # ... (_trigger_capture remains the same) ...
        print(f"Triggering capture with prompt: '{prompt[:30]}...'")
        if threading.current_thread() == threading.main_thread():
            self.capturer.capture_region(prompt)
        else:
             if self.root and self.root.winfo_exists():
                self.root.after(0, self.capturer.capture_region, prompt)

    # --- Ollama Interaction ---
    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str):
        """Starts Ollama request in a background thread using ollama_utils."""
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
        """
        try:
            # Call the utility function
            response_text = ollama_utils.request_ollama_analysis(screenshot, prompt)
            # Schedule success UI update on main thread
            self.root.after(0, self.display_ollama_response, response_text)

        # --- Handle specific Ollama errors ---
        except OllamaConnectionError as e:
            error_msg = settings.DIALOG_OLLAMA_CONN_ERROR_MSG.format(url=settings.OLLAMA_URL) # Use setting URL
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
            error_msg = settings.DIALOG_OLLAMA_TIMEOUT_MSG.format(url=settings.OLLAMA_URL) # Use setting URL
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
            # Use the detailed error message from the exception
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
         # --- Handle image encoding error from ollama_utils ---
        except ValueError as e:
             error_msg = f"Image Error: {e}"
             print(error_msg)
             self.root.after(
                 0, messagebox.showerror,
                 settings.DIALOG_PROCESSING_ERROR_TITLE, error_msg # Reuse processing error title
             )
             self.root.after(
                 0, self.update_status,
                 settings.ERROR_PREPARING_IMAGE_STATUS, settings.STATUS_COLOR_ERROR # Reuse status
             )
        # --- Handle other Ollama or unexpected errors ---
        except (OllamaError, Exception) as e:
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

    # --- Response Window (No changes needed) ---
    def display_ollama_response(self, response_text):
        """Displays the Ollama response in a formatted Toplevel window."""
        # ... (display_ollama_response remains the same) ...
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
            font=('TkDefaultFont', settings.DEFAULT_FONT_SIZE)
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

                # Update base font
                base_font_obj = tkFont.Font(font=txt_area['font'])
                base_font_obj.configure(size=new_size)
                txt_area.configure(font=base_font_obj)

                # Reconfigure tag fonts
                base_family = base_font_obj.actual()['family']
                code_family = settings.CODE_FONT_FAMILY
                try: tkFont.Font(family=code_family, size=new_size)
                except tk.TclError: code_family = base_family

                txt_area.tag_configure(
                    'bold', font=(base_family, new_size, 'bold')
                )
                txt_area.tag_configure(
                    'italic', font=(base_family, new_size, 'italic')
                )
                # Use offset for code font size calculation
                code_size = max(
                    settings.MIN_FONT_SIZE,
                    new_size + settings.CODE_FONT_SIZE_OFFSET
                )
                txt_area.tag_configure(
                    'code', font=(code_family, code_size, 'normal')
                )
                # Update label using format string from settings
                size_label.config(text=settings.FONT_SIZE_LABEL_FORMAT.format(size=new_size))
            except Exception as e:
                print(f'Error updating font size: {e}')

        # --- Slider ---
        font_slider = tk.Scale(
            control_frame, from_=settings.MIN_FONT_SIZE,
            to=settings.MAX_FONT_SIZE, orient=tk.HORIZONTAL, resolution=1,
            showvalue=0, # Hide default value display
            command=update_font_size
        )
        font_slider.set(settings.DEFAULT_FONT_SIZE)
        font_slider.pack(
            side=tk.LEFT, fill=tk.X, expand=True,
            padx=(0, settings.PADDING_LARGE) # Use padding setting
        )

        size_label = tk.Label(
            control_frame,
            text=settings.FONT_SIZE_LABEL_FORMAT.format(size=settings.DEFAULT_FONT_SIZE),
            width=settings.FONT_SIZE_LABEL_WIDTH # Use setting
        )
        size_label.pack(side=tk.LEFT)

        # --- Apply Initial Formatting ---
        apply_formatting_tags(
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
            raw_text = txt_area.get('1.0', tk.END).strip()
            self.response_window.clipboard_clear()
            self.response_window.clipboard_append(raw_text)
            copy_button.config(text=settings.COPIED_BUTTON_TEXT, relief=tk.SUNKEN)
            self.response_window.after(
                settings.COPY_BUTTON_RESET_DELAY_MS, # Use setting
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
        self.response_window.transient(self.root) # Keep above main window
        self.response_window.grab_set() # Modal behavior
        self.response_window.focus_force() # Give focus
        # Update status after response is shown
        ready_status = (settings.READY_STATUS_TEXT_TRAY if PYSTRAY_AVAILABLE
                        else settings.READY_STATUS_TEXT_NO_TRAY)
        self.update_status(ready_status, settings.STATUS_COLOR_READY)

    # --- Hotkey Listener (No changes needed) ---
    def start_hotkey_listener(self):
        """Sets up and starts the global hotkey listener using GlobalHotKeys."""
        # ... (start_hotkey_listener remains the same) ...
        print('Registering hotkeys:')
        hotkey_map = {}
        try:
            for action_name, details in settings.HOTKEY_ACTIONS.items():
                hotkey_str = details['hotkey']
                prompt = details['prompt']
                # Create partial function for callback with specific prompt
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

    # --- Status Update Method (No changes needed) ---
    def update_status(self, message, color=settings.STATUS_COLOR_DEFAULT):
        """Updates the status label in the main window (thread-safe)."""
        # ... (update_status remains the same) ...
        def _update():
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.config(text=message, fg=color)
            else:
                print(f'Status Update (UI not ready): {message}')

        if self.root and self.root.winfo_exists():
             self.root.after(0, _update) # Schedule on main thread
        else:
             print(f'Status Update (No UI): {message}')

    # --- System Tray Methods (No changes needed) ---
    def setup_tray_icon(self):
        """Creates and runs the system tray icon using settings."""
        # ... (setup_tray_icon remains the same) ...
        if not PYSTRAY_AVAILABLE or not self.icon_image:
            print('Info: System tray icon setup skipped.')
            return

        default_prompt = settings.HOTKEY_ACTIONS[
            settings.DEFAULT_MANUAL_ACTION]['prompt']
        menu = (
            pystray.MenuItem(
                settings.TRAY_SHOW_WINDOW_TEXT, # Use setting
                self.show_window, default=True,
                visible=lambda item: not self.root.winfo_viewable()
                         if self.root and self.root.winfo_exists() else False
            ),
            pystray.MenuItem(
                settings.TRAY_CAPTURE_TEXT, # Use setting
                partial(self._trigger_capture, prompt=default_prompt)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(settings.TRAY_EXIT_TEXT, self.on_exit) # Use setting
        )

        self.tray_icon = pystray.Icon(
            settings.TRAY_ICON_NAME, # Use setting
            self.icon_image,
            settings.TRAY_TOOLTIP, # Use setting
            menu
        )
        self.tray_thread = threading.Thread(
            target=self.tray_icon.run, daemon=True
        )
        self.tray_thread.start()
        print('System tray icon thread started.')

    def hide_to_tray(self):
        """Hides the main application window."""
        # ... (hide_to_tray remains the same) ...
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
            if self.tray_icon:
                self.tray_icon.update_menu() # Update menu visibility state
            print(settings.WINDOW_HIDDEN_STATUS) # Use setting

    def show_window(self):
        """Shows the main application window from the system tray."""
        # ... (show_window remains the same) ...
        def _show():
            if self.root and self.root.winfo_exists():
                 self.root.deiconify(); self.root.lift(); self.root.focus_force()
                 if self.tray_icon:
                     self.tray_icon.update_menu()
                 print(settings.WINDOW_RESTORED_STATUS) # Use setting
            else:
                 print('Cannot show window, root does not exist.')
        if self.root:
             self.root.after(0, _show) # Schedule on main thread


    # --- Exit Method (No changes needed) ---
    def on_exit(self):
        """Performs cleanup and exits the application."""
        # ... (on_exit remains the same) ...
        if not self.running: return # Prevent double-exit
        print(settings.EXITING_APP_STATUS) # Use setting
        self.running = False

        if self.hotkey_listener:
            print(settings.STOPPING_HOTKEYS_STATUS) # Use setting
            try: self.hotkey_listener.stop()
            except Exception as e: print(f'Error stopping hotkey listener: {e}')
        if self.listener_thread and self.listener_thread.is_alive():
            print('Waiting for listener thread to join...')
            self.listener_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS) # Use setting

        if self.tray_icon:
            print(settings.STOPPING_TRAY_STATUS) # Use setting
            self.tray_icon.stop()
        if self.tray_thread and self.tray_thread.is_alive():
             print('Waiting for tray thread to join...')
             self.tray_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS) # Use setting

        if self.root and self.root.winfo_exists():
            print('Destroying main window...')
            self.root.destroy()

        print(settings.APP_EXIT_COMPLETE_STATUS) # Use setting

    # --- Main Application Execution (No changes needed) ---
    def run(self):
        """Starts listeners, tray icon, and the main Tkinter event loop."""
        # ... (run remains the same) ...
        self.start_hotkey_listener()
        self.setup_tray_icon()

        status_msg = (settings.READY_STATUS_TEXT_TRAY if PYSTRAY_AVAILABLE
                      else settings.READY_STATUS_TEXT_NO_TRAY)
        self.update_status(status_msg, settings.STATUS_COLOR_READY)

        print('Starting main application loop (Tkinter)...')
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print('KeyboardInterrupt received, initiating exit...')
            self.on_exit()

        # Ensure cleanup if mainloop exits for other reasons
        if self.running:
             self.on_exit()
        print(settings.APP_FINISHED_STATUS) # Use setting


# --- Main Execution Guard (No changes needed) ---
def main():
    """Main function to initialize and run the application."""
    # ... (main remains the same) ...
    print('Screenshot to Ollama Tool Starting...')
    print(f'Platform: {platform.system()} {platform.release()}')

    # Settings are checked during import now
    if PYSTRAY_AVAILABLE:
        try:
            # Verify icon access early
            with Image.open(settings.ICON_PATH) as img:
                print(f"Tray icon '{settings.ICON_PATH}' loaded successfully.")
        except FileNotFoundError:
             if not messagebox.askokcancel(
                 settings.DIALOG_ICON_WARNING_TITLE, # Use setting
                 settings.DIALOG_ICON_WARNING_MSG.format(path=settings.ICON_PATH) # Use setting
                ): return
        except Exception as e:
             if not messagebox.askokcancel(
                 settings.DIALOG_ICON_ERROR_TITLE, # Use setting
                 settings.DIALOG_ICON_ERROR_MSG.format(path=settings.ICON_PATH, error=e) # Use setting
                ): return

    app = ScreenshotApp()
    app.run()


if __name__ == '__main__':
    main()