from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from windrose_save_editor import __version__
from windrose_save_editor.gui.style import C_BORDER, C_GOLD, C_MUTED, C_PANEL2, C_TEXT

# ── Contributor list ─────────────────────────────────────────────────────────
# Add entries here as (Name, Role/Contribution).
# The list is rendered under the Credits section; expand freely.
CONTRIBUTORS: list[tuple[str, str]] = [
    ("Eratiosu", "X"),
    ("@reisu", "Stats, talents, and GUI"),
    ("Person B", "X"),
]

# ── Quickstart steps ─────────────────────────────────────────────────────────
_QUICKSTART_STEPS: list[str] = [
    "Run the editor and it will auto-detect your Windrose save folder.",
    "Use the Inventory tab to view, upgrade, or add items to your character.",
    "Use the Stats tab to set individual stat levels, or Bulk Ops → Max All Stats.",
    "Use the Skills tab to view and edit your talent tree, one node at a time.",
    "When finished, click Save Changes — a backup is created automatically before writing.",
    "Restore Backup at any time to undo all edits since the last save.",
]


class DashboardTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(_HeroHeader())
        layout.addWidget(_SeparatorLine())
        layout.addWidget(_WelcomeCard())
        layout.addWidget(_QuickstartCard())
        layout.addWidget(_CreditsCard())

        scroll.setWidget(content)
        outer.addWidget(scroll)


# ── Sub-widgets ──────────────────────────────────────────────────────────────

class _HeroHeader(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row.setSpacing(14)

        title = QLabel("WINDROSE SAVE EDITOR")
        title.setObjectName("hero-title")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))

        badge = QLabel(f"v{__version__}")
        badge.setObjectName("version-badge")
        badge.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(title)
        row.addWidget(badge)
        row.addStretch()

        sub = QLabel("Orange Dreamcicle theme by Reisu")
        sub.setObjectName("hero-sub")

        layout.addLayout(row)
        layout.addWidget(sub)


class _SeparatorLine(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("separator")
        self.setFrameShape(QFrame.Shape.HLine)


class _Card(QFrame):
    """Base card frame with consistent padding."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._inner = QVBoxLayout(self)
        self._inner.setContentsMargins(24, 20, 24, 20)
        self._inner.setSpacing(10)


class _WelcomeCard(_Card):
    def __init__(self) -> None:
        super().__init__()
        title = QLabel("Welcome")
        title.setObjectName("section-title")

        body = QLabel(
            "Thank you for using the Windrose Save Editor!\n\n"
            "This tool lets you directly edit your Windrose save files — "
            "adjusting stats, skills, inventory items, and more — without "
            "touching the game client. Your saves are always backed up before "
            "any changes are written, so you can safely explore every option.\n\n"
            "If you run into a bug or want to suggest a feature, please open an "
            "issue on the project's GitHub page."
        )
        body.setWordWrap(True)
        body.setObjectName("muted")
        body.setStyleSheet(f"color: {C_MUTED}; line-height: 1.7; font-size: 13px;")

        self._inner.addWidget(title)
        self._inner.addWidget(body)


class _QuickstartCard(_Card):
    def __init__(self) -> None:
        super().__init__()
        title = QLabel("Quick-Start Guide")
        title.setObjectName("section-title")
        self._inner.addWidget(title)

        for i, step in enumerate(_QUICKSTART_STEPS, 1):
            row = QHBoxLayout()
            row.setSpacing(12)
            row.setAlignment(Qt.AlignmentFlag.AlignTop)

            num = QLabel(str(i))
            num.setFixedSize(26, 26)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(
                f"background-color: {C_PANEL2}; color: {C_GOLD};"
                "border-radius: 13px; font-weight: bold; font-size: 12px;"
            )

            text = QLabel(step)
            text.setWordWrap(True)
            text.setStyleSheet(f"color: {C_MUTED}; font-size: 13px;")
            text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            row.addWidget(num)
            row.addWidget(text)
            self._inner.addLayout(row)


class _CreditsCard(_Card):
    def __init__(self) -> None:
        super().__init__()

        # ── Header row
        title = QLabel("Credits")
        title.setObjectName("section-title")
        self._inner.addWidget(title)

        # ── Original author line
        author_row = QHBoxLayout()
        author_lbl = QLabel("Original project by:")
        author_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 13px;")
        author_name = QLabel("KHBIN (RimmyCode)")
        author_name.setStyleSheet(f"color: {C_GOLD}; font-weight: bold; font-size: 13px;")
        author_row.addWidget(author_lbl)
        author_row.addWidget(author_name)
        author_row.addStretch()
        self._inner.addLayout(author_row)

        # ── Contributors toggle
        self._toggle_btn = QPushButton("▶  Contributors  (%d)" % len(CONTRIBUTORS))
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {C_MUTED};"
            "text-align: left; font-size: 12px; padding: 4px 0; }"
            f"QPushButton:hover {{ color: {C_TEXT}; }}"
        )
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle_contributors)
        self._inner.addWidget(self._toggle_btn)

        # ── Contributors list (hidden by default)
        self._contrib_widget = QWidget()
        contrib_layout = QVBoxLayout(self._contrib_widget)
        contrib_layout.setContentsMargins(16, 4, 0, 4)
        contrib_layout.setSpacing(6)

        for name, role in CONTRIBUTORS:
            row = QHBoxLayout()
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(f"color: {C_TEXT}; font-size: 13px;")
            dash = QLabel("—")
            dash.setStyleSheet(f"color: {C_BORDER}; font-size: 13px;")
            role_lbl = QLabel(role)
            role_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 13px;")
            row.addWidget(name_lbl)
            row.addWidget(dash)
            row.addWidget(role_lbl)
            row.addStretch()
            contrib_layout.addLayout(row)

        self._contrib_widget.hide()
        self._inner.addWidget(self._contrib_widget)
        self._expanded = False

    def _toggle_contributors(self) -> None:
        self._expanded = not self._expanded
        self._contrib_widget.setVisible(self._expanded)
        arrow = "▼" if self._expanded else "▶"
        self._toggle_btn.setText(f"{arrow}  Contributors  ({len(CONTRIBUTORS)})")
