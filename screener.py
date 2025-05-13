# screener.py
import logging # For logging
import tkinter as tk
from tkinter import scrolledtext, messagebox, font as tkFont, ttk
import threading
from functools import partial
import platform
import time
import os # For os.path.exists in icon check
import sys

from PIL import Image # Keep Image import at top level
from pynput import keyboard

# --- Local Imports ---
# settings.py MUST be imported first as it initializes logging_config
try:
    import settings # This will initialize logging via logging_config
    import ollama_utils
    from ollama_utils import (
        OllamaError, OllamaConnectionError, OllamaTimeoutError, OllamaRequestError
    )
    from capture import ScreenshotCapturer
    import ui_utils
except (ImportError, FileNotFoundError, ValueError) as e:
    # This block handles critical failure to import `settings` itself, or if `settings`
    # raises an error during its own import time (before _initialization_errors is populated
    # or if logging_config itself fails).
    err_title_super_critical = "Screener - Critical Initialization Error"
    err_msg_super_critical = f"A critical error occurred during application startup, preventing essential modules or configurations from loading.\n\nError: {e}\n\nThe application cannot continue. Please check console output if available, or ensure all core Python files and JSON configurations are correctly placed and formatted."
    
    # Try to log this super critical error, but logging itself might not be set up.
    try:
        # Use a specific logger name for this early-stage critical error
        super_critical_logger = logging.getLogger("screener_bootstrap_error")
        super_critical_logger.critical("SUPER CRITICAL FAILURE: Error during initial imports or settings.py execution.", exc_info=True)
        super_critical_logger.critical("Error details: %s", e)
    except Exception as log_ex:
        # If logging fails, print to stdout as a last resort.
        print(f"FALLBACK PRINT (logging failed): {err_title_super_critical}\n{err_msg_super_critical}\nLogging error: {log_ex}")

    # Attempt to show a Tkinter messagebox as a last resort for user visibility.
    try:
        root_err_sc = tk.Tk()
        root_err_sc.withdraw()
        messagebox.showerror(err_title_super_critical, err_msg_super_critical, parent=root_err_sc)
        root_err_sc.destroy()
    except Exception as tk_ex:
        print(f"FALLBACK PRINT (Tkinter messagebox failed): {err_title_super_critical}\n{err_msg_super_critical}\nTkinter error: {tk_ex}")
    exit(1) # Exit with an error code

# Get a logger for this module AFTER settings (and thus logging) is successfully imported and set up.
logger = logging.getLogger(__name__)

# pystray import is optional, handle its absence
try:
    import pystray
    PYSTRAY_AVAILABLE = True
    logger.debug("pystray module loaded successfully.")
except ImportError:
    PYSTRAY_AVAILABLE = False
    logger.info("pystray module not found. System tray functionality will be disabled.")


