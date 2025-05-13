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
    # Fallback T function and language determination
    try:
        t_func = settings.T
        lang_for_err = settings.LANGUAGE
    except (NameError, AttributeError): 
        UI_TEXTS_SUPER_FALLBACK = {
            'en': {
                'dialog_settings_error_title': 'Settings Error',
                'dialog_settings_error_msg': 'Critical error loading settings ({file}):\n{error}',
                'dialog_hotkey_json_error_title': 'Hotkey/UI Config Error',
                'dialog_hotkey_json_error_msg': "Error loading or parsing '{file}':\n{error}",
            },
            'ru': {
                'dialog_settings_error_title': 'Ошибка настроек',
                'dialog_settings_error_msg': 'Критическая ошибка загрузки настроек ({file}):\n{error}',
                'dialog_hotkey_json_error_title': 'Ошибка конфиг. клавиш/UI',
                'dialog_hotkey_json_error_msg': "Ошибка загрузки или парсинга '{file}':\n{error}",
            }
        }
        try:
            import locale
            sys_lang = locale.getdefaultlocale()[0]
            if sys_lang and sys_lang.lower().startswith('ru'): lang_for_err = 'ru'
            else: lang_for_err = 'en'
        except: lang_for_err = 'en'

        def t_func_fallback(k, l=None):
            chosen_lang = l if l else lang_for_err
            return UI_TEXTS_SUPER_FALLBACK.get(chosen_lang, UI_TEXTS_SUPER_FALLBACK['en']).get(k, f"<{k} (super fallback)>")
        t_func = t_func_fallback

    failed_file = "a configuration file" 
    if isinstance(e, (FileNotFoundError, ValueError)):
        err_title = t_func('dialog_hotkey_json_error_title', lang_for_err)
        err_msg_template_str = t_func('dialog_hotkey_json_error_msg', lang_for_err)
        if hasattr(settings, 'HOTKEYS_CONFIG_FILE') and settings.HOTKEYS_CONFIG_FILE in str(e):
            failed_file = settings.HOTKEYS_CONFIG_FILE
        elif hasattr(settings, 'UI_TEXTS_FILE') and settings.UI_TEXTS_FILE in str(e):
            failed_file = settings.UI_TEXTS_FILE
        elif "DEFAULT_MANUAL_ACTION" in str(e) or "hotkey" in str(e).lower():
            failed_file = getattr(settings, 'HOTKEYS_CONFIG_FILE', 'hotkeys.json')
        elif "ui_texts.json" in str(e): 
            failed_file = "ui_texts.json"
        err_msg = err_msg_template_str.format(file=failed_file, error=e)
    elif 'settings' in str(e).lower() or (isinstance(e, AttributeError) and 'settings' in str(e).lower()):
         err_title = t_func('dialog_settings_error_title', lang_for_err)
         err_msg_template_str = t_func('dialog_settings_error_msg', lang_for_err)
         err_msg = err_msg_template_str.format(file="settings.py or related JSON files", error=e)
    else:
        module_name = "an unknown module"
        if 'ollama_utils' in str(e): module_name = 'ollama_utils.py'
        elif 'capture' in str(e): module_name = 'capture.py'
        elif 'ui_utils' in str(e): module_name = 'ui_utils.py'
        err_msg = f'A FATAL ERROR occurred: {e}\n\nPlease ensure essential files like \'{module_name}\' are present.'

    print(f"Startup Error: {err_msg}")
    try:
        root_err = tk.Tk(); root_err.withdraw()
        messagebox.showerror(err_title, err_msg)
        root_err.destroy()
    except Exception as tk_err:
        print(f"Failed to show Tkinter error dialog during critical startup error: {tk_err}")
    exit()


try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


RESPONSE_WINDOW_MIN_WIDTH = 400
RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES = 5
ESTIMATED_CONTROL_FRAME_HEIGHT_PX = 60
ESTIMATED_BUTTON_FRAME_HEIGHT_PX = 50
ESTIMATED_PADDING_PX = 20


