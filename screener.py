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
    print('Info: pystray library not found. System tray icon disabled.')


class ScreenshotApp:
    def __init__(self):
        self.root = tk.Tk()
        default_font = tkFont.nametofont('TkDefaultFont')
        default_font.configure(size=settings.DEFAULT_FONT_SIZE)
        self.root.option_add('*Font', default_font)
        try:
            s = ttk.Style()
            s.theme_use('clam') 
        except tk.TclError: pass

        self.capturer = ScreenshotCapturer(self)
        self.running = True
        self.hotkey_listener = None
        self.listener_thread = None
        self.response_window = None
        self.tray_icon = None
        self.tray_thread = None # Stores the pystray thread
        self.icon_image = None
        self.custom_prompt_var = tk.StringVar()
        self.is_rebuilding_tray = threading.Lock() # Lock for tray rebuilding

        self.main_label = None
        self.custom_prompt_label_widget = None
        self.hotkeys_list_label_widget = None
        self.hotkeys_text_area = None
        self.status_label = None
        self.capture_button = None
        self.exit_button = None

        if PYSTRAY_AVAILABLE:
            try:
                self.icon_image = Image.open(settings.ICON_PATH)
            except FileNotFoundError:
                self.icon_image = ui_utils.create_default_icon()
            except Exception:
                self.icon_image = ui_utils.create_default_icon()

        self._setup_ui_structure()
        self._update_ui_text()

    def _setup_ui_structure(self):
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
        close_action = self.hide_to_tray if PYSTRAY_AVAILABLE else lambda: self.on_exit()
        self.root.protocol('WM_DELETE_WINDOW', close_action)

    def _update_ui_text(self):
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
            # Check for language change status prefix
            lang_change_prefixes = [
                settings.T('status_lang_changed_to', lang=lc).split('{')[0] 
                for lc in settings.SUPPORTED_LANGUAGES.keys()
            ]
            if current_text in generic_statuses or any(current_text.startswith(prefix) for prefix in lang_change_prefixes):
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

    def _get_prompt_for_action(self, prompt_source):
        if prompt_source == settings.CUSTOM_PROMPT_IDENTIFIER:
            custom_prompt = self.custom_prompt_var.get().strip()
            if not custom_prompt:
                messagebox.showwarning(settings.T('dialog_warning_title'), settings.T('custom_prompt_empty_warning'))
                return None
            return custom_prompt
        elif isinstance(prompt_source, str):
            return prompt_source
        else:
            messagebox.showerror(settings.T('dialog_internal_error_title'), settings.T('dialog_internal_error_msg'))
            return None

    def _trigger_capture_from_ui(self, prompt_source):
        self._trigger_capture(prompt_source, icon=None, item=None)

    def _trigger_capture(self, prompt_source, icon=None, item=None):
        actual_prompt = self._get_prompt_for_action(prompt_source)
        if actual_prompt is None:
            ready_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
            self.update_status(settings.T(ready_key), settings.STATUS_COLOR_READY)
            return
        self.capturer.capture_region(actual_prompt)

    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str):
        self.update_status(settings.T('processing_status_text'), settings.STATUS_COLOR_PROCESSING)
        threading.Thread(target=self._ollama_request_worker, args=(screenshot, prompt), daemon=True).start()

    def _ollama_request_worker(self, screenshot: Image.Image, prompt: str):
        try:
            response_text = ollama_utils.request_ollama_analysis(screenshot, prompt)
            self.root.after(0, self.display_ollama_response, response_text)
        except OllamaConnectionError:
            msg, title = settings.T('dialog_ollama_conn_error_msg').format(url=settings.OLLAMA_URL), settings.T('dialog_ollama_conn_error_title')
            self.root.after(0, messagebox.showerror, title, msg)
            self.root.after(0, self.update_status, settings.T('ollama_conn_failed_status'), settings.STATUS_COLOR_ERROR)
        except OllamaTimeoutError:
            msg, title = settings.T('dialog_ollama_timeout_msg').format(url=settings.OLLAMA_URL), settings.T('dialog_ollama_timeout_title')
            self.root.after(0, messagebox.showerror, title, msg)
            self.root.after(0, self.update_status, settings.T('ollama_timeout_status'), settings.STATUS_COLOR_ERROR)
        except OllamaRequestError as e:
            msg = f"{settings.T('ollama_request_failed_status')}: {e.detail or str(e)}"
            self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_error_title'), msg)
            self.root.after(0, self.update_status, settings.T('ollama_request_failed_status'), settings.STATUS_COLOR_ERROR)
        except ValueError as e: 
            msg = f"{settings.T('error_preparing_image_status')}: {e}"
            self.root.after(0, messagebox.showerror, settings.T('dialog_processing_error_title'), msg)
            self.root.after(0, self.update_status, settings.T('error_preparing_image_status'), settings.STATUS_COLOR_ERROR)
        except Exception as e:
            msg = f"{settings.T('unexpected_error_status')}: {e}"
            self.root.after(0, messagebox.showerror, settings.T('dialog_unexpected_error_title'), msg)
            self.root.after(0, self.update_status, settings.T('unexpected_error_status'), settings.STATUS_COLOR_ERROR)

    def display_ollama_response(self, response_text):
        if self.response_window and self.response_window.winfo_exists(): self.response_window.destroy()
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
        def update_font_size_display(size_val_str):
            try:
                new_size = int(float(size_val_str))
                if not (settings.MIN_FONT_SIZE <= new_size <= settings.MAX_FONT_SIZE): return
                self.current_response_font_size = new_size
                size_label.config(text=settings.T('font_size_label_format').format(size=new_size))
                base_font_obj = tkFont.Font(font=txt_area['font'])
                base_font_obj.configure(size=new_size)
                txt_area.configure(font=base_font_obj)
                ui_utils.apply_formatting_tags(txt_area, response_text, new_size)
            except ValueError: pass
        font_slider = ttk.Scale(control_frame, from_=settings.MIN_FONT_SIZE, to=settings.MAX_FONT_SIZE, orient=tk.HORIZONTAL, value=self.current_response_font_size, command=update_font_size_display)
        font_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, settings.PADDING_LARGE))
        size_label = ttk.Label(control_frame, text=settings.T('font_size_label_format').format(size=self.current_response_font_size), width=settings.FONT_SIZE_LABEL_WIDTH)
        size_label.pack(side=tk.LEFT)
        ui_utils.apply_formatting_tags(txt_area, response_text, self.current_response_font_size)
        button_frame_resp = ttk.Frame(self.response_window)
        button_frame_resp.pack(pady=settings.RESPONSE_BUTTON_PADDING_Y, fill=tk.X, padx=settings.RESPONSE_BUTTON_PADDING_X)
        copy_button = ttk.Button(button_frame_resp, text=settings.T('copy_button_text'))
        def copy_to_clipboard_command():
            raw_text_content = txt_area.get('1.0', tk.END).strip()
            try:
                self.response_window.clipboard_clear()
                self.response_window.clipboard_append(raw_text_content)
                copy_button.config(text=settings.T('copied_button_text'))
                self.response_window.after(settings.COPY_BUTTON_RESET_DELAY_MS, lambda: copy_button.config(text=settings.T('copy_button_text')))
            except tk.TclError as e:
                messagebox.showerror("Clipboard Error", f"Could not copy: {e}", parent=self.response_window)
        copy_button.config(command=copy_to_clipboard_command)
        copy_button.pack(side=tk.LEFT, padx=settings.PADDING_SMALL)
        close_button = ttk.Button(button_frame_resp, text=settings.T('close_button_text'), command=self.response_window.destroy)
        close_button.pack(side=tk.RIGHT, padx=settings.PADDING_SMALL)
        self.response_window.transient(self.root)
        self.response_window.grab_set()
        self.response_window.focus_force()
        ready_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
        self.update_status(settings.T(ready_key), settings.STATUS_COLOR_READY)

    def _stop_hotkey_listener(self):
        if self.hotkey_listener:
            try: self.hotkey_listener.stop()
            except Exception: pass
            self.hotkey_listener = None
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=0.5)
            self.listener_thread = None

    def start_hotkey_listener(self):
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
            self.listener_thread = threading.Thread(target=self.hotkey_listener.run, daemon=True)
            self.listener_thread.start()
        except Exception as e:
            error_msg = settings.T('dialog_hotkey_error_msg').format(error=e)
            if self.root and self.root.winfo_exists():
                 self.root.after(0, messagebox.showerror, settings.T('dialog_hotkey_error_title'), error_msg)
            self.update_status(settings.T('hotkey_failed_status'), settings.STATUS_COLOR_ERROR)

    def update_status(self, message, color=None):
        def _update():
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.config(text=message)
                if color: self.status_label.config(foreground=color)
        if self.root and self.root.winfo_exists(): self.root.after(0, _update)
        else: print(f'Status (No UI): {message}')

    def _build_tray_menu(self):
        lang_submenu_items = []
        for code, name in settings.SUPPORTED_LANGUAGES.items():
            action = partial(self.change_language, code) 
            item = pystray.MenuItem(
                name, action,
                checked=lambda item_param, current_code_param=code: settings.LANGUAGE == current_code_param,
                radio=True
            )
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
                visible=lambda item_param: not self.root.winfo_viewable() if self.root and self.root.winfo_exists() else False),
            pystray.MenuItem(settings.T('tray_capture_text'), partial(self._trigger_capture, prompt_source=tray_capture_prompt)),
            pystray.MenuItem(settings.T('tray_language_text'), pystray.Menu(*lang_submenu_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(settings.T('tray_exit_text'), self.on_exit)
        )
        return menu

    def _request_rebuild_tray_icon_from_main_thread(self):
        """Schedules the tray icon rebuild on the main Tkinter thread."""
        if self.root and self.root.winfo_exists():
            self.root.after(0, self._rebuild_tray_icon_on_main_thread)
        else:
            print("Error: Cannot schedule tray rebuild, Tkinter root not available.")


    def _rebuild_tray_icon_on_main_thread(self):
        """Actually performs the tray icon stop/start. Runs on main thread."""
        if not PYSTRAY_AVAILABLE or not self.icon_image:
            return

        # Use a lock to prevent concurrent rebuilds if `after` calls stack up
        if not self.is_rebuilding_tray.acquire(blocking=False):
            print("Tray rebuild already in progress, skipping.")
            return
        
        try:
            old_tray_thread = None
            if self.tray_icon:
                print("Stopping existing tray icon...")
                self.tray_icon.stop() # This should signal the tray_thread to exit its run loop
                old_tray_thread = self.tray_thread # Keep a reference to the old thread
                self.tray_icon = None
                self.tray_thread = None # Clear current thread reference

            # Create and start the new tray icon and its thread
            print("Starting new tray icon...")
            self.tray_icon = pystray.Icon(
                settings.TRAY_ICON_NAME,
                self.icon_image,
                settings.T('app_title'),
                self._build_tray_menu()
            )
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True, name="PystrayThread")
            self.tray_thread.start()
            print(f"New tray icon thread ({self.tray_thread.name}) started.")

            # Now, attempt to join the *old* tray thread if it existed
            # This must be done carefully, perhaps in a separate non-blocking way
            # or with a very short timeout, as joining here can still block the main thread.
            # For now, let's assume pystray's stop() is reasonably quick.
            if old_tray_thread and old_tray_thread.is_alive():
                print(f"Attempting to join old tray thread ({old_tray_thread.name})...")
                old_tray_thread.join(timeout=1.0) # Increased timeout slightly
                if old_tray_thread.is_alive():
                    print(f"Warning: Old tray thread ({old_tray_thread.name}) did not join in time.")
        finally:
            self.is_rebuilding_tray.release()


    def setup_tray_icon(self):
        if not PYSTRAY_AVAILABLE or not self.icon_image: return
        # Initial setup can directly call the main thread version
        self._rebuild_tray_icon_on_main_thread()


    def change_language(self, lang_code, icon=None, item=None):
        if settings.LANGUAGE == lang_code: return 
        
        print(f"Change language requested for: {lang_code}. Current thread: {threading.current_thread().name}")

        if settings.set_language(lang_code): 
            # These actions are safe to call from any thread as they schedule UI updates
            # or manage non-Tkinter resources.
            self._update_ui_text()       
            self.start_hotkey_listener() 
            
            # Schedule the tray icon rebuild to happen on the main thread
            self._request_rebuild_tray_icon_from_main_thread()
            
            lang_name = settings.SUPPORTED_LANGUAGES.get(lang_code, lang_code)
            self.update_status(
                settings.T('status_lang_changed_to').format(lang_name=lang_name),
                settings.STATUS_COLOR_READY
            )
            # pystray's menu update might also need to be on the main thread if it touches UI directly,
            # but rebuilding the icon should handle the visual state.
            # if self.tray_icon: self.tray_icon.update_menu() # This might be problematic if called from tray thread.
        else:
            self.update_status(f"Failed to change to {lang_code}.", settings.STATUS_COLOR_ERROR)


    def hide_to_tray(self, event=None): 
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
            if self.tray_icon: self.tray_icon.update_menu()
            print(settings.T('window_hidden_status'))

    def show_window(self, icon=None, item=None): 
        def _show():
            if self.root and self.root.winfo_exists():
                 self.root.deiconify(); self.root.lift(); self.root.focus_force()
                 if self.tray_icon: self.tray_icon.update_menu()
                 print(settings.T('window_restored_status'))
        if self.root: self.root.after(0, _show)

    def on_exit(self, icon=None, item=None): 
        if not self.running: return
        print(settings.T('exiting_app_status'))
        self.running = False
        self._stop_hotkey_listener()
        
        # Request tray stop from main thread to avoid self-join issues
        if self.tray_icon:
            if threading.current_thread() == self.tray_thread: # If called from tray thread
                print("Exit called from tray thread. Scheduling tray stop on main thread.")
                if self.root and self.root.winfo_exists():
                    self.root.after(0, self._stop_tray_and_join_on_main)
                else: # Root gone, try to stop directly but might be risky
                    self._stop_tray_and_join_on_main() 
            else: # Called from main thread or other
                self._stop_tray_and_join_on_main()
        
        # If not stopping tray from main, proceed to destroy root if needed
        if not (self.tray_icon and threading.current_thread() == self.tray_thread):
            self._finalize_exit()


    def _stop_tray_and_join_on_main(self):
        """Helper to stop tray and join its thread, intended to run on main thread."""
        if self.tray_icon:
            print(settings.T('stopping_tray_status'))
            self.tray_icon.stop()
            current_tray_thread = self.tray_thread # Capture before it's potentially nulled
            if current_tray_thread and current_tray_thread.is_alive() and current_tray_thread != threading.current_thread():
                print(f"Joining tray thread ({current_tray_thread.name}) from main thread...")
                current_tray_thread.join(timeout=1.5) # Slightly longer timeout for exit
                if current_tray_thread.is_alive():
                    print(f"Warning: Tray thread ({current_tray_thread.name}) did not join on exit.")
            self.tray_icon = None
            self.tray_thread = None
        
        # If this was the last step before finalizing exit (e.g. called from on_exit)
        # and exit wasn't called from tray thread originally
        if threading.current_thread() != self.tray_thread: # Check if we need to finalize from here
             self._finalize_exit()


    def _finalize_exit(self):
        """Destroys the root window and prints final messages."""
        if self.root and self.root.winfo_exists():
            print('Destroying main window...')
            self.root.destroy()
        print(settings.T('app_exit_complete_status'))


    def run(self):
        self.start_hotkey_listener()
        self.setup_tray_icon()       
        status_msg_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
        self.update_status(settings.T(status_msg_key), settings.STATUS_COLOR_READY)
        print('Starting main application loop (Tkinter)...')
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_exit() 
        
        # Ensure on_exit logic runs if mainloop exits for other reasons
        # but only if not already exiting via on_exit itself
        if self.running: 
             self.on_exit()
        print(settings.T('app_finished_status'))

def main():
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