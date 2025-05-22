# ui_utils.py
import logging
import tkinter as tk
from tkinter import font as tkFont, scrolledtext # Ensure scrolledtext is imported
import re
from PIL import Image, ImageDraw, ImageFont

# Initialize logger for this module
logger = logging.getLogger(__name__)

try:
    import settings # Assuming settings.py initializes logging
    T = settings.T
except ImportError as e:
    # This fallback is primarily for standalone testing or if settings.py fails very early.
    try:
        # Attempt to use the logger even in fallback
        fallback_logger = logging.getLogger("ui_utils_fallback")
        fallback_logger.critical("FATAL ERROR: Could not import 'settings' in ui_utils.py. Using fallback T and settings.", exc_info=True)
    except Exception: # Logging itself might not be working
        print(f"FATAL ERROR (no logger): Could not import 'settings' in ui_utils.py: {e}") # Ultimate fallback print

    def T_fallback(key, lang='en'): return f"<{key} (ui_utils fallback)>"
    T = T_fallback

    # Fallback settings class if main settings are unavailable
    class settings_fallback_ui:
        CODE_FONT_FAMILY = 'Courier New'
        MIN_FONT_SIZE = 8
        CODE_FONT_SIZE_OFFSET = -1
        DEFAULT_ICON_WIDTH = 64
        DEFAULT_ICON_HEIGHT = 64
        DEFAULT_ICON_BG_COLOR = 'dimgray'
        DEFAULT_ICON_RECT_COLOR = 'dodgerblue'
        DEFAULT_ICON_RECT_WIDTH = 4
        DEFAULT_ICON_FONT_FAMILY = 'Arial' # Default for icon text
        DEFAULT_ICON_FONT_SIZE = 30
        # DEFAULT_ICON_FONT_WEIGHT = 'bold' # tkFont doesn't directly use 'weight' like this for PIL
        DEFAULT_ICON_TEXT = 'S'
        DEFAULT_ICON_TEXT_COLOR = 'white'
        CURRENT_THEME = 'light' # Default theme for fallback
        THEME_COLORS = { # Minimal theme colors for fallback
            'light': {
                'code_block_bg': '#f0f0f0', 'code_block_fg': '#000000', 'code_block_border': '#CCCCCC',
                'md_h1_fg': '#000080', 'md_h2_fg': '#00008B', 'md_list_item_fg': '#228B22',
                'md_inline_code_bg': '#E0E0E0', 'md_inline_code_fg': '#C7254E',
                'python_keyword_fg': '#0000FF', 'python_string_fg': '#008000',
                'python_comment_fg': '#808080', 'python_number_fg': '#A52A2A',
                'python_function_fg': '#800080', 'python_builtin_fg': '#800080',
            },
            'dark': {
                'code_block_bg': '#1e1e1e', 'code_block_fg': '#D4D4D4', 'code_block_border': '#444444',
                'md_h1_fg': '#569CD6', 'md_h2_fg': '#4EC9B0', 'md_list_item_fg': '#B5CEA8',
                'md_inline_code_bg': '#3A3A3A', 'md_inline_code_fg': '#D69D85',
                'python_keyword_fg': '#569CD6', 'python_string_fg': '#CE9178',
                'python_comment_fg': '#6A9955', 'python_number_fg': '#B5CEA8',
                'python_function_fg': '#DCDCAA', 'python_builtin_fg': '#DCDCAA',
            }
        }
        def get_theme_color(self, key, theme=None):
            actual_theme_name = theme if theme else self.CURRENT_THEME
            theme_dict = self.THEME_COLORS.get(actual_theme_name, self.THEME_COLORS['light'])
            color = theme_dict.get(key)
            if color is None: # Fallback to light theme if key not in current, then magenta
                color = self.THEME_COLORS['light'].get(key, '#FF00FF') 
            return color
    settings = settings_fallback_ui()
    logger.info("ui_utils.py: Using fallback settings and T function.")


