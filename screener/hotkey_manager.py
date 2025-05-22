# hotkey_manager.py
import logging
import threading
from functools import partial
from pynput import keyboard
from tkinter import messagebox

import screener.settings as settings

logger = logging.getLogger(__name__)

class HotkeyManager:
    def __init__(self, app):
        self.app = app  # Reference to the main ScreenerApp instance
        self.hotkey_listener = None
        self.listener_thread = None

    def start_listener(self):
        if self.app.root_destroyed: return
        logger.info("Attempting to start hotkey listener...")
        self.stop_listener() # Ensure any previous listener is stopped

        hotkey_map = {}
        try:
            if not settings.HOTKEY_ACTIONS:
                logger.error("Cannot start hotkey listener: No hotkey actions loaded.")
                self.app.ui_manager.update_status(f"{settings.T('hotkey_failed_status')}: No hotkeys loaded.", 'status_error_fg')
                return

            for action_name, details in settings.HOTKEY_ACTIONS.items():
                # Pass action_name or details['prompt'] to app.trigger_capture_by_hotkey
                # Using prompt directly is simpler here.
                hotkey_map[details['hotkey']] = partial(self.app.trigger_capture_from_hotkey, prompt_source=details['prompt'])
            
            if not hotkey_map:
                 logger.warning("No valid hotkeys found in configuration to map.")
                 self.app.ui_manager.update_status(f"{settings.T('hotkey_failed_status')}: No valid hotkeys configured.", 'status_error_fg')
                 return

            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            self.listener_thread = threading.Thread(target=self._run_listener_safe, daemon=True, name="HotkeyListenerThread")
            self.listener_thread.start()
            logger.info("Hotkey listener started successfully with %d hotkeys.", len(hotkey_map))
            # Status update should be handled by ScreenerApp after successful start
        except Exception as e: 
            error_msg_formatted = settings.T('dialog_hotkey_error_msg').format(error=e)
            logger.critical("Failed to start pynput hotkey listener.", exc_info=True)
            if self.app.ui_manager: self.app.ui_manager.update_status(settings.T('hotkey_failed_status'), 'status_error_fg')
            if not self.app.root_destroyed and self.app.root and self.app.root.winfo_exists():
                 self.app.root.after(0, messagebox.showerror, settings.T('dialog_hotkey_error_title'), error_msg_formatted, parent=self.app.root)


    def _run_listener_safe(self):
        try:
            if self.hotkey_listener:
                self.hotkey_listener.run()
        except Exception as e:
            # This might catch errors if the listener itself fails during run, e.g. on some platforms
            logger.error("Exception within hotkey listener run() method. Listener may have stopped.", exc_info=True)
            if self.app.ui_manager: self.app.ui_manager.update_status(f"{settings.T('hotkey_failed_status')}: Runtime error.", 'status_error_fg')
            # Attempt to show a dialog if UI is available
            if not self.app.root_destroyed and self.app.root and self.app.root.winfo_exists():
                error_msg_formatted = settings.T('dialog_hotkey_error_msg').format(error=e)
                self.app.root.after(0, messagebox.showerror, settings.T('dialog_hotkey_error_title'), error_msg_formatted, parent=self.app.root)

    def stop_listener(self):
        if self.hotkey_listener:
            logger.info("Stopping hotkey listener...")
            try:
                self.hotkey_listener.stop()
            except Exception as e:
                logger.error("Exception stopping pynput hotkey listener.", exc_info=True)
            self.hotkey_listener = None
        
        if self.listener_thread and self.listener_thread.is_alive():
            logger.debug("Joining hotkey listener thread...")
            self.listener_thread.join(timeout=settings.THREAD_JOIN_TIMEOUT_SECONDS) 
            if self.listener_thread.is_alive():
                logger.warning("Hotkey listener thread did not join in time.")
            self.listener_thread = None
        logger.info("Hotkey listener stopped.")