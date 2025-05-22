# ui_utils.py
import logging
import tkinter as tk
from tkinter import font as tkFont, scrolledtext
import re
from PIL import Image, ImageDraw, ImageFont

# Initialize logger for this module
logger = logging.getLogger(__name__)

try:
    import screener.settings as settings
    T = settings.T
except ImportError as e:
    try:
        fallback_logger = logging.getLogger("ui_utils_fallback")
        fallback_logger.critical("FATAL ERROR: Could not import 'settings' in ui_utils.py. Using fallback T and settings.", exc_info=True)
    except Exception:
        print(f"FATAL ERROR (no logger): Could not import 'settings' in ui_utils.py: {e}")

    def T_fallback(key, lang='en'): return f"<{key} (ui_utils fallback)>"
    T = T_fallback

    class settings_fallback_ui:
        CODE_FONT_FAMILY = 'Courier New'
        MIN_FONT_SIZE = 8
        CODE_FONT_SIZE_OFFSET = -1
        DEFAULT_ICON_WIDTH = 64; DEFAULT_ICON_HEIGHT = 64
        DEFAULT_ICON_BG_COLOR = 'dimgray'; DEFAULT_ICON_RECT_COLOR = 'dodgerblue'
        DEFAULT_ICON_RECT_WIDTH = 4; DEFAULT_ICON_FONT_FAMILY = 'Arial'
        DEFAULT_ICON_FONT_SIZE = 30; DEFAULT_ICON_TEXT = 'S'; DEFAULT_ICON_TEXT_COLOR = 'white'
        CURRENT_THEME = 'light'
        THEME_COLORS = {
            'light': {
                'code_block_bg': '#f0f0f0', 'code_block_fg': '#000000', 'code_block_border': '#CCCCCC',
                'md_h1_fg': '#000080', 'md_h2_fg': '#00008B', 'md_list_item_fg': '#228B22',
                'md_inline_code_bg': '#E0E0E0', 'md_inline_code_fg': '#C7254E',
                'pygments_text_fg': '#000000', 'pygments_keyword_fg': '#0000FF',
                'pygments_keyword_constant_fg': '#AA22FF', 'pygments_keyword_namespace_fg': '#0077AA',
                'pygments_name_fg': '#000000', 'pygments_name_function_fg': '#795E26',
                'pygments_name_class_fg': '#267F99', 'pygments_name_builtin_fg': '#AA22FF',
                'pygments_name_decorator_fg': '#795E26', 'pygments_string_fg': '#008000',
                'pygments_string_doc_fg': '#808080', 'pygments_comment_fg': '#808080',
                'pygments_number_fg': '#A52A2A', 'pygments_operator_fg': '#555555',
                'pygments_punctuation_fg': '#000000', 'pygments_error_fg': '#FF0000',
            },
            'dark': {
                'code_block_bg': '#1e1e1e', 'code_block_fg': '#D4D4D4', 'code_block_border': '#444444',
                'md_h1_fg': '#569CD6', 'md_h2_fg': '#4EC9B0', 'md_list_item_fg': '#B5CEA8',
                'md_inline_code_bg': '#3A3A3A', 'md_inline_code_fg': '#D69D85',
                'pygments_text_fg': '#D4D4D4', 'pygments_keyword_fg': '#569CD6',
                'pygments_keyword_constant_fg': '#C586C0', 'pygments_keyword_namespace_fg': '#4EC9B0',
                'pygments_name_fg': '#D4D4D4', 'pygments_name_function_fg': '#DCDCAA',
                'pygments_name_class_fg': '#4EC9B0', 'pygments_name_builtin_fg': '#C586C0',
                'pygments_name_decorator_fg': '#DCDCAA', 'pygments_string_fg': '#CE9178',
                'pygments_string_doc_fg': '#6A9955', 'pygments_comment_fg': '#6A9955',
                'pygments_number_fg': '#B5CEA8', 'pygments_operator_fg': '#D4D4D4',
                'pygments_punctuation_fg': '#D4D4D4', 'pygments_error_fg': '#F44747',
            }
        }
        def get_theme_color(self, key, theme=None):
            actual_theme_name = theme if theme else self.CURRENT_THEME
            theme_dict = self.THEME_COLORS.get(actual_theme_name, self.THEME_COLORS['light'])
            color = theme_dict.get(key)
            if color is None:
                color = self.THEME_COLORS['light'].get(key, '#FF00FF') 
            return color
    settings = settings_fallback_ui()
    logger.info("ui_utils.py: Using fallback settings and T function.")