# --- Python Keywords (Simplified List for basic highlighting) ---
PYTHON_KEYWORDS = [
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class',
    'continue', 'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
    'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass',
    'raise', 'return', 'try', 'while', 'with', 'yield', 'self', 'cls'
]
PYTHON_BUILTINS_FUNCTIONS = [ # Common built-ins, not exhaustive
    'print', 'len', 'range', 'open', 'str', 'int', 'float', 'list', 'dict', 'tuple', 'set',
    'sum', 'min', 'max', 'abs', 'round', 'sorted', 'reversed', 'zip', 'enumerate', 'map', 'filter'
]


def apply_formatting_tags(text_widget, text_content, initial_font_size):
    """
    Applies Markdown-like and Python syntax highlighting tags to a Tkinter Text widget.
    """
    if not text_widget or not text_widget.winfo_exists():
        logger.warning("apply_formatting_tags: text_widget is invalid or destroyed. Aborting.")
        return

    logger.debug("Applying formatting tags. Initial font size: %spt, Text length: %d",
                 initial_font_size, len(text_content or ""))

    actual_text_area = text_widget # ScrolledText proxies most calls, direct use is fine

    try:
        actual_text_area.configure(state='normal')
        actual_text_area.delete('1.0', tk.END)
        actual_text_area.insert('1.0', text_content)

        # --- Font Setup ---
        base_font_obj = tkFont.Font(font=actual_text_area['font']) # Get current font from widget
        base_family = base_font_obj.actual()['family']
        
        code_family = settings.CODE_FONT_FAMILY
        try: # Validate code font family
            tkFont.Font(family=settings.CODE_FONT_FAMILY, size=initial_font_size)
        except tk.TclError:
            logger.warning("Specified CODE_FONT_FAMILY '%s' not found. Falling back to base font family '%s'.",
                           settings.CODE_FONT_FAMILY, base_family)
            code_family = base_family

        # --- Basic Markdown Tags ---
        actual_text_area.tag_configure('bold', font=(base_family, initial_font_size, 'bold'))
        actual_text_area.tag_configure('italic', font=(base_family, initial_font_size, 'italic'))
        actual_text_area.tag_configure('h1', font=(base_family, initial_font_size + 4, 'bold'),
                                     foreground=settings.get_theme_color('md_h1_fg'))
        actual_text_area.tag_configure('h2', font=(base_family, initial_font_size + 2, 'bold'),
                                     foreground=settings.get_theme_color('md_h2_fg'))
        actual_text_area.tag_configure('h3', font=(base_family, initial_font_size + 1, 'bold')) # No specific color, uses default fg
        actual_text_area.tag_configure('list_item', foreground=settings.get_theme_color('md_list_item_fg'))
        
        inline_code_font_size = max(settings.MIN_FONT_SIZE, initial_font_size -1) # Ensure not too small
        actual_text_area.tag_configure('inline_code', font=(code_family, inline_code_font_size),
                                     background=settings.get_theme_color('md_inline_code_bg'),
                                     foreground=settings.get_theme_color('md_inline_code_fg'))

        # --- Code Block Tag (Outer block) ---
        code_font_size = max(settings.MIN_FONT_SIZE, initial_font_size + settings.CODE_FONT_SIZE_OFFSET)
        
        code_block_tag_config = {
            'background': settings.get_theme_color('code_block_bg'),
            'foreground': settings.get_theme_color('code_block_fg'),
            'font': (code_family, code_font_size, 'normal'),
            'wrap': tk.WORD, # Or tk.NONE if horizontal scrollbar is desired
            'lmargin1': 10, 'lmargin2': 10, # Left indentation
            'rmargin': 10,                  # Right margin
            'spacing1': 5, 'spacing3': 5,  # Space above and below paragraph
            'relief': tk.SOLID,
            'borderwidth': 1,
            # 'borderbackground': settings.get_theme_color('code_block_border') # Not a valid option
            # For border color, usually highlightbackground/highlightcolor on the Text widget itself,
            # or draw it manually if using a Canvas. Here, borderwidth + relief gives some outline.
        }
        actual_text_area.tag_configure('code_block', **code_block_tag_config)

        # --- Python Syntax Highlighting Tags (applied *inside* 'code_block') ---
        actual_text_area.tag_configure('python_keyword', foreground=settings.get_theme_color('python_keyword_fg'))
        actual_text_area.tag_configure('python_builtin', foreground=settings.get_theme_color('python_builtin_fg'))
        actual_text_area.tag_configure('python_string', foreground=settings.get_theme_color('python_string_fg'))
        actual_text_area.tag_configure('python_comment', foreground=settings.get_theme_color('python_comment_fg'),
                                     font=(code_family, code_font_size, 'italic'))
        actual_text_area.tag_configure('python_number', foreground=settings.get_theme_color('python_number_fg'))
        actual_text_area.tag_configure('python_function', foreground=settings.get_theme_color('python_function_fg'))

        # --- Apply Line-based Tags (Headers, List Items) ---
        current_pos = "1.0"
        while actual_text_area.compare(current_pos, "<", "end"):
            line_end_pos = actual_text_area.index(f"{current_pos} lineend")
            line_text = actual_text_area.get(current_pos, line_end_pos)

            if line_text.startswith("### "):
                actual_text_area.tag_add('h3', current_pos, f"{current_pos} + 4 chars") # Tag the '### ' part
            elif line_text.startswith("## "):
                actual_text_area.tag_add('h2', current_pos, f"{current_pos} + 3 chars")
            elif line_text.startswith("# "):
                actual_text_area.tag_add('h1', current_pos, f"{current_pos} + 2 chars")
            elif re.match(r"^\s*([-*+]|\d+\.)\s+", line_text): # Matches bullets or numbered lists
                actual_text_area.tag_add('list_item', current_pos, line_end_pos)
            
            current_pos = actual_text_area.index(f"{line_end_pos} + 1 char")


        # --- Apply Block Tags (Code Blocks) ---
        code_block_pattern = re.compile(r'^```(\w*)\n(.*?)\n^```', re.DOTALL | re.MULTILINE)
        for match in code_block_pattern.finditer(text_content):
            lang_hint = match.group(1).lower().strip()
            # code_content_raw = match.group(2) # Not directly used here, but available
            
            block_start_index_str = f"1.0 + {match.start()} chars"
            block_end_index_str = f"1.0 + {match.end()} chars"
            
            try:
                block_start_index = actual_text_area.index(block_start_index_str)
                block_end_index = actual_text_area.index(block_end_index_str)
            except tk.TclError as e:
                logger.warning("TclError calculating code block indices: %s. Match: '%s'", e, match.group(0)[:50], exc_info=False)
                continue

            if actual_text_area.compare(block_start_index, '<', block_end_index):
                actual_text_area.tag_add('code_block', block_start_index, block_end_index)

                if lang_hint == 'python':
                    # Content starts after '```python\n' and ends before '\n```'
                    # Match group 2 captures the content between the markers.
                    code_text_start_offset_in_match = match.start(2) - match.start(0) # Offset from start of full match to start of group 2
                    code_text_end_offset_in_match = match.end(2) - match.start(0)   # Offset from start of full match to end of group 2

                    python_code_start_index = actual_text_area.index(f"{block_start_index} + {code_text_start_offset_in_match} chars")
                    python_code_end_index = actual_text_area.index(f"{block_start_index} + {code_text_end_offset_in_match} chars")
                    
                    if actual_text_area.compare(python_code_start_index, '<', python_code_end_index):
                        highlight_python_syntax(actual_text_area, python_code_start_index, python_code_end_index)
                    else:
                        logger.debug("Python code block indices for highlighting are invalid or empty.")
            else:
                logger.debug("Code block indices are invalid or empty.")


        # --- Apply Inline Tags (Bold, Italic, Inline Code) ---
        # Process AFTER blocks to avoid conflicts and ensure they are not inside code_block.
        inline_markdown_patterns = {
            'bold': (re.compile(r'\*\*(.+?)\*\*'), 1), # Group 1 is content
            'italic': (re.compile(r'\*(.+?)\*'), 1),   # Group 1 is content
            'inline_code': (re.compile(r'`(.+?)`'), 1) # Group 1 is content
        }

        for tag_name, (pattern, content_group_idx) in inline_markdown_patterns.items():
            for match in pattern.finditer(text_content):
                try:
                    match_outer_start_idx_str = f"1.0 + {match.start(0)} chars" # Full match start
                    match_outer_end_idx_str = f"1.0 + {match.end(0)} chars"   # Full match end

                    match_outer_start_idx = actual_text_area.index(match_outer_start_idx_str)
                    match_outer_end_idx = actual_text_area.index(match_outer_end_idx_str)
                    
                    # Check if this match is inside an already tagged code_block
                    is_in_code_block = False
                    # Check midpoint of the match; simpler than iterating char by char for this check
                    mid_point_offset = (match.start(0) + match.end(0)) // 2
                    check_idx_str = f"1.0 + {mid_point_offset} chars"
                    check_idx = actual_text_area.index(check_idx_str)

                    if 'code_block' in actual_text_area.tag_names(check_idx):
                        is_in_code_block = True
                    
                    if not is_in_code_block:
                        # Apply tag to the inner content (group specified by content_group_idx)
                        content_start_offset_in_match = match.start(content_group_idx) - match.start(0)
                        content_end_offset_in_match = match.end(content_group_idx) - match.start(0)

                        tag_start_idx = actual_text_area.index(f"{match_outer_start_idx} + {content_start_offset_in_match} chars")
                        tag_end_idx = actual_text_area.index(f"{match_outer_start_idx} + {content_end_offset_in_match} chars")

                        if actual_text_area.compare(tag_start_idx, "<", tag_end_idx):
                            actual_text_area.tag_add(tag_name, tag_start_idx, tag_end_idx)
                            # For bold/italic, remove the markdown characters themselves from being displayed
                            # This is tricky with Tkinter tags. A common approach is to replace the text
                            # or use more complex regex to capture parts to hide.
                            # For simplicity here, we are tagging the content *inside* the markers.
                            # The markers (**, *, `) will still be visible.
                            # To hide them, you'd need to tag them with a 'hidden' tag (e.g., fg=bg)
                            # or reconstruct the text. This adds complexity.

                except tk.TclError as e:
                    logger.warning("TclError applying inline markdown tag '%s': %s. Match: '%s'", tag_name, e, match.group(0), exc_info=False)
                    continue
                except IndexError: # Regex group not found (should not happen with .+?)
                    logger.warning("IndexError for inline markdown tag '%s' - regex group issue. Match: '%s'", tag_name, match.group(0), exc_info=False)
                    continue
        
        actual_text_area.configure(state='disabled')
        logger.debug("Formatting tags applied successfully.")

    except Exception as e:
        logger.error("Unexpected error in apply_formatting_tags.", exc_info=True)
        # Attempt to restore text widget to a usable state
        try:
            if actual_text_area and actual_text_area.winfo_exists():
                actual_text_area.delete('1.0', tk.END)
                actual_text_area.insert('1.0', text_content or "Error displaying content.") # Fallback content
                actual_text_area.configure(state='disabled')
        except Exception as e_fallback:
            logger.error("Error during fallback content display in apply_formatting_tags: %s", e_fallback, exc_info=True)


