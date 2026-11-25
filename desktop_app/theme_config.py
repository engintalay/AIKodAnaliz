"""Theme configuration for the desktop app.

Edit the colors in this file to quickly restyle the UI.
All values should be hex strings in the form "#RRGGBB".
"""

APP_FONT_FAMILY = "Segoe UI, Inter, Arial, sans-serif"
MONO_FONT_FAMILY = "Consolas, JetBrains Mono, Courier New, monospace"

# Core surfaces
COLOR_BG = "#0B1220"
COLOR_SURFACE = "#121C2E"
COLOR_PANEL = "#172338"
COLOR_CARD = "#1D2B44"
COLOR_BORDER = "#31415F"

# Accent and semantic colors
COLOR_ACCENT = "#1FA187"
COLOR_ACCENT_LIGHT = "#5EEAD4"
COLOR_ACCENT_HOVER = "#158F78"
COLOR_BLUE = "#60A5FA"
COLOR_GREEN = "#34D399"
COLOR_ORANGE = "#F59E0B"
COLOR_RED = "#F87171"

# Message surfaces
COLOR_USER_BG = "#214F86"
COLOR_AI_BG = "#14233A"
COLOR_SYS_BG = "#1B2940"

# Text colors
COLOR_TEXT = "#F8FAFC"
COLOR_TEXT_SECONDARY = "#D2DAE8"
COLOR_TEXT_MUTED = "#97A6BA"

# Code blocks / markdown
COLOR_CODE_BG = "#09111D"
COLOR_CODE_TEXT = "#93C5FD"
COLOR_PRE_BG = "#060C16"
COLOR_PRE_TEXT = "#E5EDF7"


def with_alpha(hex_color: str, alpha: str) -> str:
    """Append a 2-digit alpha channel to a #RRGGBB color."""
    return f"{hex_color}{alpha}"