try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name, guess_lexer, PythonLexer
    from pygments.token import Token, Name, Keyword, String, Comment, Number, Operator, Punctuation, Error, Generic
    # For a more comprehensive list, you might use STANDARD_TYPES, but direct mapping is often clearer.
    PYGMENTS_AVAILABLE = True
    logger.debug("Pygments library loaded successfully.")
except ImportError:
    PYGMENTS_AVAILABLE = False
    logger.info("Pygments library not found. Python syntax highlighting will be basic or disabled.")


# Map Pygments token types to Tkinter tag names and style attributes
# This map helps in configuring tags and applying them.
# The 'font_style' can be 'normal', 'bold', 'italic', 'bold italic'.
PYGMENTS_TOKEN_STYLE_MAP = {
    Token: {'tag': 'pygments_text', 'color_key': 'pygments_text_fg'}, # Default for all text
    Keyword: {'tag': 'pygments_keyword', 'color_key': 'pygments_keyword_fg'},
    Keyword.Constant: {'tag': 'pygments_keyword_constant', 'color_key': 'pygments_keyword_constant_fg'},
    Keyword.Namespace: {'tag': 'pygments_keyword_namespace', 'color_key': 'pygments_keyword_namespace_fg'},
    
    Name: {'tag': 'pygments_name', 'color_key': 'pygments_name_fg'},
    Name.Function: {'tag': 'pygments_name_function', 'color_key': 'pygments_name_function_fg'},
    Name.Class: {'tag': 'pygments_name_class', 'color_key': 'pygments_name_class_fg'},
    Name.Builtin: {'tag': 'pygments_name_builtin', 'color_key': 'pygments_name_builtin_fg'},
    Name.Decorator: {'tag': 'pygments_name_decorator', 'color_key': 'pygments_name_decorator_fg'},
    
    String: {'tag': 'pygments_string', 'color_key': 'pygments_string_fg'},
    String.Doc: {'tag': 'pygments_string_doc', 'color_key': 'pygments_string_doc_fg', 'font_style': 'italic'},
    
    Comment: {'tag': 'pygments_comment', 'color_key': 'pygments_comment_fg', 'font_style': 'italic'},
    Comment.Single: {'tag': 'pygments_comment', 'color_key': 'pygments_comment_fg', 'font_style': 'italic'}, # Inherits
    Comment.Multiline: {'tag': 'pygments_comment', 'color_key': 'pygments_comment_fg', 'font_style': 'italic'}, # Inherits

    Number: {'tag': 'pygments_number', 'color_key': 'pygments_number_fg'},
    Operator: {'tag': 'pygments_operator', 'color_key': 'pygments_operator_fg'},
    Punctuation: {'tag': 'pygments_punctuation', 'color_key': 'pygments_punctuation_fg'},
    
    Error: {'tag': 'pygments_error', 'color_key': 'pygments_error_fg', 'underline': True},

    # Generic tokens often used by formatters for things like diffs, less common in pure syntax highlighting
    Generic.Heading: {'tag': 'pygments_generic_heading', 'color_key': 'pygments_generic_heading_fg', 'font_style': 'bold'},
    Generic.Subheading: {'tag': 'pygments_generic_subheading', 'color_key': 'pygments_generic_subheading_fg', 'font_style': 'bold'},
    Generic.Deleted: {'tag': 'pygments_generic_deleted', 'color_key': 'pygments_generic_deleted_fg'},
    Generic.Inserted: {'tag': 'pygments_generic_inserted', 'color_key': 'pygments_generic_inserted_fg'},
    Generic.Traceback: {'tag': 'pygments_generic_traceback', 'color_key': 'pygments_generic_traceback_fg'},
}