def highlight_python_syntax(text_widget, start_index, end_index):
    """
    Applies basic Python syntax highlighting to the text_widget
    between start_index and end_index.
    This is a simplified regex-based highlighter.
    """
    logger.debug("Applying Python syntax highlighting from %s to %s.", start_index, end_index)
    content = text_widget.get(start_index, end_index)

    # Order of regex application matters: Comments, Strings, Keywords, Numbers, Functions.
    
    # Comments (#.*$)
    for m in re.finditer(r"#.*$", content, re.MULTILINE):
        tag_start = text_widget.index(f"{start_index} + {m.start()} chars")
        tag_end = text_widget.index(f"{start_index} + {m.end()} chars")
        text_widget.tag_add("python_comment", tag_start, tag_end)

    # Strings (handles single, double, triple quotes; basic escape handling)
    string_pattern = r"('''[^'\\]*(?:\\.[^'\\]*)*'''|\"\"\"[^\"\\]*(?:\\.[^\"\\]*)*\"\"\"|'[^'\\]*(?:\\.[^'\\]*)*'|\"[^\"\\]*(?:\\.[^\"\\]*)*\")"
    for m in re.finditer(string_pattern, content):
        tag_start = text_widget.index(f"{start_index} + {m.start()} chars")
        tag_end = text_widget.index(f"{start_index} + {m.end()} chars")
        text_widget.tag_add("python_string", tag_start, tag_end)

    # Keywords & Builtins (as whole words, ensure not part of comment or string)
    keyword_pattern_str = r"\b(" + "|".join(PYTHON_KEYWORDS) + r")\b"
    builtin_pattern_str = r"\b(" + "|".join(PYTHON_BUILTINS_FUNCTIONS) + r")\b(?=\s*\()" # Lookahead for (

    for pattern_str, tag_name_py in [(keyword_pattern_str, "python_keyword"), (builtin_pattern_str, "python_builtin")]:
        for m in re.finditer(pattern_str, content):
            match_start_offset = m.start()
            tag_start = text_widget.index(f"{start_index} + {match_start_offset} chars")
            tag_end = text_widget.index(f"{start_index} + {m.end()} chars")
            
            # Check if the middle of the match is already tagged as comment or string
            check_idx = text_widget.index(f"{start_index} + {(m.start() + m.end()) // 2} chars")
            current_tags_at_check = text_widget.tag_names(check_idx)
            
            if "python_comment" not in current_tags_at_check and "python_string" not in current_tags_at_check:
                text_widget.tag_add(tag_name_py, tag_start, tag_end)

    # Numbers (integers, floats, hex; ensure not part of other constructs)
    number_pattern = r"\b(0[xX][0-9a-fA-F]+(?:\b|L|l)|(?:\d*\.\d+|\d+\.?)(?:[eE][+-]?\d+)?(?:\b|L|l|j|J)|\d+(?:\b|L|l))\b"
    for m in re.finditer(number_pattern, content):
        tag_start = text_widget.index(f"{start_index} + {m.start()} chars")
        tag_end = text_widget.index(f"{start_index} + {m.end()} chars")
        check_idx = text_widget.index(f"{start_index} + {(m.start() + m.end()) // 2} chars")
        current_tags_at_check = text_widget.tag_names(check_idx)
        if not any(t in current_tags_at_check for t in ["python_comment", "python_string", "python_keyword", "python_builtin"]):
            text_widget.tag_add("python_number", tag_start, tag_end)

    # Function definition names (def name(...))
    # Class definition names (class Name(...))
    # Simpler: highlight word after 'def' or 'class'
    for keyword, tag_to_apply in [("def", "python_function"), ("class", "python_function")]: # Using 'python_function' for class names too
        for m in re.finditer(rf"{keyword}\s+([a-zA-Z_]\w*)\s*\(", content):
            fn_name_start_offset = m.start(1) # Start of the function/class name (group 1)
            fn_name_end_offset = m.end(1)   # End of the function/class name

            tag_start = text_widget.index(f"{start_index} + {fn_name_start_offset} chars")
            tag_end = text_widget.index(f"{start_index} + {fn_name_end_offset} chars")
            
            check_idx = text_widget.index(f"{start_index} + {(fn_name_start_offset + fn_name_end_offset) // 2} chars")
            current_tags_at_check = text_widget.tag_names(check_idx)

            if not any(t in current_tags_at_check for t in ["python_comment", "python_string", "python_keyword"]):
                text_widget.tag_add(tag_to_apply, tag_start, tag_end)

    # Lower priority of syntax tags so they don't override block-level or base formatting if there's overlap.
    # This might not be strictly necessary with the current check logic but can prevent issues.
    for tag_py in ['python_comment', 'python_string', 'python_keyword', 'python_builtin', 'python_number', 'python_function']:
        text_widget.tag_lower(tag_py)


