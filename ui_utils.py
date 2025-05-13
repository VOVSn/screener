# ui_utils.py
import tkinter as tk
from tkinter import font as tkFont, scrolledtext # Ensure scrolledtext is imported
import re
from PIL import Image, ImageDraw, ImageFont

try:
    import settings
    T = settings.T
except ImportError as e:
    # ... (fallback as before, ensure new color keys are handled in fallback settings.get_theme_color) ...
    print(f"FATAL ERROR: Could not import settings in ui_utils.py: {e}")
    def T_fallback(key, lang='en'): return f"<{key} (ui_utils fallback)>"
    T = T_fallback
    class settings_fallback_ui:
        CODE_FONT_FAMILY = 'Courier New'
        MIN_FONT_SIZE = 8
        CODE_FONT_SIZE_OFFSET = -1
        DEFAULT_ICON_WIDTH = 64; DEFAULT_ICON_HEIGHT = 64
        DEFAULT_ICON_BG_COLOR = 'dimgray'; DEFAULT_ICON_RECT_COLOR = 'dodgerblue'
        DEFAULT_ICON_RECT_WIDTH = 4; DEFAULT_ICON_FONT_FAMILY = 'Arial'
        DEFAULT_ICON_FONT_SIZE = 30; DEFAULT_ICON_FONT_WEIGHT = 'bold'
        DEFAULT_ICON_TEXT = 'S'; DEFAULT_ICON_TEXT_COLOR = 'white'
        CURRENT_THEME = 'light'
        THEME_COLORS = {
            'light': {
                'code_block_bg': '#f0f0f0', 'code_block_fg': '#000000', 'code_block_border': '#CCCCCC',
                'md_h1_fg': '#000080', 'md_h2_fg': '#00008B', 'md_list_item_fg': '#228B22',
                'md_inline_code_bg': '#E0E0E0', 'md_inline_code_fg': '#C7254E',
                'python_keyword_fg': '#0000FF', 'python_string_fg': '#008000',
                'python_comment_fg': '#808080', 'python_number_fg': '#A52A2A',
                'python_function_fg': '#800080',
            },
            'dark': { # Add dark theme fallbacks too
                'code_block_bg': '#1e1e1e', 'code_block_fg': '#D4D4D4', 'code_block_border': '#444444',
                'md_h1_fg': '#569CD6', 'md_h2_fg': '#4EC9B0', 'md_list_item_fg': '#B5CEA8',
                'md_inline_code_bg': '#3A3A3A', 'md_inline_code_fg': '#D69D85',
                'python_keyword_fg': '#569CD6', 'python_string_fg': '#CE9178',
                'python_comment_fg': '#6A9955', 'python_number_fg': '#B5CEA8',
                'python_function_fg': '#DCDCAA',
            }
        }
        def get_theme_color(self, key, theme=None):
            actual_theme = theme if theme else self.CURRENT_THEME
            default_colors_for_theme = self.THEME_COLORS.get(actual_theme, self.THEME_COLORS['light'])
            return default_colors_for_theme.get(key, self.THEME_COLORS['light'].get(key, '#FF00FF')) # Fallback to light then magenta

    settings = settings_fallback_ui()

