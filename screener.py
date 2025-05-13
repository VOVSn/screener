# screener.py

import tkinter as tk
from tkinter import scrolledtext, messagebox, font as tkFont, ttk
import threading
from functools import partial
import platform
import time

from PIL import Image
from pynput import keyboard

# --- Local Imports ---
try:
    import settings
    import ollama_utils
    from ollama_utils import (
        OllamaError, OllamaConnectionError, OllamaTimeoutError, OllamaRequestError
    )
    from capture import ScreenshotCapturer
    import ui_utils
except (ImportError, FileNotFoundError, ValueError) as e:
    # ... (initial error handling - unchanged) ...
    err_title = "Initialization Error"
    try:
        t_func = settings.T
        lang_for_err = settings.LANGUAGE
    except AttributeError: 
        def t_func_fallback(k, l=None):
            return UI_TEXTS_FALLBACK.get('en', {}).get(k, f"<{k} (super fallback)>")
        t_func = t_func_fallback
        lang_for_err = getattr(settings, 'DEFAULT_LANGUAGE', 'en')
        UI_TEXTS_FALLBACK = {'en': {
            'dialog_hotkey_json_error_title': 'Hotkey Config Error',
            'dialog_hotkey_json_error_msg': "Error loading or parsing '{file}':\n{error}",
            'dialog_settings_error_title': 'Settings Error', 
            'dialog_settings_error_msg': 'Critical error loading settings ({file}):\n{error}',
        }}
    if isinstance(e, (FileNotFoundError, ValueError)) and \
       (getattr(settings, 'HOTKEYS_CONFIG_FILE', 'hotkeys.json') in str(e) or \
        "DEFAULT_MANUAL_ACTION" in str(e) or "hotkey" in str(e).lower()):
        err_title = t_func('dialog_hotkey_json_error_title', lang_for_err)
        err_msg_template_str = t_func('dialog_hotkey_json_error_msg', lang_for_err)
        err_msg = err_msg_template_str.format(
            file=getattr(settings, 'HOTKEYS_CONFIG_FILE', 'hotkeys.json'), error=e
        )
    elif 'settings' in str(e).lower() or (isinstance(e, AttributeError) and 'settings' in str(e).lower()):
         err_title = t_func('dialog_settings_error_title', lang_for_err)
         err_msg_template_str = t_func('dialog_settings_error_msg', lang_for_err)
         err_msg = err_msg_template_str.format(file="settings.py or hotkeys.json", error=e)
    else: 
        module_name = "unknown module"
        if 'ollama_utils' in str(e): module_name = 'ollama_utils.py'
        elif 'capture' in str(e): module_name = 'capture.py'
        elif 'ui_utils' in str(e): module_name = 'ui_utils.py'
        err_msg = f'FATAL ERROR: {e}\n\nPlease ensure \'{module_name}\' is in the same directory as \'screener.py\'.'
    print(f"Startup Error: {err_msg}")
    try:
        root_err = tk.Tk(); root_err.withdraw()
        messagebox.showerror(err_title, err_msg)
        root_err.destroy()
    except Exception as tk_err:
        print(f"Failed to show Tkinter error dialog: {tk_err}")
    exit()

try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