def create_default_icon():
    """Creates a default PIL Image object to be used as a fallback tray icon."""
    logger.debug("Creating default PIL icon image.")
    try:
        image = Image.new('RGB', (settings.DEFAULT_ICON_WIDTH, settings.DEFAULT_ICON_HEIGHT),
                          color=settings.DEFAULT_ICON_BG_COLOR)
        d = ImageDraw.Draw(image)
        
        # Rectangle dimensions
        mx, my = settings.DEFAULT_ICON_WIDTH * 0.15, settings.DEFAULT_ICON_HEIGHT * 0.15
        d.rectangle([(mx, my), (settings.DEFAULT_ICON_WIDTH - mx, settings.DEFAULT_ICON_HEIGHT - my)],
                    outline=settings.DEFAULT_ICON_RECT_COLOR, width=int(settings.DEFAULT_ICON_RECT_WIDTH)) # Ensure width is int

        # Font loading with fallbacks
        pil_font = None
        font_family_for_log = settings.DEFAULT_ICON_FONT_FAMILY
        try:
            # Pillow needs the .ttf extension (or .otf) for truetype fonts
            # Common system font paths might be needed if just filename doesn't work.
            # For simplicity, we assume it's in a standard font dir or use common names.
            font_path_ttf = settings.DEFAULT_ICON_FONT_FAMILY.lower()
            if not font_path_ttf.endswith((".ttf", ".otf")):
                font_path_ttf += ".ttf"
            pil_font = ImageFont.truetype(font_path_ttf, settings.DEFAULT_ICON_FONT_SIZE)
            logger.debug("Loaded icon font: %s, size %s", font_path_ttf, settings.DEFAULT_ICON_FONT_SIZE)
        except IOError:
            logger.warning("Failed to load default icon font '%s'. Trying 'arial.ttf'.", font_family_for_log)
            try:
                pil_font = ImageFont.truetype("arial.ttf", settings.DEFAULT_ICON_FONT_SIZE)
                font_family_for_log = "Arial (fallback)"
                logger.debug("Loaded icon font: arial.ttf (fallback), size %s", settings.DEFAULT_ICON_FONT_SIZE)
            except IOError:
                logger.warning("Failed to load 'arial.ttf' for default icon. Using Pillow's load_default().")
                pil_font = ImageFont.load_default() # This font is very small
                font_family_for_log = "Pillow default"
        
        # Text positioning (Pillow 9+ textbbox is preferred)
        text_to_draw = settings.DEFAULT_ICON_TEXT
        text_fill_color = settings.DEFAULT_ICON_TEXT_COLOR
        
        try: # Pillow 9+ with textbbox for more accurate centering
            bbox = d.textbbox((0,0), text_to_draw, font=pil_font, anchor="lt") # Left-Top anchor
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            # Adjust tx, ty based on anchor point (lt means bbox[0], bbox[1] are top-left of text)
            tx = (settings.DEFAULT_ICON_WIDTH - text_width) / 2 #- bbox[0] # If anchor was 'la', this would be needed
            ty = (settings.DEFAULT_ICON_HEIGHT - text_height) / 2 - bbox[1] # Correct for text starting baseline
        except AttributeError: # Fallback for older Pillow (textsize) or if textbbox fails
            logger.debug("textbbox not available, using textsize for default icon text positioning.")
            try:
                text_width, text_height = d.textsize(text_to_draw, font=pil_font)
            except TypeError: # Older Pillow versions textsize might not take font argument directly, or other issues
                logger.warning("Error with d.textsize, approximating text size for default icon.")
                # Very rough approximation if textsize fails
                text_width = len(text_to_draw) * settings.DEFAULT_ICON_FONT_SIZE * 0.6
                text_height = settings.DEFAULT_ICON_FONT_SIZE
            tx = (settings.DEFAULT_ICON_WIDTH - text_width) / 2
            ty = (settings.DEFAULT_ICON_HEIGHT - text_height) / 2
        except Exception as e_text_pos: # Catch any other error during text positioning
             logger.error("Error during text positioning for default icon: %s. Approximating.", e_text_pos, exc_info=True)
             tx = settings.DEFAULT_ICON_WIDTH * 0.25 # Fallback position
             ty = settings.DEFAULT_ICON_HEIGHT * 0.25

        d.text((tx, ty), text_to_draw, fill=text_fill_color, font=pil_font)
        logger.info("Default icon created successfully with font: %s", font_family_for_log)
        return image
    except Exception as e:
        logger.error("Failed to create default icon image.", exc_info=True)
        # Fallback: create a very simple image if all else fails
        try:
            img = Image.new('RGB', (64, 64), 'gray')
            ImageDraw.Draw(img).text((10, 10), "ERR", fill="red")
            return img
        except Exception: # Should not happen
            return None # Absolute last resort