# --- Python Keywords (Simplified List) ---
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
    if not text_widget or not text_widget.winfo_exists():
        return

    actual_text_area = text_widget
    if isinstance(text_widget, scrolledtext.ScrolledText): # Tkinter's ScrolledText
        # ScrolledText proxies most calls to its internal Text widget,
        # so we can often use the ScrolledText instance directly.
        pass # actual_text_area = text_widget is fine

    actual_text_area.configure(state='normal')
    actual_text_area.delete('1.0', tk.END)
    actual_text_area.insert('1.0', text_content)

    # --- Font Setup ---
    base_font_obj = tkFont.Font(font=actual_text_area['font'])
    base_family = base_font_obj.actual()['family']
    code_family = settings.CODE_FONT_FAMILY
    try:
        tkFont.Font(family=settings.CODE_FONT_FAMILY, size=initial_font_size)
    except tk.TclError:
        code_family = base_family # Fallback

    # --- Basic Markdown Tags ---
    actual_text_area.tag_configure('bold', font=(base_family, initial_font_size, 'bold'))
    actual_text_area.tag_configure('italic', font=(base_family, initial_font_size, 'italic'))
    actual_text_area.tag_configure('h1', font=(base_family, initial_font_size + 4, 'bold'),
                                 foreground=settings.get_theme_color('md_h1_fg'))
    actual_text_area.tag_configure('h2', font=(base_family, initial_font_size + 2, 'bold'),
                                 foreground=settings.get_theme_color('md_h2_fg'))
    actual_text_area.tag_configure('h3', font=(base_family, initial_font_size + 1, 'bold'))
    actual_text_area.tag_configure('list_item', foreground=settings.get_theme_color('md_list_item_fg'))
    
    inline_code_bg = settings.get_theme_color('md_inline_code_bg')
    inline_code_fg = settings.get_theme_color('md_inline_code_fg')
    actual_text_area.tag_configure('inline_code', font=(code_family, initial_font_size -1),
                                 background=inline_code_bg, foreground=inline_code_fg,
                                 # Add small padding/margins for inline code if possible (hard with tags)
                                 #relief=tk.SOLID, borderwidth=1 # Can look too busy inline
                                 )

    # --- Code Block Tag (Outer block) ---
    code_font_size = max(settings.MIN_FONT_SIZE, initial_font_size + settings.CODE_FONT_SIZE_OFFSET)
    code_block_bg_color = settings.get_theme_color('code_block_bg')
    code_block_fg_color = settings.get_theme_color('code_block_fg')
    
    code_block_tag_config = {
        'background': code_block_bg_color,
        'foreground': code_block_fg_color, # Default text color inside code block
        'font': (code_family, code_font_size, 'normal'),
        'wrap': tk.WORD, # Or tk.NONE if horizontal scrollbar is desired and implemented
        'lmargin1': 10, 'lmargin2': 10,
        'rmargin': 10,
        'spacing1': 5, 'spacing3': 5, # Above and below paragraph
        'relief': tk.SOLID,
        'borderwidth': 1,
    }
    actual_text_area.tag_configure('code_block', **code_block_tag_config)

    # --- Python Syntax Highlighting Tags (applied *inside* 'code_block') ---
    actual_text_area.tag_configure('python_keyword', foreground=settings.get_theme_color('python_keyword_fg'))
    actual_text_area.tag_configure('python_builtin', foreground=settings.get_theme_color('python_function_fg')) # Using function color for builtins
    actual_text_area.tag_configure('python_string', foreground=settings.get_theme_color('python_string_fg'))
    actual_text_area.tag_configure('python_comment', foreground=settings.get_theme_color('python_comment_fg'), font=(code_family, code_font_size, 'italic'))
    actual_text_area.tag_configure('python_number', foreground=settings.get_theme_color('python_number_fg'))
    actual_text_area.tag_configure('python_function', foreground=settings.get_theme_color('python_function_fg'))


    # --- Apply Tags ---
    # Iterate line by line for some markdown, then by blocks
    current_pos = "1.0"
    while actual_text_area.compare(current_pos, "<", "end"):
        line_end_pos = actual_text_area.index(f"{current_pos} lineend")
        line_text = actual_text_area.get(current_pos, line_end_pos)

        # Headers
        if line_text.startswith("### "):
            actual_text_area.tag_add('h3', current_pos, f"{current_pos} + 4 chars")
        elif line_text.startswith("## "):
            actual_text_area.tag_add('h2', current_pos, f"{current_pos} + 3 chars")
        elif line_text.startswith("# "):
            actual_text_area.tag_add('h1', current_pos, f"{current_pos} + 2 chars")
        # List items (simple version)
        elif re.match(r"^\s*[-*+]\s+", line_text) or re.match(r"^\s*\d+\.\s+", line_text):
            actual_text_area.tag_add('list_item', current_pos, line_end_pos)
        
        current_pos = actual_text_area.index(f"{line_end_pos} + 1 char")


    # Code Blocks (```python ... ``` or ``` ... ```)
    # This regex now captures the language hint (group 1) and the code content (group 2)
    code_block_pattern = re.compile(r'^```(\w*)\n(.*?)\n^```', re.DOTALL | re.MULTILINE | re.IGNORECASE)
    for match in code_block_pattern.finditer(text_content):
        lang_hint = match.group(1).lower().strip()
        code_content_raw = match.group(2)
        
        block_start_index_str = f"1.0 + {match.start()} chars"
        block_end_index_str = f"1.0 + {match.end()} chars"
        
        try:
            block_start_index = actual_text_area.index(block_start_index_str)
            block_end_index = actual_text_area.index(block_end_index_str)
        except tk.TclError: continue # Should not happen if text_content is consistent

        if block_start_index and block_end_index and actual_text_area.compare(block_start_index, '<', block_end_index):
            actual_text_area.tag_add('code_block', block_start_index, block_end_index)

            if lang_hint == 'python':
                # Apply Python syntax highlighting within this block
                # The content starts after the first line (```python)
                # and ends before the last line (```)
                code_text_start_offset = match.start(2) - match.start()
                code_text_end_offset = match.end(2) - match.start()

                python_code_start_index = actual_text_area.index(f"{block_start_index} + {code_text_start_offset} chars")
                python_code_end_index = actual_text_area.index(f"{block_start_index} + {code_text_end_offset} chars")
                
                highlight_python_syntax(actual_text_area, python_code_start_index, python_code_end_index)


    # Inline elements (bold, italic, inline_code) - process AFTER blocks to avoid conflict
    # And ensure they are not inside a code_block already (simple check, can be improved)
    inline_markdown_patterns = {
        'bold': (re.compile(r'\*\*(.+?)\*\*'), 2),  # Group 0 is full match, group 1 is content
        'italic': (re.compile(r'\*(.+?)\*'), 1),   # (excluding the markers themselves)
        'inline_code': (re.compile(r'`(.+?)`'), 1)
    }

    for tag_name, (pattern, content_group_idx) in inline_markdown_patterns.items():
        for match in pattern.finditer(text_content):
            try:
                match_outer_start_idx_str = f"1.0 + {match.start()} chars"
                match_outer_end_idx_str = f"1.0 + {match.end()} chars"

                match_outer_start_idx = actual_text_area.index(match_outer_start_idx_str)
                match_outer_end_idx = actual_text_area.index(match_outer_end_idx_str)
                
                # Check if this match is inside an already tagged code_block
                is_in_code_block = False
                check_idx = match_outer_start_idx
                while actual_text_area.compare(check_idx, "<", match_outer_end_idx):
                    if 'code_block' in actual_text_area.tag_names(check_idx):
                        is_in_code_block = True
                        break
                    check_idx = actual_text_area.index(f"{check_idx} + 1 char")
                
                if not is_in_code_block:
                    # Apply tag to the inner content
                    content_start_offset = match.start(content_group_idx) - match.start()
                    content_end_offset = match.end(content_group_idx) - match.start()

                    tag_start_idx = actual_text_area.index(f"{match_outer_start_idx} + {content_start_offset} chars")
                    tag_end_idx = actual_text_area.index(f"{match_outer_start_idx} + {content_end_offset} chars")

                    if actual_text_area.compare(tag_start_idx, "<", tag_end_idx):
                        actual_text_area.tag_add(tag_name, tag_start_idx, tag_end_idx)
            except tk.TclError: # Index errors
                continue
            except IndexError: # Regex group not found
                continue


    actual_text_area.configure(state='disabled')


