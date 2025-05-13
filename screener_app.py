# screener_app.py
import logging
import tkinter as tk
from tkinter import messagebox
import threading
import platform
import time # For short delays
import os
import sys

from PIL import Image

# Local Imports
import settings
import ollama_utils
from ollama_utils import (
    OllamaError, OllamaConnectionError, OllamaTimeoutError, OllamaRequestError
)
from capture import ScreenshotCapturer
from ui_manager import UIManager
from hotkey_manager import HotkeyManager
from tray_manager import TrayManager, PYSTRAY_AVAILABLE as TRAY_AVAILABLE_FROM_MODULE

logger = logging.getLogger(__name__)

class ScreenerApp:
    PYSTRAY_AVAILABLE = TRAY_AVAILABLE_FROM_MODULE # Make it an instance or class variable

    def __init__(self):
        logger.info("Initializing ScreenerApp...")
        self.root = tk.Tk()
        # settings.app_instance = self # No longer needed in settings.py

        self.capturer = ScreenshotCapturer(self) # Pass self (ScreenerApp instance)
        self.running = True 
        self.root_destroyed = False
        
        # Initialize Managers
        self.ui_manager = UIManager(self, self.root)
        self.hotkey_manager = HotkeyManager(self)
        self.tray_manager = TrayManager(self) if self.PYSTRAY_AVAILABLE else None
        
        self._theme_just_changed = False # Internal flags for UI update logic
        self._lang_just_changed = False

        self.ui_manager.setup_main_ui() # This will also call apply_theme and update_texts
        logger.info("ScreenerApp initialized successfully.")


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
        # This method is called by HotkeyManager
        if self.root_destroyed: return
        logger.info("Capture triggered by hotkey.")
        self.trigger_capture(prompt_source)

    def trigger_capture_from_tray(self, prompt_source):
        # This method is called by TrayManager
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
            # self.root.withdraw() # UIManager handles its own window state
            self.ui_manager.root.withdraw() # Or a dedicated hide_for_capture method in UIManager
            self.ui_manager._explicitly_hidden_to_tray = False # This hide is for capture
            # Short delay to ensure window is hidden
            self.root.after(100, lambda: self.capturer.capture_region(actual_prompt))
        else:
            logger.debug("Main window not viewable. Initiating capture directly.")
            self.capturer.capture_region(actual_prompt)


    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str):
        if self.root_destroyed: return
        logger.info("Processing screenshot with Ollama. Prompt: '%.50s...'", prompt)

        # Restore main window if it was hidden for capture, not by explicit user hide-to-tray
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
            response_text = ollama_utils.request_ollama_analysis(screenshot, prompt)
            logger.info("Ollama analysis successful. Response length: %d", len(response_text or ""))
            
            # Schedule UI updates on the main thread
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                ready_key = 'ready_status_text_tray' if self.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
                self.root.after(0, self.ui_manager.update_status, settings.T(ready_key), 'status_ready_fg')
                self.root.after(0, self.ui_manager.display_ollama_response, response_text)

        except OllamaConnectionError as e:
            msg = f"{settings.T('ollama_conn_failed_status')}"
            logger.error("Ollama connection error: %s. URL: %s", e, settings.OLLAMA_URL, exc_info=False)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
                self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_conn_error_title'), settings.T('dialog_ollama_conn_error_msg').format(url=settings.OLLAMA_URL))
        except OllamaTimeoutError as e:
            msg = f"{settings.T('ollama_timeout_status')}"
            logger.error("Ollama request timed out: %s. URL: %s", e, settings.OLLAMA_URL, exc_info=False)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
                self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_timeout_title'), settings.T('dialog_ollama_timeout_msg').format(url=settings.OLLAMA_URL))
        except OllamaRequestError as e:
            msg = f"{settings.T('ollama_request_failed_status')}: {e.detail or e}"
            logger.error("Ollama request error. Status: %s, Detail: %s", e.status_code, e.detail, exc_info=False)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
                self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_error_title'), f"{msg}\n(Status: {e.status_code})")
        except OllamaError as e: # Generic library error
            msg = f"{settings.T('ollama_request_failed_status')}: {e}"
            logger.error("Generic Ollama library error: %s", e, exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
                self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_error_title'), msg)
        except ValueError as e: # e.g., image encoding error
            msg = f"{settings.T('error_preparing_image_status')}: {e}"
            logger.error("Value error during Ollama request prep: %s", e, exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg')
        except Exception as e:
            logger.critical("Unexpected error in Ollama worker thread.", exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, settings.T('unexpected_error_status'), 'status_error_fg')
                self.root.after(0, messagebox.showerror, settings.T('dialog_unexpected_error_title'), f"{settings.T('unexpected_error_status')}: {e}")
        logger.debug("Ollama worker thread finished.")

    def change_theme(self, theme_name, icon=None, item=None): # Tray args optional
        if self.root_destroyed: return
        logger.info("Changing theme to: %s", theme_name)
        if settings.set_theme(theme_name): 
            self._theme_just_changed = True # Flag for UIManager text update logic
            self.ui_manager.apply_theme_globally() # Apply theme to all UI
            theme_name_localized = settings.T(f'tray_theme_{theme_name}_text')
            self.ui_manager.update_status(
                settings.T('status_theme_changed_to').format(theme_name=theme_name_localized),
                'status_ready_fg'
            )
            if self.tray_manager: self.tray_manager.update_menu_if_visible() # pystray handles radio checks
        else:
            logger.warning("Failed to change theme to %s.", theme_name)


    def change_language(self, lang_code, icon=None, item=None): # Tray args optional
        if self.root_destroyed: return
        if settings.LANGUAGE == lang_code: 
            logger.debug("Language already set to %s.", lang_code); return
        
        logger.info("Changing language to: %s", lang_code)
        if settings.set_language(lang_code):
            self._lang_just_changed = True # Flag for UIManager text update logic
            self.hotkey_manager.start_listener() # Prompts might have changed
            self.ui_manager.apply_theme_globally(language_changed=True) # This will call update_ui_texts
            
            lang_name = settings.SUPPORTED_LANGUAGES.get(settings.LANGUAGE, settings.LANGUAGE)
            self.ui_manager.update_status(settings.T('status_lang_changed_to').format(lang_name=lang_name), 'status_ready_fg')
            
            if self.tray_manager: self.tray_manager.request_rebuild() # Tray menu item texts change
        else:
            logger.error("Failed to change language to %s.", lang_code)
            self.ui_manager.update_status(f"Failed to change language to {lang_code}.", 'status_error_fg')


    def on_exit(self, icon=None, item=None, from_tray=False, is_wm_delete=False):
        if not self.running: 
            logger.debug("on_exit called but app already exiting."); return
        
        self.running = False 
        logger.info("Initiating application exit sequence. From: %s", 
                    "Tray" if from_tray else ("WM_DELETE" if is_wm_delete else "Button/Code"))
        
        if self.ui_manager: self.ui_manager.update_status(settings.T('exiting_app_status'), 'status_default_fg')

        logger.info(settings.T('stopping_hotkeys_status'))
        if self.hotkey_manager: self.hotkey_manager.stop_listener()

        if self.PYSTRAY_AVAILABLE and self.tray_manager:
            logger.info(settings.T('stopping_tray_status'))
            self.tray_manager.stop_tray()
        
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            logger.debug("Scheduling root window destruction.")
            # Ensure destroy is called from main thread
            if threading.current_thread() == threading.main_thread():
                self._destroy_root_safely()
            else:
                self.root.after(0, self._destroy_root_safely)
        else:
            # If root was already gone or never fully existed.
            self.root_destroyed = True 
            logger.debug("Root already destroyed or never fully existed at on_exit.")

    def _destroy_root_safely(self):
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            logger.info("Destroying Tkinter root window and any child windows...")
            try:
                if self.ui_manager: self.ui_manager.destroy_response_window_if_exists()
                self.root.destroy()
                logger.info("Tkinter root window destroyed successfully.")
            except tk.TclError as e: logger.warning("TclError during root destroy: %s", e, exc_info=False)
            except Exception as e: logger.error("Unexpected error during root destroy.", exc_info=True)
        self.root_destroyed = True


    def run(self):
        if self.root_destroyed: logger.warning("Run called on already destroyed app. Exiting."); return
        logger.info("ScreenerApp run method started.")
        
        self.hotkey_manager.start_listener()
        if self.tray_manager: self.tray_manager.setup_tray()
        
        status_msg_key = 'ready_status_text_tray' if self.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
        self.ui_manager.update_status(settings.T(status_msg_key), 'status_ready_fg')
        
        # Show main window initially unless configured otherwise (not implemented, but good place for it)
        # self.ui_manager.show_window() # If it starts hidden

        try:
            logger.info("Starting Tkinter mainloop...")
            self.root.mainloop()
            logger.info("Tkinter mainloop finished.")
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received in mainloop, initiating exit.")
            if self.running : self.on_exit()
        except Exception as e:
            logger.critical("Unhandled exception in Tkinter mainloop.", exc_info=True)
            if self.running : self.on_exit()

        # Post-mainloop cleanup
        logger.info("Post-mainloop cleanup started.")
        if self.running: # If mainloop exited without on_exit
            logger.warning("Mainloop exited but app still marked running. Forcing on_exit.")
            self.on_exit() 
        
        # Ensure threads are joined (on_exit should handle, but as safeguard)
        if self.hotkey_manager: self.hotkey_manager.stop_listener() 
        if self.tray_manager: self.tray_manager.stop_tray()
        
        if not self.root_destroyed: self._destroy_root_safely()

        logger.info(settings.T('app_exit_complete_status'))
        logger.info(settings.T('app_finished_status'))