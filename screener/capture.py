# capture.py
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
    
    # Keys for localized strings used in this module (fetched from settings.T)
    DIALOG_INTERNAL_ERROR_TITLE_KEY = 'dialog_internal_error_title'
    DIALOG_INTERNAL_ERROR_MSG_KEY = 'dialog_internal_error_msg'
    DIALOG_SCREENSHOT_ERROR_TITLE_KEY = 'dialog_screenshot_error_title'
except ImportError as e:
    # This fallback is for critical failure if settings itself cannot be imported.
    try:
        # Attempt to use the logger even in fallback, it might have been configured by a bootstrap.
        fallback_logger = logging.getLogger("capture_fallback")
        fallback_logger.critical("FATAL ERROR: Could not import 'settings' in capture.py.", exc_info=True)
    except Exception: # Logging itself might not be working
        print(f"FATAL ERROR (no logger): Could not import 'settings' in capture.py: {e}")

    # Fallback T function
    def T_fallback(key, lang='en'): return f"<{key} (capture.py fallback)>"
    T = T_fallback
    DIALOG_INTERNAL_ERROR_TITLE_KEY = 'dialog_internal_error_title'
    DIALOG_INTERNAL_ERROR_MSG_KEY = 'dialog_internal_error_msg'
    DIALOG_SCREENSHOT_ERROR_TITLE_KEY = 'dialog_screenshot_error_title'

    # Fallback settings for overlay if main settings failed
    class settings_overlay_fallback:
        OVERLAY_ALPHA = 0.4
        OVERLAY_CURSOR = 'cross'
        OVERLAY_BG_COLOR = 'gray'
        SELECTION_RECT_COLOR = 'red'
        SELECTION_RECT_WIDTH = 2
        MIN_SELECTION_WIDTH = 10
        MIN_SELECTION_HEIGHT = 10
        CAPTURE_DELAY = 0.2 # Seconds
    settings = settings_overlay_fallback()
    logger.warning("capture.py: Using fallback settings due to import error.")

    # Fallback messagebox (less likely to be needed if main app handles settings errors)
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
        self.capture_root = None # Temporary Tk() instance for the overlay
        self.app = app_instance # Reference to the main ScreenshotApp instance
        self.current_prompt = None
        logger.debug("ScreenshotCapturer initialized.")

    def _cleanup_overlay_windows(self):
        """Safely destroys overlay-related Tkinter windows."""
        logger.debug("Cleaning up overlay windows...")
        if self.selection_window and self.selection_window.winfo_exists():
            try:
                self.selection_window.destroy()
                logger.debug("Selection window destroyed.")
            except tk.TclError as e:
                logger.warning("TclError destroying selection_window: %s (likely already destroyed)", e, exc_info=False)
            finally:
                self.selection_window = None
        
        if self.capture_root and self.capture_root.winfo_exists():
            try:
                self.capture_root.destroy()
                logger.debug("Capture root (overlay Tk instance) destroyed.")
            except tk.TclError as e:
                logger.warning("TclError destroying capture_root: %s (likely already destroyed)", e, exc_info=False)
            finally:
                self.capture_root = None
        logger.debug("Overlay windows cleanup finished.")


    def capture_region(self, prompt: str):
        """
        Creates a full-screen overlay for the user to select a region.
        Once selected, captures the screenshot and passes it to the main app.
        """
        logger.info("Capture region initiated. Prompt: '%.50s...'", prompt)
        self.current_prompt = prompt

        if threading.current_thread() != threading.main_thread():
            logger.debug("capture_region called from non-main thread. Rescheduling with app.root.after().")
            if self.app and self.app.root and self.app.root.winfo_exists():
                 self.app.root.after(0, self.capture_region, prompt)
            else:
                logger.warning("Cannot reschedule capture_region: main app or its root window is unavailable.")
            return

        # Ensure any previous overlay is gone and state is reset
        self._cleanup_overlay_windows()
        self.reset_state() # Reset coordinates and prompt
        self.current_prompt = prompt # Set it again after reset

        try:
            logger.debug("Creating new Tk instance for capture overlay.")
            self.capture_root = tk.Tk()
            self.capture_root.withdraw() # Keep the root Tk window hidden

            logger.debug("Creating Toplevel selection window for overlay.")
            self.selection_window = tk.Toplevel(self.capture_root)
            self.selection_window.attributes('-fullscreen', True)
            self.selection_window.attributes('-alpha', settings.OVERLAY_ALPHA)
            self.selection_window.attributes('-topmost', True) # Ensure it's on top of other windows
            self.selection_window.overrideredirect(True) # No window decorations (title bar, borders)
            self.selection_window.update_idletasks() # Ensure attributes are applied

            canvas = tk.Canvas(self.selection_window, cursor=settings.OVERLAY_CURSOR, bg=settings.OVERLAY_BG_COLOR)
            canvas.pack(fill=tk.BOTH, expand=True)
            logger.debug("Overlay canvas created and packed.")

            def on_button_press(event):
                logger.debug("Overlay: Mouse button pressed at screen (%s, %s), canvas (%s, %s)",
                             self.selection_window.winfo_pointerx(), self.selection_window.winfo_pointery(),
                             event.x, event.y)
                # Use global screen coordinates for start_x, start_y
                self.start_x = self.selection_window.winfo_pointerx()
                self.start_y = self.selection_window.winfo_pointery()
                # Create rectangle using canvas coordinates (event.x, event.y)
                self.rect_id = canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                                     outline=settings.SELECTION_RECT_COLOR,
                                                     width=settings.SELECTION_RECT_WIDTH,
                                                     tags='selection_rectangle')
                canvas.focus_set() # Ensure canvas has focus for Escape key

            def on_mouse_drag(event):
                if self.rect_id is None or self.start_x is None: # Should not happen if press occurred
                    logger.warning("Overlay: Mouse drag event received but rect_id or start_x is None.")
                    return

                # start_x, start_y are screen coordinates.
                # event.x, event.y are canvas coordinates relative to the overlay window.
                # To draw on canvas, we need canvas coordinates for the start point as well.
                start_canvas_x = self.start_x - self.selection_window.winfo_rootx()
                start_canvas_y = self.start_y - self.selection_window.winfo_rooty()
                
                cur_canvas_x, cur_canvas_y = event.x, event.y
                canvas.coords(self.rect_id, start_canvas_x, start_canvas_y, cur_canvas_x, cur_canvas_y)
                # logger.debug("Overlay: Mouse dragged. Coords: (%s, %s) to (%s, %s)", start_canvas_x, start_canvas_y, cur_canvas_x, cur_canvas_y) # Too verbose

            def on_button_release(event):
                logger.debug("Overlay: Mouse button released.")
                if not self.capture_root or not self.capture_root.winfo_exists():
                    logger.warning("Overlay: Button release but capture_root is gone. Aborting capture.")
                    self.reset_state()
                    self._cleanup_overlay_windows()
                    return

                if self.start_x is None or self.start_y is None or self.rect_id is None:
                    logger.info("Overlay: Button release without a valid start selection (e.g., just a click). Cancelling.")
                    cancel_capture() # This will clean up windows and reset state
                    return

                # Use global screen coordinates for end_x, end_y
                end_x = self.selection_window.winfo_pointerx()
                end_y = self.selection_window.winfo_pointery()
                logger.debug("Selection rect finalized: Screen Start(%s,%s), Screen End(%s,%s)",
                             self.start_x, self.start_y, end_x, end_y)

                x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
                x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
                width, height = x2 - x1, y2 - y1

                # Preserve prompt before state reset
                prompt_for_ollama = self.current_prompt
                
                # Cleanup overlay windows *before* taking screenshot
                self._cleanup_overlay_windows()
                self.reset_state() # Resets current_prompt, so it must be preserved above

                if width < 1 or height < 1: # Should be caught by MIN_SELECTION_WIDTH/HEIGHT check mostly
                    logger.info("Selected region is too small (width < 1 or height < 1). Capture cancelled.")
                    # Windows already cleaned up by _cleanup_overlay_windows()
                    return
                
                region_to_capture = (x1, y1, width, height)
                is_valid_size = (width >= settings.MIN_SELECTION_WIDTH and height >= settings.MIN_SELECTION_HEIGHT)

                # Brief delay to ensure overlay is fully gone before screenshot
                time.sleep(settings.CAPTURE_DELAY)

                if is_valid_size:
                    if prompt_for_ollama is None: # Should not happen if logic is correct
                        logger.error("Internal error: Prompt for Ollama is None after selection.")
                        if self.app.root and self.app.root.winfo_exists():
                            self.app.root.after(0, messagebox.showerror,
                                                T(DIALOG_INTERNAL_ERROR_TITLE_KEY),
                                                T(DIALOG_INTERNAL_ERROR_MSG_KEY))
                        return
                    
                    logger.info("Attempting to capture screenshot. Region: %s", region_to_capture)
                    try:
                        screenshot = pyautogui.screenshot(region=region_to_capture)
                        logger.info("Screenshot captured successfully. Size: %sx%s", screenshot.width, screenshot.height)
                        if self.app.root and self.app.root.winfo_exists():
                            # Pass to main app for processing
                            self.app.root.after(0, self.app.process_screenshot_with_ollama, screenshot, prompt_for_ollama)
                        else:
                            logger.warning("Main app or root window unavailable to process screenshot.")
                    except Exception as e:
                        error_msg_detail = f"Failed to capture screenshot with PyAutoGUI: {e}"
                        logger.error("Screenshot capture error: %s", error_msg_detail, exc_info=True)
                        if self.app.root and self.app.root.winfo_exists():
                            self.app.root.after(0, messagebox.showerror,
                                                T(DIALOG_SCREENSHOT_ERROR_TITLE_KEY),
                                                error_msg_detail) # Show detailed error to user
                else:
                    logger.info('Selection too small (w:%s, h:%s, min_w:%s, min_h:%s). Screenshot cancelled.',
                                width, height, settings.MIN_SELECTION_WIDTH, settings.MIN_SELECTION_HEIGHT)
                    # Notify main app that capture was cancelled due to size, so it can reset status if needed.
                    if self.app and hasattr(self.app, 'update_status_safe') and self.app.root and self.app.root.winfo_exists():
                         ready_key = 'ready_status_text_tray' if getattr(self.app, 'PYSTRAY_AVAILABLE', False) else 'ready_status_text_no_tray'
                         self.app.update_status_safe(settings.T(ready_key), 'status_ready_fg')


            def cancel_capture(event=None): # event is passed if bound to Escape key
                logger.info('Capture explicitly cancelled by user (e.g., Escape key or invalid click).')
                self._cleanup_overlay_windows()
                self.reset_state()
                # Notify main app that capture was cancelled, so it can reset status if needed.
                if self.app and hasattr(self.app, 'update_status_safe') and self.app.root and self.app.root.winfo_exists():
                    ready_key = 'ready_status_text_tray' if getattr(self.app, 'PYSTRAY_AVAILABLE', False) else 'ready_status_text_no_tray'
                    self.app.update_status_safe(settings.T(ready_key), 'status_ready_fg')


            canvas.bind('<ButtonPress-1>', on_button_press)
            canvas.bind('<B1-Motion>', on_mouse_drag)
            canvas.bind('<ButtonRelease-1>', on_button_release)
            self.selection_window.bind('<Escape>', cancel_capture) # Bind Escape to cancel
            
            self.selection_window.focus_force() # Ensure overlay window has focus for Escape key
            canvas.focus_set() # Also set focus to canvas

            logger.debug("Starting mainloop for capture_root (overlay Tk instance).")
            self.capture_root.mainloop() # This blocks until the overlay is closed
            logger.debug("Mainloop for capture_root finished.")

        except tk.TclError as e:
            logger.error("TclError during overlay setup: %s. Aborting capture.", e, exc_info=True)
            self._cleanup_overlay_windows()
            self.reset_state()
        except Exception as e:
            logger.error("Unexpected error during capture_region setup: %s. Aborting capture.", e, exc_info=True)
            self._cleanup_overlay_windows()
            self.reset_state()
            # Optionally, show an error to the user via the main app if possible
            if self.app and self.app.root and self.app.root.winfo_exists():
                self.app.root.after(0, messagebox.showerror, T(DIALOG_INTERNAL_ERROR_TITLE_KEY), f"Error setting up capture: {e}")

        # Fallback cleanup if mainloop exits unexpectedly or an error occurs after windows created
        self._cleanup_overlay_windows()
        logger.debug("Exiting capture_region method.")


    def reset_state(self):
        """Resets the internal state of the capturer."""
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.current_prompt = None # Clear the prompt
        logger.debug("ScreenshotCapturer internal state reset.")

