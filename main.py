# main.py
import tkinter as tk
from tkinter import messagebox
import logging
import platform
import sys
import os
from PIL import Image

# REMOVE OR COMMENT OUT THIS ENTIRE if not logging.getLogger().hasHandlers(): BLOCK
# This was causing the logs_bootstrap issue and the "called again" message.
# settings.py will handle the primary logging setup.
# -------------------------------------------------------------------
# if not logging.getLogger().hasHandlers():
#     try:
#         # This assumes logging_config.py is in the same directory or on Python path
#         import logging_config as lc_main_bootstrap
#         # Determine a fallback log dir if settings.py hasn't run yet (less ideal)
#         bootstrap_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs_bootstrap')
#         if not os.path.exists(bootstrap_log_dir): os.makedirs(bootstrap_log_dir, exist_ok=True)
#         lc_main_bootstrap.setup_logging(app_dir_path=bootstrap_log_dir, level=logging.DEBUG)
#         logging.info("Basic logging configured by main.py bootstrap.")
#     except ImportError:
#         logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#         logging.info("Ultra-fallback basicConfig for logging used in main.py.")
#     except Exception as e_log_setup:
#         print(f"Error setting up logging in main.py bootstrap: {e_log_setup}")
# -------------------------------------------------------------------


# Now import modules that depend on logging being set up (especially settings)
# The import of settings will trigger its logging configuration.
import screener.settings as settings
from screener.screener_app import ScreenerApp # The main application class
from screener.tray_manager import PYSTRAY_AVAILABLE # Check if pystray loaded

logger = logging.getLogger(__name__) # Get logger for main.py

