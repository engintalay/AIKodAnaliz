"""Desktop app stylesheet.

Color values are loaded from desktop_app.theme_config so the palette can be
customized from a single file.
"""

from desktop_app.theme_config import (
    APP_FONT_FAMILY,
    MONO_FONT_FAMILY,
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_LIGHT,
    COLOR_AI_BG,
    COLOR_BG,
    COLOR_BLUE,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CODE_BG,
    COLOR_CODE_TEXT,
    COLOR_GREEN,
    COLOR_ORANGE,
    COLOR_PANEL,
    COLOR_PRE_BG,
    COLOR_PRE_TEXT,
    COLOR_RED,
    COLOR_SURFACE,
    COLOR_SYS_BG,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SECONDARY,
    COLOR_USER_BG,
    with_alpha,
)

C_BG = COLOR_BG
C_SURFACE = COLOR_SURFACE
C_PANEL = COLOR_PANEL
C_CARD = COLOR_CARD
C_BORDER = COLOR_BORDER
C_ACCENT = COLOR_ACCENT
C_ACCENT_LIGHT = COLOR_ACCENT_LIGHT
C_ACCENT_HOVER = COLOR_ACCENT_HOVER
C_USER_BG = COLOR_USER_BG
C_AI_BG = COLOR_AI_BG
C_SYS_BG = COLOR_SYS_BG
C_TEXT = COLOR_TEXT
C_TEXT_SECONDARY = COLOR_TEXT_SECONDARY
C_TEXT_MUTED = COLOR_TEXT_MUTED
C_GREEN = COLOR_GREEN
C_RED = COLOR_RED
C_ORANGE = COLOR_ORANGE
C_BLUE = COLOR_BLUE
C_SELECTION = with_alpha(C_ACCENT, "44")

ACCENT_SOFT = with_alpha(C_ACCENT, "24")
ACCENT_BORDER = with_alpha(C_ACCENT, "66")
ACCENT_FAINT = with_alpha(C_ACCENT, "14")
CARD_STRIPE = with_alpha(C_CARD, "66")