if __name__ == '__main__':
    # This is a basic test for the ScreenshotCapturer.
    # It requires a dummy main app class and manual interaction.
    if not logging.getLogger().hasHandlers(): # Setup basic logging if running standalone
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("Running capture.py standalone test...")

    class DummyApp:
        def __init__(self):
            self.root = tk.Tk()
            self.root.withdraw() # Hide main app window for this test
            self.PYSTRAY_AVAILABLE = False # Simulate no tray for status text

        def process_screenshot_with_ollama(self, screenshot, prompt):
            logger.info("DummyApp: Received screenshot for prompt: '%s'", prompt)
            logger.info("Screenshot size: %sx%s", screenshot.width, screenshot.height)
            # In a real app, you'd process it here. For test, just save it.
            try:
                save_path = "test_capture.png"
                screenshot.save(save_path)
                logger.info("Screenshot saved to %s", save_path)
            except Exception as e:
                logger.error("Error saving test screenshot: %s", e)
            self.root.quit() # End the test

        def update_status_safe(self, message, color_key): # Mock method
            logger.info("DummyApp Status: [%s] %s", color_key, message)

        def run(self):
            capturer = ScreenshotCapturer(self)
            # Simulate triggering capture after a short delay
            self.root.after(500, lambda: capturer.capture_region("Test capture prompt from standalone test."))
            self.root.mainloop()

    dummy_app = DummyApp()
    dummy_app.run()
    logger.info("capture.py standalone test finished.")