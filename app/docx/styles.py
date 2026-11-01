"""Document styling, color palettes, and typographic formatting.

Applies clean management consulting visual standards using python-docx.
"""

from typing import Any

from docx.shared import Inches, Pt, RGBColor

# Executive Consulting Color Palette
COLOR_PRIMARY_NAVY = RGBColor(15, 37, 55)  # #0F2537
COLOR_SECONDARY_BLUE = RGBColor(27, 54, 93)  # #1B365D
COLOR_ACCENT_TEAL = RGBColor(0, 128, 128)  # #008080
COLOR_BODY_CHARCOAL = RGBColor(45, 45, 45)  # #2D2D2D
COLOR_MUTED_GRAY = RGBColor(110, 110, 110)  # #6E6E6E


def apply_document_styles(doc: Any) -> None:
    """Configure standard typography, paragraph spacing, and margins."""
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Base Normal Style
    normal_style = doc.styles["Normal"]
    normal_font = normal_style.font
    normal_font.name = "Calibri"
    normal_font.size = Pt(11)
    normal_font.color.rgb = COLOR_BODY_CHARCOAL
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    # Heading 1 Style
    if "Heading 1" in doc.styles:
        h1_style = doc.styles["Heading 1"]
        h1_font = h1_style.font
        h1_font.name = "Calibri"
        h1_font.size = Pt(16)
        h1_font.bold = True
        h1_font.color.rgb = COLOR_PRIMARY_NAVY
        h1_style.paragraph_format.space_before = Pt(14)
        h1_style.paragraph_format.space_after = Pt(6)

    # Heading 2 Style
    if "Heading 2" in doc.styles:
        h2_style = doc.styles["Heading 2"]
        h2_font = h2_style.font
        h2_font.name = "Calibri"
        h2_font.size = Pt(13)
        h2_font.bold = True
        h2_font.color.rgb = COLOR_SECONDARY_BLUE
        h2_style.paragraph_format.space_before = Pt(10)
        h2_style.paragraph_format.space_after = Pt(4)