MAIN_STYLE = f"""
/* ─── Global ─────────────────────────────────────────── */
QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: {APP_FONT_FAMILY};
    font-size: 13px;
}}

QMainWindow {{
    background-color: {C_BG};
}}

/* ─── Title Bar (fake) ────────────────────────────────── */
#titleBar {{
    background-color: {C_SURFACE};
    border-bottom: 1px solid {C_BORDER};
}}

#titleLabel {{
    color: {C_TEXT};
    font-size: 15px;
    font-weight: bold;
    letter-spacing: 0.5px;
}}

#statusIndicator {{
    font-size: 11px;
    color: {C_TEXT_MUTED};
}}

/* ─── Sidebar ────────────────────────────────────────── */
#sidebar {{
    background-color: {C_SURFACE};
    border-right: 1px solid {C_BORDER};
}}

#sidebarTitle {{
    color: {C_TEXT_SECONDARY};
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}

#projectList {{
    background-color: transparent;
    border: none;
    outline: none;
}}

#projectList::item {{
    background-color: transparent;
    border-radius: 6px;
    padding: 8px 10px;
    margin: 1px 4px;
    color: {C_TEXT_SECONDARY};
}}

#projectList::item:hover {{
    background-color: {C_CARD};
    color: {C_TEXT};
}}

#projectList::item:selected {{
    background-color: {ACCENT_SOFT};
    color: {C_TEXT};
    border: 1px solid {ACCENT_BORDER};
}}

#serverUrlEdit {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {C_TEXT};
    font-size: 11px;
}}

#serverUrlEdit:focus {{
    border: 1px solid {C_ACCENT};
}}

/* ─── Chat Area ──────────────────────────────────────── */
#chatArea {{
    background-color: {C_BG};
    border: none;
}}

#chatScrollArea {{
    background-color: {C_BG};
    border: none;
}}

#chatScrollArea QScrollBar:vertical {{
    background: {C_SURFACE};
    width: 6px;
    border-radius: 3px;
    margin: 0;
}}

#chatScrollArea QScrollBar::handle:vertical {{
    background: {C_BORDER};
    border-radius: 3px;
    min-height: 30px;
}}

#chatScrollArea QScrollBar::handle:vertical:hover {{
    background: {C_ACCENT};
}}

#chatScrollArea QScrollBar::add-line:vertical,
#chatScrollArea QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ─── Message Bubbles ────────────────────────────────── */
#userBubble {{
    background-color: {C_USER_BG};
    border-radius: 14px;
    border-bottom-right-radius: 4px;
}}

#aiBubble {{
    background-color: {C_AI_BG};
    border-radius: 14px;
    border-bottom-left-radius: 4px;
    border: 1px solid {CARD_STRIPE};
}}

#sysBubble {{
    background-color: transparent;
}}

#aiAvatarLabel {{
    background-color: {ACCENT_SOFT};
    border-radius: 14px;
    color: {C_TEXT};
    font-size: 15px;
    font-weight: bold;
}}

#userAvatarLabel {{
    background-color: {C_USER_BG};
    border-radius: 14px;
    color: {C_TEXT_SECONDARY};
    font-size: 15px;
}}

#aiProjectTag {{
    color: {C_ACCENT_LIGHT};
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.5px;
}}

#messageTime {{
    color: {C_TEXT_MUTED};
    font-size: 10px;
}}

#sysMessageLabel {{
    color: {C_TEXT_MUTED};
    font-size: 11px;
    font-style: italic;
}}

/* ─── Input Area ─────────────────────────────────────── */
#inputArea {{
    background-color: {C_SURFACE};
    border-top: 1px solid {C_BORDER};
}}

#messageInput {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 10px 14px;
    color: {C_TEXT};
    font-size: 13px;
    selection-background-color: {ACCENT_BORDER};
}}

#messageInput:focus {{
    border: 1px solid {C_ACCENT};
    background-color: {C_PANEL};
}}

#messageInput:disabled {{
    color: {C_TEXT_MUTED};
    background-color: {C_SURFACE};
}}

/* ─── Buttons ────────────────────────────────────────── */
#sendButton {{
    background-color: {C_ACCENT};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: bold;
    min-width: 80px;
}}

#sendButton:hover {{
    background-color: {C_ACCENT_LIGHT};
}}

#sendButton:pressed {{
    background-color: {C_ACCENT_HOVER};
}}

#sendButton:disabled {{
    background-color: {C_BORDER};
    color: {C_TEXT_MUTED};
}}

#refreshButton, #logoutButton, #settingsButton {{
    background-color: transparent;
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    color: {C_TEXT_SECONDARY};
    font-size: 12px;
}}

#refreshButton:hover, #logoutButton:hover, #settingsButton:hover {{
    background-color: {C_CARD};
    border-color: {C_ACCENT};
    color: {C_TEXT};
}}

#clearButton {{
    background-color: transparent;
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    color: {C_TEXT_MUTED};
    font-size: 11px;
}}

#clearButton:hover {{
    border-color: {C_RED};
    color: {C_RED};
}}

#exportButton, #importButton {{
    background-color: transparent;
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {C_TEXT_MUTED};
    font-size: 11px;
}}

#exportButton:hover {{
    border-color: {C_ACCENT};
    color: {C_TEXT};
    background-color: {C_CARD};
}}

#importButton:hover {{
    border-color: {C_ACCENT};
    color: {C_TEXT};
    background-color: {C_CARD};
}}

/* ─── Login Dialog ───────────────────────────────────── */
#loginDialog {{
    background-color: {C_SURFACE};
}}

#loginCard {{
    background-color: {C_PANEL};
    border-radius: 20px;
    border: 1px solid {C_BORDER};
}}

#loginTitle {{
    color: {C_TEXT};
    font-size: 28px;
    font-weight: bold;
}}

#loginSubtitle {{
    color: {C_TEXT_SECONDARY};
    font-size: 14px;
}}

#loginField {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 12px 16px;
    min-height: 26px;
    color: {C_TEXT};
    font-size: 14px;
}}

#loginField:focus {{
    border: 1px solid {C_ACCENT};
}}

#loginButton {{
    background-color: {C_ACCENT};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 14px;
    min-height: 28px;
    font-size: 15px;
    font-weight: bold;
}}

#loginButton:hover {{
    background-color: {C_ACCENT_LIGHT};
}}

#loginButton:pressed {{
    background-color: {C_ACCENT_HOVER};
}}

#loginButton:disabled {{
    background-color: {C_BORDER};
    color: {C_TEXT_MUTED};
}}

#loginError {{
    color: {C_RED};
    font-size: 12px;
}}

#loginServerField {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 12px 16px;
    min-height: 24px;
    color: {C_TEXT};
    font-size: 13px;
}}

#loginServerField:focus {{
    border: 1px solid {C_ACCENT};
    color: {C_TEXT};
}}

/* ─── Misc ───────────────────────────────────────────── */
QLabel {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background: {C_SURFACE};
    width: 6px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {C_BORDER};
    border-radius: 3px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {C_ACCENT};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    height: 0;
}}

QToolTip {{
    background-color: {C_CARD};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}

#typingIndicator {{
    color: {C_ACCENT_LIGHT};
    font-size: 12px;
    font-style: italic;
}}

#welcomeTitle {{
    color: {C_ACCENT_LIGHT};
    font-size: 24px;
    font-weight: bold;
}}

#welcomeSubtitle {{
    color: {C_TEXT_SECONDARY};
    font-size: 14px;
}}

#welcomeHint {{
    color: {C_TEXT_MUTED};
    font-size: 12px;
}}

#projectBadge {{
    background-color: {ACCENT_SOFT};
    color: {C_TEXT};
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: bold;
}}

#emptyLabel {{
    color: {C_TEXT_MUTED};
    font-size: 13px;
}}
"""