def highlight_python_syntax_pygments(text_widget, code_block_text_content, code_block_tk_start_index):
    """
    Applies Python syntax highlighting using Pygments to a Tkinter Text widget.
    Args:
        text_widget: The Tkinter Text widget.
        code_block_text_content: The raw Python code string.
        code_block_tk_start_index: The Tkinter index (e.g., "3.14") where this code block starts in the text_widget.
    """
    if not PYGMENTS_AVAILABLE:
        logger.debug("Pygments not available, Python highlighting skipped for block starting at %s.", code_block_tk_start_index)
        return

    logger.debug("Applying Pygments Python syntax highlighting for block at %s.", code_block_tk_start_index)
    try:
        lexer = PythonLexer(stripnl=False, stripall=False, ensurenl=False)
    except Exception as e_lexer:
        logger.warning(f"Could not get Pygments Python lexer: {e_lexer}. Python highlighting will be skipped.", exc_info=True)
        return

    current_char_offset_in_snippet = 0
    for ttype, tvalue in lexer.get_tokens(code_block_text_content):
        style_info = None
        current_lookup_ttype = ttype
        while current_lookup_ttype is not None: # Iterate up the token hierarchy (e.g., Token.Keyword.Constant -> Token.Keyword -> Token)
            if current_lookup_ttype in PYGMENTS_TOKEN_STYLE_MAP:
                style_info = PYGMENTS_TOKEN_STYLE_MAP[current_lookup_ttype]
                break
            current_lookup_ttype = current_lookup_ttype.parent
        
        if style_info:
            tag_name = style_info['tag']
            token_start_in_widget = text_widget.index(f"{code_block_tk_start_index} + {current_char_offset_in_snippet} chars")
            token_end_in_widget = text_widget.index(f"{token_start_in_widget} + {len(tvalue)} chars")
            
            try:
                # Check if tag exists; it should have been configured in apply_formatting_tags
                if tag_name in text_widget.tag_names():
                    text_widget.tag_add(tag_name, token_start_in_widget, token_end_in_widget)
                else:
                    logger.warning("Pygments tag '%s' not configured in text widget. Skipping for token type %s.", tag_name, ttype)
            except tk.TclError as e_tag_add:
                logger.error("TclError adding Pygments tag '%s' from %s to %s: %s", 
                             tag_name, token_start_in_widget, token_end_in_widget, e_tag_add, exc_info=False)

        current_char_offset_in_snippet += len(tvalue)
    logger.debug("Pygments highlighting applied for block at %s.", code_block_tk_start_index)


