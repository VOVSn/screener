# screener/capture.py
import logging
import tkinter as tk
from tkinter import messagebox
import threading
import time
import pyautogui # For screenshots

# Initialize logger for this module
logger = logging.getLogger(__name__)

try:
    import screener.settings as settings
    T = settings.T 
    DIALOG_INTERNAL_ERROR_TITLE_KEY = 'dialog_internal_error_title'
    DIALOG_INTERNAL_ERROR_MSG_KEY = 'dialog_internal_error_msg'
    DIALOG_SCREENSHOT_ERROR_TITLE_KEY = 'dialog_screenshot_error_title'
except ImportError as e:
    try:
        fallback_logger = logging.getLogger("capture_fallback")
        fallback_logger.critical("FATAL ERROR: Could not import 'settings' in capture.py.", exc_info=True)
    except Exception: 
        print(f"FATAL ERROR (no logger): Could not import 'settings' in capture.py: {e}")
    def T_fallback(key, lang='en'): return f"<{key} (capture.py fallback)>"
    T = T_fallback
    DIALOG_INTERNAL_ERROR_TITLE_KEY = 'dialog_internal_error_title'
    DIALOG_INTERNAL_ERROR_MSG_KEY = 'dialog_internal_error_msg'
    DIALOG_SCREENSHOT_ERROR_TITLE_KEY = 'dialog_screenshot_error_title'
    class settings_overlay_fallback:
        OVERLAY_ALPHA = 0.4; OVERLAY_CURSOR = 'cross'; OVERLAY_BG_COLOR = 'gray'
        SELECTION_RECT_COLOR = 'red'; SELECTION_RECT_WIDTH = 2
        MIN_SELECTION_WIDTH = 10; MIN_SELECTION_HEIGHT = 10
        CAPTURE_DELAY = 0.2 
    settings = settings_overlay_fallback()
    logger.warning("capture.py: Using fallback settings due to import error.")
    try:
        root_err_cap = tk.Tk(); root_err_cap.withdraw()
        messagebox.showerror("Settings Error (capture.py)", f"Failed to load settings in capture.py:\n{e}")
        root_err_cap.destroy()
    except Exception as tk_err:
        logger.error("Failed to show fallback error dialog in capture.py: %s", tk_err, exc_info=False)