class ScreenshotApp:
    def __init__(self):
        self.root = tk.Tk()
        # ... (rest of __init__ - unchanged from previous version that fixed TclError) ...
        default_font = tkFont.nametofont('TkDefaultFont')
        default_font.configure(size=settings.DEFAULT_FONT_SIZE)
        self.root.option_add('*Font', default_font)
        try:
            s = ttk.Style(); s.theme_use('clam') 
        except tk.TclError: pass
        self.capturer = ScreenshotCapturer(self)
        self.running = True 
        self.root_destroyed = False 
        self.hotkey_listener = None
        self.listener_thread = None
        self.response_window = None
        self.tray_icon = None
        self.tray_thread = None
        self.icon_image = None
        self.custom_prompt_var = tk.StringVar()
        self.is_rebuilding_tray = threading.Lock()
        self.main_label = None
        self.custom_prompt_label_widget = None
        self.hotkeys_list_label_widget = None
        self.hotkeys_text_area = None
        self.status_label = None
        self.capture_button = None
        self.exit_button = None
        if PYSTRAY_AVAILABLE:
            try: self.icon_image = Image.open(settings.ICON_PATH)
            except: self.icon_image = ui_utils.create_default_icon()
        self._setup_ui_structure()
        self._update_ui_text()

    # --- UI Setup and Update Methods (largely unchanged, ensure self.root_destroyed checks) ---
    def _setup_ui_structure(self):
        # ... (as in previous version) ...
        self.root.geometry(settings.MAIN_WINDOW_GEOMETRY)
        self.root.resizable(settings.WINDOW_RESIZABLE_WIDTH, settings.WINDOW_RESIZABLE_HEIGHT)
        main_frame = ttk.Frame(self.root, padding=settings.PADDING_LARGE)
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_label = ttk.Label(main_frame)
        self.main_label.pack(pady=(0, settings.PADDING_SMALL))
        prompt_frame = ttk.Frame(main_frame)
        prompt_frame.pack(fill=tk.X, pady=settings.PADDING_SMALL)
        self.custom_prompt_label_widget = ttk.Label(prompt_frame)
        self.custom_prompt_label_widget.pack(side=tk.LEFT, padx=(0, settings.PADDING_SMALL))
        self.custom_prompt_entry = ttk.Entry(prompt_frame, textvariable=self.custom_prompt_var, width=40)
        self.custom_prompt_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.hotkeys_list_label_widget = ttk.Label(main_frame)
        self.hotkeys_list_label_widget.pack(anchor=tk.W, pady=(settings.PADDING_SMALL, 0))
        self.hotkeys_text_area = tk.Text(main_frame, height=6, wrap=tk.WORD, relief=tk.GROOVE, borderwidth=1, font=('TkDefaultFont', settings.DEFAULT_FONT_SIZE - 2))
        self.hotkeys_text_area.pack(fill=tk.X, pady=(0, settings.PADDING_SMALL), expand=False)
        self.status_label = ttk.Label(main_frame, foreground=settings.STATUS_COLOR_DEFAULT, anchor=tk.W)
        self.status_label.pack(pady=settings.PADDING_SMALL, fill=tk.X)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(settings.PADDING_LARGE, 0), side=tk.BOTTOM)
        self.capture_button = ttk.Button(button_frame)
        self.capture_button.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.exit_button = ttk.Button(button_frame, command=lambda: self.on_exit()) 
        self.exit_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(settings.PADDING_SMALL,0))
        close_action = self.hide_to_tray if PYSTRAY_AVAILABLE else lambda: self.on_exit(is_wm_delete=True)
        self.root.protocol('WM_DELETE_WINDOW', close_action)

    def _update_ui_text(self):
        # ... (as in previous version, with self.root_destroyed checks) ...
        if self.root_destroyed: return 
        self.root.title(settings.T('app_title'))
        if self.main_label: self.main_label.config(text=settings.T('main_label_text'))
        if self.custom_prompt_label_widget: self.custom_prompt_label_widget.config(text=settings.T('custom_prompt_label'))
        if self.hotkeys_list_label_widget: self.hotkeys_list_label_widget.config(text=settings.T('hotkeys_list_label'))
        if self.hotkeys_text_area:
            self.hotkeys_text_area.config(state=tk.NORMAL)
            self.hotkeys_text_area.delete('1.0', tk.END)
            hotkey_display_text = []
            if settings.HOTKEY_ACTIONS:
                for action_name, details in settings.HOTKEY_ACTIONS.items():
                    desc = details.get('description', action_name) 
                    hotkey_display_text.append(f"{details['hotkey']}: {desc}")
                self.hotkeys_text_area.insert(tk.END, "\n".join(hotkey_display_text))
            else:
                self.hotkeys_text_area.insert(tk.END, "Error: Hotkeys not loaded.")
            self.hotkeys_text_area.config(state=tk.DISABLED)
        if self.status_label:
            current_text = self.status_label.cget("text")
            is_generic_status = False
            generic_statuses = [
                settings.T('initial_status_text', lang=lc) for lc in settings.SUPPORTED_LANGUAGES.keys()
            ] + [
                settings.T('ready_status_text_no_tray', lang=lc) for lc in settings.SUPPORTED_LANGUAGES.keys()
            ] + [
                settings.T('ready_status_text_tray', lang=lc) for lc in settings.SUPPORTED_LANGUAGES.keys()
            ]
            lang_change_prefixes = [
                settings.T('status_lang_changed_to', lang=lc).split('{')[0] 
                for lc in settings.SUPPORTED_LANGUAGES.keys()
            ]
            if current_text in generic_statuses or any(current_text.startswith(prefix) for prefix in lang_change_prefixes if prefix):
                is_generic_status = True
            if is_generic_status:
                ready_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
                self.status_label.config(text=settings.T(ready_key), foreground=settings.STATUS_COLOR_READY)
        if self.capture_button:
            self.capture_button.config(text=settings.T('capture_button_text'))
            default_manual_action_details = settings.HOTKEY_ACTIONS.get(settings.DEFAULT_MANUAL_ACTION)
            prompt_for_button = "Describe image (fallback)" 
            if default_manual_action_details:
                prompt_for_button = default_manual_action_details['prompt']
                if prompt_for_button == settings.CUSTOM_PROMPT_IDENTIFIER:
                    describe_action = settings.HOTKEY_ACTIONS.get('describe', {})
                    prompt_for_button = describe_action.get('prompt', "Describe fallback")
            self.capture_button.config(command=lambda p=prompt_for_button: self._trigger_capture_from_ui(p))
        if self.exit_button:
            exit_key = 'exit_button_text_tray' if PYSTRAY_AVAILABLE else 'exit_button_text'
            self.exit_button.config(text=settings.T(exit_key))

    # --- Core Logic Methods (largely unchanged, ensure self.root_destroyed checks) ---
    def _get_prompt_for_action(self, prompt_source):
        # ... (as in previous version, with self.root_destroyed checks) ...
        if self.root_destroyed: return None
        if prompt_source == settings.CUSTOM_PROMPT_IDENTIFIER:
            custom_prompt = self.custom_prompt_var.get().strip()
            if not custom_prompt:
                if not self.root_destroyed and self.root and self.root.winfo_exists():
                    messagebox.showwarning(settings.T('dialog_warning_title'), settings.T('custom_prompt_empty_warning'))
                return None
            return custom_prompt
        elif isinstance(prompt_source, str):
            return prompt_source
        else:
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                messagebox.showerror(settings.T('dialog_internal_error_title'), settings.T('dialog_internal_error_msg'))
            return None

    def _trigger_capture_from_ui(self, prompt_source):
        # ... (as in previous version, with self.root_destroyed checks) ...
        if self.root_destroyed: return
        self._trigger_capture(prompt_source, icon=None, item=None)

    def _trigger_capture(self, prompt_source, icon=None, item=None):
        # ... (as in previous version, with self.root_destroyed checks) ...
        if self.root_destroyed: return
        actual_prompt = self._get_prompt_for_action(prompt_source)
        if actual_prompt is None:
            ready_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
            self.update_status(settings.T(ready_key), settings.STATUS_COLOR_READY)
            return
        self.capturer.capture_region(actual_prompt)
    
    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str):
        # ... (as in previous version, with self.root_destroyed checks) ...
        if self.root_destroyed: return
        self.update_status(settings.T('processing_status_text'), settings.STATUS_COLOR_PROCESSING)
        threading.Thread(target=self._ollama_request_worker, args=(screenshot, prompt), daemon=True).start()

    def _ollama_request_worker(self, screenshot: Image.Image, prompt: str):
        # ... (as in previous version, with self.root_destroyed checks) ...
        if self.root_destroyed: return
        try:
            response_text = ollama_utils.request_ollama_analysis(screenshot, prompt)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.display_ollama_response, response_text)
        except Exception as e:
            print(f"Ollama worker error: {e}")
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.update_status, settings.T('unexpected_error_status'), settings.STATUS_COLOR_ERROR)

    def display_ollama_response(self, response_text):
        # ... (as in previous version, with self.root_destroyed checks and robust widget checks) ...
        if self.root_destroyed: return
        if self.response_window and self.response_window.winfo_exists(): self.response_window.destroy()
        if not self.root or not self.root.winfo_exists(): return 
        self.response_window = tk.Toplevel(self.root)
        self.response_window.title(settings.T('response_window_title'))
        self.response_window.geometry(settings.RESPONSE_WINDOW_GEOMETRY)
        text_frame = ttk.Frame(self.response_window)
        text_frame.pack(padx=settings.RESPONSE_TEXT_PADDING_X, pady=settings.RESPONSE_TEXT_PADDING_Y_TOP, fill=tk.BOTH, expand=True)
        txt_area = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, relief=tk.FLAT, bd=0, font=('TkDefaultFont', settings.DEFAULT_FONT_SIZE))
        txt_area.pack(fill=tk.BOTH, expand=True)
        control_frame = ttk.Frame(self.response_window)
        control_frame.pack(padx=settings.RESPONSE_CONTROL_PADDING_X, pady=settings.RESPONSE_CONTROL_PADDING_Y, fill=tk.X)
        self.current_response_font_size = settings.DEFAULT_FONT_SIZE 
        size_label_ref = {'widget': None} 
        def update_font_size_display(size_val_str):
            if self.root_destroyed: return
            try:
                new_size = int(float(size_val_str))
                if not (settings.MIN_FONT_SIZE <= new_size <= settings.MAX_FONT_SIZE): return
                self.current_response_font_size = new_size
                if size_label_ref['widget'] and size_label_ref['widget'].winfo_exists():
                    size_label_ref['widget'].config(text=settings.T('font_size_label_format').format(size=new_size))
                if txt_area.winfo_exists():
                    base_font_obj = tkFont.Font(font=txt_area['font'])
                    base_font_obj.configure(size=new_size)
                    txt_area.configure(font=base_font_obj)
                    ui_utils.apply_formatting_tags(txt_area, response_text, new_size)
            except (ValueError, tk.TclError): pass
        font_slider = ttk.Scale(control_frame, from_=settings.MIN_FONT_SIZE, to=settings.MAX_FONT_SIZE, orient=tk.HORIZONTAL, value=self.current_response_font_size, command=update_font_size_display)
        font_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, settings.PADDING_LARGE))
        size_label = ttk.Label(control_frame, text=settings.T('font_size_label_format').format(size=self.current_response_font_size), width=settings.FONT_SIZE_LABEL_WIDTH)
        size_label.pack(side=tk.LEFT)
        size_label_ref['widget'] = size_label
        ui_utils.apply_formatting_tags(txt_area, response_text, self.current_response_font_size)
        button_frame_resp = ttk.Frame(self.response_window)
        button_frame_resp.pack(pady=settings.RESPONSE_BUTTON_PADDING_Y, fill=tk.X, padx=settings.RESPONSE_BUTTON_PADDING_X)
        copy_button_ref = {'widget': None}
        def copy_to_clipboard_command():
            if self.root_destroyed or not (self.response_window and self.response_window.winfo_exists()): return
            raw_text_content = txt_area.get('1.0', tk.END).strip()
            try:
                self.response_window.clipboard_clear()
                self.response_window.clipboard_append(raw_text_content)
                if copy_button_ref['widget'] and copy_button_ref['widget'].winfo_exists():
                    copy_button_ref['widget'].config(text=settings.T('copied_button_text'))
                    if self.response_window and self.response_window.winfo_exists():
                        self.response_window.after(settings.COPY_BUTTON_RESET_DELAY_MS, 
                            lambda: copy_button_ref['widget'].config(text=settings.T('copy_button_text')) if copy_button_ref['widget'] and copy_button_ref['widget'].winfo_exists() else None)
            except tk.TclError as e:
                if not self.root_destroyed and self.response_window and self.response_window.winfo_exists():
                    messagebox.showerror("Clipboard Error", f"Could not copy: {e}", parent=self.response_window)
        copy_button = ttk.Button(button_frame_resp, text=settings.T('copy_button_text'), command=copy_to_clipboard_command)
        copy_button.pack(side=tk.LEFT, padx=settings.PADDING_SMALL)
        copy_button_ref['widget'] = copy_button
        close_button = ttk.Button(button_frame_resp, text=settings.T('close_button_text'), command=lambda: self.response_window.destroy() if self.response_window and self.response_window.winfo_exists() else None)
        close_button.pack(side=tk.RIGHT, padx=settings.PADDING_SMALL)
        if self.response_window and self.response_window.winfo_exists(): # Ensure it still exists before transient
            self.response_window.transient(self.root)
            self.response_window.grab_set()
            self.response_window.focus_force()
        ready_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
        self.update_status(settings.T(ready_key), settings.STATUS_COLOR_READY)

    # --- Hotkey and Status Methods (largely unchanged, ensure self.root_destroyed checks) ---
    def _stop_hotkey_listener(self):
        # ... (as in previous version) ...
        if self.hotkey_listener:
            try: self.hotkey_listener.stop()
            except Exception: pass
            self.hotkey_listener = None
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=0.5)
            if self.listener_thread.is_alive(): print("Warning: Hotkey listener thread did not join cleanly.")
            self.listener_thread = None

    def start_hotkey_listener(self):
        # ... (as in previous version, with self.root_destroyed checks) ...
        if self.root_destroyed: return
        self._stop_hotkey_listener()
        hotkey_map = {}
        try:
            if not settings.HOTKEY_ACTIONS:
                err_msg = f"{settings.T('hotkey_failed_status')}: No hotkeys defined."
                self.update_status(err_msg, settings.STATUS_COLOR_ERROR)
                return
            for action_name, details in settings.HOTKEY_ACTIONS.items():
                hotkey_map[details['hotkey']] = partial(self._trigger_capture, prompt_source=details['prompt'])
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            self.listener_thread = threading.Thread(target=self.hotkey_listener.run, daemon=True, name="HotkeyListenerThread")
            self.listener_thread.start()
        except Exception as e:
            error_msg = settings.T('dialog_hotkey_error_msg').format(error=e)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                 self.root.after(0, messagebox.showerror, settings.T('dialog_hotkey_error_title'), error_msg)
            self.update_status(settings.T('hotkey_failed_status'), settings.STATUS_COLOR_ERROR)

    def update_status(self, message, color=None):
        # ... (as in previous version, with self.root_destroyed checks) ...
        if self.root_destroyed: return
        def _update():
            if not self.root_destroyed and hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                self.status_label.config(text=message)
                if color: self.status_label.config(foreground=color)
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            self.root.after(0, _update)

    # --- Tray Icon Methods (Key Changes Here) ---
    def _build_tray_menu(self):
        # ... (as in previous version, with self.root_destroyed checks) ...
        if self.root_destroyed: return tuple() 
        lang_submenu_items = []
        for code, name in settings.SUPPORTED_LANGUAGES.items():
            action = partial(self.change_language, code) 
            item = pystray.MenuItem( name, action,
                checked=lambda item_param, current_code_param=code: settings.LANGUAGE == current_code_param,
                radio=True )
            lang_submenu_items.append(item)
        default_manual_action_details = settings.HOTKEY_ACTIONS.get(settings.DEFAULT_MANUAL_ACTION)
        tray_capture_prompt = "Describe (tray fallback)"
        if default_manual_action_details:
            tray_capture_prompt = default_manual_action_details['prompt']
            if tray_capture_prompt == settings.CUSTOM_PROMPT_IDENTIFIER:
                describe_action = settings.HOTKEY_ACTIONS.get('describe', {})
                tray_capture_prompt = describe_action.get('prompt', "Describe image (tray fallback).")
        menu = (
            pystray.MenuItem(settings.T('tray_show_window_text'), self.show_window, default=True,
                visible=lambda item_param: not self.root_destroyed and self.root and self.root.winfo_exists() and not self.root.winfo_viewable()),
            pystray.MenuItem(settings.T('tray_capture_text'), partial(self._trigger_capture, prompt_source=tray_capture_prompt)),
            pystray.MenuItem(settings.T('tray_language_text'), pystray.Menu(*lang_submenu_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(settings.T('tray_exit_text'), lambda: self.on_exit(from_tray=True))
        )
        return menu

    def _request_rebuild_tray_icon_from_main_thread(self):
        if self.root_destroyed: return
        if self.root and self.root.winfo_exists():
            # Use a small delay for the 'after' call to allow current event processing
            # in the pystray thread to potentially complete before we try to stop it.
            self.root.after(100, self._rebuild_tray_icon_on_main_thread) # 100ms delay
        # else: print("Error: Cannot schedule tray rebuild, Tkinter root not available.") # Less verbose

    def _rebuild_tray_icon_on_main_thread(self):
        if self.root_destroyed: return
        if not PYSTRAY_AVAILABLE or not self.icon_image: return

        if not self.is_rebuilding_tray.acquire(blocking=False):
            # print("Tray rebuild already in progress, skipping.") # Less verbose
            return
        
        current_thread_name = threading.current_thread().name
        # print(f"Rebuilding tray on thread: {current_thread_name}") # Verbose

        try:
            old_tray_instance = self.tray_icon
            old_tray_thread = self.tray_thread

            if old_tray_instance:
                # print(f"Stopping existing tray icon (instance: {old_tray_instance})...") # Verbose
                old_tray_instance.stop() # Signal the icon to stop
                self.tray_icon = None # Nullify the instance variable

            # Give the old thread a moment to process the stop signal
            if old_tray_thread and old_tray_thread.is_alive():
                # print(f"Waiting for old tray thread ({old_tray_thread.name}) to finish after stop signal...") # Verbose
                old_tray_thread.join(timeout=1.5) # Slightly longer timeout
                if old_tray_thread.is_alive():
                    print(f"Warning: Old tray thread ({old_tray_thread.name}) did not stop cleanly after 1.5s.")
                # else: print(f"Old tray thread ({old_tray_thread.name}) stopped.") # Verbose
            self.tray_thread = None # Nullify thread variable

            # Create and start the new tray icon
            # print("Building and starting new tray icon...") # Verbose
            new_menu = self._build_tray_menu()
            if not new_menu and PYSTRAY_AVAILABLE: # If menu build failed (e.g. root destroyed during process)
                print("Error: Failed to build new tray menu, aborting tray rebuild.")
                self.is_rebuilding_tray.release()
                return

            self.tray_icon = pystray.Icon(
                settings.TRAY_ICON_NAME, self.icon_image, 
                settings.T('app_title'), new_menu
            )
            self.tray_thread = threading.Thread(
                target=self.tray_icon.run, daemon=True, name="PystrayThread" 
            ) # Explicitly name new threads
            self.tray_thread.start()
            # print(f"New tray icon thread ({self.tray_thread.name}) started with icon ({self.tray_icon}).") # Verbose
        
        except Exception as e:
            print(f"Exception during tray rebuild: {e}")
        finally:
            self.is_rebuilding_tray.release()
            # print("Tray rebuild lock released.") # Verbose

    def setup_tray_icon(self):
        # ... (as in previous version) ...
        if self.root_destroyed: return
        if not PYSTRAY_AVAILABLE or not self.icon_image: return
        self._rebuild_tray_icon_on_main_thread()

    def change_language(self, lang_code, icon=None, item=None):
        # ... (as in previous version) ...
        if self.root_destroyed: return
        if settings.LANGUAGE == lang_code: return 
        
        # print(f"Change language requested for: {lang_code}. Current thread: {threading.current_thread().name}") # Verbose

        if settings.set_language(lang_code): 
            self._update_ui_text()       
            self.start_hotkey_listener() 
            self._request_rebuild_tray_icon_from_main_thread()
            lang_name = settings.SUPPORTED_LANGUAGES.get(lang_code, lang_code)
            self.update_status(settings.T('status_lang_changed_to').format(lang_name=lang_name), settings.STATUS_COLOR_READY)
        else:
            self.update_status(f"Failed to change to {lang_code}.", settings.STATUS_COLOR_ERROR)

    def hide_to_tray(self, event=None): 
        # ... (as in previous version) ...
        if self.root_destroyed: return
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
            if self.tray_icon and hasattr(self.tray_icon, 'update_menu'): self.tray_icon.update_menu()

    def show_window(self, icon=None, item=None): 
        # ... (as in previous version) ...
        if self.root_destroyed: return
        def _show():
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                 self.root.deiconify(); self.root.lift(); self.root.focus_force()
                 if self.tray_icon and hasattr(self.tray_icon, 'update_menu'): self.tray_icon.update_menu()
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            self.root.after(0, _show)


    # --- Exit Logic Methods (Crucial for clean shutdown) ---
    def on_exit(self, icon=None, item=None, from_tray=False, is_wm_delete=False):
        if not self.running:
            # print("Exit already in progress.") # Less verbose
            return
        
        # print(f"on_exit called. from_tray={from_tray}, is_wm_delete={is_wm_delete}, thread={threading.current_thread().name}") # Verbose
        print(settings.T('exiting_app_status'))
        self.running = False 

        self._stop_hotkey_listener()
        # print(settings.T('stopping_hotkeys_status')) # Verbose

        # Request tray to stop. The actual stop and join will be handled carefully.
        if PYSTRAY_AVAILABLE and self.tray_icon:
            # print(settings.T('stopping_tray_status')) # Verbose
            try:
                # print(f"Requesting tray_icon.stop() for icon: {self.tray_icon}") # Verbose
                self.tray_icon.stop() # This should make the tray_thread exit its run loop
            except Exception as e:
                print(f"Error during tray_icon.stop(): {e}")
        
        # The mainloop's exit or root.destroy() will allow the main thread to proceed to final cleanup in run()
        # For WM_DELETE_WINDOW or UI Exit button (main thread calls):
        if not self.root_destroyed and self.root and self.root.winfo_exists() and threading.current_thread() == threading.main_thread():
            # print("Destroying root from on_exit (main thread)") # Verbose
            self.root.destroy() # This will cause mainloop to exit
            self.root_destroyed = True
        elif not self.root_destroyed and self.root and self.root.winfo_exists(): # Called from another thread
             self.root.after(0, self._destroy_root_safely)


    def _destroy_root_safely(self):
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            # print('Destroying main window (scheduled)...') # Verbose
            try:
                self.root.destroy()
            except tk.TclError as e:
                print(f"TclError during scheduled root destroy (already gone?): {e}")
            except Exception as e:
                print(f"Error during scheduled root destroy: {e}")
        self.root_destroyed = True


    def run(self):
        if self.root_destroyed: return
        self.start_hotkey_listener()
        self.setup_tray_icon()       
        status_msg_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
        self.update_status(settings.T(status_msg_key), settings.STATUS_COLOR_READY)
        
        # print('Starting main application loop (Tkinter)...') # Verbose
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            # print('KeyboardInterrupt received, initiating exit...') # Verbose
            self.on_exit() 
        except Exception as e:
            print(f"Unhandled error in mainloop: {e}")
            self.on_exit() # Attempt graceful cleanup
        
        # This block executes after mainloop() has exited.
        # This is the definitive place to ensure all threads are joined.
        # print("Mainloop exited. Performing final cleanup...") # Verbose

        if self.running: # If on_exit wasn't the cause of mainloop exit or didn't complete
            self.running = False # Ensure it's false
            self._stop_hotkey_listener() # Stop again if it was restarted or failed
        
        # Join tray thread here, after mainloop is confirmed down
        if PYSTRAY_AVAILABLE and self.tray_thread and self.tray_thread.is_alive():
            # print(f"Final attempt to join tray thread ({self.tray_thread.name}) post-mainloop...") # Verbose
            # icon.stop() should have been called by on_exit.
            # If tray_icon still exists and is visible, it means stop might not have been effective.
            if self.tray_icon and hasattr(self.tray_icon, 'visible') and self.tray_icon.visible:
                try:
                    # print("Tray icon still visible, attempting stop again.") # Verbose
                    self.tray_icon.stop()
                except Exception as e:
                    print(f"Error stopping tray icon post-mainloop: {e}")

            self.tray_thread.join(timeout=2.0) # Give it a bit more time on final exit
            if self.tray_thread.is_alive():
                print(f"Warning: Tray thread ({self.tray_thread.name}) still alive after final join attempt.")
            # else: print(f"Tray thread ({self.tray_thread.name}) successfully joined post-mainloop.") # Verbose
        
        # Ensure root is marked as destroyed if not already
        if not self.root_destroyed:
            # print("Marking root as destroyed post-mainloop (if not already done by on_exit).") # Verbose
            self.root_destroyed = True # Mainloop is over, root is effectively gone

        print(settings.T('app_exit_complete_status')) # Moved this to be more accurate
        print(settings.T('app_finished_status'))


def main():
    # ... (main function - unchanged) ...
    print('Screenshot to Ollama Tool Starting...')
    print(f'Platform: {platform.system()} {platform.release()}')
    print(f"App lang: {settings.LANGUAGE} ({settings.SUPPORTED_LANGUAGES.get(settings.LANGUAGE, '')})")
    if PYSTRAY_AVAILABLE:
        try:
            with Image.open(settings.ICON_PATH): pass 
        except FileNotFoundError:
             root_check = tk.Tk(); root_check.withdraw()
             proceed = messagebox.askokcancel(settings.T('dialog_icon_warning_title'), settings.T('dialog_icon_warning_msg').format(path=settings.ICON_PATH))
             root_check.destroy()
             if not proceed: return
        except Exception as e:
             root_check = tk.Tk(); root_check.withdraw()
             proceed = messagebox.askokcancel(settings.T('dialog_icon_error_title'), settings.T('dialog_icon_error_msg').format(path=settings.ICON_PATH, error=e))
             root_check.destroy()
             if not proceed: return
    app = ScreenshotApp()
    app.run()

if __name__ == '__main__':
    main()