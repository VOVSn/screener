# ui_utils.py

import tkinter as tk
from tkinter import font as tkFont
import re
from PIL import Image, ImageDraw

# Local Imports (assuming ui_utils.py is in the same directory)
try:
    import settings
except ImportError as e:
    print(f"FATAL ERROR: Could not import settings in ui_utils.py: {e}")
    # Cannot easily show Tkinter error here as this might be imported before Tk is ready
    exit()


def apply_formatting_tags(text_widget, text_content, initial_font_size):
    """
    Applies basic markdown (bold, italic, code blocks) styling using Tkinter tags.

    Args:
        text_widget: The Tkinter Text or ScrolledText widget.
        text_content: The raw text content with markdown-like syntax.
        initial_font_size: The base font size to use for calculations.
    """
    if not text_widget or not text_widget.winfo_exists():
        print("Warning: Attempted to apply formatting to non-existent widget.")
        return

    text_widget.configure(state='normal')
    text_widget.delete('1.0', tk.END)
    text_widget.insert('1.0', text_content)

    try:
        base_font = tkFont.Font(font=text_widget['font'])
        base_family = base_font.actual()['family']
        code_family = settings.CODE_FONT_FAMILY
        # Verify code font exists at the initial size to trigger fallback early if needed
        tkFont.Font(family=code_family, size=initial_font_size)
    except tk.TclError:
        print(f"Warning: Code font '{settings.CODE_FONT_FAMILY}' "
              f"not found, using '{base_family}'.")
        code_family = base_family # Fallback
    except Exception as e:
         print(f"Warning: Error accessing base font details: {e}")
         # Sensible defaults if font access fails
         base_family = "TkDefaultFont"
         code_family = "Courier New" if settings.CODE_FONT_FAMILY == 'Courier New' else base_family


    # --- Define Tags ---
    # Define tags dynamically based on current initial_font_size
    text_widget.tag_configure(
        'bold', font=(base_family, initial_font_size, 'bold')
    )
    text_widget.tag_configure(
        'italic', font=(base_family, initial_font_size, 'italic')
    )
    # Calculate code font size relative to the initial size, respecting min size
    code_font_size = max(
        settings.MIN_FONT_SIZE, # Absolute minimum
        initial_font_size + settings.CODE_FONT_SIZE_OFFSET # Relative offset
    )
    text_widget.tag_configure(
        'code', background=settings.CODE_BLOCK_BG_COLOR,
        font=(code_family, code_font_size, 'normal'),
        wrap=tk.WORD, # Use WORD wrap for code blocks if desired
        lmargin1=settings.CODE_BLOCK_MARGIN,
        lmargin2=settings.CODE_BLOCK_MARGIN,
        relief=tk.SOLID, # Optional: Add a subtle border to code blocks
        borderwidth=1    # Optional: Border width
    )

    # --- Apply Tags ---
    # Apply multiline code blocks first (```...```)
    # Make pattern non-greedy (.*?) and handle optional language hints (\w*)
    code_pattern = re.compile(r'```(\w*?)\n(.*?)\n```', re.DOTALL | re.IGNORECASE)
    for match in code_pattern.finditer(text_content):
        # Apply tag from the start of ``` to the end of ```
        start_index = text_widget.index(f'1.0 + {match.start()} chars')
        end_index = text_widget.index(f'1.0 + {match.end()} chars')
        # Check if the range is valid before applying tag
        if start_index and end_index and text_widget.compare(start_index, '<', end_index):
            text_widget.tag_add('code', start_index, end_index)
        else:
             print(f"Warning: Invalid range for code block tag: {match.group(0)[:50]}...")


    # Apply inline styles (e.g., **, *) - check they are NOT inside already tagged 'code' blocks
    inline_patterns = {
        'bold': re.compile(r'\*\*(.+?)\*\*'), # Non-greedy match inside **
        'italic': re.compile(r'\*(.+?)\*'),     # Non-greedy match inside *
        # Add inline code (`) support if needed:
        # 'inline_code': re.compile(r'`(.+?)`'),
    }

    for tag_name, pattern in inline_patterns.items():
        for match in pattern.finditer(text_content):
            # Get start/end indices for the matched content *including* the markers
            match_start_index = text_widget.index(f'1.0 + {match.start()} chars')
            match_end_index = text_widget.index(f'1.0 + {match.end()} chars')

            # Check if the *entire* match range is valid and get tags at the start
            if not match_start_index or not match_end_index or \
               not text_widget.compare(match_start_index, '<', match_end_index):
                 print(f"Warning: Invalid range for inline tag '{tag_name}': {match.group(0)}")
                 continue

            # Check if any part of this match overlaps with a 'code' block tag
            is_inside_code = False
            current_index = match_start_index
            while text_widget.compare(current_index, '<', match_end_index):
                if 'code' in text_widget.tag_names(current_index):
                    is_inside_code = True
                    break
                current_index = text_widget.index(f'{current_index} + 1 char') # Move one char forward

            if not is_inside_code:
                # Apply the tag only to the content *inside* the markers
                inner_start = text_widget.index(f'1.0 + {match.start(1)} chars')
                inner_end = text_widget.index(f'1.0 + {match.end(1)} chars')
                if inner_start and inner_end and text_widget.compare(inner_start, '<', inner_end):
                     text_widget.tag_add(tag_name, inner_start, inner_end)
                     # Optional: Hide the markdown markers themselves using elide
                     # text_widget.tag_add('elide', match_start_index, inner_start)
                     # text_widget.tag_add('elide', inner_end, match_end_index)
                else:
                    print(f"Warning: Invalid inner range for '{tag_name}': {match.group(1)}")


    # Optional: Configure elide tag to hide markers
    # text_widget.tag_configure('elide', elide=True)

    text_widget.configure(state='disabled') # Make read-only


