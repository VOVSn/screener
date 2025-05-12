import tkinter as tk
from tkinter import scrolledtext, messagebox, font as tkFont
import threading
import io
import platform
import time
import base64
import json
import re
from functools import partial

# --- Third-Party Imports ---
import pyautogui
from PIL import Image, ImageDraw
from pynput import keyboard # Using GlobalHotKeys below
import requests

# --- Local Settings Import ---
try:
    import settings
    # Validate DEFAULT_MANUAL_ACTION exists
    if settings.DEFAULT_MANUAL_ACTION not in settings.HOTKEY_ACTIONS:
        raise ImportError(
            f"DEFAULT_MANUAL_ACTION '{settings.DEFAULT_MANUAL_ACTION}' "
            f"not found in HOTKEY_ACTIONS keys in settings.py"
        )
except ImportError as e:
    err_msg = f'FATAL ERROR in settings: {e}'
    print(err_msg)
    try: # Attempt to show GUI error if possible
        root = tk.Tk(); root.withdraw()
        messagebox.showerror('Settings Error', f'Error loading settings.py:\n{e}')
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


# --- Screenshot Capturer Class ---


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
        self.selection_window.attributes('-alpha', 0.4) # Transparency
        self.selection_window.attributes('-topmost', True) # Stay on top
        self.selection_window.overrideredirect(True) # No window border/title
        self.selection_window.update_idletasks() # Ensure drawn before use

        canvas = tk.Canvas(self.selection_window, cursor='cross', bg='gray')
        canvas.pack(fill=tk.BOTH, expand=True)

        # --- Event Handlers ---
        def on_button_press(event):
            canvas.focus_set()
            self.start_x = self.selection_window.winfo_pointerx()
            self.start_y = self.selection_window.winfo_pointery()
            canvas_x, canvas_y = event.x, event.y
            self.rect_id = canvas.create_rectangle(
                canvas_x, canvas_y, canvas_x, canvas_y,
                outline='red', width=2, tags='selection'
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
                        0, messagebox.showerror, 'Internal Error',
                        'Capture prompt was lost.'
                    )
                    return
                try:
                    screenshot = pyautogui.screenshot(region=region_to_capture)
                    print('Screenshot captured. Processing...')
                    # Pass specific prompt to the processing method via main loop
                    self.app.root.after(
                        0, self.app.process_screenshot_with_ollama,
                        screenshot, prompt_for_ollama
                    )
                except Exception as e:
                    error_msg = f'Failed to capture screenshot: {e}'
                    print(f'Screenshot Error: {error_msg}')
                    self.app.root.after(
                        0, messagebox.showerror, 'Screenshot Error', error_msg
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


# --- Formatting Helper ---


def apply_formatting_tags(text_widget, text_content, initial_font_size):
    """Applies basic markdown and code block styling using Tkinter tags."""
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
    code_font_size = max(settings.MIN_FONT_SIZE - 1, initial_font_size - 1)
    text_widget.tag_configure(
        'code', background='#f0f0f0',
        font=(code_family, code_font_size, 'normal'),
        wrap=tk.WORD, lmargin1=10, lmargin2=10
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
    }
    for tag_name, pattern in inline_patterns.items():
        for match in pattern.finditer(text_content):
             start_index_tag = text_widget.index(f'1.0 + {match.start()} chars')
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

        self._setup_ui()

    def create_default_icon(self):
        """Creates a simple fallback PIL image icon."""
        width, height = 64, 64
        image = Image.new('RGB', (width, height), color='dimgray')
        d = ImageDraw.Draw(image)
        d.rectangle(
            [(10, 10), (width - 10, height - 10)],
            outline='dodgerblue', width=4
        )
        try:
            # Use a known font if possible for better consistency
            font = tkFont.Font(family='Arial', size=30, weight='bold')
        except tk.TclError:
            font = tkFont.Font(size=30, weight='bold') # Default fallback
        d.text((width / 3.5, height / 4), 'S', fill='white', font=font)
        return image

    def _setup_ui(self):
        """Configures the main Tkinter window."""
        self.root.title('Screenshot to Ollama')
        self.root.geometry('350x200')
        self.root.resizable(False, False)

        label = tk.Label(self.root, text='Screenshot Capture & Analysis')
        label.pack(pady=10)

        self.status_label = tk.Label(self.root, text='Initializing...', fg='gray')
        self.status_label.pack(pady=5)

        # Button uses the default action/prompt from settings
        default_prompt = settings.HOTKEY_ACTIONS[
            settings.DEFAULT_MANUAL_ACTION]['prompt']
        tk.Button(
            self.root, text='Capture Region Manually',
            command=partial(self._trigger_capture, prompt=default_prompt)
        ).pack(pady=10)

        exit_text = 'Exit Completely' if PYSTRAY_AVAILABLE else 'Exit'
        tk.Button(self.root, text=exit_text, command=self.on_exit).pack(pady=5)

        close_action = self.hide_to_tray if PYSTRAY_AVAILABLE else self.on_exit
        self.root.protocol('WM_DELETE_WINDOW', close_action)

    def _trigger_capture(self, prompt):
        """Safely triggers capture with a specific prompt on main thread."""
        print(f"Triggering capture with prompt: '{prompt[:30]}...'")
        if threading.current_thread() == threading.main_thread():
            self.capturer.capture_region(prompt)
        else:
             if self.root and self.root.winfo_exists():
                self.root.after(0, self.capturer.capture_region, prompt)

    # --- Ollama Interaction ---
    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str):
        """Encodes screenshot, starts Ollama request in background thread."""
        try:
            buffered = io.BytesIO()
            screenshot.save(buffered, format='PNG')
            img_byte = buffered.getvalue()
            img_base64 = base64.b64encode(img_byte).decode('utf-8')

            threading.Thread(
                target=self._send_to_ollama_thread,
                args=(img_base64, prompt),
                daemon=True
            ).start()
            self.update_status('Processing with Ollama...', 'darkorange')

        except Exception as e:
            error_msg = f'Error preparing image for Ollama: {e}'
            print(error_msg)
            self.root.after(0, messagebox.showerror, 'Processing Error', error_msg)
            self.update_status('Error preparing image.', 'red')

    def _send_to_ollama_thread(self, img_base64: str, prompt: str):
        """Sends request to Ollama API (runs in background thread)."""
        payload = {
            'model': settings.OLLAMA_MODEL,
            'prompt': prompt, # Use the specific prompt passed in
            'images': [img_base64],
            'stream': False
        }
        try:
            print(f'Sending request to: {settings.OLLAMA_URL}')
            print(f'Using model: {settings.OLLAMA_MODEL}')
            print(f"Using prompt: '{prompt[:60]}...'")
            response = requests.post(
                settings.OLLAMA_URL, json=payload, timeout=120 # 2 min timeout
            )
            response.raise_for_status() # Check for HTTP errors

            response_data = response.json()
            ollama_response_text = response_data.get(
                'response', 'No response content found in JSON.'
            )
            print('Ollama processing complete.')
            # Schedule UI update back on the main thread
            self.root.after(0, self.display_ollama_response, ollama_response_text)

        except requests.exceptions.ConnectionError:
            error_msg = (f'Connection Error: Could not connect to Ollama at '
                         f'{settings.OLLAMA_URL}. Is it running?')
            print(error_msg)
            self.root.after(0, messagebox.showerror, 'Ollama Connection Error', error_msg)
            self.root.after(0, self.update_status, 'Ollama connection failed.', 'red')
        except requests.exceptions.Timeout:
            error_msg = (f'Timeout: Ollama at {settings.OLLAMA_URL} '
                         f'took too long.')
            print(error_msg)
            self.root.after(0, messagebox.showerror, 'Ollama Timeout', error_msg)
            self.root.after(0, self.update_status, 'Ollama request timed out.', 'red')
        except requests.exceptions.RequestException as e:
            error_msg = f'Ollama Request Error: {e}'
            detail = ''
            try:
                 if e.response is not None:
                     detail = e.response.json().get('error', str(e))
                     error_msg = f'Ollama Request Error: {detail}'
            except (json.JSONDecodeError, AttributeError): pass
            print(error_msg)
            self.root.after(0, messagebox.showerror, 'Ollama Error', error_msg)
            self.root.after(0, self.update_status, 'Ollama request failed.', 'red')
        except Exception as e:
            error_msg = f'Unexpected error during Ollama communication: {e}'
            print(error_msg)
            self.root.after(0, messagebox.showerror, 'Unexpected Error', error_msg)
            self.root.after(0, self.update_status, 'Unexpected error.', 'red')

    # --- Response Window ---
    def display_ollama_response(self, response_text):
        """Displays the Ollama response in a formatted Toplevel window."""
        if self.response_window and self.response_window.winfo_exists():
            self.response_window.destroy()

        self.response_window = tk.Toplevel(self.root)
        self.response_window.title('Ollama Analysis')
        self.response_window.geometry('700x800')

        text_frame = tk.Frame(self.response_window)
        text_frame.pack(padx=10, pady=(10, 0), fill=tk.BOTH, expand=True)

        txt_area = scrolledtext.ScrolledText(
            text_frame, wrap=tk.WORD, relief=tk.FLAT, bd=0,
            font=('TkDefaultFont', settings.DEFAULT_FONT_SIZE)
        )
        txt_area.pack(fill=tk.BOTH, expand=True)

        control_frame = tk.Frame(self.response_window)
        control_frame.pack(padx=10, pady=5, fill=tk.X)

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
                code_size = max(settings.MIN_FONT_SIZE - 1, new_size - 1)
                txt_area.tag_configure(
                    'code', font=(code_family, code_size, 'normal')
                )
                size_label.config(text=f'Size: {new_size}pt')
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
        font_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        size_label = tk.Label(
            control_frame, text=f'Size: {settings.DEFAULT_FONT_SIZE}pt', width=10
        )
        size_label.pack(side=tk.LEFT)

        # --- Apply Initial Formatting ---
        apply_formatting_tags(
            txt_area, response_text, settings.DEFAULT_FONT_SIZE
        )

        # --- Button Frame ---
        button_frame = tk.Frame(self.response_window)
        button_frame.pack(pady=(5, 10), fill=tk.X, padx=10)

        def copy_to_clipboard():
            raw_text = txt_area.get('1.0', tk.END).strip()
            self.response_window.clipboard_clear()
            self.response_window.clipboard_append(raw_text)
            copy_button.config(text='Copied!', relief=tk.SUNKEN)
            self.response_window.after(
                2000, lambda: copy_button.config(text='Copy Response', relief=tk.RAISED)
            )

        copy_button = tk.Button(
            button_frame, text='Copy Response', command=copy_to_clipboard
        )
        copy_button.pack(side=tk.LEFT, padx=5)

        close_button = tk.Button(
            button_frame, text='Close', command=self.response_window.destroy
        )
        close_button.pack(side=tk.RIGHT, padx=5)

        # --- Window Behavior ---
        self.response_window.transient(self.root) # Keep above main window
        self.response_window.grab_set() # Modal behavior
        self.response_window.focus_force() # Give focus
        self.update_status('Ready. Hotkeys active or use tray.', 'blue')

    # --- Hotkey Listener ---
    def start_hotkey_listener(self):
        """Sets up and starts the global hotkey listener using GlobalHotKeys."""
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
            error_msg = (
                f'Failed to set up hotkey listener: {e}\n\nCommon causes:\n'
                '- Incorrect hotkey format in settings.py.\n'
                '- Accessibility/Input permissions missing (macOS/Linux).\n'
                '- Another app using the same hotkey.'
            )
            print(f'Error setting up hotkey listener: {e}')
            if self.root and self.root.winfo_exists():
                 self.root.after(
                    0, messagebox.showerror, 'Hotkey Error', error_msg
                 )
            self.update_status('Hotkey listener failed!', 'red')

    # --- Status Update Method ---
    def update_status(self, message, color='blue'):
        """Updates the status label in the main window (thread-safe)."""
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
        """Creates and runs the system tray icon."""
        if not PYSTRAY_AVAILABLE or not self.icon_image:
            print('Info: System tray icon setup skipped.')
            return

        default_prompt = settings.HOTKEY_ACTIONS[
            settings.DEFAULT_MANUAL_ACTION]['prompt']
        menu = (
            pystray.MenuItem(
                'Show Window', self.show_window, default=True,
                visible=lambda item: not self.root.winfo_viewable()
                         if self.root and self.root.winfo_exists() else False
            ),
            pystray.MenuItem(
                'Capture Region',
                partial(self._trigger_capture, prompt=default_prompt)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Exit', self.on_exit)
        )

        self.tray_icon = pystray.Icon(
            'screenshot_ollama', self.icon_image,
            'Screenshot to Ollama', menu
        )
        self.tray_thread = threading.Thread(
            target=self.tray_icon.run, daemon=True
        )
        self.tray_thread.start()
        print('System tray icon thread started.')

    def hide_to_tray(self):
        """Hides the main application window."""
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
            if self.tray_icon:
                self.tray_icon.update_menu() # Update menu visibility state
            print('Window hidden to system tray.')

    def show_window(self):
        """Shows the main application window from the system tray."""
        def _show():
            if self.root and self.root.winfo_exists():
                 self.root.deiconify(); self.root.lift(); self.root.focus_force()
                 if self.tray_icon:
                     self.tray_icon.update_menu()
                 print('Window restored from system tray.')
            else:
                 print('Cannot show window, root does not exist.')
        if self.root:
             self.root.after(0, _show) # Schedule on main thread

    # --- Exit Method ---
    def on_exit(self):
        """Performs cleanup and exits the application."""
        if not self.running: return # Prevent double-exit
        print('Exiting application...')
        self.running = False

        if self.hotkey_listener:
            print('Stopping hotkey listener...')
            try: self.hotkey_listener.stop()
            except Exception as e: print(f'Error stopping hotkey listener: {e}')
        if self.listener_thread and self.listener_thread.is_alive():
            print('Waiting for listener thread to join...')
            self.listener_thread.join(timeout=1.0)

        if self.tray_icon:
            print('Stopping system tray icon...')
            self.tray_icon.stop()
        if self.tray_thread and self.tray_thread.is_alive():
             self.tray_thread.join(timeout=1.0)

        if self.root and self.root.winfo_exists():
            print('Destroying main window...')
            self.root.destroy()

        print('Application exit sequence complete.')

    # --- Main Application Execution ---
    def run(self):
        """Starts listeners, tray icon, and the main Tkinter event loop."""
        self.start_hotkey_listener()
        self.setup_tray_icon()

        status_msg = 'Ready. Hotkeys active'
        status_msg += ' or use tray.' if PYSTRAY_AVAILABLE else '.'
        self.update_status(status_msg, 'blue')

        print('Starting main application loop (Tkinter)...')
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print('KeyboardInterrupt received, initiating exit...')
            self.on_exit()

        # Ensure cleanup if mainloop exits for other reasons
        if self.running:
             self.on_exit()
        print('Screenshot Tool finished.')


# --- Main Execution Guard ---


def main():
    """Main function to initialize and run the application."""
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
                 'Icon Warning',
                 f"Tray icon file '{settings.ICON_PATH}' not found.\n"
                 f"A default icon will be used. Continue?"
                ): return
        except Exception as e:
             if not messagebox.askokcancel(
                 'Icon Error',
                 f"Error loading tray icon '{settings.ICON_PATH}': {e}\n"
                 f"A default icon will be used. Continue?"
                ): return

    app = ScreenshotApp()
    app.run()


if __name__ == '__main__':
    main()