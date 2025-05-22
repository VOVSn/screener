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
    # REMOVE THE FALLBACK LOGIC FOR app_dir_path.
    # settings.py is now solely responsible for ensuring app_dir_path is sensible.
    # If app_dir_path is bad, RotatingFileHandler will raise an error, which is an
    # acceptable way to indicate a setup problem.
    # ------------------------------------------------------------------------------------
    # if not os.path.exists(app_dir_path):
    #     original_path = app_dir_path
    #     app_dir_path = os.getcwd() # This was the problematic fallback
    #     print(f"CRITICAL FALLBACK: Log directory '{original_path}' provided to setup_logging does not exist. "
    #           f"Attempting to log to current directory '{app_dir_path}'. This may indicate an issue in settings.py path logic.")
    #     if not os.path.exists(app_dir_path):
    #         try:
    #             os.makedirs(app_dir_path)
    #             print(f"INFO: Fallback log directory '{app_dir_path}' created.")
    #         except OSError as e:
    #             print(f"ERROR: Failed to create fallback log directory '{app_dir_path}': {e}. Logging may fail.")
    # ------------------------------------------------------------------------------------

    log_file_path = os.path.join(app_dir_path, LOG_FILE_NAME)
    error_log_file_path = os.path.join(app_dir_path, ERROR_LOG_FILE_NAME)

    root_logger = logging.getLogger()
    
    if root_logger.hasHandlers():
        # This guard is now fine, as settings.py's call should be the first one
        # that successfully configures file handlers.
        print("INFO: setup_logging called again, but logging is already configured. Skipping reconfiguration.")
        return

    root_logger.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
    )

    # Console Handler (can be enabled for development if needed)
    # console_handler = logging.StreamHandler(sys.stdout)
    # console_handler.setLevel(logging.DEBUG) 
    # console_handler.setFormatter(formatter)
    # root_logger.addHandler(console_handler)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"ERROR: Failed to set up main log file handler at '{log_file_path}': {e}")

    try:
        error_file_handler = logging.handlers.RotatingFileHandler(
            error_log_file_path, maxBytes=2*1024*1024, backupCount=2, encoding='utf-8'
        )
        error_file_handler.setLevel(logging.WARNING)
        error_file_handler.setFormatter(formatter)
        root_logger.addHandler(error_file_handler)
    except Exception as e:
        print(f"ERROR: Failed to set up error log file handler at '{error_log_file_path}': {e}")

    if root_logger.hasHandlers():
        logging.info("Logging initialized. Main log: %s, Error log: %s", log_file_path, error_log_file_path)
        logging.info("Application logs are being written to directory: %s", app_dir_path)
    else:
        print(f"WARNING: Logging initialized, but no handlers could be configured. Log output may be lost. Target log directory: {app_dir_path}")


if __name__ == '__main__':
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    test_log_dir = os.path.join(current_script_dir, 'logs_test_standalone')
    
    if not os.path.exists(test_log_dir):
        try:
            os.makedirs(test_log_dir)
            print(f"Created test log directory: {test_log_dir}")
        except OSError as e:
            print(f"Could not create {test_log_dir} for standalone test, using current script's directory. Error: {e}")
            test_log_dir = current_script_dir
    
    setup_logging(app_dir_path=test_log_dir, level=logging.DEBUG)
    
    logging.debug("This is a debug message (standalone test).")
    logging.info("This is an info message (standalone test).")
    # ... (rest of the test code) ...
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