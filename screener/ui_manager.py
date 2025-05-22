# ui_manager.py
import logging
import tkinter as tk
from tkinter import scrolledtext, font as tkFont, ttk, messagebox
from functools import partial

import screener.settings as settings
import screener.ui_utils as ui_utils

logger = logging.getLogger(__name__)

class UIManager:
    ACTION_BUTTONS_MAX_COLS = 1 # CHANGED to 1 for single column
    MIN_UI_FONT_SIZE = 7 

    def __init__(self, app, root):
        self.app = app  
        self.root = root
        self.style = ttk.Style(self.root)

        self.response_window = None
        self.response_text_widget = None
        self.response_font_slider = None
        self.response_size_label = None
        self.response_copy_button = None
        self.current_response_font_size = settings.DEFAULT_FONT_SIZE 

        self.custom_prompt_var = tk.StringVar()
        self._explicitly_hidden_to_tray = False

        self.main_label = None
        self.custom_prompt_label_widget = None
        self.custom_prompt_entry = None
        self.hotkeys_list_label_widget = None
        self.hotkeys_text_area = None
        self.status_label = None
        
        self.action_buttons_frame = None 
        self.exit_button = None
        
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
        # MAIN_WINDOW_GEOMETRY might need adjustment if buttons make it too tall
        self.root.geometry(settings.MAIN_WINDOW_GEOMETRY) 
        self.root.resizable(settings.WINDOW_RESIZABLE_WIDTH, settings.WINDOW_RESIZABLE_HEIGHT) # Consider True for Height
        
        adjusted_main_font_size = max(self.MIN_UI_FONT_SIZE, int(settings.DEFAULT_FONT_SIZE * 0.8))
        logger.info(f"Original default font size: {settings.DEFAULT_FONT_SIZE}, Adjusted main UI font size: {adjusted_main_font_size}")

        default_font = tkFont.nametofont('TkDefaultFont')
        default_font.configure(size=adjusted_main_font_size)
        self.root.option_add('*Font', default_font)
        
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
        
        hotkeys_font_size = max(self.MIN_UI_FONT_SIZE -1 if self.MIN_UI_FONT_SIZE > 1 else 1, adjusted_main_font_size - 2)
        self.hotkeys_text_area = tk.Text(main_frame, height=6, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1,
                                         font=('TkDefaultFont', hotkeys_font_size))
        self.hotkeys_text_area.pack(fill=tk.X, pady=(0, settings.PADDING_SMALL), expand=False)
        self.hotkeys_text_area.config(state=tk.DISABLED)
        
        self.status_label = ttk.Label(main_frame, anchor=tk.W, style='Status.TLabel')
        self.status_label.pack(pady=settings.PADDING_SMALL, fill=tk.X)
        
        bottom_buttons_container = ttk.Frame(main_frame, style='App.TFrame')
        bottom_buttons_container.pack(fill=tk.X, side=tk.BOTTOM, pady=(settings.PADDING_LARGE, 0))

        self.action_buttons_frame = ttk.Frame(bottom_buttons_container, style='App.TFrame')
        self.action_buttons_frame.pack(side=tk.TOP, fill=tk.X, expand=True, pady=(0, settings.PADDING_SMALL))
        
        # Apply specific style for Exit button
        self.exit_button = ttk.Button(bottom_buttons_container, command=lambda: self.app.on_exit(), style='Exit.TButton') 
        self.exit_button.pack(side=tk.TOP, fill=tk.X, expand=True) 
        
        close_action = self.hide_to_tray if self.app.PYSTRAY_AVAILABLE else lambda: self.app.on_exit(is_wm_delete=True)
        self.root.protocol('WM_DELETE_WINDOW', close_action)
        logger.debug("Main UI structure setup complete.")
        self.apply_theme_globally() 
        self.update_ui_texts() 


    def _apply_theme_to_tk_widget(self, widget, widget_type="tk.Text"):
        if not widget or not widget.winfo_exists():
            logger.debug("_apply_theme_to_tk_widget: Widget '%s' does not exist.", widget_type)
            return

        is_enabled = widget.cget('state') == tk.NORMAL
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
        except tk.TclError as e:
            logger.warning("TclError applying theme to %s (%s): %s", widget_type, widget, e, exc_info=False)

    def apply_theme_globally(self, language_changed=False):
        if self.app.root_destroyed: return
        logger.info("Applying global theme. Current: %s. Lang changed: %s", settings.CURRENT_THEME, language_changed)

        bg = settings.get_theme_color('app_bg'); fg = settings.get_theme_color('app_fg')
        entry_bg = settings.get_theme_color('entry_bg'); select_bg = settings.get_theme_color('entry_select_bg')
        select_fg = settings.get_theme_color('entry_select_fg'); 
        
        button_bg = settings.get_theme_color('button_bg')
        button_fg = settings.get_theme_color('button_fg')
        button_active_bg = settings.get_theme_color('button_active_bg')
        
        exit_button_bg = settings.get_theme_color('button_exit_bg')
        exit_button_fg = settings.get_theme_color('button_exit_fg')
        exit_button_active_bg = settings.get_theme_color('button_exit_active_bg') # Get this from settings too
        
        disabled_fg = settings.get_theme_color('disabled_fg'); frame_bg = settings.get_theme_color('frame_bg')
        scale_trough = settings.get_theme_color('scale_trough'); border_color = settings.get_theme_color('code_block_border')

        self.root.configure(background=bg)
        self.style.configure('.', background=bg, foreground=fg, fieldbackground=entry_bg, borderwidth=1)
        self.style.configure('App.TFrame', background=frame_bg)
        self.style.configure('App.TLabel', background=frame_bg, foreground=fg)
        
        # Standard Button Style
        self.style.configure('App.TButton', background=button_bg, foreground=button_fg, bordercolor=border_color, relief=tk.RAISED, lightcolor=button_bg, darkcolor=button_bg, focuscolor=fg)
        self.style.map('App.TButton', background=[('active', button_active_bg), ('pressed', button_active_bg), ('disabled', settings.get_theme_color('text_disabled_bg'))], foreground=[('disabled', disabled_fg)], relief=[('pressed', tk.SUNKEN), ('!pressed', tk.RAISED)])
        
        # Exit Button Style
        self.style.configure('Exit.TButton', background=exit_button_bg, foreground=exit_button_fg, bordercolor=border_color, relief=tk.RAISED, lightcolor=exit_button_bg, darkcolor=exit_button_bg, focuscolor=exit_button_fg)
        self.style.map('Exit.TButton', background=[('active', exit_button_active_bg), ('pressed', exit_button_active_bg), ('disabled', settings.get_theme_color('text_disabled_bg'))], foreground=[('disabled', disabled_fg)], relief=[('pressed', tk.SUNKEN), ('!pressed', tk.RAISED)])

        self.style.configure('App.TEntry', fieldbackground=entry_bg, foreground=settings.get_theme_color('entry_fg'), selectbackground=select_bg, selectforeground=select_fg, insertcolor=settings.get_theme_color('entry_fg'), bordercolor=border_color, lightcolor=entry_bg, darkcolor=entry_bg)
        self.style.configure('TScale', troughcolor=scale_trough, background=button_bg, sliderrelief=tk.RAISED, borderwidth=1, lightcolor=button_bg, darkcolor=button_bg)
        self.style.map('TScale', background=[('active', button_active_bg)])

        current_status_color_key = getattr(self.status_label, '_current_status_color_key', 'status_default_fg') if self.status_label else 'status_default_fg'
        status_fg_color = settings.get_theme_color(current_status_color_key)
        self.style.configure('Status.TLabel', background=frame_bg, foreground=status_fg_color)
        if self.status_label: self.status_label.configure(foreground=status_fg_color)

        if self.hotkeys_text_area: self._apply_theme_to_tk_widget(self.hotkeys_text_area)

        if self.response_window and self.response_window.winfo_exists():
            self.response_window.configure(background=bg)
            for child_frame in self.response_window.winfo_children():
                if isinstance(child_frame, ttk.Frame): child_frame.configure(style='App.TFrame')
            if self.response_text_widget: self._apply_theme_to_tk_widget(self.response_text_widget) 
            try:
                self.style.configure('Response.TScrollbar', troughcolor=settings.get_theme_color('scrollbar_trough'), background=settings.get_theme_color('scrollbar_bg'), arrowcolor=fg, bordercolor=border_color, relief=tk.FLAT)
                for child in self.response_text_widget.winfo_children():
                    if isinstance(child, ttk.Scrollbar): child.configure(style='Response.TScrollbar')
                    elif isinstance(child, tk.Scrollbar): child.config(background=settings.get_theme_color('scrollbar_bg'), troughcolor=settings.get_theme_color('scrollbar_trough'), activebackground=settings.get_theme_color('button_active_bg'))
            except (tk.TclError, AttributeError) as e: logger.warning("Minor issue theming scrollbars for response: %s", e, exc_info=False)
            if self.response_font_slider: self.response_font_slider.configure(style='TScale')
            if self.response_size_label: self.response_size_label.configure(style='App.TLabel')
            if self.response_copy_button: # And other buttons in response window
                for sibling in self.response_copy_button.master.winfo_children():
                    if isinstance(sibling, ttk.Button): sibling.configure(style='App.TButton') # Use App.TButton for response window buttons
            if self.response_text_widget and self.response_text_widget.winfo_exists():
                try:
                    current_text_content = self.response_text_widget.get("1.0", tk.END).strip()
                    if current_text_content: ui_utils.apply_formatting_tags(self.response_text_widget, current_text_content, self.current_response_font_size)
                except (tk.TclError, AttributeError) as e: logger.warning("Minor issue re-applying format tags: %s", e, exc_info=False)
        
        if language_changed: self.update_ui_texts()
        logger.debug("Global theme application finished in UIManager.")


    def update_ui_texts(self):
        if self.app.root_destroyed: return
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
            else:
                self.hotkeys_text_area.insert(tk.END, settings.T('hotkey_failed_status'))
            self.hotkeys_text_area.config(state=tk.DISABLED)

        if self.status_label: 
            current_text = self.status_label.cget("text")
            is_generic_or_change_msg = False
            generic_statuses = [settings.T(k, lang=lc) for k in ['initial_status_text', 'ready_status_text_no_tray', 'ready_status_text_tray'] for lc in settings.SUPPORTED_LANGUAGES.keys()]
            change_msg_templates = ['status_lang_changed_to', 'status_theme_changed_to']
            change_prefixes = [settings.T(tpl, lang=lc).split('{')[0] for tpl in change_msg_templates for lc in settings.SUPPORTED_LANGUAGES.keys() if settings.T(tpl, lang=lc).split('{')[0]]
            
            if current_text in generic_statuses or any(current_text.startswith(p) for p in change_prefixes if p):
                is_generic_or_change_msg = True

            if is_generic_or_change_msg and \
               not (hasattr(self.app, '_theme_just_changed') and self.app._theme_just_changed) and \
               not (hasattr(self.app, '_lang_just_changed') and self.app._lang_just_changed):
                ready_key = 'ready_status_text_tray' if self.app.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
                self.update_status(settings.T(ready_key), 'status_ready_fg')
            
            if hasattr(self.app, '_theme_just_changed'): del self.app._theme_just_changed
            if hasattr(self.app, '_lang_just_changed'): del self.app._lang_just_changed

        if self.action_buttons_frame and self.action_buttons_frame.winfo_exists():
            for widget in self.action_buttons_frame.winfo_children():
                widget.destroy()

            row, col = 0, 0 # col will always be 0 due to MAX_COLS = 1
            action_button_count = 0
            # Sort to try and keep custom prompt button consistently placed if desired, e.g., last
            sorted_actions = sorted(settings.HOTKEY_ACTIONS.items(), key=lambda item: item[0] == "custom_prompt_hotkey") 

            if settings.HOTKEY_ACTIONS:
                for action_name, details in sorted_actions: 
                    btn_text = details.get('description', action_name)
                    btn_prompt_source = details.get('prompt')

                    if not btn_prompt_source: 
                        logger.warning("Skipping button for action '%s' due to missing prompt.", action_name)
                        continue
                    
                    actual_prompt_for_button = btn_prompt_source 
                    
                    btn_command = partial(self.app._trigger_capture_from_ui, actual_prompt_for_button)
                    
                    button = ttk.Button(self.action_buttons_frame, text=btn_text, command=btn_command, style='App.TButton')
                    # Grid layout with single column
                    button.grid(row=row, column=0, sticky="ew", padx=2, pady=2)
                    action_button_count += 1
                    row += 1 # Increment row for next button
                
                # Configure column weights for the action_buttons_frame grid
                if action_button_count > 0: # Only configure if buttons exist
                     self.action_buttons_frame.grid_columnconfigure(0, weight=1)


        if self.exit_button:
            exit_key = 'exit_button_text_tray' if self.app.PYSTRAY_AVAILABLE else 'exit_button_text'
            self.exit_button.config(text=settings.T(exit_key))

        if self.response_window and self.response_window.winfo_exists():
            self.response_window.title(settings.T('response_window_title'))
            if self.response_size_label: self.response_size_label.config(text=settings.T('font_size_label_format').format(size=self.current_response_font_size))
            if self.response_copy_button:
                original_copy_text = settings.T('copy_button_text')
                copied_text_all_langs = [settings.T('copied_button_text', lang=lc) for lc in settings.SUPPORTED_LANGUAGES.keys()]
                if self.response_copy_button.cget('text') not in copied_text_all_langs:
                    self.response_copy_button.config(text=original_copy_text)
            if self.response_copy_button and self.response_copy_button.master:
                for widget in self.response_copy_button.master.winfo_children():
                    if isinstance(widget, ttk.Button) and widget != self.response_copy_button: # This is the Close button
                        widget.config(text=settings.T('close_button_text')); # It uses App.TButton style
                        break # Assuming only one other button (Close)
        logger.info("UI texts updated in UIManager.")

    def display_ollama_response(self, response_text):
        if self.app.root_destroyed: return
        logger.info("Displaying Ollama response. Length: %d", len(response_text or ""))
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
            height=settings.RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES
        )
        self._apply_theme_to_tk_widget(self.response_text_widget)
        try:
            self.style.configure('Response.TScrollbar', troughcolor=settings.get_theme_color('scrollbar_trough'), background=settings.get_theme_color('scrollbar_bg'), arrowcolor=settings.get_theme_color('app_fg'))
            for child in self.response_text_widget.winfo_children():
                if isinstance(child, ttk.Scrollbar): child.configure(style='Response.TScrollbar')
                elif isinstance(child, tk.Scrollbar): child.config(background=settings.get_theme_color('scrollbar_bg'), troughcolor=settings.get_theme_color('scrollbar_trough'), activebackground=settings.get_theme_color('button_active_bg'))
        except (tk.TclError, AttributeError) as e: logger.warning("Minor issue theming scrollbars for response: %s", e, exc_info=False)

        control_frame = ttk.Frame(self.response_window, style='App.TFrame')
        
        def update_font_size_display_themed(size_val_str):
            if self.app.root_destroyed: return
            try:
                new_size = int(float(size_val_str))
                if not (settings.MIN_FONT_SIZE <= new_size <= settings.MAX_FONT_SIZE): return
                self.current_response_font_size = new_size
                if self.response_size_label and self.response_size_label.winfo_exists():
                    self.response_size_label.config(text=settings.T('font_size_label_format').format(size=new_size))
                if self.response_text_widget and self.response_text_widget.winfo_exists(): 
                    base_font_obj = tkFont.Font(font=self.response_text_widget['font'])
                    base_font_obj.configure(size=new_size)
                    self.response_text_widget.configure(font=base_font_obj)
                    ui_utils.apply_formatting_tags(self.response_text_widget, response_text, new_size)
            except (ValueError, tk.TclError, AttributeError) as e:
                logger.warning("Error updating font size in response: %s", e, exc_info=False)

        self.response_font_slider = ttk.Scale(control_frame, from_=settings.MIN_FONT_SIZE, to=settings.MAX_FONT_SIZE, orient=tk.HORIZONTAL, value=self.current_response_font_size, command=update_font_size_display_themed, style='TScale')
        self.response_font_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, settings.PADDING_LARGE))
        self.response_size_label = ttk.Label(control_frame, text=settings.T('font_size_label_format').format(size=self.current_response_font_size), width=settings.FONT_SIZE_LABEL_WIDTH, style='App.TLabel')
        self.response_size_label.pack(side=tk.LEFT)

        button_frame_resp = ttk.Frame(self.response_window, style='App.TFrame')
        def copy_to_clipboard_command_themed():
            if self.app.root_destroyed or not (self.response_window and self.response_window.winfo_exists()): return
            raw_text_content = self.response_text_widget.get('1.0', tk.END).strip()
            try:
                self.response_window.clipboard_clear()
                self.response_window.clipboard_append(raw_text_content)
                if self.response_copy_button and self.response_copy_button.winfo_exists():
                    original_text = settings.T('copy_button_text'); copied_text = settings.T('copied_button_text')
                    self.response_copy_button.config(text=copied_text)
                    if self.response_window and self.response_window.winfo_exists():
                        self.response_window.after(settings.COPY_BUTTON_RESET_DELAY_MS, lambda: self.response_copy_button.config(text=original_text) if self.response_copy_button and self.response_copy_button.winfo_exists() else None)
            except tk.TclError as e:
                logger.error("TclError copying to clipboard: %s", e, exc_info=True)
                if not self.app.root_destroyed and self.response_window and self.response_window.winfo_exists():
                    messagebox.showerror(settings.T('dialog_internal_error_title'), f"{settings.T('unexpected_error_status')}: {e}", parent=self.response_window)

        self.response_copy_button = ttk.Button(button_frame_resp, text=settings.T('copy_button_text'), command=copy_to_clipboard_command_themed, style='App.TButton')
        self.response_copy_button.pack(side=tk.LEFT, padx=settings.PADDING_SMALL)
        close_button_resp = ttk.Button(button_frame_resp, text=settings.T('close_button_text'), style='App.TButton', command=lambda: self.response_window.destroy() if self.response_window and self.response_window.winfo_exists() else None)
        close_button_resp.pack(side=tk.RIGHT, padx=settings.PADDING_SMALL)

        self.response_window.update_idletasks()
        font_for_metrics = tkFont.Font(font=self.response_text_widget['font'])
        line_height_px = font_for_metrics.metrics("linespace")
        min_text_area_height_px = settings.RESPONSE_WINDOW_MIN_TEXT_AREA_HEIGHT_LINES * line_height_px
        min_total_height = int(min_text_area_height_px + settings.ESTIMATED_CONTROL_FRAME_HEIGHT_PX + settings.ESTIMATED_BUTTON_FRAME_HEIGHT_PX + settings.ESTIMATED_PADDING_PX * 3) 
        self.response_window.minsize(settings.RESPONSE_WINDOW_MIN_WIDTH, min_total_height)

        text_frame.pack(padx=settings.RESPONSE_TEXT_PADDING_X, pady=settings.RESPONSE_TEXT_PADDING_Y_TOP, fill=tk.BOTH, expand=True)
        self.response_text_widget.pack(fill=tk.BOTH, expand=True)
        control_frame.pack(padx=settings.RESPONSE_CONTROL_PADDING_X, pady=settings.RESPONSE_CONTROL_PADDING_Y, fill=tk.X)
        button_frame_resp.pack(pady=settings.RESPONSE_BUTTON_PADDING_Y, fill=tk.X, padx=settings.RESPONSE_BUTTON_PADDING_X)

        ui_utils.apply_formatting_tags(self.response_text_widget, response_text, self.current_response_font_size)

        if self.response_window and self.response_window.winfo_exists():
            self.response_window.transient(self.root); self.response_window.grab_set(); self.response_window.focus_force()
        
        self.update_status(settings.T('ready_status_text_tray' if self.app.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'), 'status_ready_fg')
        logger.debug("Ollama response window displayed.")

    def update_status(self, message, color_key='status_default_fg'):
        if self.app.root_destroyed: return
        def _update():
            if not self.app.root_destroyed and hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                color = settings.get_theme_color(color_key)
                self.status_label.config(text=message, foreground=color)
                setattr(self.status_label, '_current_status_color_key', color_key)
                self.style.configure('Status.TLabel', foreground=color, background=settings.get_theme_color('frame_bg'))
        if self.root and self.root.winfo_exists():
            self.root.after(0, _update)

    def hide_to_tray(self, event=None):
        if self.app.root_destroyed or not self.app.PYSTRAY_AVAILABLE: return
        logger.info("Hiding main window to system tray.")
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
            self._explicitly_hidden_to_tray = True 
            self.update_status(settings.T('window_hidden_status'), 'status_default_fg')
            if self.app.tray_manager: self.app.tray_manager.update_menu_if_visible()

    def show_window(self):
        if self.app.root_destroyed: return
        logger.info("Showing main window.")
        def _show():
            if not self.app.root_destroyed and self.root and self.root.winfo_exists():
                 self.root.deiconify(); self.root.lift(); self.root.focus_force()
                 self._explicitly_hidden_to_tray = False
                 self.update_status(settings.T('window_restored_status'), 'status_default_fg')
                 if self.app.PYSTRAY_AVAILABLE and self.app.tray_manager:
                     self.app.tray_manager.update_menu_if_visible()
        if self.root and self.root.winfo_exists(): self.root.after(0, _show)

    def is_main_window_explicitly_hidden(self):
        return self._explicitly_hidden_to_tray

    def is_main_window_viewable(self):
        return self.root and self.root.winfo_exists() and self.root.winfo_viewable()

    def get_custom_prompt(self):
        return self.custom_prompt_var.get().strip()

    def destroy_response_window_if_exists(self):
        if self.response_window and self.response_window.winfo_exists():
            logger.debug("Destroying existing response window.")
            try:
                self.response_window.destroy()
            except tk.TclError:
                logger.warning("TclError destroying response window, likely already gone.")
            self.response_window = None