def apply_formatting_tags(text_widget, text_content, initial_font_size):
    """
    Applies Markdown-like and Python syntax highlighting tags to a Tkinter Text widget.
    """
    if not text_widget or not text_widget.winfo_exists():
        logger.warning("apply_formatting_tags: text_widget is invalid or destroyed. Aborting.")
        return

    logger.debug("Applying formatting tags. Initial font size: %spt, Text length: %d",
                 initial_font_size, len(text_content or ""))

    actual_text_area = text_widget

    try:
        actual_text_area.configure(state='normal')
        actual_text_area.delete('1.0', tk.END)
        actual_text_area.insert('1.0', text_content)

        base_font_obj = tkFont.Font(font=actual_text_area['font'])
        base_family = base_font_obj.actual()['family']
        
        code_family = settings.CODE_FONT_FAMILY
        try:
            tkFont.Font(family=settings.CODE_FONT_FAMILY, size=initial_font_size)
        except tk.TclError:
            logger.warning("Specified CODE_FONT_FAMILY '%s' not found. Falling back to base font family '%s'.",
                           settings.CODE_FONT_FAMILY, base_family)
            code_family = base_family

        actual_text_area.tag_configure('bold', font=(base_family, initial_font_size, 'bold'))
        actual_text_area.tag_configure('italic', font=(base_family, initial_font_size, 'italic'))
        actual_text_area.tag_configure('h1', font=(base_family, initial_font_size + 4, 'bold'),
                                     foreground=settings.get_theme_color('md_h1_fg'))
        actual_text_area.tag_configure('h2', font=(base_family, initial_font_size + 2, 'bold'),
                                     foreground=settings.get_theme_color('md_h2_fg'))
        actual_text_area.tag_configure('h3', font=(base_family, initial_font_size + 1, 'bold'))
        actual_text_area.tag_configure('list_item', foreground=settings.get_theme_color('md_list_item_fg'))
        
        inline_code_font_size = max(settings.MIN_FONT_SIZE, initial_font_size -1)
        actual_text_area.tag_configure('inline_code', font=(code_family, inline_code_font_size),
                                     background=settings.get_theme_color('md_inline_code_bg'),
                                     foreground=settings.get_theme_color('md_inline_code_fg'))

        code_font_size = max(settings.MIN_FONT_SIZE, initial_font_size + settings.CODE_FONT_SIZE_OFFSET)
        code_block_tag_config = {
            'background': settings.get_theme_color('code_block_bg'),
            'foreground': settings.get_theme_color('code_block_fg'), # This is the default for code block text
            'font': (code_family, code_font_size, 'normal'),
            'wrap': tk.WORD, 'lmargin1': 10, 'lmargin2': 10, 'rmargin': 10,
            'spacing1': 5, 'spacing3': 5, 'relief': tk.SOLID, 'borderwidth': 1,
        }
        actual_text_area.tag_configure('code_block', **code_block_tag_config)

        # --- Configure Pygments Tags ---
        if PYGMENTS_AVAILABLE:
            for token_type, style_info in PYGMENTS_TOKEN_STYLE_MAP.items():
                tag_name = style_info['tag']
                tag_config = {}
                
                color_key = style_info.get('color_key')
                if color_key:
                    tag_config['foreground'] = settings.get_theme_color(color_key)
                
                font_style_str = style_info.get('font_style', 'normal') # 'normal', 'bold', 'italic', 'bold italic'
                # Ensure font config uses the code_family and code_font_size for Pygments tags
                tag_config['font'] = (code_family, code_font_size, font_style_str)

                if style_info.get('underline'):
                    tag_config['underline'] = True
                
                if style_info.get('background_key'): # For tokens that need specific background
                     tag_config['background'] = settings.get_theme_color(style_info['background_key'])

                if tag_config: # Only configure if there are properties to set
                    actual_text_area.tag_configure(tag_name, **tag_config)
            logger.debug("Pygments tags configured in text_widget.")


        current_pos = "1.0"
        while actual_text_area.compare(current_pos, "<", "end"):
            line_end_pos = actual_text_area.index(f"{current_pos} lineend")
            line_text = actual_text_area.get(current_pos, line_end_pos)
            if line_text.startswith("### "): actual_text_area.tag_add('h3', current_pos, f"{current_pos} + 4 chars")
            elif line_text.startswith("## "): actual_text_area.tag_add('h2', current_pos, f"{current_pos} + 3 chars")
            elif line_text.startswith("# "): actual_text_area.tag_add('h1', current_pos, f"{current_pos} + 2 chars")
            elif re.match(r"^\s*([-*+]|\d+\.)\s+", line_text): actual_text_area.tag_add('list_item', current_pos, line_end_pos)
            current_pos = actual_text_area.index(f"{line_end_pos} + 1 char")

        code_block_pattern = re.compile(r'^```(\w*)\n(.*?)\n^```', re.DOTALL | re.MULTILINE)
        for match in code_block_pattern.finditer(text_content):
            lang_hint = match.group(1).lower().strip()
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

                if lang_hint == 'python' and PYGMENTS_AVAILABLE:
                    code_content_for_pygments = match.group(2)
                    # Start index of the actual code content (after ```python\n) within the Text widget
                    python_code_tk_start_index = actual_text_area.index(f"{block_start_index} + {match.start(2) - match.start(0)} chars")
                    highlight_python_syntax_pygments(actual_text_area, code_content_for_pygments, python_code_tk_start_index)
                elif lang_hint == 'python': # Pygments not available or other language
                    logger.debug("Pygments not available or lang '%s' not Python, using default code_block styling.", lang_hint)
            else:
                logger.debug("Code block indices are invalid or empty.")

        inline_markdown_patterns = {
            'bold': (re.compile(r'\*\*(.+?)\*\*'), 1),
            'italic': (re.compile(r'\*(.+?)\*'), 1),
            'inline_code': (re.compile(r'`(.+?)`'), 1)
        }
        for tag_name, (pattern, content_group_idx) in inline_markdown_patterns.items():
            for match in pattern.finditer(text_content):
                try:
                    match_outer_start_idx_str = f"1.0 + {match.start(0)} chars"
                    match_outer_start_idx = actual_text_area.index(match_outer_start_idx_str)
                    
                    check_idx_str = f"1.0 + {(match.start(0) + match.end(0)) // 2} chars"
                    check_idx = actual_text_area.index(check_idx_str)
                    if 'code_block' in actual_text_area.tag_names(check_idx): continue
                    
                    content_start_offset_in_match = match.start(content_group_idx) - match.start(0)
                    content_end_offset_in_match = match.end(content_group_idx) - match.start(0)
                    tag_start_idx = actual_text_area.index(f"{match_outer_start_idx} + {content_start_offset_in_match} chars")
                    tag_end_idx = actual_text_area.index(f"{match_outer_start_idx} + {content_end_offset_in_match} chars")

                    if actual_text_area.compare(tag_start_idx, "<", tag_end_idx):
                        actual_text_area.tag_add(tag_name, tag_start_idx, tag_end_idx)
                except (tk.TclError, IndexError) as e:
                    logger.warning("Error applying inline markdown tag '%s': %s. Match: '%s'", tag_name, e, match.group(0), exc_info=False)
                    continue
        
        actual_text_area.configure(state='disabled')
        logger.debug("Formatting tags applied successfully.")

    except Exception as e:
        logger.error("Unexpected error in apply_formatting_tags.", exc_info=True)
        try:
            if actual_text_area and actual_text_area.winfo_exists():
                actual_text_area.delete('1.0', tk.END)
                actual_text_area.insert('1.0', text_content or "Error displaying content.")
                actual_text_area.configure(state='disabled')
        except Exception as e_fallback:
            logger.error("Error during fallback content display in apply_formatting_tags: %s", e_fallback, exc_info=True)

