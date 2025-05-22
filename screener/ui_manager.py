# screener/ui_manager.py
import logging
import tkinter as tk
from tkinter import scrolledtext, font as tkFont, ttk, messagebox
from functools import partial
from PIL import Image, ImageTk 

import screener.settings as settings
import screener.ui_utils as ui_utils

logger = logging.getLogger(__name__)

class UIManager:
    ACTION_BUTTONS_MAX_COLS = 1
    MIN_UI_FONT_SIZE = 7

    def __init__(self, app, root):
        self.app = app
        self.root = root
        self.style = ttk.Style(self.root)

        self.response_window: tk.Toplevel | None = None
        self.response_text_widget: scrolledtext.ScrolledText | None = None 
        self.response_font_slider: ttk.Scale | None = None
        self.response_size_label: ttk.Label | None = None
        self.response_copy_button: ttk.Button | None = None
        self.current_response_font_size = settings.DEFAULT_FONT_SIZE
        
        self.image_preview_label: ttk.Label | None = None 
        self._current_photo_image: ImageTk.PhotoImage | None = None 
        self.follow_up_input_field: tk.Text | None = None 
        self.ask_button: ttk.Button | None = None
        self.back_button: ttk.Button | None = None
        self.forward_button: ttk.Button | None = None
        self.follow_up_label: ttk.Label | None = None

        self.custom_prompt_var = tk.StringVar()
        self._explicitly_hidden_to_tray = False
        self._hidden_by_capture_process = False # ADDED: Flag for capture-induced hide
        self.main_label: ttk.Label | None = None
        self.custom_prompt_label_widget: ttk.Label | None = None
        self.custom_prompt_entry: ttk.Entry | None = None
        self.status_label: ttk.Label | None = None
        self.prompt_frame: ttk.Frame | None = None
        self.action_buttons_frame: ttk.Frame | None = None
        self.reopen_response_button: ttk.Button | None = None 
        self.ping_ollama_button: ttk.Button | None = None
        self.exit_button: ttk.Button | None = None

        self._setup_ttk_themes()

    def _setup_ttk_themes(self):
        try:
            preferred_themes = ['clam', 'alt', 'vista', 'xpnative']
            current_theme_set = False
            for theme_name in preferred_themes:
                if theme_name in self.style.theme_names():
                    self.style.theme_use(theme_name)
                    logger.info("Using ttk theme: '%s'", theme_name)
                    current_theme_set = True
                    break
            if not current_theme_set and self.style.theme_names():
                fallback_theme = self.style.theme_names()[0]
                self.style.theme_use(fallback_theme)
                logger.info("Preferred ttk themes not found. Using fallback theme: '%s'", fallback_theme)
            elif not self.style.theme_names():
                logger.warning("No ttk themes available. UI might look very basic.")
        except tk.TclError as e:
            logger.warning("TclError setting ttk theme: %s. Using system default.", e, exc_info=False)


    def setup_main_ui(self):
        logger.debug("Setting up main UI structure...")
        self.root.geometry(settings.MAIN_WINDOW_GEOMETRY)
        self.root.resizable(settings.WINDOW_RESIZABLE_WIDTH, settings.WINDOW_RESIZABLE_HEIGHT)
        
        adjusted_main_font_size = max(self.MIN_UI_FONT_SIZE, int(settings.DEFAULT_FONT_SIZE * 0.8))

        default_font = tkFont.nametofont('TkDefaultFont')
        default_font.configure(size=adjusted_main_font_size)
        self.root.option_add('*Font', default_font)
        
        main_frame = ttk.Frame(self.root, padding=settings.PADDING_LARGE, style='App.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.main_label = ttk.Label(main_frame, style='App.TLabel')
        self.main_label.pack(pady=(0, settings.PADDING_SMALL))
        
        self.status_label = ttk.Label(main_frame, anchor=tk.W, style='Status.TLabel')
        self.status_label.pack(pady=(settings.PADDING_SMALL, settings.PADDING_SMALL), fill=tk.X)
        
        self.ping_ollama_button = ttk.Button(main_frame,
                                             command=self.app.ping_ollama_service,
                                             style='App.TButton')
        self.ping_ollama_button.pack(pady=(0, settings.PADDING_LARGE), fill=tk.X, side=tk.TOP)

        bottom_controls_container = ttk.Frame(main_frame, style='App.TFrame')
        bottom_controls_container.pack(fill=tk.X, side=tk.BOTTOM, pady=(settings.PADDING_SMALL, 0))

        self.prompt_frame = ttk.Frame(bottom_controls_container, style='App.TFrame')
        self.prompt_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, settings.PADDING_SMALL))
        
        self.custom_prompt_label_widget = ttk.Label(self.prompt_frame, style='App.TLabel')
        self.custom_prompt_label_widget.pack(side=tk.LEFT, padx=(0, settings.PADDING_SMALL))
        self.custom_prompt_entry = ttk.Entry(self.prompt_frame, textvariable=self.custom_prompt_var, width=40, style='App.TEntry')
        self.custom_prompt_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.action_buttons_frame = ttk.Frame(bottom_controls_container, style='App.TFrame')
        self.action_buttons_frame.pack(side=tk.TOP, fill=tk.X, expand=True, pady=(settings.PADDING_SMALL, settings.PADDING_SMALL))
        
        self.reopen_response_button = ttk.Button(bottom_controls_container,
                                                 command=self.app.reopen_last_response_ui, 
                                                 style='App.TButton', state=tk.NORMAL) 
        self.reopen_response_button.pack(side=tk.TOP, fill=tk.X, expand=True, pady=(0, settings.PADDING_SMALL))

        self.exit_button = ttk.Button(bottom_controls_container, command=lambda: self.app.on_exit(), style='Exit.TButton')
        self.exit_button.pack(side=tk.TOP, fill=tk.X, expand=True, pady=(settings.PADDING_SMALL,0))
        
        close_action = self.hide_to_tray if self.app.PYSTRAY_AVAILABLE else lambda: self.app.on_exit(is_wm_delete=True)
        self.root.protocol('WM_DELETE_WINDOW', close_action)
        
        self._hidden_by_capture_process = False # Initialize flag
        
        logger.debug("Main UI structure setup complete.")
        self.apply_theme_globally(language_changed=True)


    def _apply_theme_to_tk_widget(self, widget, widget_type="tk.Text"):
        if not widget or not widget.winfo_exists():
            return
        is_enabled = widget.cget('state') != tk.DISABLED 
        text_bg_color = settings.get_theme_color('text_bg') if is_enabled else settings.get_theme_color('text_disabled_bg')
        text_fg_color = settings.get_theme_color('text_fg')
        border_color = settings.get_theme_color('code_block_border')
        config_options = {
            'background': text_bg_color, 'foreground': text_fg_color,
            'insertbackground': text_fg_color,
            'selectbackground': settings.get_theme_color('entry_select_bg'),
            'selectforeground': settings.get_theme_color('entry_select_fg'),
            'highlightthickness': 1, 'highlightbackground': border_color,
        }
        if is_enabled:
             config_options['highlightcolor'] = settings.get_theme_color('entry_select_bg')
        try:
            widget.configure(**config_options)
            if widget_type == "tk.Text" and not is_enabled: 
                widget.configure(foreground=settings.get_theme_color('disabled_fg'))
        except tk.TclError as e:
            logger.warning("TclError applying theme to %s (%s): %s", widget_type, widget, e, exc_info=False)

    def apply_theme_globally(self, language_changed=False, from_response_update=False):
        if self.app.root_destroyed: return
        logger.info("Applying global theme. Current: %s. Lang changed: %s. From response update: %s", 
                    settings.CURRENT_THEME, language_changed, from_response_update)

        bg = settings.get_theme_color('app_bg'); fg = settings.get_theme_color('app_fg')
        entry_bg = settings.get_theme_color('entry_bg'); select_bg = settings.get_theme_color('entry_select_bg')
        select_fg = settings.get_theme_color('entry_select_fg');
        button_bg = settings.get_theme_color('button_bg'); button_fg = settings.get_theme_color('button_fg')
        button_active_bg = settings.get_theme_color('button_active_bg')
        exit_button_bg = settings.get_theme_color('button_exit_bg'); exit_button_fg = settings.get_theme_color('button_exit_fg')
        exit_button_active_bg = settings.get_theme_color('button_exit_active_bg')
        disabled_fg = settings.get_theme_color('disabled_fg'); frame_bg = settings.get_theme_color('frame_bg')
        scale_trough = settings.get_theme_color('scale_trough'); border_color = settings.get_theme_color('code_block_border')

        self.root.configure(background=bg)
        self.style.configure('.', background=bg, foreground=fg, fieldbackground=entry_bg, borderwidth=1)
        self.style.configure('App.TFrame', background=frame_bg); self.style.configure('App.TLabel', background=frame_bg, foreground=fg)
        self.style.configure('App.TButton', background=button_bg, foreground=button_fg, bordercolor=border_color, relief=tk.RAISED, lightcolor=button_bg, darkcolor=button_bg, focuscolor=fg)
        self.style.map('App.TButton', background=[('active', button_active_bg), ('pressed', button_active_bg), ('disabled', settings.get_theme_color('text_disabled_bg'))], foreground=[('disabled', disabled_fg)], relief=[('pressed', tk.SUNKEN), ('!pressed', tk.RAISED)])
        self.style.configure('Exit.TButton', background=exit_button_bg, foreground=exit_button_fg, bordercolor=border_color, relief=tk.RAISED, lightcolor=exit_button_bg, darkcolor=exit_button_bg, focuscolor=exit_button_fg)
        self.style.map('Exit.TButton', background=[('active', exit_button_active_bg), ('pressed', exit_button_active_bg), ('disabled', settings.get_theme_color('text_disabled_bg'))], foreground=[('disabled', disabled_fg)], relief=[('pressed', tk.SUNKEN), ('!pressed', tk.RAISED)])
        self.style.configure('App.TEntry', fieldbackground=entry_bg, foreground=settings.get_theme_color('entry_fg'), selectbackground=select_bg, selectforeground=select_fg, insertcolor=settings.get_theme_color('entry_fg'), bordercolor=border_color, lightcolor=entry_bg, darkcolor=entry_bg)
        self.style.configure('TScale', troughcolor=scale_trough, background=button_bg, sliderrelief=tk.RAISED, borderwidth=1, lightcolor=button_bg, darkcolor=button_bg)
        self.style.map('TScale', background=[('active', button_active_bg)])
        current_status_color_key = getattr(self.status_label, '_current_status_color_key', 'status_default_fg') if self.status_label else 'status_default_fg'
        status_fg_color = settings.get_theme_color(current_status_color_key)
        self.style.configure('Status.TLabel', background=frame_bg, foreground=status_fg_color)
        if self.status_label: self.status_label.configure(foreground=status_fg_color)

        if language_changed: self.update_ui_texts()

        if self.response_window and self.response_window.winfo_exists() and not from_response_update:
            logger.debug("apply_theme_globally: Response window open, queueing update_response_display.")
            self.response_window.after_idle(self.update_response_display)
        elif self.response_window and self.response_window.winfo_exists() and from_response_update:
            self.response_window.configure(background=bg)
            for child_widget in self.response_window.winfo_children():
                if isinstance(child_widget, (ttk.Frame, tk.PanedWindow)):
                    child_widget.configure(background=settings.get_theme_color('app_bg'))
                    if isinstance(child_widget, tk.PanedWindow):
                        for pane_child_frame_id in child_widget.panes():
                            try:
                                pane_frame = child_widget.nametowidget(pane_child_frame_id)
                                if isinstance(pane_frame, ttk.Frame): pane_frame.configure(style='App.TFrame')
                            except tk.TclError: pass 
            if self.image_preview_label: self.image_preview_label.configure(style='App.TLabel')
            if self.response_text_widget: self._apply_theme_to_tk_widget(self.response_text_widget)
            if self.follow_up_input_field: self._apply_theme_to_tk_widget(self.follow_up_input_field, widget_type="tk.Text")
            if self.follow_up_label: self.follow_up_label.configure(style='App.TLabel')
            try:
                self.style.configure('Response.TScrollbar', troughcolor=settings.get_theme_color('scrollbar_trough'), background=settings.get_theme_color('scrollbar_bg'), arrowcolor=fg, bordercolor=border_color, relief=tk.FLAT)
                if self.response_text_widget:
                    for child in self.response_text_widget.winfo_children():
                        if isinstance(child, ttk.Scrollbar): child.configure(style='Response.TScrollbar')
                        elif isinstance(child, tk.Scrollbar): child.config(background=settings.get_theme_color('scrollbar_bg'), troughcolor=settings.get_theme_color('scrollbar_trough'), activebackground=settings.get_theme_color('button_active_bg'))
            except (tk.TclError, AttributeError) as e: logger.warning("Minor issue theming scrollbars: %s", e, exc_info=False)
            if self.response_font_slider: self.response_font_slider.configure(style='TScale')
            if self.response_size_label: self.response_size_label.configure(style='App.TLabel')
            button_widgets = [self.response_copy_button, self.ask_button, self.back_button, self.forward_button]
            if hasattr(self.response_window, '_response_close_button'): button_widgets.append(getattr(self.response_window, '_response_close_button'))
            for btn in button_widgets:
                if btn and btn.winfo_exists(): btn.configure(style='App.TButton')
        
        logger.debug("Global theme application finished in UIManager.")

    def update_ui_texts(self):
        if self.app.root_destroyed: return
        logger.info("Updating UI texts for language: %s", settings.LANGUAGE)
        
        self.root.title(settings.T('app_title'))
        if self.main_label: self.main_label.config(text=settings.T('main_label_text'))
        if self.custom_prompt_label_widget: self.custom_prompt_label_widget.config(text=settings.T('custom_prompt_label'))
        if self.ping_ollama_button and self.ping_ollama_button.winfo_exists():
            self.ping_ollama_button.config(text=settings.T('ping_ollama_button_text'))
        
        if self.status_label:
            current_text = self.status_label.cget("text")
            is_generic_or_change_msg = False
            all_generic_statuses = []
            for lc in settings.SUPPORTED_LANGUAGES.keys():
                 all_generic_statuses.extend([settings.T(k, lang=lc) for k in ['initial_status_text', 'ready_status_text_no_tray', 'ready_status_text_tray', 'session_loaded_status', 'no_sessions_found_status', 'error_reopening_session_status']]) 
            change_msg_templates = ['status_lang_changed_to', 'status_theme_changed_to']
            all_change_prefixes = []
            for tpl in change_msg_templates:
                for lc in settings.SUPPORTED_LANGUAGES.keys():
                    prefix = settings.T(tpl, lang=lc).split('{')[0]
                    if prefix: all_change_prefixes.append(prefix)
            if current_text in all_generic_statuses or any(current_text.startswith(p) for p in all_change_prefixes if p):
                is_generic_or_change_msg = True
            ping_related_status_keys = ['pinging_ollama_status', 'ollama_reachable_status', 'ollama_unreachable_conn_error_status', 'ollama_unreachable_timeout_status', 'ollama_unreachable_http_error_status', 'ollama_unreachable_other_error_status']
            is_ping_status = False
            for key in ping_related_status_keys:
                if key == 'ollama_unreachable_http_error_status':
                    if current_text.startswith(settings.T(key).split('{')[0]): is_ping_status = True; break
                elif current_text == settings.T(key): is_ping_status = True; break
            if is_generic_or_change_msg and \
               not (hasattr(self.app, '_theme_just_changed') and self.app._theme_just_changed) and \
               not (hasattr(self.app, '_lang_just_changed') and self.app._lang_just_changed) and \
               not is_ping_status:
                ready_key = 'ready_status_text_tray' if self.app.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
                self.update_status(settings.T(ready_key), 'status_ready_fg')
            if hasattr(self.app, '_theme_just_changed'): self.app._theme_just_changed = False
            if hasattr(self.app, '_lang_just_changed'): self.app._lang_just_changed = False

        if self.action_buttons_frame and self.action_buttons_frame.winfo_exists():
            for widget in self.action_buttons_frame.winfo_children(): widget.destroy()
            row = 0; action_button_count = 0
            def create_action_button(action_details, frame, current_row):
                description = action_details.get('description', 'N/A'); hotkey = action_details.get('hotkey', 'N/A')
                btn_text = f"{description}\n({hotkey})"
                btn_prompt_source = action_details.get('prompt')
                if not btn_prompt_source: logger.warning("Skipping button: missing prompt: %s", description); return current_row
                btn_command = partial(self.app._trigger_capture_from_ui, btn_prompt_source)
                button = ttk.Button(frame, text=btn_text, command=btn_command, style='App.TButton')
                button.grid(row=current_row, column=0, sticky="ew", padx=2, pady=2); return current_row + 1
            custom_prompt_action_name = "custom_prompt_hotkey"
            if settings.HOTKEY_ACTIONS and custom_prompt_action_name in settings.HOTKEY_ACTIONS:
                details = settings.HOTKEY_ACTIONS[custom_prompt_action_name]
                row = create_action_button(details, self.action_buttons_frame, row); action_button_count += 1
            if settings.HOTKEY_ACTIONS:
                remaining_actions = sorted([(name, det) for name, det in settings.HOTKEY_ACTIONS.items() if name != custom_prompt_action_name], key=lambda item: item[1].get('description', item[0]))
                for action_name, details in remaining_actions: row = create_action_button(details, self.action_buttons_frame, row); action_button_count += 1
            if action_button_count > 0: self.action_buttons_frame.grid_columnconfigure(0, weight=1)

        if self.reopen_response_button: self.reopen_response_button.config(text=settings.T('reopen_response_button_text')) 
        if self.exit_button:
            exit_key = 'exit_button_text_tray' if self.app.PYSTRAY_AVAILABLE else 'exit_button_text'
            self.exit_button.config(text=settings.T(exit_key))

        if self.response_window and self.response_window.winfo_exists():
            self.response_window.title(settings.T('response_window_title'))
            if self.response_size_label: self.response_size_label.config(text=settings.T('font_size_label_format').format(size=self.current_response_font_size))
            if self.response_copy_button:
                original_copy_text = settings.T('copy_button_text')
                copied_text_all_langs = [settings.T('copied_button_text', lang=lc) for lc in settings.SUPPORTED_LANGUAGES.keys()]
                if self.response_copy_button.cget('text') not in copied_text_all_langs: self.response_copy_button.config(text=original_copy_text)
            if self.ask_button: self.ask_button.config(text=settings.T('ask_button_text'))
            if self.back_button: self.back_button.config(text=settings.T('back_button_text'))
            if self.forward_button: self.forward_button.config(text=settings.T('forward_button_text'))
            if self.follow_up_label: self.follow_up_label.config(text=settings.T('follow_up_prompt_label'))
            if hasattr(self.response_window, '_response_close_button') and getattr(self.response_window, '_response_close_button').winfo_exists():
                getattr(self.response_window, '_response_close_button').config(text=settings.T('close_button_text'))
        logger.info("UI texts updated in UIManager.")


    def display_ollama_response(self, screenshot_image: Image.Image):
        if self.app.root_destroyed: return
        logger.info("Displaying Ollama response window.")
        self.destroy_response_window_if_exists() 

        if not self.root or not self.root.winfo_exists(): return
        if not screenshot_image: logger.error("Cannot display response: screenshot_image is None."); return

        self.response_window = tk.Toplevel(self.root)
        self.response_window.title(settings.T('response_window_title'))
        self.response_window.geometry(settings.RESPONSE_WINDOW_GEOMETRY)
        self.response_window.configure(background=settings.get_theme_color('app_bg'))

        main_paned_window = tk.PanedWindow(self.response_window, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, background=settings.get_theme_color('app_bg'))
        main_paned_window.pack(fill=tk.BOTH, expand=True)

        image_preview_frame = ttk.Frame(main_paned_window, style='App.TFrame', width=settings.RESPONSE_WINDOW_IMAGE_PREVIEW_MIN_WIDTH)
        image_preview_frame.pack_propagate(False) 
        self.image_preview_label = ttk.Label(image_preview_frame, style='App.TLabel', anchor=tk.CENTER)
        self.image_preview_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_paned_window.add(image_preview_frame, minsize=settings.RESPONSE_WINDOW_IMAGE_PREVIEW_MIN_WIDTH)
        setattr(self.image_preview_label, '_original_pil_image', screenshot_image)
        image_preview_frame.bind("<Configure>", self._on_image_pane_resize)

        right_pane_frame = ttk.Frame(main_paned_window, style='App.TFrame')
        right_pane_frame.pack_propagate(False); main_paned_window.add(right_pane_frame)

        text_area_frame = ttk.Frame(right_pane_frame, style='App.TFrame')
        text_area_frame.pack(fill=tk.BOTH, expand=True, padx=settings.RESPONSE_TEXT_PADDING_X, pady=settings.RESPONSE_TEXT_PADDING_Y_TOP)

        self.response_text_widget = scrolledtext.ScrolledText(text_area_frame, wrap=tk.WORD, relief=tk.FLAT, bd=0, font=('TkDefaultFont', self.current_response_font_size), height=settings.RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES, state=tk.DISABLED)
        self._apply_theme_to_tk_widget(self.response_text_widget); self.response_text_widget.pack(fill=tk.BOTH, expand=True)
        try:
            self.style.configure('Response.TScrollbar', troughcolor=settings.get_theme_color('scrollbar_trough'), background=settings.get_theme_color('scrollbar_bg'), arrowcolor=settings.get_theme_color('app_fg'))
            for child in self.response_text_widget.winfo_children(): 
                if isinstance(child, ttk.Scrollbar): child.configure(style='Response.TScrollbar')
                elif isinstance(child, tk.Scrollbar): child.config(background=settings.get_theme_color('scrollbar_bg'), troughcolor=settings.get_theme_color('scrollbar_trough'), activebackground=settings.get_theme_color('button_active_bg'))
        except (tk.TclError, AttributeError) as e: logger.warning("Minor issue theming scrollbars for response: %s", e, exc_info=False)

        follow_up_controls_frame = ttk.Frame(right_pane_frame, style='App.TFrame')
        follow_up_controls_frame.pack(fill=tk.X, padx=settings.RESPONSE_CONTROL_PADDING_X, pady=(settings.PADDING_LARGE, settings.PADDING_SMALL))
        self.follow_up_label = ttk.Label(follow_up_controls_frame, text=settings.T('follow_up_prompt_label'), style='App.TLabel')
        self.follow_up_label.pack(side=tk.TOP, anchor='w', pady=(0,2))
        self.follow_up_input_field = tk.Text(follow_up_controls_frame, height=3, wrap=tk.WORD, relief=tk.SOLID, bd=1) 
        self._apply_theme_to_tk_widget(self.follow_up_input_field, widget_type="tk.Text"); self.follow_up_input_field.pack(fill=tk.X, expand=True, pady=(0, settings.PADDING_SMALL))
        nav_buttons_frame = ttk.Frame(follow_up_controls_frame, style='App.TFrame')
        nav_buttons_frame.pack(fill=tk.X)
        self.ask_button = ttk.Button(nav_buttons_frame, text=settings.T('ask_button_text'), style='App.TButton', command=lambda: self.app.handle_follow_up_question(self.follow_up_input_field.get("1.0", tk.END).strip()))
        self.ask_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, settings.PADDING_SMALL))
        self.back_button = ttk.Button(nav_buttons_frame, text=settings.T('back_button_text'), style='App.TButton', command=lambda: self.app.navigate_conversation("back"))
        self.back_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, settings.PADDING_SMALL))
        self.forward_button = ttk.Button(nav_buttons_frame, text=settings.T('forward_button_text'), style='App.TButton', command=lambda: self.app.navigate_conversation("forward"))
        self.forward_button.pack(side=tk.LEFT, expand=True, fill=tk.X)

        general_controls_frame = ttk.Frame(right_pane_frame, style='App.TFrame')
        general_controls_frame.pack(fill=tk.X, padx=settings.RESPONSE_CONTROL_PADDING_X, pady=settings.RESPONSE_CONTROL_PADDING_Y)
        def update_font_size_display_themed(size_val_str): 
            if self.app.root_destroyed: return
            try:
                new_size = int(float(size_val_str))
                if not (settings.MIN_FONT_SIZE <= new_size <= settings.MAX_FONT_SIZE): return
                self.current_response_font_size = new_size
                if self.response_size_label and self.response_size_label.winfo_exists(): self.response_size_label.config(text=settings.T('font_size_label_format').format(size=new_size))
                if self.response_text_widget and self.response_text_widget.winfo_exists():
                    base_font_obj = tkFont.Font(font=self.response_text_widget['font']); base_font_obj.configure(size=new_size)
                    self.response_text_widget.configure(font=base_font_obj)
                    current_text_content = ""; 
                    if self.app.conversation_history and 0 <= self.app.current_turn_index < len(self.app.conversation_history):
                        current_text_content = self.app.conversation_history[self.app.current_turn_index].get("ollama_response", "")
                    ui_utils.apply_formatting_tags(self.response_text_widget, current_text_content, new_size)
            except (ValueError, tk.TclError, AttributeError) as e: logger.warning("Error updating font size: %s", e, exc_info=False)
        self.response_font_slider = ttk.Scale(general_controls_frame, from_=settings.MIN_FONT_SIZE, to=settings.MAX_FONT_SIZE, orient=tk.HORIZONTAL, value=self.current_response_font_size, command=update_font_size_display_themed, style='TScale')
        self.response_font_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, settings.PADDING_LARGE))
        self.response_size_label = ttk.Label(general_controls_frame, text=settings.T('font_size_label_format').format(size=self.current_response_font_size), width=settings.FONT_SIZE_LABEL_WIDTH, style='App.TLabel')
        self.response_size_label.pack(side=tk.LEFT)
        bottom_buttons_frame = ttk.Frame(right_pane_frame, style='App.TFrame')
        bottom_buttons_frame.pack(fill=tk.X, pady=settings.RESPONSE_BUTTON_PADDING_Y, padx=settings.RESPONSE_BUTTON_PADDING_X)
        def copy_to_clipboard_command_themed(): 
            if self.app.root_destroyed or not (self.response_window and self.response_window.winfo_exists()): return
            raw_text_content = self.response_text_widget.get('1.0', tk.END).strip()
            try:
                self.response_window.clipboard_clear(); self.response_window.clipboard_append(raw_text_content)
                if self.response_copy_button and self.response_copy_button.winfo_exists():
                    original_text = settings.T('copy_button_text'); copied_text = settings.T('copied_button_text')
                    self.response_copy_button.config(text=copied_text)
                    if self.response_window and self.response_window.winfo_exists(): self.response_window.after(settings.COPY_BUTTON_RESET_DELAY_MS, lambda: self.response_copy_button.config(text=original_text) if self.response_copy_button and self.response_copy_button.winfo_exists() else None)
            except tk.TclError as e:
                logger.error("TclError copying to clipboard: %s", e, exc_info=True)
                if not self.app.root_destroyed and self.response_window and self.response_window.winfo_exists(): messagebox.showerror(settings.T('dialog_internal_error_title'), f"{settings.T('unexpected_error_status')}: {e}", parent=self.response_window)
        self.response_copy_button = ttk.Button(bottom_buttons_frame, text=settings.T('copy_button_text'), command=copy_to_clipboard_command_themed, style='App.TButton')
        self.response_copy_button.pack(side=tk.LEFT, padx=settings.RESPONSE_BUTTON_PADDING_X, expand=True, fill=tk.X)
        response_close_button = ttk.Button(bottom_buttons_frame, text=settings.T('close_button_text'), style='App.TButton', command=self.destroy_response_window_if_exists)
        response_close_button.pack(side=tk.LEFT, padx=settings.RESPONSE_BUTTON_PADDING_X, expand=True, fill=tk.X)
        setattr(self.response_window, '_response_close_button', response_close_button) 
        min_text_height_px = settings.RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES * tkFont.Font(font=self.response_text_widget['font']).metrics("linespace")
        min_follow_up_height_px = 3 * tkFont.Font(font=self.follow_up_input_field['font']).metrics("linespace") + settings.ESTIMATED_PADDING_PX 
        min_total_height = int( max(min_text_height_px + min_follow_up_height_px, settings.RESPONSE_WINDOW_IMAGE_PREVIEW_MIN_WIDTH * 0.6) + settings.ESTIMATED_CONTROL_FRAME_HEIGHT_PX + settings.ESTIMATED_BUTTON_FRAME_HEIGHT_PX + settings.ESTIMATED_PADDING_PX * 5) 
        self.response_window.minsize(settings.RESPONSE_WINDOW_MIN_WIDTH, min_total_height)
        self.response_window.transient(self.root); self.response_window.grab_set(); self.response_window.focus_force()
        self.response_window.protocol("WM_DELETE_WINDOW", self.destroy_response_window_if_exists)
        self.update_response_display()
        self.response_window.after(50, lambda: self._on_image_pane_resize())
        status_key = 'session_loaded_status' if self.app.current_turn_index > -1 and self.app.conversation_history else 'ready_status_text_tray'
        self.update_status(settings.T(status_key), 'status_ready_fg')
        logger.debug("Ollama response window displayed and configured.")

    def _on_image_pane_resize(self, event=None):
        if not self.image_preview_label or not self.image_preview_label.winfo_exists(): return
        original_pil_image = getattr(self.image_preview_label, '_original_pil_image', None)
        if not original_pil_image: return
        try:
            container_width = self.image_preview_label.master.winfo_width()
            container_height = self.image_preview_label.master.winfo_height()
        except tk.TclError: 
            if self.response_window and self.response_window.winfo_exists(): self.response_window.after(100, self._on_image_pane_resize) 
            return
        if container_width <= 1 or container_height <= 1: return
        img_copy = original_pil_image.copy(); img_width, img_height = img_copy.size
        if img_width <= 0 or img_height <= 0: return 
        ratio = min(container_width / img_width, container_height / img_height)
        new_width = int(img_width * ratio); new_height = int(img_height * ratio)
        if new_width <=0 or new_height <=0: return 
        try:
            resample_filter = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.ANTIALIAS
            resized_image = img_copy.resize((new_width, new_height), resample=resample_filter)
        except Exception as e_resize: logger.error("Error resizing image for preview: %s", e_resize); return
        try:
            self._current_photo_image = ImageTk.PhotoImage(resized_image)
            self.image_preview_label.config(image=self._current_photo_image)
        except Exception as e_photo: logger.warning("Error creating/configuring PhotoImage for preview: %s", e_photo)

    def update_response_display(self):
        if not self.response_window or not self.response_window.winfo_exists(): return
        if self.app.root_destroyed: return
        logger.debug("Updating response display. Current turn index: %d", self.app.current_turn_index)
        self.apply_theme_globally(from_response_update=True) # Ensure base theme is set first
        ollama_response_text = ""; next_question_text = "" 
        if self.app.conversation_history and 0 <= self.app.current_turn_index < len(self.app.conversation_history):
            current_turn = self.app.conversation_history[self.app.current_turn_index]
            ollama_response_text = current_turn.get("ollama_response", "")
            next_question_text = current_turn.get("subsequent_user_question", "") or ""
            is_latest_turn_after_ask = (self.app.current_turn_index == len(self.app.conversation_history) - 1) and (not current_turn.get("subsequent_user_question"))
            if is_latest_turn_after_ask: next_question_text = ""
        else: logger.debug("No valid conversation history or index to display.")
        if self.response_text_widget and self.response_text_widget.winfo_exists():
            ui_utils.apply_formatting_tags(self.response_text_widget, ollama_response_text, self.current_response_font_size)
        if self.follow_up_input_field and self.follow_up_input_field.winfo_exists():
            current_input_state = self.follow_up_input_field.cget('state')
            self.follow_up_input_field.config(state=tk.NORMAL)
            self.follow_up_input_field.delete("1.0", tk.END)
            self.follow_up_input_field.insert("1.0", next_question_text)
            if current_input_state == tk.DISABLED : self.follow_up_input_field.config(state=tk.DISABLED)
        can_go_back = self.app.conversation_history and self.app.current_turn_index > 0
        can_go_forward = self.app.conversation_history and self.app.current_turn_index < len(self.app.conversation_history) - 1
        if self.back_button and self.back_button.winfo_exists(): self.back_button.config(state=tk.NORMAL if can_go_back else tk.DISABLED)
        if self.forward_button and self.forward_button.winfo_exists(): self.forward_button.config(state=tk.NORMAL if can_go_forward else tk.DISABLED)
        if self.ask_button and self.ask_button.winfo_exists(): self.ask_button.config(state=tk.NORMAL if self.app.current_screenshot_image else tk.DISABLED)
        logger.debug("Response display updated for turn %d.", self.app.current_turn_index)

    def update_status(self, message, color_key='status_default_fg'):
        if self.app.root_destroyed: return
        def _update():
            if not self.app.root_destroyed and hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                color = settings.get_theme_color(color_key)
                self.status_label.config(text=message, foreground=color)
                setattr(self.status_label, '_current_status_color_key', color_key)
                self.style.configure('Status.TLabel', foreground=color, background=settings.get_theme_color('frame_bg'))
        if self.root and self.root.winfo_exists(): self.root.after(0, _update)

    def hide_to_tray(self, event=None): 
        if self.app.root_destroyed or not self.app.PYSTRAY_AVAILABLE: return
        logger.info("Hiding main window to system tray (user action).")
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
            self._explicitly_hidden_to_tray = True 
            self._hidden_by_capture_process = False 
            self.update_status(settings.T('window_hidden_status'), 'status_default_fg')
            if self.app.tray_manager: self.app.tray_manager.update_menu_if_visible()

    def show_window(self): 
        if self.app.root_destroyed: return
        logger.info("Showing main window.")
        def _show():
            if not self.app.root_destroyed and self.root and self.root.winfo_exists():
                 self.root.deiconify(); self.root.lift(); self.root.focus_force()
                 self._explicitly_hidden_to_tray = False 
                 self._hidden_by_capture_process = False 
                 self.update_status(settings.T('window_restored_status'), 'status_default_fg')
                 if self.app.PYSTRAY_AVAILABLE and self.app.tray_manager: self.app.tray_manager.update_menu_if_visible()
        if self.root and self.root.winfo_exists(): self.root.after(0, _show)

    def show_window_after_action_if_hidden(self):
        if self.app.root_destroyed: return
        if self.root and self.root.winfo_exists() and \
           not self.is_main_window_viewable() and \
           not self._explicitly_hidden_to_tray:
            logger.info("Showing main window after capture cancel/error or if it was hidden by capture.")
            self.root.after(0, self.show_window) 
        elif self._explicitly_hidden_to_tray: logger.debug("Main window explicitly hidden to tray, not showing automatically.")
        elif self.is_main_window_viewable(): logger.debug("Main window already viewable, not showing again.")

    def is_main_window_explicitly_hidden(self): return self._explicitly_hidden_to_tray
    def is_main_window_viewable(self): return self.root and self.root.winfo_exists() and self.root.winfo_viewable() 
    def get_custom_prompt(self): return self.custom_prompt_var.get().strip() 

    def destroy_response_window_if_exists(self):
        if self.response_window and self.response_window.winfo_exists():
            logger.debug("Destroying existing response window.")
            try: self.response_window.grab_release(); self.response_window.destroy()
            except tk.TclError: logger.warning("TclError destroying response window, likely already gone.")
            self.response_window = None
            self.image_preview_label = None; self._current_photo_image = None
            self.response_text_widget = None; self.follow_up_input_field = None
            self.ask_button = None; self.back_button = None; self.forward_button = None
            self.response_font_slider = None; self.response_size_label = None
            self.response_copy_button = None; self.follow_up_label = None

    def enable_reopen_response_button(self): 
        if self.app.root_destroyed: return
        if self.reopen_response_button and self.reopen_response_button.winfo_exists():
            self.reopen_response_button.config(state=tk.NORMAL) 

    def disable_reopen_response_button(self): 
        if self.app.root_destroyed: return
        if self.reopen_response_button and self.reopen_response_button.winfo_exists():
            self.reopen_response_button.config(state=tk.DISABLED)