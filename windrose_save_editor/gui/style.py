from __future__ import annotations

# Colour palette — matches the professionally commissioned UI
C_BG         = "#0c0d10"   # main background
C_PANEL      = "#111318"   # sidebar / panel surfaces
C_PANEL2     = "#16191f"   # slightly lighter panel (center)
C_BORDER     = "#1e2229"   # panel borders / dividers
C_BORDER2    = "#252a33"   # slightly more visible border
C_TEXT       = "#c9d1d9"   # primary text
C_MUTED      = "#6b7685"   # muted / secondary text
C_HEADER     = "#8a9aaa"   # section header text (ALL CAPS labels)
C_GOLD       = "#c9a84c"   # accent gold (save button, active nodes)
C_GOLD_DIM   = "#7a6030"   # dimmed gold
C_TEAL       = "#4a8fa8"   # partial-node ring / accent teal
C_RED        = "#c0392b"   # danger / remove
C_TOPBAR     = "#0a0b0d"   # top bar (darkest)

WINDROSE_DARK = f"""
/* ── Base ────────────────────────────────────────────────────────── */
QMainWindow, QDialog {{ background: {C_BG}; }}
QWidget {{ background: transparent; color: {C_TEXT};
          font-family: "Segoe UI", "Arial", sans-serif; font-size: 12px; }}

/* ── Scroll ──────────────────────────────────────────────────────── */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {C_PANEL}; width: 6px; margin: 0; border-radius: 3px; }}
QScrollBar::handle:vertical {{
    background: {C_BORDER2}; border-radius: 3px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: #3a4555; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {C_PANEL}; height: 6px; margin: 0; border-radius: 3px; }}
QScrollBar::handle:horizontal {{
    background: {C_BORDER2}; border-radius: 3px; min-width: 20px; }}
QScrollBar::handle:horizontal:hover {{ background: #3a4555; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Frames ───────────────────────────────────────────────────────── */
QFrame#topbar     {{ background: {C_TOPBAR}; border-bottom: 1px solid {C_BORDER}; }}
QFrame#pathbar    {{ background: {C_BG};     border-bottom: 1px solid {C_BORDER}; }}
QFrame#left-panel {{ background: {C_PANEL};  border-right:  1px solid {C_BORDER}; }}
QFrame#right-panel{{ background: {C_PANEL};  border-left:   1px solid {C_BORDER}; }}
QFrame#card       {{ background: {C_PANEL};  border: 1px solid {C_BORDER}; border-radius: 6px; }}
QFrame#separator  {{ background: {C_BORDER}; max-height: 1px; min-height: 1px; }}

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {{
    background: {C_PANEL}; color: {C_TEXT};
    border: 1px solid {C_BORDER2}; border-radius: 5px;
    padding: 5px 14px; font-size: 12px;
}}
QPushButton:hover  {{ background: {C_BORDER2}; border-color: #3a4555; }}
QPushButton:pressed{{ background: {C_BG}; }}
QPushButton:disabled {{ color: {C_MUTED}; }}

QPushButton#save-btn {{
    background: {C_GOLD}; color: {C_BG};
    border: none; font-weight: bold; padding: 5px 18px;
}}
QPushButton#save-btn:hover {{ background: #d4b56a; }}
QPushButton#save-btn:pressed {{ background: #b8953f; }}

QPushButton#tab-btn {{
    background: transparent; border: none; border-radius: 0;
    border-bottom: 2px solid transparent;
    padding: 6px 16px; color: {C_MUTED}; font-size: 12px;
}}
QPushButton#tab-btn:hover {{ color: {C_TEXT}; }}
QPushButton#tab-btn[active="true"] {{
    color: {C_GOLD}; border-bottom-color: {C_GOLD};
    font-weight: bold;
}}

QPushButton#section-expand {{
    background: transparent; border: none;
    color: {C_MUTED}; font-size: 11px;
    text-align: left; padding: 0;
}}
QPushButton#section-expand:hover {{ color: {C_TEXT}; }}

/* ── Labels ─────────────────────────────────────────────────────── */
QLabel {{ background: transparent; color: {C_TEXT}; }}
QLabel#char-title  {{ color: {C_TEXT}; font-size: 14px; font-weight: bold; }}
QLabel#char-name   {{ color: {C_MUTED}; font-size: 11px; font-style: italic; }}
QLabel#lvl-badge   {{
    background: {C_GOLD_DIM}; color: {C_GOLD};
    border: 1px solid {C_GOLD_DIM}; border-radius: 10px;
    padding: 1px 8px; font-size: 11px; font-weight: bold;
}}
QLabel#section-header {{
    color: {C_HEADER}; font-size: 10px; font-weight: bold;
    letter-spacing: 1.5px;
}}
QLabel#stat-value {{ color: {C_TEXT}; font-size: 12px; }}
QLabel#stat-value-hi {{ color: {C_GOLD}; font-size: 12px; font-weight: bold; }}
QLabel#muted {{ color: {C_MUTED}; font-size: 11px; }}
QLabel#version {{ color: #2a3240; font-size: 10px; }}
QLabel#layout-btn {{ color: {C_MUTED}; font-size: 10px; text-decoration: underline; padding: 0 3px; }}
QLabel#layout-btn[active="true"] {{ color: {C_TEXT}; }}

/* ── Inputs ──────────────────────────────────────────────────────── */
QSpinBox, QLineEdit {{
    background: #1a1f28; border: 1px solid {C_BORDER2};
    border-radius: 4px; padding: 3px 7px; color: {C_TEXT};
}}
QSpinBox:focus, QLineEdit:focus {{ border-color: {C_GOLD}; }}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {C_BORDER2}; border: none; width: 18px; border-radius: 2px;
}}
QSpinBox::up-button   {{ subcontrol-position: top right; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: #3a4555; }}
QSpinBox::up-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {C_TEXT};
    width: 0; height: 0;
}}
QSpinBox::down-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C_TEXT};
    width: 0; height: 0;
}}

/* ── Progress bar ────────────────────────────────────────────────── */
QProgressBar {{
    background: #1a1f28; border: none; border-radius: 3px;
    height: 5px; text-align: center;
}}
QProgressBar::chunk {{ background: {C_GOLD}; border-radius: 3px; }}

/* ── Graphics view ───────────────────────────────────────────────── */
QGraphicsView {{ border: none; background: {C_BG}; }}

/* ── Tooltips ────────────────────────────────────────────────────── */
QToolTip {{
    background: #1c2230; color: {C_TEXT};
    border: 1px solid {C_BORDER2}; border-radius: 5px;
    padding: 7px 10px; font-size: 12px;
}}

/* ── Status bar ──────────────────────────────────────────────────── */
QStatusBar {{
    background: {C_TOPBAR}; color: {C_MUTED};
    border-top: 1px solid {C_BORDER}; font-size: 10px;
}}

/* ── Dashboard card ──────────────────────────────────────────────── */
QFrame#dash-card {{
    background: {C_PANEL}; border: 1px solid {C_BORDER};
    border-radius: 8px;
}}
QLabel#hero-title {{
    font-size: 28px; font-weight: bold; color: #e6edf3;
    letter-spacing: 3px;
}}
QLabel#hero-sub {{ font-size: 12px; color: {C_MUTED}; }}
QLabel#version-badge {{
    background: #1a1f28; border: 1px solid {C_GOLD_DIM};
    border-radius: 10px; padding: 2px 10px;
    color: {C_GOLD}; font-size: 11px; font-weight: bold;
}}
"""
