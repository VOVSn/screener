# screener/logging_config.py
import logging
import logging.handlers
import os
import sys

LOG_FILE_NAME = 'screener_app.log'
ERROR_LOG_FILE_NAME = 'screener_error.log'

def setup_logging(app_dir_path: str, level=logging.INFO):
    """
    Configures logging for the application.
    Args:
        app_dir_path (str): The directory where log files will be stored.
                            settings.py is responsible for ensuring this path is valid and writable.
        level: The minimum logging level for the root logger.
    """
    # For safety, check if the provided path exists, though settings.py should handle this.
    if not os.path.exists(app_dir_path):
        # This is an unexpected situation if settings.py worked correctly.
        # Fallback to current working directory as an absolute last resort.
        # This message will go to console only as handlers are not yet set up.
        original_path = app_dir_path
        app_dir_path = os.getcwd()
        print(f"CRITICAL FALLBACK: Log directory '{original_path}' provided to setup_logging does not exist. "
              f"Attempting to log to current directory '{app_dir_path}'. This may indicate an issue in settings.py path logic.")
        # Try to create the current working directory path if it somehow doesn't exist (highly unlikely for getcwd())
        if not os.path.exists(app_dir_path):
            try:
                os.makedirs(app_dir_path)
                print(f"INFO: Fallback log directory '{app_dir_path}' created.")
            except OSError as e:
                print(f"ERROR: Failed to create fallback log directory '{app_dir_path}': {e}. Logging may fail.")


    log_file_path = os.path.join(app_dir_path, LOG_FILE_NAME)
    error_log_file_path = os.path.join(app_dir_path, ERROR_LOG_FILE_NAME)

    # --- Root Logger Configuration ---
    root_logger = logging.getLogger()
    
    # Prevent duplicate handlers if setup_logging is called multiple times
    if root_logger.hasHandlers():
        # Assuming the first setup is correct and sufficient.
        # If re-configuration (e.g., changing log level dynamically) were needed,
        # you might clear existing handlers:
        # for handler in root_logger.handlers[:]:
        #     root_logger.removeHandler(handler)
        #     handler.close()
        # print("INFO: Logging re-initialized after clearing previous handlers.")
        print("INFO: setup_logging called again, but logging is already configured. Skipping reconfiguration.")
        return

    root_logger.setLevel(level) # Set the minimum level for the root logger

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
    )

    # --- Console Handler (optional, good for development, commented out for default) ---
    # console_handler = logging.StreamHandler(sys.stdout)
    # console_handler.setLevel(logging.DEBUG) # Show DEBUG and above in console during dev
    # console_handler.setFormatter(formatter)
    # root_logger.addHandler(console_handler)

    # --- File Handler (for general logs) ---
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8' # 5MB per file, 3 backups
        )
        file_handler.setLevel(logging.INFO) # Log INFO and above to the main log file
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # This message will go to console if file handler setup fails.
        print(f"ERROR: Failed to set up main log file handler at '{log_file_path}': {e}")


    # --- Error File Handler (for WARNING, ERROR, CRITICAL) ---
    try:
        error_file_handler = logging.handlers.RotatingFileHandler(
            error_log_file_path, maxBytes=2*1024*1024, backupCount=2, encoding='utf-8' # 2MB, 2 backups
        )
        error_file_handler.setLevel(logging.WARNING) # Log WARNING and above to a separate error file
        error_file_handler.setFormatter(formatter)
        root_logger.addHandler(error_file_handler)
    except Exception as e:
        # This message will go to console if error file handler setup fails.
        print(f"ERROR: Failed to set up error log file handler at '{error_log_file_path}': {e}")

    # This log message will now go to the configured handlers (if any were successful).
    # It's important this comes after handlers are added.
    if root_logger.hasHandlers():
        logging.info("Logging initialized. Main log: %s, Error log: %s", log_file_path, error_log_file_path)
        logging.info("Application logs are being written to directory: %s", app_dir_path)
    else:
        print(f"WARNING: Logging initialized, but no handlers could be configured. Log output may be lost. Target log directory: {app_dir_path}")


# --- Example usage within this file (for testing logging_config.py directly) ---
if __name__ == '__main__':
    # When running this script directly, setup basic logging
    # Determine a logs directory for direct testing
    # This will create 'screener/logs_test_standalone' if run from 'screener/'
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    test_log_dir = os.path.join(current_script_dir, 'logs_test_standalone')
    
    if not os.path.exists(test_log_dir):
        try:
            os.makedirs(test_log_dir)
            print(f"Created test log directory: {test_log_dir}")
        except OSError as e:
            print(f"Could not create {test_log_dir} for standalone test, using current script's directory. Error: {e}")
            test_log_dir = current_script_dir # Fallback to script's dir
    
    setup_logging(app_dir_path=test_log_dir, level=logging.DEBUG) # Pass the path for testing
    
    logging.debug("This is a debug message (standalone test).")
    logging.info("This is an info message (standalone test).")
    logging.warning("This is a warning message (standalone test).")
    logging.error("This is an error message (standalone test).")
    logging.critical("This is a critical message (standalone test).")

    # Test with a logger from another "module"
    test_logger = logging.getLogger("my_test_module")
    test_logger.info("Info message from test_logger (standalone test).")
    try:
        1/0
    except ZeroDivisionError:
        test_logger.error("Error from test_logger with exception info (standalone test):", exc_info=True)