def create_default_icon():
    """Creates a simple fallback PIL image icon using settings."""
    width = settings.DEFAULT_ICON_WIDTH
    height = settings.DEFAULT_ICON_HEIGHT
    image = Image.new('RGB', (width, height), color=settings.DEFAULT_ICON_BG_COLOR)
    d = ImageDraw.Draw(image)
    # Simple margin calculation
    margin_x = width * 0.15
    margin_y = height * 0.15
    d.rectangle(
        [(margin_x, margin_y), (width - margin_x, height - margin_y)],
        outline=settings.DEFAULT_ICON_RECT_COLOR,
        width=settings.DEFAULT_ICON_RECT_WIDTH
    )
    try:
        # Attempt to load the specified font
        font = tkFont.Font(
            family=settings.DEFAULT_ICON_FONT_FAMILY,
            size=settings.DEFAULT_ICON_FONT_SIZE,
            weight=settings.DEFAULT_ICON_FONT_WEIGHT
        )
        font_family_found = settings.DEFAULT_ICON_FONT_FAMILY
    except tk.TclError:
        # Fallback if the specified font isn't found
        print(f"Warning: Default icon font '{settings.DEFAULT_ICON_FONT_FAMILY}'"
              " not found, using Tk default.")
        font = tkFont.Font(
            size=settings.DEFAULT_ICON_FONT_SIZE,
            weight=settings.DEFAULT_ICON_FONT_WEIGHT
        )
        try:
            font_family_found = font.actual()['family'] # Get the actual fallback family
        except Exception:
            font_family_found = "TkDefaultFont" # Ultimate fallback

    # Use textbbox for potentially better centering if available and font loaded
    try:
         # (x0, y0, x1, y1) bbox of the text
         bbox = d.textbbox((0, 0), settings.DEFAULT_ICON_TEXT, font=font)
         text_width = bbox[2] - bbox[0]
         text_height = bbox[3] - bbox[1]
         # Center text based on bbox dimensions
         text_x = (width - text_width) / 2 - bbox[0] # Adjust x by bbox's left offset
         text_y = (height - text_height) / 2 - bbox[1] # Adjust y by bbox's top offset
    except AttributeError: # Fallback for older Pillow versions or if font fails severely
         # Very basic approximation if textbbox fails
         text_x = width / 3.5
         text_y = height / 4
    except Exception as e:
        print(f"Warning: Could not get text bounding box for default icon: {e}")
        text_x = width / 3.5
        text_y = height / 4


    print(f"Using font '{font_family_found}' for default icon text.")
    d.text(
        (text_x, text_y),
        settings.DEFAULT_ICON_TEXT,
        fill=settings.DEFAULT_ICON_TEXT_COLOR,
        font=font
    )
    return image