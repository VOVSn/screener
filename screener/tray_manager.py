# screener/tray_manager.py
import logging
import threading
from functools import partial
import os
from PIL import Image

import screener.settings as settings
import screener.ui_utils as ui_utils# For create_default_icon

# pystray import is optional, handle its absence
try:
    import pystray
    PYSTRAY_AVAILABLE = True
    logger_tray_init = logging.getLogger(__name__) # Use a logger before self.logger is set
    logger_tray_init.debug("pystray module loaded successfully by TrayManager.")
except ImportError:
    PYSTRAY_AVAILABLE = False
    logger_tray_init = logging.getLogger(__name__)
    logger_tray_init.info("pystray module not found. TrayManager will be inactive.")


logger = logging.getLogger(__name__)

class TrayManager:
    def __init__(self, app):
        self.app = app  # Reference to the main ScreenerApp instance
        self.tray_icon = None
        self.tray_thread = None
        self.icon_image = None
        self.is_rebuilding_tray = threading.Lock()
        self.PYSTRAY_AVAILABLE = PYSTRAY_AVAILABLE # Store local copy

        if self.PYSTRAY_AVAILABLE:
            self._load_icon_image()

    def _load_icon_image(self):
        if not self.PYSTRAY_AVAILABLE: return
        try:
            logger.debug("TrayManager: Attempting to load pystray icon from: %s", settings.ICON_PATH)
            if os.path.exists(settings.ICON_PATH):
                self.icon_image = Image.open(settings.ICON_PATH)
                logger.info("TrayManager: pystray icon loaded successfully from: %s", settings.ICON_PATH)
            else:
                logger.warning("TrayManager: pystray icon file not found at '%s'. Using default.", settings.ICON_PATH)
                self.icon_image = ui_utils.create_default_icon()
        except Exception as e:
            logger.error("TrayManager: Failed to load pystray icon: %s. Using default.", e, exc_info=True)
            self.icon_image = ui_utils.create_default_icon()
    
    def _build_menu(self):
        if self.app.root_destroyed or not self.PYSTRAY_AVAILABLE: return tuple()
        logger.debug("TrayManager: Building pystray menu.")
        
        lang_submenu_items = []
        for code, name in settings.SUPPORTED_LANGUAGES.items():
            action = partial(self.app.change_language, code) # Calls app's method
            item = pystray.MenuItem(name, action, checked=lambda item_param, current_code_param=code: settings.LANGUAGE == current_code_param, radio=True)
            lang_submenu_items.append(item)

        theme_submenu_items = [
            pystray.MenuItem(settings.T('tray_theme_light_text'), partial(self.app.change_theme, 'light'), checked=lambda item: settings.CURRENT_THEME == 'light', radio=True ),
            pystray.MenuItem(settings.T('tray_theme_dark_text'), partial(self.app.change_theme, 'dark'), checked=lambda item: settings.CURRENT_THEME == 'dark', radio=True )
        ]
        
        default_manual_action_details = settings.HOTKEY_ACTIONS.get(settings.DEFAULT_MANUAL_ACTION)
        tray_capture_prompt = settings.T('ollama_no_response_content') 
        if default_manual_action_details:
            tray_capture_prompt = default_manual_action_details['prompt']
            if tray_capture_prompt == settings.CUSTOM_PROMPT_IDENTIFIER: # Fallback for custom prompt in tray
                describe_action = settings.HOTKEY_ACTIONS.get('describe', {})
                tray_capture_prompt = describe_action.get('prompt', "Describe (tray fallback)")

        menu_items = [
            pystray.MenuItem(
                settings.T('tray_show_window_text'), 
                self.app.ui_manager.show_window, # Directly call UIManager's show
                default=True, 
                visible=lambda item: not self.app.root_destroyed and self.app.root and self.app.root.winfo_exists() and not self.app.ui_manager.is_main_window_viewable()
            ),
            pystray.MenuItem(
                settings.T('tray_capture_text'), 
                partial(self.app.trigger_capture_from_tray, prompt_source=tray_capture_prompt)
            ),
            pystray.MenuItem(settings.T('tray_language_text'), pystray.Menu(*lang_submenu_items)),
            pystray.MenuItem(settings.T('tray_theme_text'), pystray.Menu(*theme_submenu_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(settings.T('tray_exit_text'), self.request_app_exit_from_menu) # MODIFIED HERE
        ]
        return tuple(menu_items)

    def request_app_exit_from_menu(self, icon=None, item=None):
        """Called by the tray menu's exit action to initiate app shutdown."""
        if not self.PYSTRAY_AVAILABLE: return
        logger.info("TrayManager: Exit requested from tray menu action.")
        
        # Step 1: Stop the pystray icon. This is done from the pystray thread itself.
        # This allows the icon.run() loop to terminate cleanly.
        if self.tray_icon:
            self.tray_icon.stop()
            logger.debug("TrayManager: pystray icon.stop() called from menu action.")
        
        # Step 2: Schedule the main application's exit procedure on the Tkinter main thread.
        # This avoids deadlocks and ensures UI/app state changes are thread-safe.
        if self.app.root and self.app.root.winfo_exists():
            self.app.root.after(50, lambda: self.app.on_exit(from_tray=True, _initiated_by_tray_thread=True))
        else:
            logger.warning("TrayManager: Root window not found when scheduling app exit. Calling app.on_exit directly.")
            self.app.on_exit(from_tray=True, _initiated_by_tray_thread=True)

    def _rebuild_on_main_thread(self):
        if self.app.root_destroyed or not self.PYSTRAY_AVAILABLE: return
        if not self.is_rebuilding_tray.acquire(blocking=False):
            logger.info("TrayManager: Rebuild already in progress. Skipping.")
            return
        
        logger.info("TrayManager: Starting tray icon rebuild on main thread.")
        try:
            if self.tray_icon:
                logger.debug("TrayManager: Stopping old pystray instance...")
                self.tray_icon.stop()
            if self.tray_thread and self.tray_thread.is_alive():
                logger.debug("TrayManager: Joining old pystray thread...")
                self.tray_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS)
                if self.tray_thread.is_alive(): logger.warning("TrayManager: Old pystray thread didn't exit.")
            
            self.tray_icon = None
            self.tray_thread = None

            new_menu = self._build_menu()
            if not new_menu: 
                logger.warning("TrayManager: Menu could not be built during rebuild.")
                self.is_rebuilding_tray.release(); return

            if not self.icon_image: self._load_icon_image() # Ensure icon is loaded

            logger.debug("TrayManager: Creating new pystray.Icon instance.")
            self.tray_icon = pystray.Icon(settings.TRAY_ICON_NAME, self.icon_image, settings.T('app_title'), new_menu)
            
            self.tray_thread = threading.Thread(target=self._run_tray_safe, daemon=True, name="PystrayThread")
            self.tray_thread.start()
            logger.info("TrayManager: New pystray icon started.")
        except Exception as e: logger.error("TrayManager: Exception during tray rebuild.", exc_info=True)
        finally: self.is_rebuilding_tray.release()

    def _run_tray_safe(self):
        try:
            if self.tray_icon:
                self.tray_icon.run()
                logger.info("TrayManager: pystray icon.run() has exited.") # Log when it exits
        except Exception as e:
            logger.error("TrayManager: Exception during pystray icon run(). Tray may be non-functional.", exc_info=True)
            if not self.app.root_destroyed and self.app.root and self.app.root.winfo_exists():
                self.app.root.after(0, self.app.ui_manager.update_status, settings.T("icon_load_fail_status"), "status_error_fg")


    def request_rebuild(self):
        if self.app.root_destroyed or not self.PYSTRAY_AVAILABLE: return
        logger.debug("TrayManager: Requesting tray icon rebuild from main thread.")
        if self.app.root and self.app.root.winfo_exists():
            self.app.root.after(100, self._rebuild_on_main_thread)

    def setup_tray(self):
        if self.app.root_destroyed or not self.PYSTRAY_AVAILABLE:
            logger.info("TrayManager: Skipping tray setup (root destroyed or pystray unavailable).")
            return
        logger.info("TrayManager: Setting up system tray icon initially.")
        self._rebuild_on_main_thread() # This will start the tray_thread

    def stop_and_join_thread_blocking(self):
        """
        Stops the pystray icon and attempts to join its thread.
        This method should be called from a thread OTHER THAN the pystray thread itself (e.g., main thread).
        """
        if not self.PYSTRAY_AVAILABLE: return
        logger.info("TrayManager: Stopping system tray icon and joining thread (blocking call)...")
        
        if self.tray_icon:
            try:
                self.tray_icon.stop() 
                logger.debug("TrayManager: tray_icon.stop() called.")
            except Exception as e:
                logger.error("TrayManager: Error during tray_icon.stop().", exc_info=True)
        
        if self.tray_thread and self.tray_thread.is_alive():
            if threading.current_thread() == self.tray_thread:
                logger.warning("TrayManager: stop_and_join_thread_blocking called from tray_thread itself. Skipping join. Thread should exit due to icon.stop().")
            else:
                logger.debug("TrayManager: Attempting to join PystrayThread.")
                self.tray_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS)
                if self.tray_thread.is_alive():
                    logger.warning("TrayManager: Pystray thread did not exit cleanly after join attempt.")
                else:
                    logger.info("TrayManager: Pystray thread joined successfully.")
        elif self.tray_thread:
             logger.debug("TrayManager: Pystray thread was not alive before join attempt.")
        
        self.tray_icon = None 
        self.tray_thread = None
        logger.info("TrayManager: System tray icon resources considered released.")


    def update_menu_if_visible(self):
        """Requests pystray to update its menu if the icon is currently visible."""
        if self.PYSTRAY_AVAILABLE and self.tray_icon and hasattr(self.tray_icon, 'update_menu') and self.tray_icon.visible:
            logger.debug("TrayManager: Requesting pystray menu update.")
            self.tray_icon.update_menu()