def highlight_python_syntax(text_widget, start_index, end_index):
    """
    Applies basic Python syntax highlighting to the text_widget
    between start_index and end_index.
    This is a simplified regex-based highlighter. For production, use Pygments.
    """
    content = text_widget.get(start_index, end_index)

    # Order matters: comments first, then strings, then keywords, etc.
    
    # Comments
    for m in re.finditer(r"#.*$", content, re.MULTILINE):
        tag_start = text_widget.index(f"{start_index} + {m.start()} chars")
        tag_end = text_widget.index(f"{start_index} + {m.end()} chars")
        text_widget.tag_add("python_comment", tag_start, tag_end)

    # Strings (simple version: single, double, triple quotes)
    # This regex is basic and can be fooled by escaped quotes within strings.
    for m in re.finditer(r"('''[^'\\]*(?:\\.[^'\\]*)*'''|\"\"\"[^\"\\]*(?:\\.[^\"\\]*)*\"\"\"|'[^'\\]*(?:\\.[^'\\]*)*'|\"[^\"\\]*(?:\\.[^\"\\]*)*\")", content):
        tag_start = text_widget.index(f"{start_index} + {m.start()} chars")
        tag_end = text_widget.index(f"{start_index} + {m.end()} chars")
        text_widget.tag_add("python_string", tag_start, tag_end)
        # Prevent re-tagging parts of strings as keywords etc.
        text_widget.tag_lower("python_string", tag_start, tag_end) 


    # Keywords & Builtins (as whole words, not substrings)
    # And ensure they are not already part of a comment or string
    keyword_pattern_str = r"\b(" + "|".join(PYTHON_KEYWORDS) + r")\b"
    builtin_pattern_str = r"\b(" + "|".join(PYTHON_BUILTINS_FUNCTIONS) + r")\b(?=\s*\()" # Lookahead for (

    for pattern_str, tag_name in [(keyword_pattern_str, "python_keyword"), (builtin_pattern_str, "python_builtin")]:
        for m in re.finditer(pattern_str, content):
            tag_start = text_widget.index(f"{start_index} + {m.start()} chars")
            tag_end = text_widget.index(f"{start_index} + {m.end()} chars")
            
            # Check if already tagged as comment or string
            current_tags = text_widget.tag_names(tag_start)
            if "python_comment" not in current_tags and "python_string" not in current_tags:
                text_widget.tag_add(tag_name, tag_start, tag_end)
                text_widget.tag_lower(tag_name, tag_start, tag_end)


    # Numbers (integers, floats, hex)
    for m in re.finditer(r"\b(0[xX][0-9a-fA-F]+|\d*\.\d+|\d+\.?)\b", content):
        tag_start = text_widget.index(f"{start_index} + {m.start()} chars")
        tag_end = text_widget.index(f"{start_index} + {m.end()} chars")
        current_tags = text_widget.tag_names(tag_start)
        if "python_comment" not in current_tags and "python_string" not in current_tags and \
           "python_keyword" not in current_tags and "python_builtin" not in current_tags:
            text_widget.tag_add("python_number", tag_start, tag_end)
            text_widget.tag_lower("python_number", tag_start, tag_end)

    # Basic function definition names (def name(...))
    for m in re.finditer(r"def\s+([a-zA-Z_]\w*)\s*\(", content):
        # m.start(1) is the start of the function name
        fn_name_start_offset = m.start(1)
        fn_name_end_offset = m.end(1)
        tag_start = text_widget.index(f"{start_index} + {fn_name_start_offset} chars")
        tag_end = text_widget.index(f"{start_index} + {fn_name_end_offset} chars")
        current_tags = text_widget.tag_names(tag_start)
        if "python_comment" not in current_tags and "python_string" not in current_tags and \
           "python_keyword" not in current_tags : # Allow builtins to be func names
            text_widget.tag_add("python_function", tag_start, tag_end)
            text_widget.tag_lower("python_function", tag_start, tag_end)