# HTML template for chat messages
MESSAGE_HTML_STYLE = f"""
<style>
body {{
    margin: 0; padding: 0;
    background: transparent;
    color: {C_TEXT};
    font-family: {APP_FONT_FAMILY};
    font-size: 13px;
    line-height: 1.6;
}}
p {{ margin: 0 0 8px 0; }}
p:last-child {{ margin-bottom: 0; }}
h1, h2, h3, h4 {{
    color: {C_ACCENT_LIGHT};
    margin: 12px 0 6px 0;
    font-weight: bold;
}}
h1 {{ font-size: 18px; }}
h2 {{ font-size: 16px; }}
h3 {{ font-size: 14px; }}
code {{
    background-color: {COLOR_CODE_BG};
    color: {COLOR_CODE_TEXT};
    border-radius: 4px;
    padding: 1px 5px;
    font-family: {MONO_FONT_FAMILY};
    font-size: 12px;
}}
pre {{
    background-color: {COLOR_PRE_BG};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 14px 16px;
    overflow-x: auto;
    margin: 10px 0;
}}
pre code {{
    background: transparent;
    padding: 0;
    color: {COLOR_PRE_TEXT};
    font-size: 12px;
    line-height: 1.5;
}}
ul, ol {{ margin: 6px 0 6px 20px; padding: 0; }}
li {{ margin: 3px 0; }}
blockquote {{
    border-left: 3px solid {C_ACCENT};
    margin: 8px 0;
    padding: 4px 12px;
    color: {C_TEXT_SECONDARY};
    background-color: {ACCENT_FAINT};
    border-radius: 0 6px 6px 0;
}}
strong {{ color: {C_TEXT}; font-weight: bold; }}
em {{ color: {C_TEXT_SECONDARY}; }}
a {{ color: {C_ACCENT_LIGHT}; text-decoration: none; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th {{
    background-color: {ACCENT_SOFT};
    color: {C_TEXT};
    padding: 6px 12px;
    border: 1px solid {C_BORDER};
    text-align: left;
}}
td {{
    padding: 5px 12px;
    border: 1px solid {C_BORDER};
    color: {C_TEXT_SECONDARY};
}}
tr:nth-child(even) td {{ background-color: {CARD_STRIPE}; }}
hr {{ border: none; border-top: 1px solid {C_BORDER}; margin: 12px 0; }}
</style>
"""