class ScreenshotCapturer:
    def __init__(self, app_instance):
        self.selection_window = None
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.app = app_instance 
        self.current_prompt = None
        self._capture_in_progress_lock = threading.Lock()
        self._escape_pressed_flag = threading.Event() 
        self.canvas = None # Store canvas reference
        logger.debug("ScreenshotCapturer initialized.")

    def _cleanup_overlay_windows(self):
        logger.debug("Cleaning up overlay windows...")
        if self.selection_window and self.selection_window.winfo_exists():
            try:
                self.selection_window.unbind('<Escape>')
                if self.canvas and self.canvas.winfo_exists(): # Check if canvas exists
                    self.canvas.unbind('<Escape>') # Unbind from canvas as well
                
                self.selection_window.grab_release() 
                self.selection_window.destroy()
                logger.debug("Selection window destroyed.")
            except tk.TclError as e:
                logger.warning("TclError destroying selection_window: %s (likely already destroyed or during unbind)", e, exc_info=False)
            finally:
                self.selection_window = None
                self.canvas = None # Clear canvas reference
        logger.debug("Overlay windows cleanup finished.")


    def capture_region(self, prompt: str):
        logger.info("Capture region initiated. Prompt: '%.50s...'", prompt)
        
        if not self._capture_in_progress_lock.acquire(blocking=False):
            logger.warning("Capture already in progress. New request for prompt '%.50s...' ignored.", prompt)
            return

        self._escape_pressed_flag.clear() 

        try: 
            self.current_prompt = prompt 

            if threading.current_thread() != threading.main_thread():
                logger.debug("capture_region called from non-main thread. Rescheduling with app.root.after().")
                if self.app and self.app.root and self.app.root.winfo_exists():
                    self.app.root.after(0, self.capture_region, prompt)
                else:
                    logger.warning("Cannot reschedule capture_region: main app or its root window is unavailable.")
                return 

            if not self.app.root or not self.app.root.winfo_exists():
                logger.error("Main application window does not exist. Cannot start capture.")
                return

            self._cleanup_overlay_windows() 
            self.reset_state() 
            self.current_prompt = prompt 

            try:
                logger.debug("Creating Toplevel selection window for overlay, parented to app.root.")
                self.selection_window = tk.Toplevel(self.app.root) 
                self.selection_window.attributes('-fullscreen', True)
                self.selection_window.attributes('-alpha', settings.OVERLAY_ALPHA)
                self.selection_window.attributes('-topmost', True) 
                self.selection_window.overrideredirect(True) 
                
                self.selection_window.update_idletasks() 

                self.canvas = tk.Canvas(self.selection_window, cursor=settings.OVERLAY_CURSOR, bg=settings.OVERLAY_BG_COLOR) # Use self.canvas
                self.canvas.pack(fill=tk.BOTH, expand=True)
                logger.debug("Overlay canvas created and packed.")

                try:
                    self.selection_window.grab_set()
                    logger.debug("Overlay grab_set successful.")
                except tk.TclError as e_grab:
                    logger.error("Failed to grab_set on selection_window: %s", e_grab, exc_info=True)
                
                try:
                    self.selection_window.focus_force() 
                    self.canvas.focus_set() 
                    logger.debug("Overlay focus_force/focus_set attempted.")
                except tk.TclError as e_focus:
                    logger.warning("Failed to focus_force/focus_set on overlay: %s", e_focus, exc_info=False)


                def on_button_press(event):
                    if self._escape_pressed_flag.is_set(): return
                    logger.debug("Overlay: Mouse button pressed at screen (%s, %s), canvas (%s, %s)",
                                self.selection_window.winfo_pointerx(), self.selection_window.winfo_pointery(),
                                event.x, event.y)
                    self.start_x = self.selection_window.winfo_pointerx()
                    self.start_y = self.selection_window.winfo_pointery()
                    if self.rect_id and self.canvas and self.canvas.winfo_exists() : 
                        try: self.canvas.delete(self.rect_id)
                        except tk.TclError: pass 
                    if self.canvas and self.canvas.winfo_exists(): # Ensure canvas exists
                        self.rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                                            outline=settings.SELECTION_RECT_COLOR,
                                                            width=settings.SELECTION_RECT_WIDTH,
                                                            tags='selection_rectangle')

                def on_mouse_drag(event):
                    if self._escape_pressed_flag.is_set(): return
                    if self.rect_id is None or self.start_x is None: 
                        logger.warning("Overlay: Mouse drag event received but rect_id or start_x is None.")
                        return
                    if not self.canvas or not self.canvas.winfo_exists() or not self.selection_window or not self.selection_window.winfo_exists(): return

                    start_canvas_x = self.start_x - self.selection_window.winfo_rootx()
                    start_canvas_y = self.start_y - self.selection_window.winfo_rooty()
                    cur_canvas_x, cur_canvas_y = event.x, event.y
                    try:
                        self.canvas.coords(self.rect_id, start_canvas_x, start_canvas_y, cur_canvas_x, cur_canvas_y)
                    except tk.TclError: 
                        logger.warning("TclError during canvas.coords in on_mouse_drag.")


                def on_button_release(event):
                    if self._escape_pressed_flag.is_set():
                        logger.debug("Button release ignored due to escape flag.")
                        return

                    logger.debug("Overlay: Mouse button released.")
                    if not self.selection_window or not self.selection_window.winfo_exists():
                        logger.warning("Overlay: Button release but selection_window is gone. Aborting capture.")
                        self.reset_state() 
                        return

                    if self.start_x is None or self.start_y is None or self.rect_id is None:
                        logger.info("Overlay: Button release without a valid start selection. Cancelling via _handle_cancel_capture_from_event().")
                        if not self._escape_pressed_flag.is_set(): 
                             _handle_cancel_capture_from_event() # Pass no event
                        return

                    end_x = self.selection_window.winfo_pointerx()
                    end_y = self.selection_window.winfo_pointery()
                    logger.debug("Selection rect finalized: Screen Start(%s,%s), Screen End(%s,%s)",
                                self.start_x, self.start_y, end_x, end_y)

                    x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
                    x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
                    width, height = x2 - x1, y2 - y1

                    prompt_for_ollama = self.current_prompt
                    
                    self._cleanup_overlay_windows() 
                    
                    if width < 1 or height < 1: 
                        logger.info("Selected region is too small (width < 1 or height < 1). Capture cancelled.")
                        self.reset_state() 
                        if self.app and self.app.ui_manager and self.app.root and self.app.root.winfo_exists():
                            ready_key = 'ready_status_text_tray' if getattr(self.app, 'PYSTRAY_AVAILABLE', False) else 'ready_status_text_no_tray'
                            self.app.ui_manager.update_status(settings.T(ready_key), 'status_ready_fg')
                            self.app.ui_manager.show_window_after_action_if_hidden() # Show window
                        return
                    
                    region_to_capture = (x1, y1, width, height)
                    is_valid_size = (width >= settings.MIN_SELECTION_WIDTH and height >= settings.MIN_SELECTION_HEIGHT)

                    time.sleep(settings.CAPTURE_DELAY) 

                    if is_valid_size:
                        if prompt_for_ollama is None: 
                            logger.error("Internal error: Prompt for Ollama is None after selection.")
                            if self.app.root and self.app.root.winfo_exists():
                                self.app.root.after(0, messagebox.showerror,
                                                    T(DIALOG_INTERNAL_ERROR_TITLE_KEY),
                                                    T(DIALOG_INTERNAL_ERROR_MSG_KEY))
                            self.reset_state() 
                            if self.app and self.app.ui_manager: self.app.ui_manager.show_window_after_action_if_hidden() # Also show on error
                            return
                        
                        logger.info("Attempting to capture screenshot. Region: %s", region_to_capture)
                        try:
                            screenshot = pyautogui.screenshot(region=region_to_capture)
                            logger.info("Screenshot captured successfully. Size: %sx%s", screenshot.width, screenshot.height)
                            # Window showing is handled by process_screenshot_with_ollama
                            if self.app.root and self.app.root.winfo_exists():
                                self.app.root.after(0, self.app.process_screenshot_with_ollama, screenshot, prompt_for_ollama)
                            else:
                                logger.warning("Main app or root window unavailable to process screenshot.")
                        except Exception as e:
                            error_msg_detail = f"Failed to capture screenshot with PyAutoGUI: {e}"
                            logger.error("Screenshot capture error: %s", error_msg_detail, exc_info=True)
                            if self.app.root and self.app.root.winfo_exists():
                                self.app.root.after(0, messagebox.showerror,
                                                    T(DIALOG_SCREENSHOT_ERROR_TITLE_KEY),
                                                    error_msg_detail)
                            if self.app and self.app.ui_manager: self.app.ui_manager.show_window_after_action_if_hidden() # Also show on error
                    else: 
                        logger.info('Selection too small (w:%s, h:%s, min_w:%s, min_h:%s). Screenshot cancelled.',
                                    width, height, settings.MIN_SELECTION_WIDTH, settings.MIN_SELECTION_HEIGHT)
                        if self.app and self.app.ui_manager and self.app.root and self.app.root.winfo_exists():
                            ready_key = 'ready_status_text_tray' if getattr(self.app, 'PYSTRAY_AVAILABLE', False) else 'ready_status_text_no_tray'
                            self.app.ui_manager.update_status(settings.T(ready_key), 'status_ready_fg')
                            self.app.ui_manager.show_window_after_action_if_hidden() # Show window
                    
                    self.reset_state() 

                def _handle_cancel_capture_from_event(event=None):
                    if self._escape_pressed_flag.is_set():
                        logger.debug("Cancel event handling skipped, already escaping.")
                        return
                    
                    self._escape_pressed_flag.set() 

                    logger.info('Capture explicitly cancelled by user (e.g., Escape key or invalid click).')
                    self._cleanup_overlay_windows() 
                    self.reset_state()
                    if self.app and self.app.ui_manager and self.app.root and self.app.root.winfo_exists():
                        ready_key = 'ready_status_text_tray' if getattr(self.app, 'PYSTRAY_AVAILABLE', False) else 'ready_status_text_no_tray'
                        self.app.ui_manager.update_status(settings.T(ready_key), 'status_ready_fg')
                        self.app.ui_manager.show_window_after_action_if_hidden() # Show main window
                    
                    if event:
                        return "break"


                self.canvas.bind('<ButtonPress-1>', on_button_press)
                self.canvas.bind('<B1-Motion>', on_mouse_drag)
                self.canvas.bind('<ButtonRelease-1>', on_button_release)
                
                self.selection_window.bind('<Escape>', lambda e: _handle_cancel_capture_from_event(e))
                self.canvas.bind('<Escape>', lambda e: _handle_cancel_capture_from_event(e)) # Bind to canvas too
                
                logger.debug("Overlay Toplevel created. Awaiting user interaction via main app event loop.")

            except tk.TclError as e:
                logger.error("TclError during overlay setup: %s. Aborting capture.", e, exc_info=True)
                self._cleanup_overlay_windows(); self.reset_state()
                if self.app and self.app.ui_manager: self.app.ui_manager.show_window_after_action_if_hidden()

            except Exception as e:
                logger.error("Unexpected error during capture_region setup: %s. Aborting capture.", e, exc_info=True)
                self._cleanup_overlay_windows(); self.reset_state()
                if self.app and self.app.root and self.app.root.winfo_exists():
                    self.app.root.after(0, messagebox.showerror, T(DIALOG_INTERNAL_ERROR_TITLE_KEY), f"Error setting up capture: {e}")
                if self.app and self.app.ui_manager: self.app.ui_manager.show_window_after_action_if_hidden()
        
        finally:
            if self._escape_pressed_flag.is_set():
                logger.debug("Capture was cancelled by escape, ensuring lock is released.")
            self._capture_in_progress_lock.release() 

        logger.debug("Exiting capture_region method.")


    def reset_state(self):
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.current_prompt = None 
        logger.debug("ScreenshotCapturer internal state reset.")

