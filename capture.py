# capture.py

import tkinter as tk
from tkinter import messagebox
import threading
import time
import pyautogui

try:
    import settings
    T = settings.T 
    # Keys for localized strings used in this module
    DIALOG_INTERNAL_ERROR_TITLE_KEY = 'dialog_internal_error_title'
    DIALOG_INTERNAL_ERROR_MSG_KEY = 'dialog_internal_error_msg'
    DIALOG_SCREENSHOT_ERROR_TITLE_KEY = 'dialog_screenshot_error_title'
except ImportError as e:
    print(f"FATAL ERROR: Could not import settings in capture.py: {e}")
    # Fallback T function
    def T_fallback(key, lang='en'): return f"<{key} (fallback)>"
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
        CAPTURE_DELAY = 0.2
    settings = settings_overlay_fallback()

    try:
        root_err_cap = tk.Tk(); root_err_cap.withdraw()
        messagebox.showerror("Settings Error", f"Failed to load settings in capture.py:\n{e}")
        root_err_cap.destroy()
    except Exception: pass
    # Do not exit here if T is defined, allow partial functionality if possible
    # exit() # Reconsider exiting immediately


class ScreenshotCapturer:
    def __init__(self, app_instance):
        self.selection_window = None
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.capture_root = None 
        self.app = app_instance 
        self.current_prompt = None

    def capture_region(self, prompt):
        print(f"Creating selection window for prompt: '{prompt[:30]}...'")
        self.current_prompt = prompt

        if threading.current_thread() != threading.main_thread():
            if self.app and self.app.root and self.app.root.winfo_exists():
                 self.app.root.after(0, self.capture_region, prompt)
            return

        if self.capture_root and self.capture_root.winfo_exists():
            try: self.capture_root.destroy()
            except tk.TclError: pass
        self.reset_state()
        self.current_prompt = prompt

        self.capture_root = tk.Tk()
        self.capture_root.withdraw() 

        self.selection_window = tk.Toplevel(self.capture_root)
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-alpha', settings.OVERLAY_ALPHA)
        self.selection_window.attributes('-topmost', True)
        self.selection_window.overrideredirect(True) 
        self.selection_window.update_idletasks() 

        canvas = tk.Canvas(self.selection_window, cursor=settings.OVERLAY_CURSOR, bg=settings.OVERLAY_BG_COLOR)
        canvas.pack(fill=tk.BOTH, expand=True)

        def on_button_press(event):
            self.start_x = self.selection_window.winfo_pointerx()
            self.start_y = self.selection_window.winfo_pointery()
            self.rect_id = canvas.create_rectangle(event.x, event.y, event.x, event.y, 
                                                 outline=settings.SELECTION_RECT_COLOR, width=settings.SELECTION_RECT_WIDTH, tags='selection')
            canvas.focus_set()

        def on_mouse_drag(event):
            if self.rect_id is None: return
            start_canvas_x = self.start_x - self.selection_window.winfo_rootx()
            start_canvas_y = self.start_y - self.selection_window.winfo_rooty()
            cur_canvas_x, cur_canvas_y = event.x, event.y
            canvas.coords(self.rect_id, start_canvas_x, start_canvas_y, cur_canvas_x, cur_canvas_y)

        def on_button_release(event):
            if not self.capture_root or not self.capture_root.winfo_exists():
                self.reset_state(); return

            if self.start_x is None or self.start_y is None:
                cancel_capture(); return

            end_x = self.selection_window.winfo_pointerx()
            end_y = self.selection_window.winfo_pointery()
            x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
            x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
            width, height = x2 - x1, y2 - y1

            if width < 1 or height < 1:
                cancel_capture(); return
            
            region_to_capture = (x1, y1, width, height)
            prompt_for_ollama = self.current_prompt
            is_valid_size = (width >= settings.MIN_SELECTION_WIDTH and height >= settings.MIN_SELECTION_HEIGHT)

            try:
                if self.selection_window and self.selection_window.winfo_exists(): self.selection_window.destroy()
            except tk.TclError: pass
            finally: self.selection_window = None
            try:
                 if self.capture_root and self.capture_root.winfo_exists(): self.capture_root.destroy()
            except tk.TclError: pass
            finally: self.capture_root = None
            
            self.reset_state() 
            time.sleep(settings.CAPTURE_DELAY)

            if is_valid_size:
                if prompt_for_ollama is None:
                    if self.app.root and self.app.root.winfo_exists():
                        self.app.root.after(0, messagebox.showerror, T(DIALOG_INTERNAL_ERROR_TITLE_KEY), T(DIALOG_INTERNAL_ERROR_MSG_KEY))
                    return
                try:
                    screenshot = pyautogui.screenshot(region=region_to_capture)
                    if self.app.root and self.app.root.winfo_exists():
                        self.app.root.after(0, self.app.process_screenshot_with_ollama, screenshot, prompt_for_ollama)
                except Exception as e:
                    error_msg_detail = f"Failed to capture screenshot: {e}"
                    print(f'Screenshot Error: {error_msg_detail}')
                    if self.app.root and self.app.root.winfo_exists():
                        self.app.root.after(0, messagebox.showerror, T(DIALOG_SCREENSHOT_ERROR_TITLE_KEY), error_msg_detail)
            else:
                print('Selection too small. Screenshot cancelled.')

        def cancel_capture(event=None):
            print('Capture cancelled by user.')
            try:
                if self.selection_window and self.selection_window.winfo_exists(): self.selection_window.destroy()
            except tk.TclError: pass
            try:
                if self.capture_root and self.capture_root.winfo_exists(): self.capture_root.destroy()
            except tk.TclError: pass
            self.reset_state()

        canvas.bind('<ButtonPress-1>', on_button_press)
        canvas.bind('<B1-Motion>', on_mouse_drag)
        canvas.bind('<ButtonRelease-1>', on_button_release)
        self.selection_window.bind('<Escape>', cancel_capture)
        self.selection_window.focus_force()
        canvas.focus_set()

        if self.capture_root and self.capture_root.winfo_exists(): self.capture_root.mainloop()
        else: self.reset_state()

    def reset_state(self):
        self.selection_window = None
        self.capture_root = None
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.current_prompt = None