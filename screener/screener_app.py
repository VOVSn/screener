# screener/screener_app.py
import logging
import tkinter as tk
from tkinter import messagebox
import threading
import platform
import time 
import os
import sys
import json 
import random 
from datetime import datetime 
from functools import partial
from PIL import Image

# Local Imports
import screener.settings as settings
from screener.ollama_utils import (
    OllamaError, OllamaConnectionError, OllamaTimeoutError, OllamaRequestError,
    check_ollama_connection, PING_SUCCESS, PING_CONN_ERROR, PING_TIMEOUT,
    PING_HTTP_ERROR, PING_OTHER_ERROR, request_ollama_analysis
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
        
        self.current_screenshot_image: Image.Image | None = None
        self.initial_prompt_for_current_image: str | None = None
        self.conversation_history: list[dict] = [] 
        self.current_turn_index: int = -1 
        self.current_session_path: str | None = None 

        self.ui_manager.setup_main_ui()
        logger.info("ScreenerApp initialized successfully.")

    def _get_sessions_base_dir(self) -> str:
        return os.path.join(settings._PROJECT_ROOT_DIR, settings.CAPTURED_SESSIONS_DIR_NAME)

    def _generate_session_path(self) -> str:
        base_sessions_dir = self._get_sessions_base_dir()
        if not os.path.exists(base_sessions_dir):
            try:
                os.makedirs(base_sessions_dir, exist_ok=True)
                logger.info("Created base directory for captured sessions: %s", base_sessions_dir)
            except OSError as e:
                logger.error("Failed to create base sessions directory '%s': %s.", base_sessions_dir, e)
                return os.path.join(settings._PROJECT_ROOT_DIR, f"session_fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(100, 999)}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_id = random.randint(100, 999)
        session_name = f"{timestamp}_{random_id}"
        return os.path.join(base_sessions_dir, session_name)

    def _ensure_current_session_directory_exists(self):
        if self.current_session_path and not os.path.exists(self.current_session_path):
            try:
                os.makedirs(self.current_session_path, exist_ok=True)
                logger.info("Created directory for current session: %s", self.current_session_path)
            except OSError as e:
                logger.error("Failed to create current session directory '%s': %s.", self.current_session_path, e)
                return False
        elif not self.current_session_path: 
            logger.error("Cannot ensure session directory: current_session_path is None.")
            return False
        return True

    def save_current_conversation(self):
        if not self.current_session_path or not self.conversation_history:
            logger.debug("Cannot save: No active session path or history empty.")
            return
        if not self._ensure_current_session_directory_exists(): 
            logger.error("Conversation not saved: Session directory issue.")
            return
        conversation_data = {
            "initial_prompt": self.initial_prompt_for_current_image,
            "history": self.conversation_history
        }
        json_path = os.path.join(self.current_session_path, settings.CONVERSATION_FILENAME)
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=4, ensure_ascii=False)
            logger.info("Conversation saved to: %s", json_path)
        except Exception as e:
            logger.error("Failed to save conversation to '%s': %s", json_path, e, exc_info=True)

    def load_conversation_from_session(self, session_path: str) -> bool:
        logger.info("Attempting to load session from: %s", session_path)
        screenshot_path = os.path.join(session_path, settings.SCREENSHOT_FILENAME_IN_SESSION)
        json_path = os.path.join(session_path, settings.CONVERSATION_FILENAME)
        if not os.path.exists(screenshot_path) or not os.path.exists(json_path):
            logger.warning("Session load failed: Files missing in %s", session_path); return False
        try:
            self.current_screenshot_image = Image.open(screenshot_path)
            logger.debug("Loaded screenshot from: %s", screenshot_path)
            with open(json_path, 'r', encoding='utf-8') as f: conversation_data = json.load(f)
            self.initial_prompt_for_current_image = conversation_data.get("initial_prompt")
            self.conversation_history = conversation_data.get("history", [])
            if not self.conversation_history : logger.warning("Loaded conversation history is empty from %s", json_path)
            self.current_session_path = session_path
            self.current_turn_index = len(self.conversation_history) - 1 if self.conversation_history else -1
            logger.info("Session loaded. History turns: %d. Current turn: %d", len(self.conversation_history), self.current_turn_index)
            return True
        except Exception as e:
            logger.error("Failed to load session from '%s': %s", session_path, e, exc_info=True)
            self.current_screenshot_image = None; self.initial_prompt_for_current_image = None
            self.conversation_history = []; self.current_turn_index = -1; self.current_session_path = None
            return False

    def ping_ollama_service(self):
        if self.root_destroyed: return
        logger.info("Ping Ollama service requested from UI.")
        self.ui_manager.update_status(settings.T('pinging_ollama_status'), 'status_processing_fg')
        threading.Thread(target=self._ping_ollama_worker, daemon=True, name="OllamaPingWorkerThread").start()

    def _ping_ollama_worker(self):
        if self.root_destroyed: return; logger.debug("Ollama ping worker thread started.")
        status_type, details = check_ollama_connection(); message = ""; color_key = 'status_default_fg'
        if status_type == PING_SUCCESS: message = settings.T('ollama_reachable_status'); color_key = 'status_ready_fg'; logger.info("Ollama ping successful.")
        elif status_type == PING_CONN_ERROR: message = settings.T('ollama_unreachable_conn_error_status'); color_key = 'status_error_fg'; logger.warning("Ollama ping failed: Connection error. Details: %s", details)
        elif status_type == PING_TIMEOUT: message = settings.T('ollama_unreachable_timeout_status'); color_key = 'status_error_fg'; logger.warning("Ollama ping failed: Timeout. Details: %s", details)
        elif status_type == PING_HTTP_ERROR: message = settings.T('ollama_unreachable_http_error_status').format(status_code=details); color_key = 'status_error_fg'; logger.warning("Ollama ping failed: HTTP error. Status code: %s", details)
        elif status_type == PING_OTHER_ERROR: message = f"{settings.T('ollama_unreachable_other_error_status')}"; color_key = 'status_error_fg'; logger.warning("Ollama ping failed: Other error. Details: %s", details)
        if not self.root_destroyed and self.root and self.root.winfo_exists(): self.root.after(0, self.ui_manager.update_status, message, color_key)
        logger.debug("Ollama ping worker thread finished.")

    def _get_prompt_for_action(self, prompt_source):
        if self.root_destroyed: return None
        if prompt_source == settings.CUSTOM_PROMPT_IDENTIFIER:
            custom_prompt = self.ui_manager.get_custom_prompt()
            if not custom_prompt:
                logger.warning("Custom prompt action: field empty.")
                if self.root and self.root.winfo_exists(): messagebox.showwarning(settings.T('dialog_warning_title'), settings.T('custom_prompt_empty_warning'), parent=self.root)
                return None
            logger.debug("Using custom prompt: '%.50s...'", custom_prompt); return custom_prompt
        elif isinstance(prompt_source, str): logger.debug("Using pre-defined prompt: '%.50s...'", prompt_source); return prompt_source
        else:
            logger.error("Invalid prompt_source type: %s. Value: %s", type(prompt_source), prompt_source)
            if self.root and self.root.winfo_exists(): messagebox.showerror(settings.T('dialog_internal_error_title'), settings.T('dialog_internal_error_msg'), parent=self.root)
            return None

    def _trigger_capture_from_ui(self, prompt_source):
        if self.root_destroyed: return; logger.debug("Capture triggered from UI button.")
        self.trigger_capture(prompt_source)

    def trigger_capture_from_hotkey(self, prompt_source):
        if self.root_destroyed: return; logger.info("Capture triggered by hotkey.")
        self.trigger_capture(prompt_source)

    def trigger_capture_from_tray(self, prompt_source):
        if self.root_destroyed: return; logger.info("Capture triggered from tray menu.")
        self.trigger_capture(prompt_source)

    def trigger_capture(self, prompt_source):
        if self.root_destroyed: return
        logger.info("Triggering capture. Prompt source type: %s", type(prompt_source).__name__)
        actual_prompt = self._get_prompt_for_action(prompt_source)
        if actual_prompt is None:
            logger.info("Capture aborted: actual_prompt is None.")
            ready_key = 'ready_status_text_tray' if self.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
            self.ui_manager.update_status(settings.T(ready_key), 'status_ready_fg'); return

        self.current_screenshot_image = None 
        self.initial_prompt_for_current_image = actual_prompt 
        self.conversation_history = []; self.current_turn_index = -1
        self.current_session_path = None 
        logger.info("In-memory session state reset for new capture.")

        if self.ui_manager.is_main_window_viewable():
            logger.debug("Main window viewable. Withdrawing for capture.")
            self.ui_manager._hidden_by_capture_process = True # Set flag
            self.ui_manager.root.withdraw()
            self.root.after(100, lambda: self.capturer.capture_region(actual_prompt))
        else:
            self.ui_manager._hidden_by_capture_process = False # Ensure flag is false
            logger.debug("Main window not viewable. Initiating capture directly.")
            if threading.current_thread() != threading.main_thread():
                if self.root and self.root.winfo_exists(): self.root.after(0, self.capturer.capture_region, actual_prompt)
                else: logger.warning("Cannot schedule capture_region: main app root unavailable.")
            else: self.capturer.capture_region(actual_prompt)

    def process_screenshot_with_ollama(self, screenshot: Image.Image, prompt: str): 
        if self.root_destroyed: return
        logger.info("Processing screenshot with Ollama. Initial Prompt: '%.50s...'", prompt)

        self.current_screenshot_image = screenshot 
        self.current_session_path = self._generate_session_path() 
        
        if not self._ensure_current_session_directory_exists():
            logger.error("Failed to create session directory %s. Aborting.", self.current_session_path)
            self.ui_manager.update_status(settings.T('unexpected_error_status'), 'status_error_fg') 
            self.ui_manager._hidden_by_capture_process = False # Reset flag
            if not self.ui_manager.is_main_window_viewable() and not self.ui_manager.is_main_window_explicitly_hidden(): self.ui_manager.show_window()
            return
        screenshot_save_path = os.path.join(self.current_session_path, settings.SCREENSHOT_FILENAME_IN_SESSION)
        try:
            self.current_screenshot_image.save(screenshot_save_path, format=settings.SCREENSHOT_FORMAT)
            logger.info("Screenshot saved to session: %s", screenshot_save_path)
        except Exception as e_save:
            logger.error("Failed to save screenshot to '%s': %s. Aborting.", screenshot_save_path, e_save, exc_info=True)
            self.ui_manager.update_status(settings.T('unexpected_error_status'), 'status_error_fg') 
            self.ui_manager._hidden_by_capture_process = False # Reset flag
            if not self.ui_manager.is_main_window_viewable() and not self.ui_manager.is_main_window_explicitly_hidden(): self.ui_manager.show_window()
            return
        
        self.ui_manager._hidden_by_capture_process = False # Reset flag as processing proceeds

        if not self.ui_manager.is_main_window_viewable() and not self.ui_manager.is_main_window_explicitly_hidden():
            logger.debug("Main window hidden for capture; restoring it.")
            self.ui_manager.show_window() 

        self.ui_manager.update_status(settings.T('processing_status_text'), 'status_processing_fg')
        threading.Thread(target=self._ollama_initial_request_worker, args=(self.current_screenshot_image, self.initial_prompt_for_current_image), daemon=True, name="OllamaInitialWorkerThread").start()

    def _ollama_initial_request_worker(self, screenshot: Image.Image, initial_prompt: str): 
        if self.root_destroyed: return
        logger.debug("Ollama initial request worker thread started.")
        try:
            response_text = request_ollama_analysis(screenshot, initial_prompt)
            logger.info("Ollama initial analysis successful. Response length: %d", len(response_text or ""))
            if response_text is not None:
                initial_turn = {"ollama_response": response_text, "subsequent_user_question": None}
                self.conversation_history = [initial_turn]; self.current_turn_index = 0
                self.save_current_conversation() 
            else: self.conversation_history = []; self.current_turn_index = -1
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.display_ollama_response, self.current_screenshot_image)
                self.root.after(0, self.ui_manager.enable_reopen_response_button) 
        except OllamaConnectionError as e:
            msg = f"{settings.T('ollama_conn_failed_status')}"; logger.error("Ollama connection error: %s. URL: %s", e, settings.OLLAMA_URL, exc_info=False)
            if not self.root_destroyed and self.root and self.root.winfo_exists(): self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg'); self.root.after(0, lambda: messagebox.showerror(settings.T('dialog_ollama_conn_error_title'), settings.T('dialog_ollama_conn_error_msg').format(url=settings.OLLAMA_URL), parent=self.root))
        except OllamaTimeoutError as e:
            msg = f"{settings.T('ollama_timeout_status')}"; logger.error("Ollama request timed out: %s. URL: %s", e, settings.OLLAMA_URL, exc_info=False)
            if not self.root_destroyed and self.root and self.root.winfo_exists(): self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg'); self.root.after(0, lambda: messagebox.showerror(settings.T('dialog_ollama_timeout_title'), settings.T('dialog_ollama_timeout_msg').format(url=settings.OLLAMA_URL), parent=self.root))
        except OllamaRequestError as e:
            msg = f"{settings.T('ollama_request_failed_status')}: {e.detail or e}"; logger.error("Ollama request error. Status: %s, Detail: %s", e.status_code, e.detail, exc_info=False)
            if not self.root_destroyed and self.root and self.root.winfo_exists(): self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg'); self.root.after(0, lambda: messagebox.showerror(settings.T('dialog_ollama_error_title'), f"{msg}\n(Status: {e.status_code})", parent=self.root))
        except OllamaError as e:
            msg = f"{settings.T('ollama_request_failed_status')}: {e}"; logger.error("Generic Ollama library error: %s", e, exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists(): self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg'); self.root.after(0, lambda: messagebox.showerror(settings.T('dialog_ollama_error_title'), msg, parent=self.root))
        except ValueError as e: 
            msg = f"{settings.T('error_preparing_image_status')}: {e}"; logger.error("Value error during Ollama request prep: %s", e, exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists(): self.root.after(0, self.ui_manager.update_status, msg, 'status_error_fg'); self.root.after(0, lambda: messagebox.showerror(settings.T('dialog_internal_error_title'), msg, parent=self.root))
        except Exception as e:
            logger.critical("Unexpected error in Ollama initial request worker thread.", exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists(): self.root.after(0, self.ui_manager.update_status, settings.T('unexpected_error_status'), 'status_error_fg'); self.root.after(0, lambda: messagebox.showerror(settings.T('dialog_unexpected_error_title'), f"{settings.T('unexpected_error_status')}: {e}", parent=self.root))
        logger.debug("Ollama initial request worker thread finished.")

    def _build_composite_prompt(self, current_history_index: int, new_user_question: str) -> str:
        if not self.initial_prompt_for_current_image: logger.error("Cannot build composite prompt: initial_prompt missing."); return new_user_question 
        prompt_parts = [f"You were given an image with the initial system prompt: \"{self.initial_prompt_for_current_image}\""]
        for i in range(current_history_index + 1) : 
            turn = self.conversation_history[i]
            if i == 0 : prompt_parts.append(f"Your initial response to this was: \"{turn['ollama_response']}\"")
            else:
                previous_turn_question = self.conversation_history[i-1].get('subsequent_user_question', '[User question not recorded]')
                prompt_parts.append(f"Then the user asked: \"{previous_turn_question}\""); prompt_parts.append(f"And you responded: \"{turn['ollama_response']}\"")
        prompt_parts.append(f"Now the user asks: \"{new_user_question}\""); prompt_parts.append("Please provide the answer to this new question, considering the image and the entire conversation history provided.")
        composite = "\n\n".join(prompt_parts); logger.debug("Built composite prompt: %.200s...", composite); return composite

    def handle_follow_up_question(self, user_question: str):
        if self.root_destroyed or not self.current_screenshot_image or not self.conversation_history: logger.warning("Cannot handle follow-up: App state invalid."); return
        if not user_question.strip(): logger.info("Follow-up question empty, ignoring."); return
        logger.info("Handling follow-up question: '%.50s...'", user_question); self.ui_manager.update_status(settings.T('processing_status_text'), 'status_processing_fg')
        if self.current_turn_index < len(self.conversation_history) - 1:
            logger.info("Forking conversation. Truncating history from index %d.", self.current_turn_index + 1)
            self.conversation_history = self.conversation_history[:self.current_turn_index + 1]
        try: self.conversation_history[self.current_turn_index]["subsequent_user_question"] = user_question
        except IndexError: logger.error("Error updating subsequent_user_question: index %d out of bounds.", self.current_turn_index); self.ui_manager.update_status(settings.T('unexpected_error_status'), 'status_error_fg'); return
        composite_prompt = self._build_composite_prompt(self.current_turn_index, user_question)
        threading.Thread(target=self._ollama_follow_up_worker, args=(self.current_screenshot_image, composite_prompt, user_question), daemon=True, name="OllamaFollowUpWorkerThread").start()

    def _ollama_follow_up_worker(self, image: Image.Image, composite_prompt: str, original_user_question: str):
        if self.root_destroyed: return; logger.debug("Ollama follow-up worker thread started.")
        try:
            follow_up_response_text = request_ollama_analysis(image, composite_prompt)
            logger.info("Ollama follow-up analysis successful. Response length: %d", len(follow_up_response_text or ""))
            if follow_up_response_text is not None:
                new_turn = {"ollama_response": follow_up_response_text, "subsequent_user_question": None}
                self.conversation_history.append(new_turn); self.current_turn_index = len(self.conversation_history) - 1 
                self.save_current_conversation()
            else: logger.error("Follow-up response was None unexpectedly.")
            if not self.root_destroyed and self.root and self.root.winfo_exists(): self.root.after(0, self.ui_manager.update_response_display)
        except Exception as e: 
            logger.error("Error in Ollama follow-up worker: %s", e, exc_info=True)
            if not self.root_destroyed and self.root and self.root.winfo_exists():
                self.root.after(0, self.ui_manager.update_status, settings.T('ollama_request_failed_status'), 'status_error_fg')
                self.root.after(0, messagebox.showerror, settings.T('dialog_ollama_error_title'), f"{settings.T('ollama_request_failed_status')}: {e}", parent=self.root)
        logger.debug("Ollama follow-up worker thread finished.")

    def navigate_conversation(self, direction: str):
        if self.root_destroyed or not self.conversation_history: return
        if direction == "back":
            if self.current_turn_index > 0: self.current_turn_index -= 1; logger.debug("Navigated back. New turn index: %d", self.current_turn_index)
            else: logger.debug("Cannot navigate back: at beginning."); return 
        elif direction == "forward":
            if self.current_turn_index < len(self.conversation_history) - 1: self.current_turn_index += 1; logger.debug("Navigated forward. New turn index: %d", self.current_turn_index)
            else: logger.debug("Cannot navigate forward: at end."); return 
        if not self.root_destroyed and self.root and self.root.winfo_exists(): self.root.after(0, self.ui_manager.update_response_display)

    def reopen_last_response_ui(self):
        if self.root_destroyed: return; logger.info("Re-open last response requested.")
        sessions_base_dir = self._get_sessions_base_dir()
        if not os.path.exists(sessions_base_dir) or not os.listdir(sessions_base_dir):
            logger.info("No captured sessions found in %s.", sessions_base_dir)
            self.ui_manager.update_status(settings.T('no_sessions_found_status'), 'status_default_fg') 
            if self.root and self.root.winfo_exists(): messagebox.showinfo(settings.T('app_title'), settings.T('no_sessions_found_status'), parent=self.root)
            return
        try:
            session_folders = [os.path.join(sessions_base_dir, d) for d in os.listdir(sessions_base_dir) if os.path.isdir(os.path.join(sessions_base_dir, d))]
            if not session_folders: logger.info("No session subdirectories found in %s.", sessions_base_dir); self.ui_manager.update_status(settings.T('no_sessions_found_status'), 'status_default_fg'); return
            valid_session_folders = []
            for folder in session_folders:
                if os.path.exists(os.path.join(folder, settings.SCREENSHOT_FILENAME_IN_SESSION)) and os.path.exists(os.path.join(folder, settings.CONVERSATION_FILENAME)):
                    valid_session_folders.append(folder)
            if not valid_session_folders:
                logger.info("No valid (non-empty) session folders found.")
                self.ui_manager.update_status(settings.T('no_sessions_found_status'), 'status_default_fg')
                if self.root and self.root.winfo_exists(): messagebox.showinfo(settings.T('app_title'), settings.T('no_sessions_found_status'), parent=self.root)
                return
            latest_session_path = max(valid_session_folders, key=os.path.getmtime) 
            logger.debug("Latest valid session found: %s", latest_session_path)
            if self.load_conversation_from_session(latest_session_path):
                if self.current_screenshot_image and self.conversation_history:
                    logger.info("Successfully loaded last session. Displaying response window.")
                    self.ui_manager.display_ollama_response(self.current_screenshot_image)
                else: logger.warning("Session loaded, but image or history missing."); self.ui_manager.update_status(settings.T('error_reopening_session_status'), 'status_error_fg')
            else:
                logger.warning("Failed to load latest session from %s.", latest_session_path); self.ui_manager.update_status(settings.T('error_reopening_session_status'), 'status_error_fg')
                if self.root and self.root.winfo_exists(): messagebox.showerror(settings.T('app_title'), settings.T('error_reopening_session_status'), parent=self.root)
        except Exception as e_reopen:
            logger.error("Error during reopen_last_response_ui: %s", e_reopen, exc_info=True)
            self.ui_manager.update_status(settings.T('unexpected_error_status'), 'status_error_fg')

    def change_theme(self, theme_name, icon=None, item=None):
        if self.root_destroyed: return; logger.info("Changing theme to: %s", theme_name)
        if settings.set_theme(theme_name):
            self._theme_just_changed = True; self.ui_manager.apply_theme_globally()
            theme_name_localized = settings.T(f'tray_theme_{theme_name}_text')
            self.ui_manager.update_status(settings.T('status_theme_changed_to').format(theme_name=theme_name_localized), 'status_ready_fg')
            if self.tray_manager: self.tray_manager.update_menu_if_visible()
            if self.ui_manager.response_window and self.ui_manager.response_window.winfo_exists(): self.ui_manager.update_response_display() 
        else: logger.warning("Failed to change theme to %s.", theme_name)

    def change_language(self, lang_code, icon=None, item=None):
        if self.root_destroyed: return
        if settings.LANGUAGE == lang_code: logger.debug("Language already set to %s.", lang_code); return
        logger.info("Changing language to: %s", lang_code)
        if settings.set_language(lang_code): 
            self._lang_just_changed = True; self.hotkey_manager.start_listener(); self.ui_manager.apply_theme_globally(language_changed=True) 
            lang_name = settings.SUPPORTED_LANGUAGES.get(settings.LANGUAGE, settings.LANGUAGE)
            self.ui_manager.update_status(settings.T('status_lang_changed_to').format(lang_name=lang_name), 'status_ready_fg')
            if self.tray_manager: self.tray_manager.request_rebuild()
            if self.ui_manager.response_window and self.ui_manager.response_window.winfo_exists(): self.ui_manager.update_response_display() 
        else: logger.error("Failed to change language to %s.", lang_code); self.ui_manager.update_status(f"Failed to change language to {lang_code}.", 'status_error_fg')

    def on_exit(self, icon=None, item=None, from_tray=False, is_wm_delete=False, _initiated_by_tray_thread=False):
        if not self.running: logger.debug("on_exit called but app already exiting."); return
        self.running = False; source_description = "Button/Code"
        if from_tray: source_description = "Tray"; 
        if is_wm_delete: source_description = "WM_DELETE"
        if _initiated_by_tray_thread: source_description += " (tray thread initiated)"
        logger.info("Initiating application exit sequence. From: %s", source_description)
        if self.ui_manager and self.ui_manager.root and self.ui_manager.root.winfo_exists(): self.ui_manager.update_status(settings.T('exiting_app_status'), 'status_default_fg')
        logger.info(settings.T('stopping_hotkeys_status')); 
        if self.hotkey_manager: self.hotkey_manager.stop_listener()
        if self.PYSTRAY_AVAILABLE and self.tray_manager:
            logger.info(settings.T('stopping_tray_status'))
            if _initiated_by_tray_thread: logger.debug("on_exit: Tray shutdown by tray thread.")
            else: self.tray_manager.stop_and_join_thread_blocking()
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            logger.debug("Scheduling root window destruction."); 
            if threading.current_thread() == threading.main_thread(): self._destroy_root_safely()
            else: 
                if self.root and self.root.winfo_exists(): self.root.after(0, self._destroy_root_safely)
                else: self.root_destroyed = True; logger.debug("Root vanished before after(0, _destroy_root_safely).")
        else: self.root_destroyed = True; logger.debug("Root already destroyed or never fully existed at on_exit call.")

    def _destroy_root_safely(self):
        if not self.root_destroyed and self.root and self.root.winfo_exists():
            logger.info("Destroying Tkinter root window and any child windows...")
            try:
                if self.ui_manager: self.ui_manager.destroy_response_window_if_exists()
                if hasattr(self, 'capturer') and self.capturer and hasattr(self.capturer, 'selection_window') and self.capturer.selection_window and self.capturer.selection_window.winfo_exists():
                    logger.info("Capture overlay active during exit. Closing."); self.capturer._cleanup_overlay_windows(); self.capturer.reset_state()
                self.root.quit(); self.root.destroy(); logger.info("Tkinter root window destroyed successfully.")
            except tk.TclError as e: logger.warning("TclError during root destroy: %s", e, exc_info=False)
            except Exception as e: logger.error("Unexpected error during root destroy.", exc_info=True)
        self.root_destroyed = True

    def run(self):
        if self.root_destroyed: logger.warning("Run called on already destroyed app. Exiting."); return
        logger.info("ScreenerApp run method started."); self.hotkey_manager.start_listener()
        if self.tray_manager: self.tray_manager.setup_tray()
        status_msg_key = 'ready_status_text_tray' if self.PYSTRAY_AVAILABLE else 'ready_status_text_no_tray'
        if self.ui_manager and self.ui_manager.root and self.ui_manager.root.winfo_exists(): self.ui_manager.update_status(settings.T(status_msg_key), 'status_ready_fg')
        try:
            logger.info("Starting Tkinter mainloop..."); self.root.mainloop(); logger.info("Tkinter mainloop finished.") 
        except KeyboardInterrupt: logger.info("KeyboardInterrupt received, initiating exit.");
        except Exception as e: logger.critical("Unhandled exception in Tkinter mainloop.", exc_info=True)
        finally: 
            if self.running : self.on_exit(is_wm_delete=True) 
        logger.info("Post-mainloop cleanup started.")
        if self.running: logger.warning("Mainloop exited but app still marked running. Forcing on_exit."); self.on_exit(is_wm_delete=True, _initiated_by_tray_thread=False) 
        if self.hotkey_manager: logger.debug("Post-mainloop: Ensuring hotkey listener stopped."); self.hotkey_manager.stop_listener() 
        if self.tray_manager: logger.debug("Post-mainloop: Ensuring tray manager stopped."); self.tray_manager.stop_and_join_thread_blocking()
        if not self.root_destroyed: logger.debug("Post-mainloop: Ensuring root is destroyed."); self._destroy_root_safely()
        logger.info(settings.T('app_exit_complete_status')); logger.info(settings.T('app_finished_status'))