if __name__ == '__main__':
    if not logging.getLogger().hasHandlers(): 
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Running capture.py standalone test...")
    class DummyApp:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("Dummy Main App Window (for Capture Test)")
            self.root.geometry("300x100")
            tk.Label(self.root, text="This is the main app. Overlay will appear on top.").pack(pady=20)
            self.PYSTRAY_AVAILABLE = False 
            class DummyUIManager:
                def update_status(self, message, color_key):
                    logger.info("DummyUIManager Status: [%s] %s", color_key, message)
                def show_window_after_action_if_hidden(self): # Mock this method
                    logger.info("DummyUIManager: show_window_after_action_if_hidden called")
                    if not self.is_main_window_viewable(): # Simulate showing
                         self.show_window()
                def is_main_window_viewable(self): # Mock
                    return True # Or make it reflect a dummy state
                def show_window(self): # Mock
                    logger.info("DummyUIManager: show_window called (simulated)")

            self.ui_manager = DummyUIManager()
        def process_screenshot_with_ollama(self, screenshot, prompt):
            logger.info("DummyApp: Received screenshot for prompt: '%s'", prompt)
            logger.info("Screenshot size: %sx%s", screenshot.width, screenshot.height)
            try:
                save_path = "test_capture.png"; screenshot.save(save_path)
                logger.info("Screenshot saved to %s", save_path)
            except Exception as e: logger.error("Error saving test screenshot: %s", e)
        def run(self):
            capturer = ScreenshotCapturer(self)
            tk.Button(self.root, text="Test Capture Overlay", 
                      command=lambda: capturer.capture_region("Test capture prompt from standalone test.")
            ).pack(pady=10)
            self.root.mainloop()
    dummy_app = DummyApp(); dummy_app.run()
    logger.info("capture.py standalone test finished.")