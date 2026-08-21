# -*- coding: utf-8 -*-
"""
Design System - Venus Coffee
ثوابت الأنماط والمساعدات المركزية لجميع شاشات venus/ui/
"""

from PyQt5.QtWidgets import QApplication, QStyle
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QSize


# ─────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────

class Colors:
    PRIMARY = "#4A90D9"
    PRIMARY_HOVER = "#3B7DB8"
    SUCCESS = "#10B981"
    SUCCESS_HOVER = "#059669"
    SUCCESS_PRESSED = "#047857"
    DANGER = "#EF4444"
    DANGER_HOVER = "#DC2626"
    WARNING = "#F59E0B"
    WARNING_HOVER = "#D97706"
    GRAY = "#6B7280"
    GRAY_HOVER = "#4B5563"
    DARK = "#1F2937"
    DARK_TEXT = "#1F2937"
    BODY_TEXT = "#1F2937"
    SECONDARY_TEXT = "#6B7280"
    LIGHT_TEXT = "#9CA3AF"
    LIGHT_GRAY = "#F3F4F5"
    BORDER = "#E5E7EB"
    WHITE = "#FFFFFF"
    BACKGROUND = "#F9FAFB"
    TABLE_ALT = "#F9FAFB"
    CARD_BG = "#FFFFFF"
    SIDEBAR_BG = "#111827"
    SIDEBAR_BTN = "#1F2937"
    SIDEBAR_BTN_HOVER = "#374151"
    SIDEBAR_BTN_ACTIVE = "#4A90D9"
    SIDEBAR_TITLE_BG = "#1F2937"
    INPUT_BG = "#FFFFFF"
    INPUT_DISABLED = "#F3F4F5"
    TAB_BG = "#E5E7EB"
    TAB_HOVER = "#6B7280"
    CASH_BG = "#FFFFFF"
    CASH_BORDER = "#4A90D9"
    EXPENSE_BG = "#FFFFFF"
    EXPENSE_BORDER = "#EF4444"
    WITHDRAWAL_BG = "#FFFFFF"
    WITHDRAWAL_BORDER = "#F59E0B"
    CLOSE_BG = "#FFFBEB"
    CLOSE_BORDER = "#F59E0B"
    FOCUS_GREEN = "#10B981"
    FOCUS_BLUE = "#4A90D9"
    FOCUS_ORANGE = "#F59E0B"
    FOCUS_RED = "#EF4444"
    FOCUS_TEAL = "#14B8A6"
    FOCUS_PURPLE = "#8B5CF6"
    PURPLE = FOCUS_PURPLE
    TEAL = FOCUS_TEAL
    ORANGE = WARNING


# ─────────────────────────────────────────────
# Typography
# ─────────────────────────────────────────────

class FontSizes:
    XS = "11px"
    SM = "12px"
    MD = "13px"
    LG = "14px"
    XL = "15px"
    XL2 = "16px"
    XL3 = "18px"
    XL4 = "20px"
    XL5 = "22px"
    XL6 = "24px"
    XL7 = "32px"


# ─────────────────────────────────────────────
# Spacing (integers for Qt layout methods)
# ─────────────────────────────────────────────

class Spacing:
    XS = 4
    SM = 8
    MD = 16
    LG = 24
    XL = 32


def _px(value):
    return f"{value}px"


# ─────────────────────────────────────────────
# Border Radius
# ─────────────────────────────────────────────

class BorderRadius:
    SM = "6px"
    MD = "8px"
    LG = "12px"
    XL = "16px"


# ─────────────────────────────────────────────
# Button Heights
# ─────────────────────────────────────────────

class ButtonHeight:
    SM = 32
    MD = 34
    LG = 40
    XL = 45
    SIDEBAR = 55


# ─────────────────────────────────────────────
# GroupBox Styles (RTL-aware)
# ─────────────────────────────────────────────

def group_box_style(border_color, font_size=FontSizes.LG, title_color=Colors.DARK_TEXT,
                     border_radius=BorderRadius.LG, margin_top=_px(Spacing.SM), padding_top=_px(Spacing.LG),
                     right_offset=_px(Spacing.LG), title_padding=_px(Spacing.SM) + " 0 " + _px(Spacing.SM) + " 0"):
    return f"""
        QGroupBox {{
            font-size: {font_size};
            font-weight: bold;
            color: {title_color};
            border: 1px solid {border_color};
            border-radius: {border_radius};
            margin-top: {margin_top};
            padding-top: {padding_top};
            background-color: {Colors.CARD_BG};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            right: {right_offset};
            padding: {title_padding};
        }}
    """


def card_group_box_style(border_color):
    return f"""
        QGroupBox {{
            font-size: {FontSizes.XS};
            font-weight: bold;
            color: {border_color};
            border: 1px solid {border_color};
            border-radius: {BorderRadius.XL};
            margin-top: 0px;
            padding-top: 0px;
            background-color: {Colors.CARD_BG};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            right: {_px(Spacing.LG)};
            padding: 0 {_px(Spacing.MD)} 0 {_px(Spacing.MD)};
        }}
    """