class ScreenshotApp:
    def __init__(self):
        logger.info("Initializing ScreenshotApp...")
        self.root = tk.Tk()
        settings.app_instance = self # Make app instance available to settings for callbacks

        # Configure default font size for Tkinter
        default_font = tkFont.nametofont('TkDefaultFont')
        default_font.configure(size=settings.DEFAULT_FONT_SIZE)
        self.root.option_add('*Font', default_font)
        logger.debug("Default Tkinter font size set to %spt.", settings.DEFAULT_FONT_SIZE)
        
        # Initialize and configure ttk.Style
        self.style = ttk.Style(self.root)
        try:
            # Attempt to use a modern theme if available
            preferred_themes = ['clam', 'alt', 'vista', 'xpnative'] # Order of preference
            current_theme_set = False
            for theme_name in preferred_themes:
                if theme_name in self.style.theme_names():
                    self.style.theme_use(theme_name)
                    logger.info("Using ttk theme: '%s'", theme_name)
                    current_theme_set = True
                    break
            if not current_theme_set and self.style.theme_names():
                # Fallback to the first available theme if preferred ones are not found
                fallback_theme = self.style.theme_names()[0]
                self.style.theme_use(fallback_theme)
                logger.info("Preferred ttk themes not found. Using fallback theme: '%s'", fallback_theme)
            elif not self.style.theme_names():
                logger.warning("No ttk themes available. UI might look very basic.")

        except tk.TclError as e:
            logger.warning("TclError setting ttk theme: %s. Using system default.", e, exc_info=False)

        self.capturer = ScreenshotCapturer(self)
        self.running = True 
        self.root_destroyed = False 
        self.hotkey_listener = None
        self.listener_thread = None
        
        self.response_window = None
        self.response_text_widget = None
        self.response_font_slider = None
        self.response_size_label = None
        self.response_copy_button = None
        self.current_response_font_size = settings.DEFAULT_FONT_SIZE

        self.tray_icon = None
        self.tray_thread = None
        self.icon_image = None # PIL.Image object for pystray
        self.custom_prompt_var = tk.StringVar()
        self._explicitly_hidden_to_tray = False # Flag for hide_to_tray behavior
        self.is_rebuilding_tray = threading.Lock() # Lock for tray rebuild process
        
        # UI Widget references
        self.main_label = None
        self.custom_prompt_label_widget = None
        self.custom_prompt_entry = None
        self.hotkeys_list_label_widget = None
        self.hotkeys_text_area = None
        self.status_label = None
        self.capture_button = None
        self.exit_button = None
        
        # Load tray icon image
        if PYSTRAY_AVAILABLE:
            try:
                # settings.ICON_PATH is resolved by settings.py to be correct for bundled/dev
                logger.debug("Attempting to load pystray icon from: %s", settings.ICON_PATH)
                if os.path.exists(settings.ICON_PATH):
                    self.icon_image = Image.open(settings.ICON_PATH)
                    logger.info("pystray icon loaded successfully from: %s", settings.ICON_PATH)
                else:
                    logger.warning("pystray icon file not found at '%s'. Using default.", settings.ICON_PATH)
                    self.icon_image = ui_utils.create_default_icon()
            except Exception as e:
                logger.error("Failed to load pystray icon from '%s': %s. Using default icon.",
                             settings.ICON_PATH, e, exc_info=True)
                self.icon_image = ui_utils.create_default_icon()
        
        self._setup_ui_structure()
        self.apply_theme_globally() # Apply initial theme to all widgets
        self._update_ui_text()      # Populate UI with initial texts
        logger.info("ScreenshotApp initialized successfully.")

    def _setup_ui_structure(self):
        logger.debug("Setting up main UI structure...")
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
        
        # Using tk.Text for hotkeys_text_area for more control over border/bg if ttk.Frame looks off
        self.hotkeys_text_area = tk.Text(main_frame, height=6, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1,
                                         font=('TkDefaultFont', settings.DEFAULT_FONT_SIZE - 2))
        self.hotkeys_text_area.pack(fill=tk.X, pady=(0, settings.PADDING_SMALL), expand=False)
        self.hotkeys_text_area.config(state=tk.DISABLED) # Disable editing by default
        
        self.status_label = ttk.Label(main_frame, anchor=tk.W, style='Status.TLabel')
        self.status_label.pack(pady=settings.PADDING_SMALL, fill=tk.X)
        
        button_frame = ttk.Frame(main_frame, style='App.TFrame')
        button_frame.pack(fill=tk.X, pady=(settings.PADDING_LARGE, 0), side=tk.BOTTOM)
        
        self.capture_button = ttk.Button(button_frame, style='App.TButton') # Command set in _update_ui_text
        self.capture_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, settings.PADDING_SMALL // 2))
        
        self.exit_button = ttk.Button(button_frame, command=lambda: self.on_exit(), style='App.TButton')
        self.exit_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(settings.PADDING_SMALL // 2, 0))
        
        # Determine close action based on pystray availability
        close_action = self.hide_to_tray if PYSTRAY_AVAILABLE else lambda: self.on_exit(is_wm_delete=True)
        self.root.protocol('WM_DELETE_WINDOW', close_action)
        logger.debug("Main UI structure setup complete.")

    def _apply_theme_to_tk_widget(self, widget, widget_type="tk.Text"):
        if not widget or not widget.winfo_exists():
            logger.debug("_apply_theme_to_tk_widget: Widget '%s' does not exist or is destroyed.", widget_type)
            return

        is_enabled = widget.cget('state') == tk.NORMAL
        text_bg_color = settings.get_theme_color('text_bg') if is_enabled else settings.get_theme_color('text_disabled_bg')
        text_fg_color = settings.get_theme_color('text_fg')
        border_color = settings.get_theme_color('code_block_border') # Consistent border color

        config_options = {
            'background': text_bg_color,
            'foreground': text_fg_color,
            'insertbackground': text_fg_color, 
            'selectbackground': settings.get_theme_color('entry_select_bg'),
            'selectforeground': settings.get_theme_color('entry_select_fg'),
            'highlightthickness': 1, 
            'highlightbackground': border_color, # Unfocused border for tk.Text
        }
        if is_enabled: # Focused border color for tk.Text
             config_options['highlightcolor'] = settings.get_theme_color('entry_select_bg')

        try:
            widget.configure(**config_options)
        except tk.TclError as e:
            logger.warning("TclError applying theme to %s (%s): %s", widget_type, widget, e, exc_info=False)

    def apply_theme_globally(self, language_changed=False):
        if self.root_destroyed:
            logger.debug("apply_theme_globally called but root is destroyed. Skipping.")
            return
        logger.info("Applying global theme. Current theme: %s. Language changed: %s", settings.CURRENT_THEME, language_changed)

        bg = settings.get_theme_color('app_bg')
        fg = settings.get_theme_color('app_fg')
        entry_bg = settings.get_theme_color('entry_bg')
        select_bg = settings.get_theme_color('entry_select_bg')
        select_fg = settings.get_theme_color('entry_select_fg')
        button_bg = settings.get_theme_color('button_bg')
        button_fg = settings.get_theme_color('button_fg')
        button_active_bg = settings.get_theme_color('button_active_bg')
        disabled_fg = settings.get_theme_color('disabled_fg')
        frame_bg = settings.get_theme_color('frame_bg') # Use for frames containing other widgets
        scale_trough = settings.get_theme_color('scale_trough')
        border_color = settings.get_theme_color('code_block_border') # Used for entry/button borders via ttk

        self.root.configure(background=bg) # Main window background

        # General style for ALL ttk widgets (some might override specific parts)
        self.style.configure('.', background=bg, foreground=fg, fieldbackground=entry_bg, borderwidth=1)
        
        self.style.configure('App.TFrame', background=frame_bg) # Frames that contain other widgets
        self.style.configure('App.TLabel', background=frame_bg, foreground=fg)
        
        self.style.configure('App.TButton', background=button_bg, foreground=button_fg, bordercolor=border_color,
                             relief=tk.RAISED, lightcolor=button_bg, darkcolor=button_bg, focuscolor=fg)
        self.style.map('App.TButton',
                       background=[('active', button_active_bg), ('pressed', button_active_bg), ('disabled', settings.get_theme_color('text_disabled_bg'))],
                       foreground=[('disabled', disabled_fg)],
                       relief=[('pressed', tk.SUNKEN), ('!pressed', tk.RAISED)]) # Ensure relief resets

        self.style.configure('App.TEntry', fieldbackground=entry_bg, foreground=settings.get_theme_color('entry_fg'),
                             selectbackground=select_bg, selectforeground=select_fg,
                             insertcolor=settings.get_theme_color('entry_fg'), bordercolor=border_color, lightcolor=entry_bg, darkcolor=entry_bg)
        
        self.style.configure('TScale', troughcolor=scale_trough, background=button_bg, sliderrelief=tk.RAISED, borderwidth=1, lightcolor=button_bg, darkcolor=button_bg)
        self.style.map('TScale', background=[('active', button_active_bg)])

        # Status label specific styling (foreground changes based on status type)
        current_status_color_key = getattr(self.status_label, '_current_status_color_key', 'status_default_fg') if self.status_label else 'status_default_fg'
        status_fg_color = settings.get_theme_color(current_status_color_key)
        self.style.configure('Status.TLabel', background=frame_bg, foreground=status_fg_color)
        if self.status_label: self.status_label.configure(foreground=status_fg_color) # Direct configure for immediate effect

        # Theme pure tk.Text widget (hotkeys_text_area)
        if self.hotkeys_text_area: self._apply_theme_to_tk_widget(self.hotkeys_text_area)

        # Theme response window if it exists
        if self.response_window and self.response_window.winfo_exists():
            logger.debug("Applying theme to existing response window.")
            self.response_window.configure(background=bg)
            for child_frame in self.response_window.winfo_children():
                if isinstance(child_frame, ttk.Frame): child_frame.configure(style='App.TFrame')
            
            if self.response_text_widget: 
                self._apply_theme_to_tk_widget(self.response_text_widget)
                try: # Theme scrollbars of ScrolledText
                    self.style.configure('Response.TScrollbar', # Potentially a unique style for response window scrollbars
                                         troughcolor=settings.get_theme_color('scrollbar_trough'), 
                                         background=settings.get_theme_color('scrollbar_bg'),
                                         arrowcolor=fg, bordercolor=border_color, relief=tk.FLAT)
                    for child in self.response_text_widget.winfo_children():
                        if isinstance(child, ttk.Scrollbar):
                            child.configure(style='Response.TScrollbar') # Apply specific style
                        elif isinstance(child, tk.Scrollbar): # Fallback for pure tk.Scrollbar
                             child.config(background=settings.get_theme_color('scrollbar_bg'),
                                          troughcolor=settings.get_theme_color('scrollbar_trough'),
                                          activebackground=settings.get_theme_color('button_active_bg'))
                except (tk.TclError, AttributeError) as e:
                    logger.warning("Minor issue theming scrollbars in apply_theme_globally for response window: %s", e, exc_info=False)

            if self.response_font_slider: self.response_font_slider.configure(style='TScale')
            if self.response_size_label: self.response_size_label.configure(style='App.TLabel')
            if self.response_copy_button: # And implicitly other buttons in its frame
                for sibling in self.response_copy_button.master.winfo_children():
                    if isinstance(sibling, ttk.Button): sibling.configure(style='App.TButton')
            
            if self.response_text_widget and self.response_text_widget.winfo_exists():
                try: # Re-apply markdown tags as colors might have changed
                    current_text_content = self.response_text_widget.get("1.0", tk.END).strip()
                    if current_text_content: # Only if there's text
                        ui_utils.apply_formatting_tags(self.response_text_widget, current_text_content, self.current_response_font_size)
                except (tk.TclError, AttributeError) as e:
                     logger.warning("Minor issue re-applying formatting tags in apply_theme_globally: %s", e, exc_info=False)
        
        if language_changed:
            logger.info("Language changed, triggering UI text update.")
            self._update_ui_text()

        if PYSTRAY_AVAILABLE and self.tray_icon and hasattr(self.tray_icon, 'update_menu') and self.tray_icon.visible:
             logger.debug("Requesting pystray menu update due to theme/language change.")
             self.tray_icon.update_menu() # pystray should handle re-rendering checkmarks/radio items
        logger.debug("Global theme application finished.")
        
    def _update_ui_text(self):
        if self.root_destroyed: return
        logger.info("Updating UI texts for language: %s", settings.LANGUAGE)
        
        self.root.title(settings.T('app_title'))
        if self.main_label: self.main_label.config(text=settings.T('main_label_text'))
        if self.custom_prompt_label_widget: self.custom_prompt_label_widget.config(text=settings.T('custom_prompt_label'))
        if self.hotkeys_list_label_widget: self.hotkeys_list_label_widget.config(text=settings.T('hotkeys_list_label'))
        
        if self.hotkeys_text_area:
            self.hotkeys_text_area.config(state=tk.NORMAL)
            self.hotkeys_text_area.delete('1.0', tk.END)
            hotkey_display_text = []
            if settings.HOTKEY_ACTIONS:
                for _, details in settings.HOTKEY_ACTIONS.items():
                    hotkey_display_text.append(f"{details['hotkey']}: {details['description']}")
                self.hotkeys_text_area.insert(tk.END, "\n".join(hotkey_display_text))
                logger.debug("Updated hotkeys display area with %d hotkeys.", len(settings.HOTKEY_ACTIONS))
            else:
                self.hotkeys_text_area.insert(tk.END, settings.T('hotkey_failed_status'))
                logger.warning("HOTKEY_ACTIONS not loaded, displaying failure status in UI.")
            self.hotkeys_text_area.config(state=tk.DISABLED)

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
            
            if current_text in generic_statuses or any(current_text.startswith(p) for p in change_prefixes if p):
                is_generic_status_or_change_msg = True

            if is_generic_status_or_change_msg and \
               not (hasattr(self, '_theme_just_changed') and self._theme_just_changed) and \
               not (hasattr(self, '_lang_just_changed') and self._lang_just_changed):
                ready_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
                self.update_status(settings.T(ready_key), 'status_ready_fg')
                logger.debug("Status label reset to 'Ready'.")
            
            if hasattr(self, '_theme_just_changed'): del self._theme_just_changed
            if hasattr(self, '_lang_just_changed'): del self._lang_just_changed

        if self.capture_button:
            self.capture_button.config(text=settings.T('capture_button_text'))
            default_manual_action_details = settings.HOTKEY_ACTIONS.get(settings.DEFAULT_MANUAL_ACTION)
            prompt_for_button = settings.T('ollama_no_response_content') # Fallback
            if default_manual_action_details:
                prompt_for_button = default_manual_action_details['prompt']
                if prompt_for_button == settings.CUSTOM_PROMPT_IDENTIFIER:
                    describe_action = settings.HOTKEY_ACTIONS.get('describe', {})
                    prompt_for_button = describe_action.get('prompt', "Describe (fallback prompt for button)")
            self.capture_button.config(command=lambda p=prompt_for_button: self._trigger_capture_from_ui(p))

        if self.exit_button:
            exit_key = 'exit_button_text_tray' if PYSTRAY_AVAILABLE else 'exit_button_text'
            self.exit_button.config(text=settings.T(exit_key))

        if self.response_window and self.response_window.winfo_exists():
            logger.debug("Updating texts in open response window.")
            self.response_window.title(settings.T('response_window_title'))
            if self.response_size_label:
                self.response_size_label.config(text=settings.T('font_size_label_format').format(size=self.current_response_font_size))
            if self.response_copy_button:
                original_copy_text = settings.T('copy_button_text')
                copied_text_all_langs = [settings.T('copied_button_text', lang=lc) for lc in settings.SUPPORTED_LANGUAGES.keys()]
                if self.response_copy_button.cget('text') not in copied_text_all_langs:
                    self.response_copy_button.config(text=original_copy_text)
            
            if self.response_copy_button and self.response_copy_button.master: # Find close button
                for widget in self.response_copy_button.master.winfo_children():
                    if isinstance(widget, ttk.Button) and widget != self.response_copy_button:
                        widget.config(text=settings.T('close_button_text'))
                        break
        logger.info("UI texts updated.")

    def _get_prompt_for_action(self, prompt_source):
        if self.root_destroyed: return None
        if prompt_source == settings.CUSTOM_PROMPT_IDENTIFIER:
            custom_prompt = self.custom_prompt_var.get().strip()
            if not custom_prompt:
                logger.warning("Custom prompt action triggered, but prompt field is empty.")
                if self.root and self.root.winfo_exists():
                    messagebox.showwarning(settings.T('dialog_warning_title'), settings.T('custom_prompt_empty_warning'), parent=self.root)
                return None
            logger.debug("Using custom prompt: '%.50s...'", custom_prompt)
            return custom_prompt
        elif isinstance(prompt_source, str):
            logger.debug("Using pre-defined prompt: '%.50s...'", prompt_source)
            return prompt_source
        else: 
            logger.error("Invalid prompt_source type: %s. Value: %s", type(prompt_source), prompt_source)
            if self.root and self.root.winfo_exists():
                messagebox.showerror(settings.T('dialog_internal_error_title'), settings.T('dialog_internal_error_msg'), parent=self.root)
            return None

    def _trigger_capture_from_ui(self, prompt_source):
        if self.root_destroyed: return
        logger.debug("Capture triggered from UI button.")
        self._trigger_capture(prompt_source)

    def _trigger_capture(self, prompt_source, icon=None, item=None): # Tray args included
        if self.root_destroyed: return
        logger.info("Triggering capture. Prompt source type: %s", type(prompt_source).__name__)
        actual_prompt = self._get_prompt_for_action(prompt_source)
        
        if actual_prompt is None:
            logger.info("Capture aborted as actual_prompt is None (e.g., custom prompt was empty).")
            ready_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
            self.update_status(settings.T(ready_key), 'status_ready_fg') # Reset status
            return
        
        if self.root and self.root.winfo_viewable():
            logger.debug("Main window is viewable. Hiding it before capture.")
            self.root.withdraw()
            self._explicitly_hidden_to_tray = False # This hide is for capture, not user "hide to tray"
            self.root.after(100, lambda: self.capturer.capture_region(actual_prompt))
        else:
            logger.debug("Main window not viewable or not primary. Initiating capture directly.")
            self.capturer.capture_region(actual_prompt)

    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str):
        if self.root_destroyed: return
        logger.info("Processing screenshot with Ollama. Prompt: '%.50s...'", prompt)

        if self.root and not self.root.winfo_viewable() and PYSTRAY_AVAILABLE:
             if not self._explicitly_hidden_to_tray: # Only show if hidden for capture, not user action
                  logger.debug("Main window was hidden for capture; restoring it.")
                  self.show_window()

        self.update_status(settings.T('processing_status_text'), 'status_processing_fg')
        threading.Thread(target=self._ollama_request_worker, args=(screenshot, prompt), daemon=True, name="OllamaWorkerThread").start()

    def _ollama_request_worker(self, screenshot: Image.Image, prompt: str):
        if self.root_destroyed: return
        logger.debug("Ollama worker thread started.")
        try:
            response_text = ollama_utils.request_ollama_analysis(screenshot, prompt)
            logger.info("Ollama analysis successful. Response length: %d", len(response_text or ""))
            self.update_status_safe(settings.T('ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'), 'status_ready_fg')
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.display_ollama_response, response_text)
        except OllamaConnectionError as e:
            msg = f"{settings.T('ollama_conn_failed_status')}" # Base message
            logger.error("Ollama connection error: %s. URL: %s", e, settings.OLLAMA_URL, exc_info=False)
            self.update_status_safe(msg, 'status_error_fg')
            if self.root and self.root.winfo_exists():
                self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_conn_error_title'), settings.T('dialog_ollama_conn_error_msg').format(url=settings.OLLAMA_URL))
        except OllamaTimeoutError as e:
            msg = f"{settings.T('ollama_timeout_status')}"
            logger.error("Ollama request timed out: %s. URL: %s", e, settings.OLLAMA_URL, exc_info=False)
            self.update_status_safe(msg, 'status_error_fg')
            if self.root and self.root.winfo_exists():
                 self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_timeout_title'), settings.T('dialog_ollama_timeout_msg').format(url=settings.OLLAMA_URL))
        except OllamaRequestError as e:
            msg = f"{settings.T('ollama_request_failed_status')}: {e.detail or e}"
            logger.error("Ollama request error. Status: %s, Detail: %s, Error: %s", e.status_code, e.detail, e, exc_info=False)
            self.update_status_safe(msg, 'status_error_fg')
            if self.root and self.root.winfo_exists():
                self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_error_title'), f"{msg}\n(Status: {e.status_code})")
        except OllamaError as e: # Generic library error
            msg = f"{settings.T('ollama_request_failed_status')}: {e}"
            logger.error("Generic Ollama library error: %s", e, exc_info=True)
            self.update_status_safe(msg, 'status_error_fg')
            if self.root and self.root.winfo_exists():
                self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_error_title'), msg)
        except ValueError as e: # e.g., image encoding error before request
            msg = f"{settings.T('error_preparing_image_status')}: {e}"
            logger.error("Value error during Ollama request preparation (e.g., image encoding): %s", e, exc_info=True)
            self.update_status_safe(msg, 'status_error_fg')
        except Exception as e:
            logger.critical("Unexpected error in Ollama worker thread.", exc_info=True)
            self.update_status_safe(settings.T('unexpected_error_status'), 'status_error_fg')
            if self.root and self.root.winfo_exists():
                 self.root.after(0, messagebox.showerror, settings.T('dialog_unexpected_error_title'), f"{settings.T('unexpected_error_status')}: {e}")
        logger.debug("Ollama worker thread finished.")

    def display_ollama_response(self, response_text):
        if self.root_destroyed: return
        logger.info("Displaying Ollama response. Length: %d", len(response_text or ""))
        if self.response_window and self.response_window.winfo_exists():
            logger.debug("Previous response window exists. Destroying it.")
            try: self.response_window.destroy()
            except tk.TclError: pass
        
        if not self.root or not self.root.winfo_exists():
            logger.warning("Cannot display Ollama response, main root window is gone.")
            return

        self.response_window = tk.Toplevel(self.root)
        self.response_window.title(settings.T('response_window_title'))
        self.response_window.geometry(settings.RESPONSE_WINDOW_GEOMETRY)
        self.response_window.configure(background=settings.get_theme_color('app_bg'))

        text_frame = ttk.Frame(self.response_window, style='App.TFrame')
        self.response_text_widget = scrolledtext.ScrolledText(
            text_frame, wrap=tk.WORD, relief=tk.FLAT, bd=0,
            font=('TkDefaultFont', self.current_response_font_size),
            height=settings.RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES
        )
        self._apply_theme_to_tk_widget(self.response_text_widget)
        try: # Theme scrollbars
            self.style.configure('Response.TScrollbar', troughcolor=settings.get_theme_color('scrollbar_trough'), background=settings.get_theme_color('scrollbar_bg'), arrowcolor=settings.get_theme_color('app_fg'))
            for child in self.response_text_widget.winfo_children():
                if isinstance(child, ttk.Scrollbar): child.configure(style='Response.TScrollbar')
                elif isinstance(child, tk.Scrollbar): child.config(background=settings.get_theme_color('scrollbar_bg'), troughcolor=settings.get_theme_color('scrollbar_trough'), activebackground=settings.get_theme_color('button_active_bg'))
        except (tk.TclError, AttributeError) as e: logger.warning("Minor issue theming scrollbars for response: %s", e, exc_info=False)

        control_frame = ttk.Frame(self.response_window, style='App.TFrame')
        def update_font_size_display_themed(size_val_str):
            # ... (same as your existing, ensure logger.debug/warning for issues)
            if self.root_destroyed: return
            try:
                new_size = int(float(size_val_str))
                if not (settings.MIN_FONT_SIZE <= new_size <= settings.MAX_FONT_SIZE): return
                logger.debug("Response window font size changing to %dpt", new_size)
                self.current_response_font_size = new_size
                if self.response_size_label and self.response_size_label.winfo_exists():
                    self.response_size_label.config(text=settings.T('font_size_label_format').format(size=new_size))
                
                text_w = self.response_text_widget 
                if text_w and text_w.winfo_exists(): 
                    base_font_obj = tkFont.Font(font=text_w['font'])
                    base_font_obj.configure(size=new_size)
                    text_w.configure(font=base_font_obj)
                    ui_utils.apply_formatting_tags(text_w, response_text, new_size) # Pass original full text
            except (ValueError, tk.TclError, AttributeError) as e:
                logger.warning("Error updating font size in response window: %s", e, exc_info=False)


        self.response_font_slider = ttk.Scale(control_frame, from_=settings.MIN_FONT_SIZE, to=settings.MAX_FONT_SIZE, 
                                       orient=tk.HORIZONTAL, value=self.current_response_font_size,
                                       command=update_font_size_display_themed, style='TScale')
        self.response_font_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, settings.PADDING_LARGE))
        self.response_size_label = ttk.Label(control_frame, text=settings.T('font_size_label_format').format(size=self.current_response_font_size),
                                      width=settings.FONT_SIZE_LABEL_WIDTH, style='App.TLabel')
        self.response_size_label.pack(side=tk.LEFT)

        button_frame_resp = ttk.Frame(self.response_window, style='App.TFrame')
        def copy_to_clipboard_command_themed():
            # ... (same as your existing, ensure logger.debug/warning for issues)
            if self.root_destroyed or not (self.response_window and self.response_window.winfo_exists()): return
            raw_text_content = self.response_text_widget.get('1.0', tk.END).strip()
            try:
                self.response_window.clipboard_clear()
                self.response_window.clipboard_append(raw_text_content)
                logger.info("Response text copied to clipboard. Length: %d", len(raw_text_content))
                if self.response_copy_button and self.response_copy_button.winfo_exists():
                    original_text = settings.T('copy_button_text')
                    copied_text = settings.T('copied_button_text')
                    self.response_copy_button.config(text=copied_text)
                    if self.response_window and self.response_window.winfo_exists(): # Ensure window still exists for after()
                        self.response_window.after(settings.COPY_BUTTON_RESET_DELAY_MS, 
                            lambda: self.response_copy_button.config(text=original_text) if self.response_copy_button and self.response_copy_button.winfo_exists() else None)
            except tk.TclError as e:
                logger.error("TclError copying to clipboard: %s", e, exc_info=True)
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
        min_text_area_height_px = settings.RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES * line_height_px
        min_total_height = int(min_text_area_height_px + settings.ESTIMATED_CONTROL_FRAME_HEIGHT_PX + \
                               settings.ESTIMATED_BUTTON_FRAME_HEIGHT_PX + settings.ESTIMATED_PADDING_PX * 3) 
        self.response_window.minsize(settings.RESPONSE_WINDOW_MIN_WIDTH, min_total_height)

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
        logger.debug("Ollama response window displayed.")

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
        logger.debug("Updating status (safe): '%s', color_key: %s", message, color_key)
        if self.root and self.root.winfo_exists():
            self.root.after(0, self.update_status, message, color_key)

    def _build_tray_menu(self):
        if self.root_destroyed or not PYSTRAY_AVAILABLE: return tuple()
        logger.debug("Building pystray menu.")
        lang_submenu_items = []
        for code, name in settings.SUPPORTED_LANGUAGES.items():
            action = partial(self.change_language, code) 
            item = pystray.MenuItem(name, action, checked=lambda item_param, current_code_param=code: settings.LANGUAGE == current_code_param, radio=True)
            lang_submenu_items.append(item)
        theme_submenu_items = [
            pystray.MenuItem(settings.T('tray_theme_light_text'), partial(self.change_theme, 'light'), checked=lambda item: settings.CURRENT_THEME == 'light', radio=True ),
            pystray.MenuItem(settings.T('tray_theme_dark_text'), partial(self.change_theme, 'dark'), checked=lambda item: settings.CURRENT_THEME == 'dark', radio=True )]
        default_manual_action_details = settings.HOTKEY_ACTIONS.get(settings.DEFAULT_MANUAL_ACTION)
        tray_capture_prompt = settings.T('ollama_no_response_content') 
        if default_manual_action_details:
            tray_capture_prompt = default_manual_action_details['prompt']
            if tray_capture_prompt == settings.CUSTOM_PROMPT_IDENTIFIER:
                describe_action = settings.HOTKEY_ACTIONS.get('describe', {})
                tray_capture_prompt = describe_action.get('prompt', "Describe (tray fallback)")
        menu_items = [
            pystray.MenuItem(settings.T('tray_show_window_text'), self.show_window, default=True, visible=lambda item: not self.root_destroyed and self.root and self.root.winfo_exists() and not self.root.winfo_viewable()),
            pystray.MenuItem(settings.T('tray_capture_text'), partial(self._trigger_capture, prompt_source=tray_capture_prompt)),
            pystray.MenuItem(settings.T('tray_language_text'), pystray.Menu(*lang_submenu_items)),
            pystray.MenuItem(settings.T('tray_theme_text'), pystray.Menu(*theme_submenu_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(settings.T('tray_exit_text'), lambda: self.on_exit(from_tray=True))]
        return tuple(menu_items)

    def _request_rebuild_tray_icon_from_main_thread(self):
        if self.root_destroyed: return
        logger.debug("Requesting tray icon rebuild from main thread.")
        if self.root and self.root.winfo_exists() and PYSTRAY_AVAILABLE:
            self.root.after(100, self._rebuild_tray_icon_on_main_thread)

    def _rebuild_tray_icon_on_main_thread(self):
        if self.root_destroyed or not PYSTRAY_AVAILABLE: return
        if not self.is_rebuilding_tray.acquire(blocking=False):
            logger.info("Tray rebuild already in progress or lock acquisition failed. Skipping.")
            return
        logger.info("Starting tray icon rebuild on main thread.")
        try:
            old_tray_instance = self.tray_icon
            old_tray_thread = self.tray_thread
            if old_tray_instance:
                logger.debug("Stopping old pystray instance...")
                old_tray_instance.stop() 
                self.tray_icon = None
            if old_tray_thread and old_tray_thread.is_alive():
                logger.debug("Joining old pystray thread...")
                old_tray_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS)
                if old_tray_thread.is_alive(): logger.warning("Old pystray thread did not exit in time.")
            self.tray_thread = None

            new_menu = self._build_tray_menu()
            if not new_menu: 
                logger.warning("Tray menu could not be built during rebuild. Aborting tray setup.")
                self.is_rebuilding_tray.release(); return

            if not self.icon_image:
                 logger.warning("Tray icon image is not loaded. Attempting to load/create default for rebuild.")
                 try: self.icon_image = Image.open(settings.ICON_PATH) if os.path.exists(settings.ICON_PATH) else ui_utils.create_default_icon()
                 except Exception as e_icon: logger.error("Error loading icon during tray rebuild: %s", e_icon, exc_info=True); self.icon_image = ui_utils.create_default_icon()

            logger.debug("Creating new pystray.Icon instance.")
            self.tray_icon = pystray.Icon(settings.TRAY_ICON_NAME, self.icon_image, settings.T('app_title'), new_menu)
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True, name="PystrayThread")
            self.tray_thread.start()
            logger.info("New pystray icon started in its thread.")
        except Exception as e: logger.error("Exception during tray rebuild process.", exc_info=True)
        finally: self.is_rebuilding_tray.release(); logger.debug("Tray rebuild lock released.")

    def setup_tray_icon(self):
        if self.root_destroyed or not PYSTRAY_AVAILABLE:
            logger.info("Skipping tray icon setup (root destroyed or pystray unavailable).")
            return
        if not self.icon_image:
            logger.warning("Tray icon image not loaded prior to setup_tray_icon. Attempting to load default.")
            self.icon_image = ui_utils.create_default_icon() # Ensure there's an image
        logger.info("Setting up system tray icon initially.")
        self._rebuild_tray_icon_on_main_thread() # Use the main thread rebuild logic for consistency

    def change_theme(self, theme_name, icon=None, item=None): # Tray args
        if self.root_destroyed: return
        logger.info("Changing theme to: %s", theme_name)
        if settings.set_theme(theme_name): 
            self._theme_just_changed = True
            # pystray handles radio item checkmarks. Menu text itself doesn't change with theme.
        else:
            logger.warning("Failed to change theme to %s (already current or unsupported).", theme_name)

    def change_language(self, lang_code, icon=None, item=None): # Tray args
        if self.root_destroyed: return
        if settings.LANGUAGE == lang_code: logger.debug("Language already set to %s. No change.", lang_code); return
        
        logger.info("Changing language to: %s", lang_code)
        if settings.set_language(lang_code): 
            self.start_hotkey_listener() # Prompts might have changed
            lang_name = settings.SUPPORTED_LANGUAGES.get(settings.LANGUAGE, settings.LANGUAGE)
            self.update_status(settings.T('status_lang_changed_to').format(lang_name=lang_name), 'status_ready_fg')
            self._lang_just_changed = True
            self._request_rebuild_tray_icon_from_main_thread() # Tray menu item texts change
        else:
            logger.error("Failed to change language to %s (unsupported or error during reload).", lang_code)
            self.update_status(f"Failed to change language to {lang_code}.", 'status_error_fg')

    def hide_to_tray(self, event=None): 
        if self.root_destroyed or not PYSTRAY_AVAILABLE: return
        logger.info("Hiding main window to system tray.")
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
            self._explicitly_hidden_to_tray = True
            self.update_status(settings.T('window_hidden_status'), 'status_default_fg')
            if self.tray_icon and hasattr(self.tray_icon, 'update_menu'): self.tray_icon.update_menu()

    def show_window(self, icon=None, item=None): 
        if self.root_destroyed: return
        logger.info("Showing main window from system tray or initial state.")
        def _show():
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                 self.root.deiconify(); self.root.lift(); self.root.focus_force()
                 self._explicitly_hidden_to_tray = False
                 self.update_status(settings.T('window_restored_status'), 'status_default_fg')
                 if PYSTRAY_AVAILABLE and self.tray_icon and hasattr(self.tray_icon, 'update_menu'): self.tray_icon.update_menu()
        if self.root and self.root.winfo_exists(): self.root.after(0, _show)

    def _stop_hotkey_listener(self):
        if self.hotkey_listener:
            logger.info("Stopping hotkey listener...")
            try: self.hotkey_listener.stop()
            except Exception as e: logger.error("Exception stopping pynput hotkey listener.", exc_info=True)
            self.hotkey_listener = None
        if self.listener_thread and self.listener_thread.is_alive():
            logger.debug("Joining hotkey listener thread...")
            self.listener_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS) 
            if self.listener_thread.is_alive(): logger.warning("Hotkey listener thread did not join in time.")
            self.listener_thread = None
        logger.info("Hotkey listener stopped.")

    def start_hotkey_listener(self):
        if self.root_destroyed: return
        logger.info("Attempting to start hotkey listener...")
        self._stop_hotkey_listener()
        hotkey_map = {}
        try:
            if not settings.HOTKEY_ACTIONS:
                logger.error("Cannot start hotkey listener: No hotkey actions loaded.")
                self.update_status_safe(f"{settings.T('hotkey_failed_status')}: No hotkeys loaded.", 'status_error_fg')
                return
            for _, details in settings.HOTKEY_ACTIONS.items():
                hotkey_map[details['hotkey']] = partial(self._trigger_capture, prompt_source=details['prompt'])
            if not hotkey_map:
                 logger.warning("No valid hotkeys found in configuration to map.")
                 self.update_status_safe(f"{settings.T('hotkey_failed_status')}: No valid hotkeys configured.", 'status_error_fg')
                 return

            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            self.listener_thread = threading.Thread(target=self.hotkey_listener.run, daemon=True, name="HotkeyListenerThread")
            self.listener_thread.start()
            logger.info("Hotkey listener started successfully with %d hotkeys.", len(hotkey_map))
        except Exception as e: 
            error_msg_formatted = settings.T('dialog_hotkey_error_msg').format(error=e)
            logger.critical("Failed to start pynput hotkey listener.", exc_info=True)
            self.update_status_safe(settings.T('hotkey_failed_status'), 'status_error_fg')
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                 self.root.after(0, messagebox.showerror, settings.T('dialog_hotkey_error_title'), error_msg_formatted, parent=self.root)

    def on_exit(self, icon=None, item=None, from_tray=False, is_wm_delete=False):
        if not self.running: logger.debug("on_exit called but app already exiting."); return
        
        self.running = False 
        logger.info("Initiating application exit sequence. Called from: %s", "Tray" if from_tray else ("WM_DELETE" if is_wm_delete else "Button/Code"))
        self.update_status_safe(settings.T('exiting_app_status'), 'status_default_fg')

        logger.info(settings.T('stopping_hotkeys_status'))
        self._stop_hotkey_listener()

        if PYSTRAY_AVAILABLE and self.tray_icon:
            logger.info(settings.T('stopping_tray_status'))
            try: self.tray_icon.stop() 
            except Exception as e: logger.error("Error stopping pystray icon during exit.", exc_info=True)
        
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            logger.debug("Scheduling root window destruction.")
            if threading.current_thread() == threading.main_thread(): self._destroy_root_safely()
            else: self.root.after(0, self._destroy_root_safely)
        else: self.root_destroyed = True; logger.debug("Root already destroyed or never fully existed.")

    def _destroy_root_safely(self):
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            logger.info("Destroying Tkinter root window and any child windows...")
            try:
                if self.response_window and self.response_window.winfo_exists():
                    logger.debug("Destroying response window...")
                    self.response_window.destroy()
                logger.debug("Destroying main root window...")
                self.root.destroy()
                logger.info("Tkinter root window destroyed successfully.")
            except tk.TclError as e: logger.warning("TclError during root destroy (likely already happening): %s", e, exc_info=False)
            except Exception as e: logger.error("Unexpected error during root destroy.", exc_info=True)
        self.root_destroyed = True

    def run(self):
        if self.root_destroyed: logger.warning("Run called on already destroyed app. Exiting."); return
        logger.info("ScreenshotApp run method started.")
        self.start_hotkey_listener()
        self.setup_tray_icon()
        
        status_msg_key = 'ready_status_text_tray' if PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
        self.update_status(settings.T(status_msg_key), 'status_ready_fg')
        
        try:
            logger.info("Starting Tkinter mainloop...")
            self.root.mainloop()
            logger.info("Tkinter mainloop finished.")
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received in mainloop, initiating exit.")
            if self.running : self.on_exit()
        except Exception as e: # Catch any other unhandled TclError or other issues from mainloop
            logger.critical("Unhandled exception in Tkinter mainloop.", exc_info=True)
            if self.running : self.on_exit() # Attempt graceful shutdown

        # Post-mainloop cleanup actions
        logger.info("Post-mainloop cleanup started.")
        if self.running: # If mainloop exited without on_exit being called (e.g. external kill)
            logger.warning("Mainloop exited but app was still marked as running. Forcing on_exit.")
            self.on_exit() 
        
        # Ensure threads are joined (on_exit should handle this, but as a safeguard)
        self._stop_hotkey_listener() 
        if PYSTRAY_AVAILABLE and self.tray_thread and self.tray_thread.is_alive():
            logger.debug("Post-mainloop: Joining pystray thread...")
            if self.tray_icon and self.tray_icon.visible: self.tray_icon.stop() # Ensure it's signalled
            self.tray_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS)
            if self.tray_thread.is_alive(): logger.warning("Pystray thread did not exit cleanly post-mainloop.")
        
        if not self.root_destroyed: self._destroy_root_safely() # Final check for root window

        logger.info(settings.T('app_exit_complete_status'))
        logger.info(settings.T('app_finished_status'))


