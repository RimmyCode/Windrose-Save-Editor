from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStackedWidget, QFrame, QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from windrose_save_editor import __version__
from windrose_save_editor.gui.tabs.dashboard import DashboardTab
from windrose_save_editor.gui.tabs.skills_tab import SkillsTab

_NAV_ITEMS: list[tuple[str, str, str]] = [
    # (display label, nav key, unicode icon)
    ("Dashboard",  "dashboard",  "⌂"),
    ("Inventory",  "inventory",  "⚔"),
    ("Stats",      "stats",      "◈"),
    ("Skills",     "skills",     "✦"),
    ("Bulk Ops",   "bulk",       "⚡"),
    ("Tools",      "tools",      "⚙"),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Windrose Save Editor  —  v{__version__}")
        self.setMinimumSize(1100, 680)
        self.resize(1320, 820)
        self._setup_ui()
        self._activate_nav("dashboard")

    # ── Setup ────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_content(), 1)

        self.statusBar().showMessage("No save loaded — open a save file to begin editing")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(0)

        # ── Logo area
        logo = QLabel("⚓  WINDROSE")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            "color: #c9a84c; font-size: 14px; font-weight: bold;"
            "letter-spacing: 3px; padding: 20px 0 20px 0;"
            "border-bottom: 1px solid #21262d;"
        )
        layout.addWidget(logo)
        layout.addSpacing(8)

        # ── Nav buttons
        self._nav_buttons: dict[str, QPushButton] = {}
        for label, key, icon in _NAV_ITEMS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setObjectName("nav-btn")
            btn.setProperty("active", "false")
            btn.setFixedHeight(42)
            btn.setFont(QFont("Segoe UI", 12))
            btn.clicked.connect(lambda _checked, k=key: self._activate_nav(k))
            layout.addWidget(btn)
            self._nav_buttons[key] = btn

        layout.addStretch()

        # ── Version tag
        ver = QLabel(f"v{__version__}")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color: #30363d; font-size: 11px;")
        layout.addWidget(ver)

        return sidebar

    def _build_content(self) -> QStackedWidget:
        stack = QStackedWidget()
        self._stack = stack

        self._tabs: dict[str, tuple[QWidget, int]] = {}
        self._dashboard = DashboardTab()
        self._skills = SkillsTab()

        self._register_tab("dashboard", self._dashboard)
        self._register_tab("skills",    self._skills)

        # Placeholder pages for not-yet-implemented tabs
        for key in ("inventory", "stats", "bulk", "tools"):
            self._register_tab(key, self._make_placeholder(key))

        return stack

    def _register_tab(self, key: str, widget: QWidget) -> None:
        idx = self._stack.addWidget(widget)
        self._tabs[key] = (widget, idx)

    def _make_placeholder(self, name: str) -> QWidget:
        w = QWidget()
        lbl = QLabel(f"{name.capitalize()} — coming soon")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #30363d; font-size: 20px;")
        layout = QVBoxLayout(w)
        layout.addWidget(lbl)
        return w

    # ── Navigation ───────────────────────────────────────────────────────

    def _activate_nav(self, key: str) -> None:
        for k, btn in self._nav_buttons.items():
            active = (k == key)
            btn.setProperty("active", "true" if active else "false")
            # Force Qt to re-evaluate the stylesheet property
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if key in self._tabs:
            _, idx = self._tabs[key]
            self._stack.setCurrentIndex(idx)