# Removed old highlight_python_syntax and related PYTHON_KEYWORDS, PYTHON_BUILTINS_FUNCTIONS

def create_default_icon():
    """Creates a default PIL Image object to be used as a fallback tray icon."""
    logger.debug("Creating default PIL icon image.")
    try:
        image = Image.new('RGB', (settings.DEFAULT_ICON_WIDTH, settings.DEFAULT_ICON_HEIGHT),
                          color=settings.DEFAULT_ICON_BG_COLOR)
        d = ImageDraw.Draw(image)
        
        mx, my = settings.DEFAULT_ICON_WIDTH * 0.15, settings.DEFAULT_ICON_HEIGHT * 0.15
        d.rectangle([(mx, my), (settings.DEFAULT_ICON_WIDTH - mx, settings.DEFAULT_ICON_HEIGHT - my)],
                    outline=settings.DEFAULT_ICON_RECT_COLOR, width=int(settings.DEFAULT_ICON_RECT_WIDTH))

        pil_font = None; font_family_for_log = settings.DEFAULT_ICON_FONT_FAMILY
        try:
            font_path_ttf = settings.DEFAULT_ICON_FONT_FAMILY.lower()
            if not font_path_ttf.endswith((".ttf", ".otf")): font_path_ttf += ".ttf"
            pil_font = ImageFont.truetype(font_path_ttf, settings.DEFAULT_ICON_FONT_SIZE)
        except IOError:
            logger.warning("Failed to load default icon font '%s'. Trying 'arial.ttf'.", font_family_for_log)
            try:
                pil_font = ImageFont.truetype("arial.ttf", settings.DEFAULT_ICON_FONT_SIZE)
                font_family_for_log = "Arial (fallback)"
            except IOError:
                logger.warning("Failed to load 'arial.ttf' for default icon. Using Pillow's load_default().")
                pil_font = ImageFont.load_default()
                font_family_for_log = "Pillow default"
        
        text_to_draw = settings.DEFAULT_ICON_TEXT
        text_fill_color = settings.DEFAULT_ICON_TEXT_COLOR
        
        try:
            bbox = d.textbbox((0,0), text_to_draw, font=pil_font, anchor="lt")
            text_width = bbox[2] - bbox[0]; text_height = bbox[3] - bbox[1]
            tx = (settings.DEFAULT_ICON_WIDTH - text_width) / 2
            ty = (settings.DEFAULT_ICON_HEIGHT - text_height) / 2 - bbox[1]
        except AttributeError:
            logger.debug("textbbox not available, using textsize for default icon text positioning.")
            try: text_width, text_height = d.textsize(text_to_draw, font=pil_font)
            except TypeError:
                text_width = len(text_to_draw) * settings.DEFAULT_ICON_FONT_SIZE * 0.6
                text_height = settings.DEFAULT_ICON_FONT_SIZE
            tx = (settings.DEFAULT_ICON_WIDTH - text_width) / 2
            ty = (settings.DEFAULT_ICON_HEIGHT - text_height) / 2
        except Exception as e_text_pos:
             logger.error("Error during text positioning for default icon: %s. Approximating.", e_text_pos, exc_info=True)
             tx = settings.DEFAULT_ICON_WIDTH * 0.25; ty = settings.DEFAULT_ICON_HEIGHT * 0.25

        d.text((tx, ty), text_to_draw, fill=text_fill_color, font=pil_font)
        logger.info("Default icon created successfully with font: %s", font_family_for_log)
        return image
    except Exception as e:
        logger.error("Failed to create default icon image.", exc_info=True)
        try:
            img = Image.new('RGB', (64, 64), 'gray')
            ImageDraw.Draw(img).text((10, 10), "ERR", fill="red")
            return img
        except Exception: return None