def main():
    # Logging should be configured by settings.py by the time we are here.
    # If settings.py failed to import, the except block at the top of this file handles it.
    
    # 1. Check for non-critical initialization errors from settings.py
    # (e.g., hotkeys.json or ui_texts.json failed to load, but settings.py itself was okay)
    if hasattr(settings, '_initialization_errors') and settings._initialization_errors:
        logger.critical("Initialization errors detected from settings.py. Showing error dialog and exiting.")
        error_title_key = 'dialog_settings_error_title'
        error_msg_template_key = 'dialog_hotkey_json_error_msg'
        try:
            title = settings.T(error_title_key)
            error_details_list = []
            for e_item_str in settings._initialization_errors:
                import re # Local import for this specific formatting
                match = re.search(r"\((.*?)\):", e_item_str)
                file_hint = match.group(1) if match else "a configuration file"
                actual_error_msg = e_item_str.split(': ', 1)[-1] if ': ' in e_item_str else e_item_str
                error_details_list.append(f"- {file_hint}: {actual_error_msg}")
            error_details = "\n".join(error_details_list)
            message = settings.T(error_msg_template_key).format(file="one or more critical data files", error=error_details)
            logger.error("Formatted initialization error for dialog: Title='%s', Message='%s'", title, message)
        except Exception as e_format: # Fallback if T function or formatting fails
            logger.error("Error formatting initialization error message for dialog.", exc_info=True)
            title = "Screener - Configuration Error"
            error_details = "\n".join([f"- {e_item}" for e_item in settings._initialization_errors])
            message = f"Failed to load essential configuration or UI text files.\nDetails:\n{error_details}"
        
        try:
            root_err_dialog = tk.Tk(); root_err_dialog.withdraw()
            messagebox.showerror(title, message, parent=root_err_dialog)
            root_err_dialog.destroy()
        except Exception as tk_popup_err: logger.error("Could not display initialization error dialog.", exc_info=True)
        return # Exit
    
    logger.info("-----------------------------------------------------------")
    logger.info("%s Starting...", settings.T('app_title'))
    logger.info('Platform: %s %s', platform.system(), platform.release())
    logger.info("Python version: %s", sys.version)
    logger.info("Ollama URL: %s", settings.OLLAMA_URL)
    logger.info("Ollama Model: %s", settings.OLLAMA_MODEL)
    logger.info("App language: %s (%s)", settings.LANGUAGE, settings.SUPPORTED_LANGUAGES.get(settings.LANGUAGE, 'Unknown'))
    logger.info("App theme: %s", settings.CURRENT_THEME)
    logger.info("Icon path for tray (from settings): %s", settings.ICON_PATH)
    logger.info("Bundle Dir (_BUNDLE_DIR): %s", settings._BUNDLE_DIR)
    logger.info("App Dir (_APP_DIR): %s", settings._APP_DIR)
    logger.info("Settings.json expected at: %s", settings.SETTINGS_FILE_PATH)
    logger.info("-----------------------------------------------------------")

    # 2. Check for optional tray icon file (icon.png for pystray)
    # This is done after critical file checks. A default icon can be used if this fails.
    if PYSTRAY_AVAILABLE:
        icon_path_to_check = settings.ICON_PATH # This path is already resolved by settings.py
        try:
            if not os.path.exists(icon_path_to_check):
                logger.warning("pystray icon file '%s' does not exist. Dialog will be shown.", icon_path_to_check)
                # Raise FileNotFoundError to trigger the messagebox logic below
                raise FileNotFoundError(f"Tray icon file not found: {icon_path_to_check}")
            with Image.open(icon_path_to_check) as img: # Check if it's a valid image
                logger.debug("pystray icon '%s' loaded successfully for pre-check.", icon_path_to_check)
        except FileNotFoundError: # Catches explicit raise above or if Image.open fails
            root_check = tk.Tk(); root_check.withdraw()
            proceed = messagebox.askokcancel(
                settings.T('dialog_icon_warning_title'),
                settings.T('dialog_icon_warning_msg').format(path=icon_path_to_check), parent=root_check )
            root_check.destroy()
            if not proceed: logger.info("User opted to exit due to missing tray icon file."); return
            logger.info("User acknowledged missing tray icon. Default will be used.")
        except Exception as e: # Other PIL errors loading the icon
            logger.error("Error loading pystray icon '%s': %s. Dialog will be shown.", icon_path_to_check, e, exc_info=False)
            root_check = tk.Tk(); root_check.withdraw()
            proceed = messagebox.askokcancel(
                settings.T('dialog_icon_error_title'),
                settings.T('dialog_icon_error_msg').format(path=icon_path_to_check, error=e), parent=root_check )
            root_check.destroy()
            if not proceed: logger.info("User opted to exit due to tray icon loading error."); return
            logger.info("User acknowledged tray icon loading error. Default will be used.")
    
    app = ScreenshotApp()
    app.run()

if __name__ == '__main__':
    # Ensure logging is set up before main() is called if running as script directly
    # This is mostly redundant if settings.py is imported correctly, but safe.
    if not logging.getLogger().hasHandlers():
        try:
            # Attempt to use the app's logging config if possible
            # This path might need adjustment if screener.py is not in the root of 'screener' package
            if os.path.exists("logging_config.py"):
                import logging_config as lc_main
                lc_main.setup_logging(level=logging.DEBUG) # More verbose for direct script run
                logging.info("Basic logging configured for direct script run of screener.py.")
            else: # Absolute fallback
                logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                logging.info("Ultra-fallback basicConfig for logging used in screener.py __main__.")
        except Exception as e_log_setup:
            print(f"Error setting up logging in screener.py __main__: {e_log_setup}")

    main()