from __future__ import annotations

WINDROSE_DARK = """
/* ── Base ─────────────────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}

/* ── Scroll bars ──────────────────────────────────────────────── */
QScrollArea { border: none; }

QScrollBar:vertical {
    background: #161b22; width: 7px; margin: 0; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #30363d; border-radius: 4px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #484f58; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: #161b22; height: 7px; margin: 0; border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #30363d; border-radius: 4px; min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background: #484f58; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Buttons ──────────────────────────────────────────────────── */
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton:hover { background-color: #30363d; border-color: #484f58; }
QPushButton:pressed { background-color: #161b22; }

QPushButton#nav-btn {
    background-color: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
    padding: 10px 14px;
    text-align: left;
    color: #8b949e;
    font-size: 13px;
}
QPushButton#nav-btn:hover {
    background-color: #161b22;
    color: #c9d1d9;
}
QPushButton#nav-btn[active="true"] {
    background-color: #1c2333;
    color: #c9a84c;
    border-left: 3px solid #c9a84c;
}

QPushButton#accent-btn {
    background-color: #c9a84c;
    color: #0d1117;
    border: none;
    font-weight: bold;
    padding: 8px 20px;
}
QPushButton#accent-btn:hover { background-color: #d4b56a; }
QPushButton#accent-btn:pressed { background-color: #b8953f; }

QPushButton#danger-btn {
    background-color: #21262d;
    color: #f85149;
    border: 1px solid #f8514940;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton#danger-btn:hover { background-color: #f8514918; border-color: #f85149; }

/* ── Labels ───────────────────────────────────────────────────── */
QLabel { background: transparent; color: #c9d1d9; }
QLabel#hero-title {
    font-size: 32px;
    font-weight: bold;
    color: #e6edf3;
    letter-spacing: 3px;
}
QLabel#hero-sub {
    font-size: 13px;
    color: #8b949e;
}
QLabel#version-badge {
    background-color: #21262d;
    border: 1px solid #c9a84c;
    border-radius: 10px;
    padding: 2px 10px;
    color: #c9a84c;
    font-size: 11px;
    font-weight: bold;
}
QLabel#section-title {
    font-size: 15px;
    font-weight: bold;
    color: #c9d1d9;
}
QLabel#muted {
    color: #8b949e;
    font-size: 12px;
}
QLabel#gold { color: #c9a84c; }

/* ── Frames / Cards ───────────────────────────────────────────── */
QFrame#sidebar {
    background-color: #161b22;
    border-right: 1px solid #21262d;
}
QFrame#card {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
}
QFrame#separator {
    background-color: #21262d;
    max-height: 1px;
    min-height: 1px;
}

/* ── GroupBox ─────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #30363d;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #c9a84c;
    font-weight: bold;
    font-size: 12px;
}

/* ── Tables ───────────────────────────────────────────────────── */
QTableWidget {
    background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 6px;
    gridline-color: #21262d;
}
QTableWidget::item { padding: 6px 10px; color: #c9d1d9; }
QTableWidget::item:selected { background-color: #1c2333; color: #c9d1d9; }
QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #21262d;
    font-weight: bold;
    font-size: 11px;
}

/* ── Inputs ───────────────────────────────────────────────────── */
QSpinBox, QLineEdit {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
    color: #c9d1d9;
}
QSpinBox:focus, QLineEdit:focus { border-color: #c9a84c; }
QSpinBox::up-button, QSpinBox::down-button {
    background: #30363d;
    border: none;
    width: 16px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #484f58; }

/* ── Graphics view ────────────────────────────────────────────── */
QGraphicsView {
    border: none;
    background-color: #080c13;
    border-radius: 10px;
}

/* ── Tooltips ─────────────────────────────────────────────────── */
QToolTip {
    background-color: #1c2333;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
}

/* ── Status bar ───────────────────────────────────────────────── */
QStatusBar {
    background: #161b22;
    color: #8b949e;
    border-top: 1px solid #21262d;
    font-size: 11px;
}
"""