# ─────────────────────────────────────────────
# Table Styles
# ─────────────────────────────────────────────

def _darken_hex(hex_color, factor=120):
    c = QColor(hex_color)
    c = c.darker(factor)
    return c.name()


def table_style(header_color, border_radius=BorderRadius.LG):
    return f"""
        QTableWidget {{
            border: 1px solid {Colors.BORDER};
            border-radius: {border_radius};
            background-color: {Colors.CARD_BG};
            gridline-color: {Colors.LIGHT_GRAY};
        }}
        QHeaderView::section {{
            background-color: {Colors.LIGHT_GRAY};
            color: {Colors.DARK_TEXT};
            border: none;
            border-bottom: 1px solid {Colors.BORDER};
            border-top: 3px solid {header_color};
            padding: {_px(Spacing.SM)} {_px(Spacing.MD)};
            font-weight: bold;
            font-size: {FontSizes.SM};
        }}
        QTableWidget::item {{
            padding: {_px(Spacing.SM)} {_px(Spacing.MD)};
            font-size: {FontSizes.SM};
        }}
    """


def table_style_compact(header_color):
    return f"""
        QTableWidget {{
            border: 1px solid {Colors.BORDER};
            border-radius: {BorderRadius.MD};
            background-color: {Colors.CARD_BG};
            gridline-color: {Colors.LIGHT_GRAY};
        }}
        QHeaderView::section {{
            background-color: {Colors.LIGHT_GRAY};
            color: {Colors.DARK_TEXT};
            border: none;
            border-bottom: 1px solid {Colors.BORDER};
            border-top: 3px solid {header_color};
            padding: {_px(Spacing.XS)} {_px(Spacing.SM)};
            font-weight: bold;
            font-size: {FontSizes.XS};
        }}
        QTableWidget::item {{
            padding: {_px(Spacing.XS)} {_px(Spacing.SM)};
            font-size: {FontSizes.XS};
        }}
    """


# ─────────────────────────────────────────────
# Button Styles
# ─────────────────────────────────────────────

def primary_button_style(bg=Colors.PRIMARY, hover=Colors.PRIMARY_HOVER, pressed=None,
                         text_color=Colors.WHITE, border_radius=BorderRadius.MD,
                         font_size=FontSizes.LG, padding="6px 16px"):
    pressed = pressed or hover
    return f"""
        QPushButton {{
            background-color: {bg};
            color: {text_color};
            border: none;
            padding: {padding};
            border-radius: {border_radius};
            font-size: {font_size};
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {pressed}; }}
        QPushButton:disabled {{ background-color: {Colors.GRAY}; }}
    """


def success_button_style(hover=Colors.SUCCESS_HOVER, pressed=Colors.SUCCESS_PRESSED, **kwargs):
    return primary_button_style(Colors.SUCCESS, hover, pressed, **kwargs)


def danger_button_style(hover=Colors.DANGER_HOVER, **kwargs):
    return primary_button_style(Colors.DANGER, hover, **kwargs)


def warning_button_style(hover=Colors.WARNING_HOVER, **kwargs):
    return primary_button_style(Colors.WARNING, hover, **kwargs)


def purple_button_style(hover="#7C3AED", **kwargs):
    return primary_button_style("#8B5CF6", hover, **kwargs)


def teal_button_style(hover=Colors.FOCUS_TEAL, **kwargs):
    return primary_button_style(Colors.FOCUS_TEAL, hover, **kwargs)


def gray_button_style(hover=Colors.GRAY_HOVER, **kwargs):
    return primary_button_style(Colors.GRAY, hover, **kwargs)


# ─────────────────────────────────────────────
# Input Styles
# ─────────────────────────────────────────────

def input_style(focus_color=Colors.FOCUS_GREEN, border_radius=BorderRadius.MD,
                padding=Spacing.SM, font_size=FontSizes.LG, border_color=Colors.BORDER, min_width=None):
    result = f"""
        QLineEdit {{
            padding: {_px(padding)};
            font-size: {font_size};
            border: 1px solid {border_color};
            border-radius: {border_radius};
            background-color: {Colors.INPUT_BG};
        """
    if min_width:
        result += f"\n            min-width: {min_width};"
    result += f"""
        }}
        QLineEdit:focus {{ border-color: {focus_color}; }}
        QLineEdit:disabled {{ background-color: {Colors.INPUT_DISABLED}; color: {Colors.SECONDARY_TEXT}; }}
    """
    return result


def combo_style(focus_color=Colors.FOCUS_GREEN, border_radius=BorderRadius.MD,
                padding=Spacing.SM, font_size=FontSizes.LG, min_width="140px"):
    return f"""
        QComboBox {{
            padding: {_px(padding)};
            font-size: {font_size};
            border: 1px solid {Colors.BORDER};
            border-radius: {border_radius};
            background-color: {Colors.INPUT_BG};
            min-width: {min_width};
        }}
        QComboBox:focus {{ border-color: {focus_color}; }}
        QComboBox::drop-down {{ border: none; width: 30px; }}
    """