def run_app():
    # 1. Check for critical initialization errors from settings.py
    if hasattr(settings, '_initialization_errors') and settings._initialization_errors:
        logger.critical("Initialization errors from settings.py. Showing dialog and exiting.")
        error_title_key = 'dialog_settings_error_title'
        error_msg_template_key = 'dialog_hotkey_json_error_msg' # This key is generic enough
        try:
            title = settings.T(error_title_key)
            error_details_list = []
            for e_item_str in settings._initialization_errors:
                import re
                match = re.search(r"\((.*?)\):", e_item_str)
                file_hint = match.group(1) if match else "a configuration file"
                actual_error_msg = e_item_str.split(': ', 1)[-1] if ': ' in e_item_str else e_item_str
                error_details_list.append(f"- {file_hint}: {actual_error_msg}")
            error_details = "\n".join(error_details_list)
            # Using a more generic message if multiple file types can fail (hotkeys, ui_texts)
            message_body_key = 'dialog_critical_files_error_msg' # NEW KEY NEEDED IN UI_TEXTS.JSON
            if hasattr(settings, 'T') and callable(settings.T) and settings.T(message_body_key, lang='en') != f"<{message_body_key}>":
                 message = settings.T(message_body_key).format(details=error_details)
            else: # Fallback if T function or new key isn't ready/available
                message = f"Failed to load essential configuration or UI text files.\nDetails:\n{error_details}"

        except Exception as e_format:
            logger.error("Error formatting initialization error message for dialog.", exc_info=True)
            title = "Screener - Configuration Error"
            error_details = "\n".join([f"- {e_item}" for e_item in settings._initialization_errors])
            message = f"Failed to load essential configuration or UI text files.\nDetails:\n{error_details}"

        try:
            root_err_dialog = tk.Tk(); root_err_dialog.withdraw()
            messagebox.showerror(title, message, parent=root_err_dialog)
            root_err_dialog.destroy()
        except Exception as tk_popup_err: logger.error("Could not display init error dialog.", exc_info=True)
        return

    logger.info("-----------------------------------------------------------")
    logger.info("%s Starting...", settings.T('app_title'))
    logger.info('Platform: %s %s', platform.system(), platform.release())
    logger.info("Python version: %s", sys.version)
    logger.info("Ollama URL: %s, Model: %s", settings.OLLAMA_URL, settings.OLLAMA_MODEL)
    logger.info("App language: %s (%s)", settings.LANGUAGE, settings.SUPPORTED_LANGUAGES.get(settings.LANGUAGE, 'Unknown'))
    logger.info("App theme: %s", settings.CURRENT_THEME)
    logger.info("Icon path for tray: %s", settings.ICON_PATH)
    logger.info("Bundle Dir (_BUNDLE_DIR) (for resources): %s", settings._BUNDLE_DIR)
    logger.info("Project Root Dir (_PROJECT_ROOT_DIR) (for user data): %s", settings._PROJECT_ROOT_DIR) # CHANGED HERE
    logger.info("Pystray available: %s", PYSTRAY_AVAILABLE)
    logger.info("-----------------------------------------------------------")

    if PYSTRAY_AVAILABLE:
        icon_path_to_check = settings.ICON_PATH
        try:
            if not os.path.exists(icon_path_to_check):
                raise FileNotFoundError(f"Tray icon file not found: {icon_path_to_check}")
            with Image.open(icon_path_to_check) as img:
                pass # Check if it can be opened
            logger.debug("Tray icon '%s' seems valid.", icon_path_to_check)
        except FileNotFoundError:
            root_check = tk.Tk(); root_check.withdraw()
            proceed = messagebox.askokcancel(
                settings.T('dialog_icon_warning_title'),
                settings.T('dialog_icon_warning_msg').format(path=icon_path_to_check), parent=root_check)
            root_check.destroy()
            if not proceed: logger.info("User exited due to missing tray icon."); return
            logger.info("User acknowledged missing tray icon. Default will be used by TrayManager.")
        except Exception as e: # Catch other PIL errors too
            root_check = tk.Tk(); root_check.withdraw()
            proceed = messagebox.askokcancel(
                settings.T('dialog_icon_error_title'),
                settings.T('dialog_icon_error_msg').format(path=icon_path_to_check, error=e), parent=root_check)
            root_check.destroy()
            if not proceed: logger.info("User exited due to tray icon error."); return
            logger.info("User acknowledged tray icon error. Default will be used by TrayManager.")

    try:
        app = ScreenerApp()
        app.run()
    except (ImportError, FileNotFoundError, ValueError) as e_bootstrap: # Catch common bootstrap issues
        # This is a super critical error, likely settings.py or core modules failed to load properly
        err_title_super_critical = "Screener - Critical Initialization Error"
        err_msg_super_critical = f"A critical error occurred during application startup, preventing essential modules or configurations from loading.\n\nError: {e_bootstrap}\n\nThe application cannot continue. Please check console output if available, or ensure all core Python files and JSON configurations are correctly placed and formatted."
        try:
            critical_startup_logger = logging.getLogger("screener_critical_startup")
            critical_startup_logger.critical("SUPER CRITICAL FAILURE: %s", err_msg_super_critical, exc_info=True)
        except Exception as log_ex:
            print(f"FALLBACK PRINT (logging failed): {err_title_super_critical}\nLogging error: {log_ex}")

        try:
            root_err_sc = tk.Tk(); root_err_sc.withdraw()
            messagebox.showerror(err_title_super_critical, err_msg_super_critical, parent=root_err_sc)
            root_err_sc.destroy()
        except Exception as tk_ex: # If Tkinter itself is the problem
            print(f"FALLBACK PRINT (Tkinter messagebox failed): {err_title_super_critical}\nTkinter error: {tk_ex}")
        sys.exit(1) # Critical failure, exit
    except Exception as e_unknown_critical: # Catch any other unexpected critical error during app.run()
        err_title_unknown_critical = "Screener - Unhandled Critical Error"
        err_msg_unknown_critical = f"An unhandled critical error occurred during application execution:\n\nError: {e_unknown_critical}\n\nThe application will now exit. Please report this error along with any logs."
        try:
            critical_startup_logger = logging.getLogger("screener_critical_startup")
            critical_startup_logger.critical("UNHANDLED CRITICAL FAILURE in app.run(): %s", err_msg_unknown_critical, exc_info=True)
        except Exception as log_ex:
            print(f"FALLBACK PRINT (logging failed): {err_title_unknown_critical}\nLogging error: {log_ex}")
        try:
            root_err_uc = tk.Tk(); root_err_uc.withdraw()
            messagebox.showerror(err_title_unknown_critical, err_msg_unknown_critical, parent=root_err_uc)
            root_err_uc.destroy()
        except Exception as tk_ex:
            print(f"FALLBACK PRINT (Tkinter messagebox failed): {err_title_unknown_critical}\nTkinter error: {tk_ex}")
        sys.exit(1)


if __name__ == '__main__':
    run_app()