class ScreenshotApp:
    def __init__(self):
        self.root = tk.Tk()
        settings.app_instance = self

        default_font = tkFont.nametofont('TkDefaultFont')
        default_font.configure(size=settings.DEFAULT_FONT_SIZE)
        self.root.option_add('*Font', default_font)
        
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use('clam')
        except tk.TclError:
            print("Warning: ttk theme 'clam' not found. Using default.")
            available_themes = self.style.theme_names()
            if available_themes: self.style.theme_use(available_themes[0])


        self.capturer = ScreenshotCapturer(self)
        self.running = True 
        self.root_destroyed = False 
        self.hotkey_listener = None
        self.listener_thread = None
        
        self.response_window = None
        self.response_text_widget = None # This will be the ScrolledText instance
        self.response_font_slider = None
        self.response_size_label = None
        self.response_copy_button = None
        self.current_response_font_size = settings.DEFAULT_FONT_SIZE

        self.tray_icon = None
        self.tray_thread = None
        self.icon_image = None
        self.custom_prompt_var = tk.StringVar()
        self.is_rebuilding_tray = threading.Lock()
        
        self.main_label = None
        self.custom_prompt_label_widget = None
        self.custom_prompt_entry = None
        self.hotkeys_list_label_widget = None
        self.hotkeys_text_area = None
        self.status_label = None
        self.capture_button = None
        self.exit_button = None
        
        if PYSTRAY_AVAILABLE:
            try: self.icon_image = Image.open(settings.ICON_PATH)
            except Exception: self.icon_image = ui_utils.create_default_icon()
        
        self._setup_ui_structure()
        self.apply_theme_globally() 
        self._update_ui_text()

    def _setup_ui_structure(self):
        self.root.geometry(settings.MAIN_WINDOW_GEOMETRY)
        self.root.resizable(settings.WINDOW_RESIZABLE_WIDTH, settings.WINDOW_RESIZABLE_HEIGHT)
        
        main_frame = ttk.Frame(self.root, padding=settings.PADDING_LARGE, style='App.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.main_label = ttk.Label(main_frame, style='App.TLabel')
        self.main_label.pack(pady=(0, settings.PADDING_SMALL))
        
        prompt_frame = ttk.Frame(main_frame, style='App.TFrame')
        prompt_frame.pack(fill=tk.X, pady=settings.PADDING_SMALL)
        self.custom_prompt_label_widget = ttk.Label(prompt_frame, style='App.TLabel')
        self.custom_prompt_label_widget.pack(side=tk.LEFT, padx=(0, settings.PADDING_SMALL))
        self.custom_prompt_entry = ttk.Entry(prompt_frame, textvariable=self.custom_prompt_var, width=40, style='App.TEntry')
        self.custom_prompt_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.hotkeys_list_label_widget = ttk.Label(main_frame, style='App.TLabel')
        self.hotkeys_list_label_widget.pack(anchor=tk.W, pady=(settings.PADDING_SMALL, 0))
        
        self.hotkeys_text_area = tk.Text(main_frame, height=6, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1,
                                         font=('TkDefaultFont', settings.DEFAULT_FONT_SIZE - 2))
        self.hotkeys_text_area.pack(fill=tk.X, pady=(0, settings.PADDING_SMALL), expand=False)
        
        self.status_label = ttk.Label(main_frame, anchor=tk.W, style='Status.TLabel')
        self.status_label.pack(pady=settings.PADDING_SMALL, fill=tk.X)
        
        button_frame = ttk.Frame(main_frame, style='App.TFrame')
        button_frame.pack(fill=tk.X, pady=(settings.PADDING_LARGE, 0), side=tk.BOTTOM)
        
        self.capture_button = ttk.Button(button_frame, style='App.TButton')
        self.capture_button.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.exit_button = ttk.Button(button_frame, command=lambda: self.on_exit(), style='App.TButton')
        self.exit_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(settings.PADDING_SMALL,0))
        
        close_action = self.hide_to_tray if PYSTRAY_AVAILABLE else lambda: self.on_exit(is_wm_delete=True)
        self.root.protocol('WM_DELETE_WINDOW', close_action)

    def _apply_theme_to_tk_widget(self, widget, widget_type="tk.Text"):
        if not widget or not widget.winfo_exists(): return

        is_enabled = widget.cget('state') == tk.NORMAL
        text_bg_color = settings.get_theme_color('text_bg') if is_enabled else settings.get_theme_color('text_disabled_bg')
        text_fg_color = settings.get_theme_color('text_fg')
        border_color = settings.get_theme_color('code_block_border')

        config_options = {
            'background': text_bg_color,
            'foreground': text_fg_color,
            'insertbackground': text_fg_color, 
            'selectbackground': settings.get_theme_color('entry_select_bg'),
            'selectforeground': settings.get_theme_color('entry_select_fg'),
        }
        
        # For tk.Text (and ScrolledText which embeds it), highlightthickness and highlightbackground control the border
        widget.configure(highlightthickness=1, highlightbackground=border_color)
        if is_enabled: # Focused border color
             widget.configure(highlightcolor=settings.get_theme_color('entry_select_bg'))


        try:
            widget.configure(**config_options)
        except tk.TclError as e:
            print(f"Warning: TclError applying theme to {widget_type} ({widget}): {e}")


    def apply_theme_globally(self, language_changed=False):
        if self.root_destroyed: return

        bg = settings.get_theme_color('app_bg')
        fg = settings.get_theme_color('app_fg')
        entry_bg = settings.get_theme_color('entry_bg')
        select_bg = settings.get_theme_color('entry_select_bg')
        select_fg = settings.get_theme_color('entry_select_fg')
        button_bg = settings.get_theme_color('button_bg')
        button_fg = settings.get_theme_color('button_fg')
        button_active_bg = settings.get_theme_color('button_active_bg')
        disabled_fg = settings.get_theme_color('disabled_fg')
        frame_bg = settings.get_theme_color('frame_bg')
        scale_trough = settings.get_theme_color('scale_trough')
        border_color = settings.get_theme_color('code_block_border')

        self.root.configure(background=bg)

        self.style.configure('.', background=bg, foreground=fg, fieldbackground=entry_bg, borderwidth=1)
        self.style.configure('App.TFrame', background=frame_bg)
        self.style.configure('App.TLabel', background=frame_bg, foreground=fg)
        
        self.style.configure('App.TButton', background=button_bg, foreground=button_fg, bordercolor=border_color,
                             relief=tk.RAISED, lightcolor=button_bg, darkcolor=button_bg, focuscolor=fg)
        self.style.map('App.TButton',
                       background=[('active', button_active_bg), ('pressed', button_active_bg), ('disabled', settings.get_theme_color('text_disabled_bg'))],
                       foreground=[('disabled', disabled_fg)],
                       relief=[('pressed', tk.SUNKEN), ('active', tk.RAISED)])

        self.style.configure('App.TEntry', fieldbackground=entry_bg, foreground=settings.get_theme_color('entry_fg'),
                             selectbackground=select_bg, selectforeground=select_fg,
                             insertcolor=settings.get_theme_color('entry_fg'), bordercolor=border_color, lightcolor=entry_bg, darkcolor=entry_bg)
        
        self.style.configure('TScale', troughcolor=scale_trough, background=button_bg, sliderrelief=tk.RAISED, borderwidth=1, lightcolor=button_bg, darkcolor=button_bg)
        self.style.map('TScale', background=[('active',button_active_bg)])

        current_status_color_key = getattr(self.status_label, '_current_status_color_key', 'status_default_fg') if self.status_label else 'status_default_fg'
        status_fg_color = settings.get_theme_color(current_status_color_key)
        self.style.configure('Status.TLabel', background=frame_bg, foreground=status_fg_color)
        if self.status_label: self.status_label.configure(foreground=status_fg_color)

        if self.hotkeys_text_area: self._apply_theme_to_tk_widget(self.hotkeys_text_area)

        if self.response_window and self.response_window.winfo_exists():
            self.response_window.configure(background=bg)
            for child_frame in self.response_window.winfo_children():
                if isinstance(child_frame, ttk.Frame): child_frame.configure(style='App.TFrame')
            
            if self.response_text_widget: 
                self._apply_theme_to_tk_widget(self.response_text_widget)
                try:
                    for child in self.response_text_widget.winfo_children(): # ScrolledText is a Frame
                        if isinstance(child, ttk.Scrollbar):
                            child.configure(style='TScrollbar')
                        elif isinstance(child, tk.Scrollbar):
                             child.config(
                                 background=settings.get_theme_color('scrollbar_bg'),
                                 troughcolor=settings.get_theme_color('scrollbar_trough'),
                                 activebackground=settings.get_theme_color('button_active_bg')
                             )
                    self.style.configure('TScrollbar', troughcolor=settings.get_theme_color('scrollbar_trough'), 
                                         background=settings.get_theme_color('scrollbar_bg'),
                                         arrowcolor=fg, bordercolor=border_color, relief=tk.FLAT)
                except (tk.TclError, AttributeError) as e:
                    print(f"Minor issue theming scrollbars in apply_theme_globally: {e}")


            if self.response_font_slider: self.response_font_slider.configure(style='TScale')
            if self.response_size_label: self.response_size_label.configure(style='App.TLabel')
            if self.response_copy_button: self.response_copy_button.configure(style='App.TButton')
            
            if self.response_copy_button: 
                for sibling in self.response_copy_button.master.winfo_children():
                    if isinstance(sibling, ttk.Button): sibling.configure(style='App.TButton')
            
            if self.response_text_widget and self.response_text_widget.winfo_exists():
                try:
                    current_text = self.response_text_widget.get("1.0", tk.END) 
                    ui_utils.apply_formatting_tags(self.response_text_widget, current_text, self.current_response_font_size)
                except (tk.TclError, AttributeError) as e:
                     print(f"Minor issue re-applying tags in apply_theme_globally: {e}")


        if language_changed:
            self._update_ui_text()

        if PYSTRAY_AVAILABLE and self.tray_icon and hasattr(self.tray_icon, 'update_menu') and self.tray_icon.visible:
             self.tray_icon.update_menu()
        

    def _update_ui_text(self):
        if self.root_destroyed: return
        self.root.title(settings.T('app_title'))
        
        if self.main_label: self.main_label.config(text=settings.T('main_label_text'))
        if self.custom_prompt_label_widget: self.custom_prompt_label_widget.config(text=settings.T('custom_prompt_label'))
        if self.hotkeys_list_label_widget: self.hotkeys_list_label_widget.config(text=settings.T('hotkeys_list_label'))
        
        if self.hotkeys_text_area:
            current_state = self.hotkeys_text_area.cget('state')
            self.hotkeys_text_area.config(state=tk.NORMAL)
            self.hotkeys_text_area.delete('1.0', tk.END)
            hotkey_display_text = []
            if settings.HOTKEY_ACTIONS:
                for _, details in settings.HOTKEY_ACTIONS.items():
                    hotkey_display_text.append(f"{details['hotkey']}: {details['description']}")
                self.hotkeys_text_area.insert(tk.END, "\n".join(hotkey_display_text))
            else:
                self.hotkeys_text_area.insert(tk.END, settings.T('hotkey_failed_status'))
            self.hotkeys_text_area.config(state=current_state)

        if self.status_label:
            current_text = self.status_label.cget("text")
            is_generic_status_or_change_msg = False
            generic_statuses = [settings.T('initial_status_text', lang=lc) for lc in settings.SUPPORTED_LANGUAGES.keys()] + \
                               [settings.T('ready_status_text_no_tray', lang=lc) for lc in settings.SUPPORTED_LANGUAGES.keys()] + \
                               [settings.T('ready_status_text_tray', lang=lc) for lc in settings.SUPPORTED_LANGUAGES.keys()]
            change_msg_templates = ['status_lang_changed_to', 'status_theme_changed_to']
            change_prefixes = []
            for template_key in change_msg_templates:
                for lc in settings.SUPPORTED_LANGUAGES.keys():
                    prefix = settings.T(template_key, lang=lc).split('{')[0]
                    if prefix: change_prefixes.append(prefix)
            
            if current_text in generic_statuses or any(current_text.startswith(p) for p in change_prefixes if p): # check if p is not empty
                is_generic_status_or_change_msg = True

            if is_generic_status_or_change_msg and not (hasattr(self, '_theme_just_changed') and self._theme_just_changed) \
               and not (hasattr(self, '_lang_just_changed') and self._lang_just_changed):
                ready_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
                self.update_status(settings.T(ready_key), 'status_ready_fg')
            
            if hasattr(self, '_theme_just_changed'): del self._theme_just_changed
            if hasattr(self, '_lang_just_changed'): del self._lang_just_changed

        if self.capture_button:
            self.capture_button.config(text=settings.T('capture_button_text'))
            default_manual_action_details = settings.HOTKEY_ACTIONS.get(settings.DEFAULT_MANUAL_ACTION)
            prompt_for_button = settings.T('ollama_no_response_content') 
            if default_manual_action_details:
                prompt_for_button = default_manual_action_details['prompt']
                if prompt_for_button == settings.CUSTOM_PROMPT_IDENTIFIER:
                    describe_action = settings.HOTKEY_ACTIONS.get('describe', {})
                    prompt_for_button = describe_action.get('prompt', "Describe (fallback prompt)")
            self.capture_button.config(command=lambda p=prompt_for_button: self._trigger_capture_from_ui(p))

        if self.exit_button:
            exit_key = 'exit_button_text_tray' if PYSTRAY_AVAILABLE else 'exit_button_text'
            self.exit_button.config(text=settings.T(exit_key))

    def _get_prompt_for_action(self, prompt_source):
        if self.root_destroyed: return None
        if prompt_source == settings.CUSTOM_PROMPT_IDENTIFIER:
            custom_prompt = self.custom_prompt_var.get().strip()
            if not custom_prompt:
                if not self.root_destroyed and self.root and self.root.winfo_exists():
                    messagebox.showwarning(settings.T('dialog_warning_title'), settings.T('custom_prompt_empty_warning'), parent=self.root)
                return None
            return custom_prompt
        elif isinstance(prompt_source, str):
            return prompt_source
        else: 
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                messagebox.showerror(settings.T('dialog_internal_error_title'), settings.T('dialog_internal_error_msg'), parent=self.root)
            return None

    def _trigger_capture_from_ui(self, prompt_source):
        if self.root_destroyed: return
        self._trigger_capture(prompt_source)

    def _trigger_capture(self, prompt_source, icon=None, item=None):
        if self.root_destroyed: return
        actual_prompt = self._get_prompt_for_action(prompt_source)
        if actual_prompt is None:
            ready_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
            self.update_status(settings.T(ready_key), 'status_ready_fg')
            return
        if self.root and self.root.winfo_viewable():
            self.root.withdraw()
            self.root.after(100, lambda: self.capturer.capture_region(actual_prompt))
        else:
            self.capturer.capture_region(actual_prompt)

    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str):
        if self.root_destroyed: return
        if self.root and not self.root.winfo_viewable() and PYSTRAY_AVAILABLE : # Only show if hidden by tray logic
            # Check if the window was hidden by capture logic or by explicit hide_to_tray
            # This logic might need refinement based on how `hide_to_tray` sets state
             if not getattr(self, '_explicitly_hidden_to_tray', False):
                  self.show_window()


        self.update_status(settings.T('processing_status_text'), 'status_processing_fg')
        threading.Thread(target=self._ollama_request_worker, args=(screenshot, prompt), daemon=True).start()

    def _ollama_request_worker(self, screenshot: Image.Image, prompt: str):
        if self.root_destroyed: return
        try:
            response_text = ollama_utils.request_ollama_analysis(screenshot, prompt)
            self.update_status_safe(settings.T('ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'), 'status_ready_fg')
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.display_ollama_response, response_text)
        except OllamaConnectionError as e:
            msg = f"{settings.T('ollama_conn_failed_status')}: {e}"
            self.update_status_safe(msg, 'status_error_fg')
        except OllamaTimeoutError as e:
            msg = f"{settings.T('ollama_timeout_status')}: {e}"
            self.update_status_safe(msg, 'status_error_fg')
        except OllamaRequestError as e:
            msg = f"{settings.T('ollama_request_failed_status')} (Code: {e.status_code}, Detail: {e.detail})"
            self.update_status_safe(msg, 'status_error_fg')
        except OllamaError as e:
            msg = f"{settings.T('ollama_request_failed_status')}: {e}"
            self.update_status_safe(msg, 'status_error_fg')
        except ValueError as e: 
            msg = f"{settings.T('error_preparing_image_status')}: {e}"
            self.update_status_safe(msg, 'status_error_fg')
        except Exception as e:
            print(f"Unexpected Ollama worker error: {e}")
            self.update_status_safe(settings.T('unexpected_error_status'), 'status_error_fg')


    def display_ollama_response(self, response_text):
        if self.root_destroyed: return
        if self.response_window and self.response_window.winfo_exists():
            try: self.response_window.destroy()
            except tk.TclError: pass
        
        if not self.root or not self.root.winfo_exists(): return

        self.response_window = tk.Toplevel(self.root)
        self.response_window.title(settings.T('response_window_title'))
        self.response_window.geometry(settings.RESPONSE_WINDOW_GEOMETRY)
        self.response_window.configure(background=settings.get_theme_color('app_bg'))

        text_frame = ttk.Frame(self.response_window, style='App.TFrame')
        
        self.response_text_widget = scrolledtext.ScrolledText(
            text_frame, wrap=tk.WORD, relief=tk.FLAT, bd=0,
            font=('TkDefaultFont', self.current_response_font_size),
            height=RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES
        )
        self._apply_theme_to_tk_widget(self.response_text_widget)
        try:
            for child in self.response_text_widget.winfo_children():
                if isinstance(child, ttk.Scrollbar):
                    child.configure(style='TScrollbar')
                elif isinstance(child, tk.Scrollbar):
                    child.config(
                        background=settings.get_theme_color('scrollbar_bg'),
                        troughcolor=settings.get_theme_color('scrollbar_trough'),
                        activebackground=settings.get_theme_color('button_active_bg')
                    )
        except (tk.TclError, AttributeError) as e:
            print(f"Minor issue theming scrollbars in display_ollama_response: {e}")


        control_frame = ttk.Frame(self.response_window, style='App.TFrame')
        
        def update_font_size_display_themed(size_val_str):
            if self.root_destroyed: return
            try:
                new_size = int(float(size_val_str))
                if not (settings.MIN_FONT_SIZE <= new_size <= settings.MAX_FONT_SIZE): return
                self.current_response_font_size = new_size
                if self.response_size_label and self.response_size_label.winfo_exists():
                    self.response_size_label.config(text=settings.T('font_size_label_format').format(size=new_size))
                
                text_w = self.response_text_widget 
                if text_w and text_w.winfo_exists(): 
                    base_font_obj = tkFont.Font(font=text_w['font'])
                    base_font_obj.configure(size=new_size)
                    text_w.configure(font=base_font_obj)
                    ui_utils.apply_formatting_tags(text_w, response_text, new_size)
            except (ValueError, tk.TclError, AttributeError): pass

        self.response_font_slider = ttk.Scale(control_frame, from_=settings.MIN_FONT_SIZE, to=settings.MAX_FONT_SIZE, 
                                       orient=tk.HORIZONTAL, value=self.current_response_font_size,
                                       command=update_font_size_display_themed, style='TScale')
        self.response_font_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, settings.PADDING_LARGE))
        
        self.response_size_label = ttk.Label(control_frame, text=settings.T('font_size_label_format').format(size=self.current_response_font_size),
                                      width=settings.FONT_SIZE_LABEL_WIDTH, style='App.TLabel')
        self.response_size_label.pack(side=tk.LEFT)

        button_frame_resp = ttk.Frame(self.response_window, style='App.TFrame')
        
        def copy_to_clipboard_command_themed():
            if self.root_destroyed or not (self.response_window and self.response_window.winfo_exists()): return
            raw_text_content = self.response_text_widget.get('1.0', tk.END).strip()
            try:
                self.response_window.clipboard_clear()
                self.response_window.clipboard_append(raw_text_content)
                if self.response_copy_button and self.response_copy_button.winfo_exists():
                    self.response_copy_button.config(text=settings.T('copied_button_text'))
                    if self.response_window and self.response_window.winfo_exists():
                        self.response_window.after(settings.COPY_BUTTON_RESET_DELAY_MS, 
                            lambda: self.response_copy_button.config(text=settings.T('copy_button_text')) if self.response_copy_button and self.response_copy_button.winfo_exists() else None)
            except tk.TclError as e:
                if not self.root_destroyed and self.response_window and self.response_window.winfo_exists():
                    messagebox.showerror(settings.T('dialog_internal_error_title'), f"{settings.T('unexpected_error_status')}: {e}", parent=self.response_window)

        self.response_copy_button = ttk.Button(button_frame_resp, text=settings.T('copy_button_text'),
                                          command=copy_to_clipboard_command_themed, style='App.TButton')
        self.response_copy_button.pack(side=tk.LEFT, padx=settings.PADDING_SMALL)
        
        close_button_resp = ttk.Button(button_frame_resp, text=settings.T('close_button_text'), style='App.TButton',
                                   command=lambda: self.response_window.destroy() if self.response_window and self.response_window.winfo_exists() else None)
        close_button_resp.pack(side=tk.RIGHT, padx=settings.PADDING_SMALL)

        self.response_window.update_idletasks()
        font_for_metrics = tkFont.Font(font=self.response_text_widget['font'])
        line_height_px = font_for_metrics.metrics("linespace")
        min_text_area_height_px = RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES * line_height_px
        min_total_height = int(min_text_area_height_px + ESTIMATED_CONTROL_FRAME_HEIGHT_PX + \
                               ESTIMATED_BUTTON_FRAME_HEIGHT_PX + ESTIMATED_PADDING_PX * 3) 
        self.response_window.minsize(RESPONSE_WINDOW_MIN_WIDTH, min_total_height)

        text_frame.pack(padx=settings.RESPONSE_TEXT_PADDING_X, pady=settings.RESPONSE_TEXT_PADDING_Y_TOP, fill=tk.BOTH, expand=True)
        self.response_text_widget.pack(fill=tk.BOTH, expand=True)
        control_frame.pack(padx=settings.RESPONSE_CONTROL_PADDING_X, pady=settings.RESPONSE_CONTROL_PADDING_Y, fill=tk.X)
        button_frame_resp.pack(pady=settings.RESPONSE_BUTTON_PADDING_Y, fill=tk.X, padx=settings.RESPONSE_BUTTON_PADDING_X)

        ui_utils.apply_formatting_tags(self.response_text_widget, response_text, self.current_response_font_size)

        if self.response_window and self.response_window.winfo_exists():
            self.response_window.transient(self.root)
            self.response_window.grab_set()
            self.response_window.focus_force()
        
        self.update_status(settings.T('ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'), 'status_ready_fg')

    def update_status(self, message, color_key='status_default_fg'):
        if self.root_destroyed: return
        def _update():
            if not self.root_destroyed and hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                color = settings.get_theme_color(color_key)
                self.status_label.config(text=message, foreground=color)
                setattr(self.status_label, '_current_status_color_key', color_key)
                self.style.configure('Status.TLabel', foreground=color, background=settings.get_theme_color('frame_bg'))
        if self.root and self.root.winfo_exists():
            self.root.after(0, _update)
            
    def update_status_safe(self, message, color_key='status_default_fg'):
        if self.root_destroyed: return
        if self.root and self.root.winfo_exists():
            self.root.after(0, self.update_status, message, color_key)

    def _build_tray_menu(self):
        if self.root_destroyed: return tuple()
        
        lang_submenu_items = []
        for code, name in settings.SUPPORTED_LANGUAGES.items():
            action = partial(self.change_language, code) 
            item = pystray.MenuItem(name, action,
                checked=lambda item_param, current_code_param=code: settings.LANGUAGE == current_code_param,
                radio=True)
            lang_submenu_items.append(item)

        theme_submenu_items = [
            pystray.MenuItem(
                settings.T('tray_theme_light_text'),
                partial(self.change_theme, 'light'),
                checked=lambda item: settings.CURRENT_THEME == 'light', radio=True ),
            pystray.MenuItem(
                settings.T('tray_theme_dark_text'),
                partial(self.change_theme, 'dark'),
                checked=lambda item: settings.CURRENT_THEME == 'dark', radio=True )
        ]
        
        default_manual_action_details = settings.HOTKEY_ACTIONS.get(settings.DEFAULT_MANUAL_ACTION)
        tray_capture_prompt = settings.T('ollama_no_response_content') 
        if default_manual_action_details:
            tray_capture_prompt = default_manual_action_details['prompt']
            if tray_capture_prompt == settings.CUSTOM_PROMPT_IDENTIFIER:
                describe_action = settings.HOTKEY_ACTIONS.get('describe', {})
                tray_capture_prompt = describe_action.get('prompt', "Describe (tray fallback)")

        menu_items = [
            pystray.MenuItem(settings.T('tray_show_window_text'), self.show_window, default=True,
                             visible=lambda item: not self.root_destroyed and self.root and self.root.winfo_exists() and not self.root.winfo_viewable()),
            pystray.MenuItem(settings.T('tray_capture_text'), partial(self._trigger_capture, prompt_source=tray_capture_prompt)),
            pystray.MenuItem(settings.T('tray_language_text'), pystray.Menu(*lang_submenu_items)),
            pystray.MenuItem(settings.T('tray_theme_text'), pystray.Menu(*theme_submenu_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(settings.T('tray_exit_text'), lambda: self.on_exit(from_tray=True))
        ]
        return tuple(menu_items)

    def _request_rebuild_tray_icon_from_main_thread(self):
        if self.root_destroyed: return
        if self.root and self.root.winfo_exists() and PYSTRAY_AVAILABLE:
            self.root.after(100, self._rebuild_tray_icon_on_main_thread)

    def _rebuild_tray_icon_on_main_thread(self):
        if self.root_destroyed or not PYSTRAY_AVAILABLE: return
        if not self.is_rebuilding_tray.acquire(blocking=False): return
        try:
            old_tray_instance = self.tray_icon
            old_tray_thread = self.tray_thread

            if old_tray_instance:
                old_tray_instance.stop() 
                self.tray_icon = None
            
            if old_tray_thread and old_tray_thread.is_alive():
                pass 
            self.tray_thread = None

            new_menu = self._build_tray_menu()
            if not new_menu : 
                self.is_rebuilding_tray.release(); return

            self.tray_icon = pystray.Icon(settings.TRAY_ICON_NAME, self.icon_image, settings.T('app_title'), new_menu)
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True, name="PystrayThread")
            self.tray_thread.start()
        except Exception as e: print(f"Exception during tray rebuild: {e}")
        finally: self.is_rebuilding_tray.release()


    def setup_tray_icon(self):
        if self.root_destroyed or not PYSTRAY_AVAILABLE or not self.icon_image: return
        self._rebuild_tray_icon_on_main_thread()

    def change_theme(self, theme_name, icon=None, item=None):
        if self.root_destroyed: return
        if settings.set_theme(theme_name): 
            self._theme_just_changed = True
            # Tray checkmarks should update via pystray's own logic when menu is shown or item clicked.
            # If you need to force an update of the visual menu (e.g. if text changed):
            # self._request_rebuild_tray_icon_from_main_thread()

    def change_language(self, lang_code, icon=None, item=None):
        if self.root_destroyed: return
        if settings.LANGUAGE == lang_code: return
        
        if settings.set_language(lang_code): 
            # self._update_ui_text() # Called by apply_theme_globally(language_changed=True) via set_language
            self.start_hotkey_listener() 
            
            lang_name = settings.SUPPORTED_LANGUAGES.get(settings.LANGUAGE, settings.LANGUAGE)
            self.update_status(settings.T('status_lang_changed_to').format(lang_name=lang_name), 'status_ready_fg')
            self._lang_just_changed = True
            
            self._request_rebuild_tray_icon_from_main_thread()
        else:
            self.update_status(f"Failed to change language to {lang_code}.", 'status_error_fg')


    def hide_to_tray(self, event=None): 
        if self.root_destroyed or not PYSTRAY_AVAILABLE: return
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
            self._explicitly_hidden_to_tray = True # Flag that it was hidden by user/WM_DELETE
            self.update_status(settings.T('window_hidden_status'), 'status_default_fg')
            if self.tray_icon and hasattr(self.tray_icon, 'update_menu'): self.tray_icon.update_menu()

    def show_window(self, icon=None, item=None): 
        if self.root_destroyed: return
        def _show():
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                 self.root.deiconify(); self.root.lift(); self.root.focus_force()
                 self._explicitly_hidden_to_tray = False # Window is now shown
                 self.update_status(settings.T('window_restored_status'), 'status_default_fg')
                 if PYSTRAY_AVAILABLE and self.tray_icon and hasattr(self.tray_icon, 'update_menu'): self.tray_icon.update_menu()
        if self.root and self.root.winfo_exists(): self.root.after(0, _show)

    def _stop_hotkey_listener(self):
        if self.hotkey_listener:
            try: self.hotkey_listener.stop()
            except Exception: pass
            self.hotkey_listener = None
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=0.2) 
            self.listener_thread = None

    def start_hotkey_listener(self):
        if self.root_destroyed: return
        self._stop_hotkey_listener()
        hotkey_map = {}
        try:
            if not settings.HOTKEY_ACTIONS:
                self.update_status_safe(f"{settings.T('hotkey_failed_status')}: No hotkeys loaded.", 'status_error_fg')
                return

            for _, details in settings.HOTKEY_ACTIONS.items():
                hotkey_map[details['hotkey']] = partial(self._trigger_capture, prompt_source=details['prompt'])

            if not hotkey_map:
                 self.update_status_safe(f"{settings.T('hotkey_failed_status')}: No valid hotkeys configured.", 'status_error_fg')
                 return

            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            self.listener_thread = threading.Thread(target=self.hotkey_listener.run, daemon=True, name="HotkeyListenerThread")
            self.listener_thread.start()
        except Exception as e: 
            error_msg = settings.T('dialog_hotkey_error_msg').format(error=e)
            self.update_status_safe(settings.T('hotkey_failed_status'), 'status_error_fg')
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                 self.root.after(0, messagebox.showerror, settings.T('dialog_hotkey_error_title'), error_msg, parent=self.root)


    def on_exit(self, icon=None, item=None, from_tray=False, is_wm_delete=False):
        if not self.running: return
        
        self.running = False 
        print(settings.T('exiting_app_status'))
        self.update_status_safe(settings.T('exiting_app_status'), 'status_default_fg')

        self._stop_hotkey_listener()

        if PYSTRAY_AVAILABLE and self.tray_icon:
            try:
                self.tray_icon.stop() 
            except Exception as e: print(f"Error stopping tray icon: {e}")
        
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            if threading.current_thread() == threading.main_thread():
                self._destroy_root_safely()
            else:
                self.root.after(0, self._destroy_root_safely)

    def _destroy_root_safely(self):
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            try:
                if self.response_window and self.response_window.winfo_exists():
                    self.response_window.destroy()
                self.root.destroy()
            except tk.TclError: pass 
        self.root_destroyed = True

    def run(self):
        if self.root_destroyed: return
        self.start_hotkey_listener()
        self.setup_tray_icon()
        
        status_msg_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
        self.update_status(settings.T(status_msg_key), 'status_ready_fg')
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("KeyboardInterrupt received, initiating exit.")
            if self.running : self.on_exit()
        except Exception as e:
            print(f"Unhandled error in Tkinter mainloop: {e}")
            if self.running : self.on_exit()

        if self.running: self.running = False 
        
        self._stop_hotkey_listener() 

        if PYSTRAY_AVAILABLE and self.tray_thread and self.tray_thread.is_alive():
            self.tray_thread.join(timeout=0.5) 
        
        if not self.root_destroyed:
            self._destroy_root_safely()

        print(settings.T('app_exit_complete_status'))
        print(settings.T('app_finished_status'))


def main():
    print(f"{settings.T('app_title')} Starting...")
    print(f'Platform: {platform.system()} {platform.release()}')
    print(f"App language: {settings.LANGUAGE} ({settings.SUPPORTED_LANGUAGES.get(settings.LANGUAGE, 'Unknown')})")
    print(f"App theme: {settings.CURRENT_THEME}")

    if PYSTRAY_AVAILABLE:
        try:
            with Image.open(settings.ICON_PATH) as img: pass
        except FileNotFoundError:
            root_check = tk.Tk(); root_check.withdraw()
            proceed = messagebox.askokcancel(
                settings.T('dialog_icon_warning_title'),
                settings.T('dialog_icon_warning_msg').format(path=settings.ICON_PATH),
                parent=root_check 
            )
            root_check.destroy()
            if not proceed: return
        except Exception as e: 
            root_check = tk.Tk(); root_check.withdraw()
            proceed = messagebox.askokcancel(
                settings.T('dialog_icon_error_title'),
                settings.T('dialog_icon_error_msg').format(path=settings.ICON_PATH, error=e),
                parent=root_check
            )
            root_check.destroy()
            if not proceed: return
    
    app = ScreenshotApp()
    app.run()

if __name__ == '__main__':
    main()