def date_edit_style(focus_color=Colors.FOCUS_BLUE, min_width="140px"):
    return f"""
        QDateEdit {{
            padding: {_px(Spacing.SM)};
            font-size: {FontSizes.LG};
            border: 1px solid {Colors.BORDER};
            border-radius: {BorderRadius.MD};
            background-color: {Colors.INPUT_BG};
            min-width: {min_width};
        }}
        QDateEdit:focus {{ border-color: {focus_color}; }}
    """


# ─────────────────────────────────────────────
# Tab Styles (unified 2px border)
# ─────────────────────────────────────────────

def tab_style():
    return f"""
        QTabWidget::pane {{
            border: 1px solid {Colors.BORDER};
            border-radius: {BorderRadius.LG};
            padding: {_px(Spacing.MD)};
            background-color: {Colors.BACKGROUND};
        }}
        QTabBar::tab {{
            background-color: {Colors.TAB_BG};
            color: {Colors.DARK_TEXT};
            padding: {_px(Spacing.SM)} {_px(Spacing.LG)};
            margin-right: {_px(Spacing.XS)};
            border-top-left-radius: {BorderRadius.LG};
            border-top-right-radius: {BorderRadius.LG};
            font-weight: bold;
            font-size: {FontSizes.LG};
        }}
        QTabBar::tab:selected {{
            background-color: {Colors.PRIMARY};
            color: {Colors.WHITE};
        }}
        QTabBar::tab:hover {{
            background-color: {Colors.TAB_HOVER};
            color: {Colors.WHITE};
        }}
    """


# ─────────────────────────────────────────────
# Sidebar Button Style
# ─────────────────────────────────────────────

def sidebar_button_style():
    return f"""
        QPushButton {{
            background-color: {Colors.SIDEBAR_BTN};
            color: #FFFFFF;
            border: none;
            padding: 8px 16px;
            font-size: {FontSizes.LG};
            text-align: left;
            border-radius: {BorderRadius.MD};
        }}
        QPushButton:hover {{
            background-color: {Colors.SIDEBAR_BTN_HOVER};
            color: white;
        }}
        QPushButton:checked {{
            background-color: {Colors.SIDEBAR_BTN_ACTIVE};
            font-weight: bold;
            color: white;
        }}
    """


# ─────────────────────────────────────────────
# Icon Size
# ─────────────────────────────────────────────

ICON_SIZE = QSize(16, 16)
ACTION_BUTTON_SIZE = QSize(32, 28)


# ─────────────────────────────────────────────
# Label Styles
# ─────────────────────────────────────────────

def title_label_style(font_size=FontSizes.XL3, color=Colors.DARK_TEXT):
    return f"""
        font-size: {font_size};
        font-weight: bold;
        color: {color};
        padding: {_px(Spacing.SM)};
    """


def summary_label_style(color=Colors.DARK_TEXT, bg=Colors.BACKGROUND,
                         border_color=Colors.BORDER, border_radius=BorderRadius.MD,
                         padding=Spacing.MD):
    return f"""
        font-size: {FontSizes.XL};
        font-weight: bold;
        color: {color};
        padding: {_px(padding)};
        background-color: {bg};
        border: 1px solid {border_color};
        border-radius: {border_radius};
    """


def info_label_style(color=Colors.WARNING, bg="#FFFBEB", border_color="#FDE68A",
                     font_size=FontSizes.SM):
    return f"""
        color: {color};
        font-size: {font_size};
        padding: {_px(Spacing.SM)} {_px(Spacing.MD)};
        background-color: {bg};
        border: 1px solid {border_color};
        border-radius: {BorderRadius.SM};
    """


def summary_card_style(bg=Colors.BACKGROUND, border_color=Colors.BORDER):
    return f"""
        font-size: {FontSizes.XL};
        font-weight: bold;
        color: {Colors.DARK_TEXT};
        background-color: {bg};
        border: 1px solid {border_color};
        border-radius: {BorderRadius.LG};
        padding: {_px(Spacing.LG)};
        min-width: 180px;
        min-height: 70px;
    """


# ─────────────────────────────────────────────
# Panel Styles (cash, expenses, withdrawals)
# ─────────────────────────────────────────────

def cash_panel_style(border_color=Colors.CASH_BORDER):
    return f"""
        background-color: {Colors.CASH_BG};
        border: 1px solid {border_color};
        border-radius: {BorderRadius.XL};
    """


def close_panel_style():
    return f"""
        background-color: {Colors.CLOSE_BG};
        border: 1px solid {Colors.CLOSE_BORDER};
        border-radius: {BorderRadius.XL};
    """


# ─────────────────────────────────────────────
# Status Bar / Message Styles (unified colors)
# ─────────────────────────────────────────────

def status_bar_style(level="info"):
    if level == "success":
        bg = Colors.SUCCESS
        fg = Colors.WHITE
    elif level == "warning":
        bg = Colors.WARNING
        fg = Colors.WHITE
    elif level == "error":
        bg = Colors.DANGER
        fg = Colors.WHITE
    else:
        bg = Colors.BACKGROUND
        fg = Colors.DARK_TEXT
    return f"""
        background-color: {bg};
        color: {fg};
        font-weight: bold;
        padding: 4px 12px;
        border: none;
    """
