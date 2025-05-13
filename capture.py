# capture.py

import tkinter as tk
from tkinter import messagebox
import threading
import time

import pyautogui

# Local Imports (assuming capture.py is in the same directory)
try:
    import settings
    # Import specific dialog settings needed within this module
    from settings import (
        DIALOG_INTERNAL_ERROR_TITLE, DIALOG_INTERNAL_ERROR_MSG,
        DIALOG_SCREENSHOT_ERROR_TITLE
    )
except ImportError as e:
    # Provide a more specific error if settings are missing
    print(f"FATAL ERROR: Could not import settings in capture.py: {e}")
    # Attempt to show a basic Tkinter error if possible
    try:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Settings Error", f"Failed to load settings in capture.py:\n{e}")
        root.destroy()
    except Exception: pass
    exit()


class ScreenshotCapturer:
    """Handles the screen region selection overlay and capturing."""

    def __init__(self, app_instance):
        """
        Initializes the capturer.

        Args:
            app_instance: The main ScreenshotApp instance, needed for callbacks
                          and accessing the root window for scheduling tasks.
        """
        self.selection_window = None
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.capture_root = None # Temporary Tk root for the overlay
        self.app = app_instance # Reference to the main ScreenshotApp
        self.current_prompt = None # Store prompt for the current operation

    def capture_region(self, prompt):
        """Creates a fullscreen transparent window to select a region."""
        print(f"Creating selection window for prompt: '{prompt[:30]}...'")
        self.current_prompt = prompt

        # Ensure this runs on the main thread
        if threading.current_thread() != threading.main_thread():
            print('Error: Tried to create Tkinter window from non-main thread.')
            if self.app and self.app.root and self.app.root.winfo_exists():
                 # Schedule the call on the main thread via the app instance
                 self.app.root.after(0, self.capture_region, prompt)
            else:
                 print('Cannot schedule capture: App root not available.')
            return

        # Clean up any existing capture window first
        if self.capture_root and self.capture_root.winfo_exists():
            try: self.capture_root.destroy()
            except tk.TclError: pass
        self.reset_state()
        self.current_prompt = prompt # Set again after potential reset

        # Create a new temporary root for the overlay
        self.capture_root = tk.Tk()
        self.capture_root.withdraw() # Hide the standard root window

        # Create the overlay window
        self.selection_window = tk.Toplevel(self.capture_root)
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-alpha', settings.OVERLAY_ALPHA)
        self.selection_window.attributes('-topmost', True)
        self.selection_window.overrideredirect(True) # No window decorations
        self.selection_window.update_idletasks() # Ensure drawn before use

        canvas = tk.Canvas(
            self.selection_window,
            cursor=settings.OVERLAY_CURSOR,
            bg=settings.OVERLAY_BG_COLOR
        )
        canvas.pack(fill=tk.BOTH, expand=True)

        # --- Event Handlers (defined inside capture_region) ---
        def on_button_press(event):
            # Capture starting point relative to the screen
            self.start_x = self.selection_window.winfo_pointerx()
            self.start_y = self.selection_window.winfo_pointery()
            # Create rectangle starting at the click position *within the canvas*
            self.rect_id = canvas.create_rectangle(
                event.x, event.y, event.x, event.y, # Start with zero size
                outline=settings.SELECTION_RECT_COLOR,
                width=settings.SELECTION_RECT_WIDTH,
                tags='selection'
            )
            canvas.focus_set() # Ensure canvas has focus for Esc key

        def on_mouse_drag(event):
            if self.rect_id is None: return
            # Update rectangle coords based on starting screen pos and current event pos
            # Convert start screen coordinates to canvas coordinates
            start_canvas_x = self.start_x - self.selection_window.winfo_rootx()
            start_canvas_y = self.start_y - self.selection_window.winfo_rooty()
            # Current mouse position within the canvas is event.x, event.y
            cur_canvas_x, cur_canvas_y = event.x, event.y
            # Update the rectangle coordinates on the canvas
            canvas.coords(
                self.rect_id, start_canvas_x, start_canvas_y,
                cur_canvas_x, cur_canvas_y
            )

        def on_button_release(event):
            # Ensure capture wasn't cancelled prematurely
            if not self.capture_root or not self.capture_root.winfo_exists():
                print('Capture cancelled: Overlay window closed prematurely.')
                self.reset_state()
                return

            # If no drag occurred (start pos not set or same as end)
            if self.start_x is None or self.start_y is None:
                print('Selection cancelled (no area selected).')
                cancel_capture()
                return

            # Get final screen coordinates
            end_x = self.selection_window.winfo_pointerx()
            end_y = self.selection_window.winfo_pointery()

            # Calculate region based on screen coordinates
            x1 = min(self.start_x, end_x)
            y1 = min(self.start_y, end_y)
            x2 = max(self.start_x, end_x)
            y2 = max(self.start_y, end_y)
            width = x2 - x1
            height = y2 - y1

            # Prevent tiny selections causing issues
            if width < 1 or height < 1:
                print('Selection too small or invalid. Capture cancelled.')
                cancel_capture()
                return

            print(f'Selected region: ({x1}, {y1}) to ({x2}, {y2})'
                  f' - {width}x{height}')
            region_to_capture = (x1, y1, width, height)
            prompt_for_ollama = self.current_prompt

            # Store necessary info *before* destroying windows
            is_valid_size = (width >= settings.MIN_SELECTION_WIDTH and
                             height >= settings.MIN_SELECTION_HEIGHT)

            # --- Cleanup Overlay Windows ---
            # Use try-except blocks as windows might be destroyed by Esc key
            try:
                if self.selection_window and self.selection_window.winfo_exists():
                    self.selection_window.destroy()
            except tk.TclError as e:
                print(f'Minor error destroying selection window: {e}')
            finally:
                 self.selection_window = None

            try:
                 if self.capture_root and self.capture_root.winfo_exists():
                     self.capture_root.destroy()
            except tk.TclError as e:
                 print(f'Minor error destroying capture root: {e}')
            finally:
                 self.capture_root = None # Ensure it's cleared

            # Reset state *after* cleanup
            self.reset_state() # This also clears current_prompt

            # Delay slightly to ensure overlay is fully gone
            time.sleep(settings.CAPTURE_DELAY)

            # --- Process Capture ---
            if is_valid_size:
                if prompt_for_ollama is None:
                    print('Error: Prompt was lost before processing. Aborting.')
                    # Use app's root to schedule messagebox on main thread
                    if self.app.root and self.app.root.winfo_exists():
                        self.app.root.after(
                            0, messagebox.showerror,
                            DIALOG_INTERNAL_ERROR_TITLE, # Use imported setting
                            DIALOG_INTERNAL_ERROR_MSG   # Use imported setting
                        )
                    return
                try:
                    # Capture the screenshot
                    screenshot = pyautogui.screenshot(region=region_to_capture)
                    print('Screenshot captured. Processing...')
                    # Call the app's processing method via the main event loop
                    if self.app.root and self.app.root.winfo_exists():
                        self.app.root.after(
                            0, self.app.process_screenshot_with_ollama,
                            screenshot, prompt_for_ollama
                        )
                except Exception as e:
                    error_msg = f'Failed to capture screenshot: {e}'
                    print(f'Screenshot Error: {error_msg}')
                    # Use app's root to schedule messagebox on main thread
                    if self.app.root and self.app.root.winfo_exists():
                        self.app.root.after(
                            0, messagebox.showerror,
                            DIALOG_SCREENSHOT_ERROR_TITLE, error_msg # Use imported setting
                        )
            else:
                print('Selection too small. Screenshot cancelled.')


        def cancel_capture(event=None):
            """Cancels capture and cleans up overlay windows."""
            print('Capture cancelled by user.')
            try:
                if self.selection_window and self.selection_window.winfo_exists():
                    self.selection_window.destroy()
            except tk.TclError: pass
            try:
                if self.capture_root and self.capture_root.winfo_exists():
                    self.capture_root.destroy()
            except tk.TclError: pass
            self.reset_state()

        # Bind events
        canvas.bind('<ButtonPress-1>', on_button_press)
        canvas.bind('<B1-Motion>', on_mouse_drag)
        canvas.bind('<ButtonRelease-1>', on_button_release)
        # Bind Escape key to the selection_window itself for reliable cancellation
        self.selection_window.bind('<Escape>', cancel_capture)

        # Force focus onto the overlay
        self.selection_window.focus_force()
        canvas.focus_set()

        # Start the temporary event loop for the overlay
        # This loop blocks until the capture_root is destroyed
        if self.capture_root and self.capture_root.winfo_exists():
             self.capture_root.mainloop()
        else:
             # Should not happen if setup is correct, but handle defensively
             print('Capture setup failed, not running overlay mainloop.')
             self.reset_state()


    def reset_state(self):
        """Resets internal state variables after capture or cancellation."""
        self.selection_window = None # Ensure references are cleared
        self.capture_root = None
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.current_prompt = None # Crucial: Reset prompt