def create_default_icon(): # Unchanged
    # ... (same as before) ...
    image = Image.new('RGB', (settings.DEFAULT_ICON_WIDTH, settings.DEFAULT_ICON_HEIGHT), color=settings.DEFAULT_ICON_BG_COLOR)
    d = ImageDraw.Draw(image)
    mx, my = settings.DEFAULT_ICON_WIDTH * 0.15, settings.DEFAULT_ICON_HEIGHT * 0.15
    d.rectangle([(mx, my), (settings.DEFAULT_ICON_WIDTH - mx, settings.DEFAULT_ICON_HEIGHT - my)], 
                outline=settings.DEFAULT_ICON_RECT_COLOR, width=settings.DEFAULT_ICON_RECT_WIDTH)
    pil_font = None; font_family_for_print = settings.DEFAULT_ICON_FONT_FAMILY
    try: pil_font = ImageFont.truetype(settings.DEFAULT_ICON_FONT_FAMILY.lower() + ".ttf", settings.DEFAULT_ICON_FONT_SIZE)
    except IOError:
        try: pil_font = ImageFont.truetype("arial.ttf", settings.DEFAULT_ICON_FONT_SIZE); font_family_for_print = "Arial (fallback)"
        except IOError: pil_font = ImageFont.load_default(); font_family_for_print = "Pillow default"
    try:
        bbox = d.textbbox((0,0), settings.DEFAULT_ICON_TEXT, font=pil_font) # Pillow 9+
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx, ty = (settings.DEFAULT_ICON_WIDTH - text_width) / 2 - bbox[0], (settings.DEFAULT_ICON_HEIGHT - text_height) / 2 - bbox[1]
    except AttributeError: # Fallback for older Pillow (textsize) or if textbbox fails
        try: # Older Pillow textsize
            text_width, text_height = d.textsize(settings.DEFAULT_ICON_TEXT, font=pil_font)
            tx, ty = (settings.DEFAULT_ICON_WIDTH - text_width) / 2, (settings.DEFAULT_ICON_HEIGHT - text_height) / 2
        except Exception: # Ultimate fallback if all else fails
            char_w = settings.DEFAULT_ICON_FONT_SIZE * 0.6; char_h = settings.DEFAULT_ICON_FONT_SIZE
            text_width_approx = char_w * len(settings.DEFAULT_ICON_TEXT)
            tx = (settings.DEFAULT_ICON_WIDTH - text_width_approx) / 2
            ty = (settings.DEFAULT_ICON_HEIGHT - char_h) / 2.5 
            if not pil_font: pil_font = ImageFont.load_default()
    d.text((tx, ty), settings.DEFAULT_ICON_TEXT, fill=settings.DEFAULT_ICON_TEXT_COLOR, font=pil_font)
    return image