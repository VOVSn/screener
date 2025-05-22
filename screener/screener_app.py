# screener/screener_app.py
import logging
import tkinter as tk
from tkinter import messagebox
import threading
import platform
import time # For short delays
import os
import sys
from functools import partial 

from PIL import Image

# Local Imports
import screener.settings as settings
# import screener.ollama_utils as ollama_utils # ollama_utils functions are imported directly below
from screener.ollama_utils import (
    OllamaError, OllamaConnectionError, OllamaTimeoutError, OllamaRequestError,
    check_ollama_connection, PING_SUCCESS, PING_CONN_ERROR, PING_TIMEOUT, 
    PING_HTTP_ERROR, PING_OTHER_ERROR, request_ollama_analysis # Add new PING constants and import request_ollama_analysis
)
from screener.capture import ScreenshotCapturer
from screener.ui_manager import UIManager
from screener.hotkey_manager import HotkeyManager
from screener.tray_manager import TrayManager, PYSTRAY_AVAILABLE as TRAY_AVAILABLE_FROM_MODULE

logger = logging.getLogger(__name__)

class ScreenerApp:
    PYSTRAY_AVAILABLE = TRAY_AVAILABLE_FROM_MODULE 

    def __init__(self):
        logger.info("Initializing ScreenerApp...")
        self.root = tk.Tk()
        
        self.capturer = ScreenshotCapturer(self) 
        self.running = True 
        self.root_destroyed = False
        
        self.ui_manager = UIManager(self, self.root)
        self.hotkey_manager = HotkeyManager(self)
        self.tray_manager = TrayManager(self) if self.PYSTRAY_AVAILABLE else None
        
        self._theme_just_changed = False 
        self._lang_just_changed = False
        self._last_ollama_response = None # ADDED: To store the last response text

        self.ui_manager.setup_main_ui() 
        logger.info("ScreenerApp initialized successfully.")

    # --- Add Ping Ollama methods ---
    def ping_ollama_service(self):
        if self.root_destroyed: return
        logger.info("Ping Ollama service requested from UI.")
        self.ui_manager.update_status(settings.T('pinging_ollama_status'), 'status_processing_fg')
        # Run the ping in a separate thread to avoid freezing the UI
        threading.Thread(target=self._ping_ollama_worker, daemon=True, name="OllamaPingWorkerThread").start()

    def _ping_ollama_worker(self):
        if self.root_destroyed: return
        logger.debug("Ollama ping worker thread started.")
        
        status_type, details = check_ollama_connection() # Call the new utility
        
        message = ""
        color_key = 'status_default_fg' # Default color

        if status_type == PING_SUCCESS:
            message = settings.T('ollama_reachable_status')
            color_key = 'status_ready_fg' # Greenish/Blueish for success
            logger.info("Ollama ping successful.")
        elif status_type == PING_CONN_ERROR:
            message = settings.T('ollama_unreachable_conn_error_status')
            color_key = 'status_error_fg' # Red for error
            logger.warning("Ollama ping failed: Connection error. Details: %s", details)
        elif status_type == PING_TIMEOUT:
            message = settings.T('ollama_unreachable_timeout_status')
            color_key = 'status_error_fg'
            logger.warning("Ollama ping failed: Timeout. Details: %s", details)
        elif status_type == PING_HTTP_ERROR:
            message = settings.T('ollama_unreachable_http_error_status').format(status_code=details)
            color_key = 'status_error_fg'
            logger.warning("Ollama ping failed: HTTP error. Status code: %s", details)
        elif status_type == PING_OTHER_ERROR:
            message = f"{settings.T('ollama_unreachable_other_error_status')}" # Simple message
            # Optionally, include details if they are user-friendly:
            # message = f"{settings.T('ollama_unreachable_other_error_status')} ({details})"
            color_key = 'status_error_fg'
            logger.warning("Ollama ping failed: Other error. Details: %s", details)
        
        # Schedule UI update on the main thread
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            self.root.after(0, self.ui_manager.update_status, message, color_key)
        
        logger.debug("Ollama ping worker thread finished.")

    def _get_prompt_for_action(self, prompt_source):
        if self.root_destroyed: return None
        if prompt_source == settings.CUSTOM_PROMPT_IDENTIFIER:
            custom_prompt = self.ui_manager.get_custom_prompt()
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
        self.trigger_capture(prompt_source)

    def trigger_capture_from_hotkey(self, prompt_source):
        if self.root_destroyed: return
        logger.info("Capture triggered by hotkey.")
        self.trigger_capture(prompt_source)

    def trigger_capture_from_tray(self, prompt_source):
        if self.root_destroyed: return
        logger.info("Capture triggered from tray menu.")
        self.trigger_capture(prompt_source)

    def trigger_capture(self, prompt_source):
        if self.root_destroyed: return
        logger.info("Triggering capture. Prompt source type: %s", type(prompt_source).__name__)
        actual_prompt = self._get_prompt_for_action(prompt_source)
        
        if actual_prompt is None:
            logger.info("Capture aborted as actual_prompt is None.")
            ready_key = 'ready_status_text_tray' if self.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
            self.ui_manager.update_status(settings.T(ready_key), 'status_ready_fg')
            return
        
        if self.ui_manager.is_main_window_viewable():
            logger.debug("Main window is viewable. Withdrawing it before capture.")
            self.ui_manager.root.withdraw() 
            self.ui_manager._explicitly_hidden_to_tray = False 
            self.root.after(100, lambda: self.capturer.capture_region(actual_prompt))
        else:
            logger.debug("Main window not viewable. Initiating capture directly.")
            if threading.current_thread() != threading.main_thread():
                if self.root and self.root.winfo_exists():
                    self.root.after(0, self.capturer.capture_region, actual_prompt)
                else:
                    logger.warning("Cannot schedule capture_region: main app root is unavailable.")
            else:
                self.capturer.capture_region(actual_prompt)


    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str):
        if self.root_destroyed: return
        logger.info("Processing screenshot with Ollama. Prompt: '%.50s...'", prompt)

        if not self.ui_manager.is_main_window_viewable() and \
           not self.ui_manager.is_main_window_explicitly_hidden():
            logger.debug("Main window was hidden for capture; restoring it.")
            self.ui_manager.show_window()

        self.ui_manager.update_status(settings.T('processing_status_text'), 'status_processing_fg')
        threading.Thread(target=self._ollama_request_worker, args=(screenshot, prompt), daemon=True, name="OllamaWorkerThread").start()

    def _ollama_request_worker(self, screenshot: Image.Image, prompt: str):
        if self.root_destroyed: return
        logger.debug("Ollama worker thread started.")
        try:
            response_text = request_ollama_analysis(screenshot, prompt) # Use imported function
            logger.info("Ollama analysis successful. Response length: %d", len(response_text or ""))
            
            self._last_ollama_response = response_text # STORED
            
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                ready_key = 'ready_status_text_tray' if self.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
                self.root.after(0, self.ui_manager.update_status, settings.T(ready_key), 'status_ready_fg')
                self.root.after(0, self.ui_manager.display_ollama_response, response_text)
                self.root.after(0, self.ui_manager.enable_reopen_response_button) # Enable button

        except OllamaConnectionError as e:
            msg = f"{settings.T('ollama_conn_failed_status')}"
            logger.error("Ollama connection error: %s. URL: %s", e, settings.OLLAMA_URL, exc_info=False)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
                show_error_callable = partial(messagebox.showerror, 
                                              settings.T('dialog_ollama_conn_error_title'), 
                                              settings.T('dialog_ollama_conn_error_msg').format(url=settings.OLLAMA_URL), 
                                              parent=self.root)
                self.root.after(0, lambda: show_error_callable())
        except OllamaTimeoutError as e:
            msg = f"{settings.T('ollama_timeout_status')}"
            logger.error("Ollama request timed out: %s. URL: %s", e, settings.OLLAMA_URL, exc_info=False)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
                show_error_callable = partial(messagebox.showerror, 
                                              settings.T('dialog_ollama_timeout_title'), 
                                              settings.T('dialog_ollama_timeout_msg').format(url=settings.OLLAMA_URL), 
                                              parent=self.root)
                self.root.after(0, lambda: show_error_callable())
        except OllamaRequestError as e:
            msg = f"{settings.T('ollama_request_failed_status')}: {e.detail or e}"
            logger.error("Ollama request error. Status: %s, Detail: %s", e.status_code, e.detail, exc_info=False)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
                show_error_callable = partial(messagebox.showerror, 
                                              settings.T('dialog_ollama_error_title'), 
                                              f"{msg}\n(Status: {e.status_code})", 
                                              parent=self.root)
                self.root.after(0, lambda: show_error_callable())
        except OllamaError as e: 
            msg = f"{settings.T('ollama_request_failed_status')}: {e}"
            logger.error("Generic Ollama library error: %s", e, exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
                show_error_callable = partial(messagebox.showerror, 
                                              settings.T('dialog_ollama_error_title'), 
                                              msg, 
                                              parent=self.root)
                self.root.after(0, lambda: show_error_callable())
        except ValueError as e: 
            msg = f"{settings.T('error_preparing_image_status')}: {e}"
            logger.error("Value error during Ollama request prep: %s", e, exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
                show_error_callable = partial(messagebox.showerror, 
                                              settings.T('dialog_internal_error_title'), 
                                              msg, 
                                              parent=self.root)
                self.root.after(0, lambda: show_error_callable())
        except Exception as e:
            logger.critical("Unexpected error in Ollama worker thread.", exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, settings.T('unexpected_error_status'), 'status_error_fg')
                show_error_callable = partial(messagebox.showerror, 
                                              settings.T('dialog_unexpected_error_title'), 
                                              f"{settings.T('unexpected_error_status')}: {e}", 
                                              parent=self.root)
                self.root.after(0, lambda: show_error_callable())
        logger.debug("Ollama worker thread finished.")

    # ADDED: Method to handle re-opening the response
    def reopen_last_response_ui(self):
        if self.root_destroyed: return
        if self._last_ollama_response is not None:
            logger.info("Re-opening last Ollama response.")
            self.ui_manager.display_ollama_response(self._last_ollama_response)
        else:
            logger.info("No last Ollama response to re-open.")
            self.ui_manager.update_status(settings.T('no_response_to_reopen_status'), 'status_default_fg')


    def change_theme(self, theme_name, icon=None, item=None): 
        if self.root_destroyed: return
        logger.info("Changing theme to: %s", theme_name)
        if settings.set_theme(theme_name): 
            self._theme_just_changed = True 
            self.ui_manager.apply_theme_globally() 
            theme_name_localized = settings.T(f'tray_theme_{theme_name}_text')
            self.ui_manager.update_status(
                settings.T('status_theme_changed_to').format(theme_name=theme_name_localized),
                'status_ready_fg'
            )
            if self.tray_manager: self.tray_manager.update_menu_if_visible() 
        else:
            logger.warning("Failed to change theme to %s.", theme_name)


    def change_language(self, lang_code, icon=None, item=None): 
        if self.root_destroyed: return
        if settings.LANGUAGE == lang_code: 
            logger.debug("Language already set to %s.", lang_code); return
        
        logger.info("Changing language to: %s", lang_code)
        if settings.set_language(lang_code):
            self._lang_just_changed = True 
            self.hotkey_manager.start_listener() 
            self.ui_manager.apply_theme_globally(language_changed=True) 
            
            lang_name = settings.SUPPORTED_LANGUAGES.get(settings.LANGUAGE, settings.LANGUAGE)
            self.ui_manager.update_status(settings.T('status_lang_changed_to').format(lang_name=lang_name), 'status_ready_fg')
            
            if self.tray_manager: self.tray_manager.request_rebuild() 
        else:
            logger.error("Failed to change language to %s.", lang_code)
            self.ui_manager.update_status(f"Failed to change language to {lang_code}.", 'status_error_fg')


    def on_exit(self, icon=None, item=None, from_tray=False, is_wm_delete=False, _initiated_by_tray_thread=False):
        if not self.running: 
            logger.debug("on_exit called but app already exiting."); return
        
        self.running = False 
        source_description = "Button/Code"
        if from_tray: source_description = "Tray"
        if is_wm_delete: source_description = "WM_DELETE"
        if _initiated_by_tray_thread: source_description += " (tray thread initiated)"
        logger.info("Initiating application exit sequence. From: %s", source_description)
        
        if self.ui_manager and self.ui_manager.root and self.ui_manager.root.winfo_exists():
            self.ui_manager.update_status(settings.T('exiting_app_status'), 'status_default_fg')

        logger.info(settings.T('stopping_hotkeys_status'))
        if self.hotkey_manager: self.hotkey_manager.stop_listener()

        if self.PYSTRAY_AVAILABLE and self.tray_manager:
            logger.info(settings.T('stopping_tray_status'))
            if _initiated_by_tray_thread:
                logger.debug("on_exit: Tray shutdown was initiated by tray thread. Tray thread manages its own stop. Final join later.")
            else:
                self.tray_manager.stop_and_join_thread_blocking()
        
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            logger.debug("Scheduling root window destruction if not on main thread, else direct.")
            if threading.current_thread() == threading.main_thread():
                self._destroy_root_safely()
            else:
                if self.root and self.root.winfo_exists(): 
                    self.root.after(0, self._destroy_root_safely)
                else: 
                    self.root_destroyed = True
                    logger.debug("Root vanished before after(0, _destroy_root_safely) could be scheduled from non-main thread.")
        else:
            self.root_destroyed = True 
            logger.debug("Root already destroyed or never fully existed at on_exit call.")

    def _destroy_root_safely(self):
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            logger.info("Destroying Tkinter root window and any child windows...")
            try:
                if self.ui_manager: self.ui_manager.destroy_response_window_if_exists()
                
                if hasattr(self, 'capturer') and self.capturer and \
                   hasattr(self.capturer, 'selection_window') and \
                   self.capturer.selection_window and \
                   self.capturer.selection_window.winfo_exists():
                    logger.info("Capture overlay seems to be active during exit. Attempting to close it.")
                    self.capturer._cleanup_overlay_windows() 
                    self.capturer.reset_state()
                
                self.root.quit() 
                self.root.destroy() 
                logger.info("Tkinter root window destroyed successfully.")
            except tk.TclError as e: logger.warning("TclError during root destroy: %s (likely already gone)", e, exc_info=False)
            except Exception as e: logger.error("Unexpected error during root destroy.", exc_info=True)
        self.root_destroyed = True


    def run(self):
        if self.root_destroyed: 
            logger.warning("Run called on already destroyed app. Exiting."); return
        logger.info("ScreenerApp run method started.")
        
        self.hotkey_manager.start_listener()
        if self.tray_manager: self.tray_manager.setup_tray()
        
        status_msg_key = 'ready_status_text_tray' if self.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
        if self.ui_manager and self.ui_manager.root and self.ui_manager.root.winfo_exists(): 
            self.ui_manager.update_status(settings.T(status_msg_key), 'status_ready_fg')
        
        try:
            logger.info("Starting Tkinter mainloop...")
            self.root.mainloop()
            logger.info("Tkinter mainloop finished.") 
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received in mainloop, initiating exit.")
            if self.running : self.on_exit(is_wm_delete=True) 
        except Exception as e:
            logger.critical("Unhandled exception in Tkinter mainloop.", exc_info=True)
            if self.running : self.on_exit(is_wm_delete=True) 

        logger.info("Post-mainloop cleanup started.")
        if self.running: 
            logger.warning("Mainloop exited but app still marked running. Forcing on_exit.")
            self.on_exit(is_wm_delete=True, _initiated_by_tray_thread=False) 
        
        if self.hotkey_manager: 
            logger.debug("Post-mainloop: Ensuring hotkey listener is stopped.")
            self.hotkey_manager.stop_listener() 
        if self.tray_manager: 
            logger.debug("Post-mainloop: Ensuring tray manager is stopped and thread joined.")
            self.tray_manager.stop_and_join_thread_blocking()
        
        if not self.root_destroyed: 
            logger.debug("Post-mainloop: Ensuring root is destroyed.")
            self._destroy_root_safely()

        logger.info(settings.T('app_exit_complete_status'))
        logger.info(settings.T('app_finished_status'))