# ui_utils.py

import tkinter as tk
from tkinter import font as tkFont
import re
from PIL import Image, ImageDraw, ImageFont

try:
    import settings
    T = settings.T
except ImportError as e:
    print(f"FATAL ERROR: Could not import settings in ui_utils.py: {e}")
    def T_fallback(key, lang='en'): return f"<{key} (ui_utils fallback)>"
    T = T_fallback
    class settings_fallback_ui: # Fallback for constants used here
        CODE_FONT_FAMILY = 'Courier New'
        MIN_FONT_SIZE = 8
        CODE_FONT_SIZE_OFFSET = -1
        CODE_BLOCK_BG_COLOR = '#f0f0f0'
        CODE_BLOCK_MARGIN = 10
        DEFAULT_ICON_WIDTH = 64; DEFAULT_ICON_HEIGHT = 64
        DEFAULT_ICON_BG_COLOR = 'dimgray'; DEFAULT_ICON_RECT_COLOR = 'dodgerblue'
        DEFAULT_ICON_RECT_WIDTH = 4; DEFAULT_ICON_FONT_FAMILY = 'Arial'
        DEFAULT_ICON_FONT_SIZE = 30; DEFAULT_ICON_FONT_WEIGHT = 'bold'
        DEFAULT_ICON_TEXT = 'S'; DEFAULT_ICON_TEXT_COLOR = 'white'
    settings = settings_fallback_ui()


def apply_formatting_tags(text_widget, text_content, initial_font_size):
    if not text_widget or not text_widget.winfo_exists():
        print("Warning: apply_formatting_tags: Non-existent widget.")
        return

    text_widget.configure(state='normal')
    text_widget.delete('1.0', tk.END)
    text_widget.insert('1.0', text_content)

    base_family, code_family = "TkDefaultFont", settings.CODE_FONT_FAMILY
    try:
        base_font = tkFont.Font(font=text_widget['font'])
        base_family = base_font.actual()['family']
        tkFont.Font(family=settings.CODE_FONT_FAMILY, size=initial_font_size) # Verify
    except tk.TclError:
        print(f"Warning: Code font '{settings.CODE_FONT_FAMILY}' not found, using '{base_family}'.")
        code_family = base_family
    except Exception as e:
         print(f"Warning: Error accessing base font details: {e}")
         code_family = base_family if settings.CODE_FONT_FAMILY != 'Courier New' else 'Courier New'

    text_widget.tag_configure('bold', font=(base_family, initial_font_size, 'bold'))
    text_widget.tag_configure('italic', font=(base_family, initial_font_size, 'italic'))
    code_font_size = max(settings.MIN_FONT_SIZE, initial_font_size + settings.CODE_FONT_SIZE_OFFSET)
    text_widget.tag_configure('code', background=settings.CODE_BLOCK_BG_COLOR, 
                              font=(code_family, code_font_size, 'normal'), wrap=tk.WORD,
                              lmargin1=settings.CODE_BLOCK_MARGIN, lmargin2=settings.CODE_BLOCK_MARGIN,
                              relief=tk.SOLID, borderwidth=1)

    code_pattern = re.compile(r'```(\w*?)\n(.*?)\n```', re.DOTALL | re.IGNORECASE)
    for match in code_pattern.finditer(text_content):
        start_index = text_widget.index(f'1.0 + {match.start()} chars')
        end_index = text_widget.index(f'1.0 + {match.end()} chars')
        if start_index and end_index and text_widget.compare(start_index, '<', end_index):
            text_widget.tag_add('code', start_index, end_index)

    inline_patterns = {'bold': re.compile(r'\*\*(.+?)\*\*'), 'italic': re.compile(r'\*(.+?)\*')}
    for tag_name, pattern in inline_patterns.items():
        for match in pattern.finditer(text_content):
            match_start_index = text_widget.index(f'1.0 + {match.start()} chars')
            match_end_index = text_widget.index(f'1.0 + {match.end()} chars')
            if not (match_start_index and match_end_index and text_widget.compare(match_start_index, '<', match_end_index)):
                 continue
            is_inside_code = any('code' in text_widget.tag_names(idx) for idx in 
                                 (text_widget.index(f'{match_start_index} + {i} chars') 
                                  for i in range(match.end() - match.start())))
            if not is_inside_code:
                inner_start = text_widget.index(f'1.0 + {match.start(1)} chars')
                inner_end = text_widget.index(f'1.0 + {match.end(1)} chars')
                if inner_start and inner_end and text_widget.compare(inner_start, '<', inner_end):
                     text_widget.tag_add(tag_name, inner_start, inner_end)
    text_widget.configure(state='disabled')

def create_default_icon():
    image = Image.new('RGB', (settings.DEFAULT_ICON_WIDTH, settings.DEFAULT_ICON_HEIGHT), color=settings.DEFAULT_ICON_BG_COLOR)
    d = ImageDraw.Draw(image)
    mx, my = settings.DEFAULT_ICON_WIDTH * 0.15, settings.DEFAULT_ICON_HEIGHT * 0.15
    d.rectangle([(mx, my), (settings.DEFAULT_ICON_WIDTH - mx, settings.DEFAULT_ICON_HEIGHT - my)], 
                outline=settings.DEFAULT_ICON_RECT_COLOR, width=settings.DEFAULT_ICON_RECT_WIDTH)
    
    pil_font = None
    font_family_for_print = settings.DEFAULT_ICON_FONT_FAMILY
    try:
        # Try to load a TrueType font for better quality
        pil_font = ImageFont.truetype(settings.DEFAULT_ICON_FONT_FAMILY.lower() + ".ttf", settings.DEFAULT_ICON_FONT_SIZE)
    except IOError:
        try:
            pil_font = ImageFont.truetype("arial.ttf", settings.DEFAULT_ICON_FONT_SIZE) # Common fallback
            font_family_for_print = "Arial (fallback)"
        except IOError:
            pil_font = ImageFont.load_default() # Pillow's built-in bitmap font
            font_family_for_print = "Pillow default"
            print(f"Warning: Default icon font '{settings.DEFAULT_ICON_FONT_FAMILY}' and Arial not found. Using Pillow's bitmap default.")

    try:
        bbox = d.textbbox((0,0), settings.DEFAULT_ICON_TEXT, font=pil_font)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx, ty = (settings.DEFAULT_ICON_WIDTH - text_width) / 2 - bbox[0], (settings.DEFAULT_ICON_HEIGHT - text_height) / 2 - bbox[1]
    except Exception as e: # Fallback for older Pillow or if textbbox fails
        print(f"Warning: Could not get text bounding box for default icon: {e}. Using basic centering.")
        # Approximate centering for bitmap fonts or errors
        char_w = settings.DEFAULT_ICON_FONT_SIZE * 0.6 
        char_h = settings.DEFAULT_ICON_FONT_SIZE
        text_width_approx = char_w * len(settings.DEFAULT_ICON_TEXT)
        tx = (settings.DEFAULT_ICON_WIDTH - text_width_approx) / 2
        ty = (settings.DEFAULT_ICON_HEIGHT - char_h) / 2.5 # Adjusted for typical text baseline
        if not pil_font: pil_font = ImageFont.load_default()


    print(f"Using font '{font_family_for_print}' for default icon text.")
    d.text((tx, ty), settings.DEFAULT_ICON_TEXT, fill=settings.DEFAULT_ICON_TEXT_COLOR, font=pil_font)
    return image