from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QStackedWidget, QFrame, QLabel, QScrollArea,
    QSizePolicy, QProgressBar, QSpacerItem,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPixmap

from windrose_save_editor import __version__
from windrose_save_editor.gui import icons
from windrose_save_editor.gui.style import (
    C_GOLD, C_MUTED, C_TEXT, C_BORDER, C_HEADER,
)
from windrose_save_editor.gui.tabs.dashboard import DashboardTab
from windrose_save_editor.gui.tabs.skills_tab import SkillsTab

# Ordered list of the 6 core stats shown in the top bar and allocation panel
_STAT_ORDER = ["Strength", "Agility", "Precision", "Mastery", "Vitality", "Endurance"]

# Colour per stat for the allocation bars
_STAT_COLORS: dict[str, str] = {
    "Strength":  "#c0392b",
    "Agility":   "#27ae60",
    "Precision": "#2980b9",
    "Mastery":   "#8e44ad",
    "Vitality":  "#e74c3c",
    "Endurance": "#16a085",
}

# Equipment slot types shown in the left panel
_ARMOR_SLOTS    = ["Head", "Torso", "Gloves", "Legs", "Feet"]
_ACC_SLOTS      = ["Ring", "Necklace", "Belt"]
_WEAPON_SLOTS   = ["MainHand", "OffHand", "RangedMainHand", "RangedOffHand"]


# ─────────────────────────────────────────────────────────────────────────────
# Top bar
# ─────────────────────────────────────────────────────────────────────────────

class _TopBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(0)

        # ── App identity
        logo = QLabel("⚓")
        logo.setStyleSheet(f"color: {C_GOLD}; font-size: 20px; padding-right: 8px;")
        title = QLabel("Windrose Save Editor")
        title.setStyleSheet(
            f"color: {C_TEXT}; font-size: 13px; font-weight: bold; letter-spacing: 1px;"
        )
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addSpacing(24)

        # ── Nav tab buttons (Dashboard | Character Editor)
        self._tab_btns: dict[str, QPushButton] = {}
        for key, label in (("dashboard", "Dashboard"), ("editor", "Character Editor")):
            btn = QPushButton(label)
            btn.setObjectName("tab-btn")
            btn.setCheckable(False)
            btn.setProperty("active", "false")
            btn.setFixedHeight(56)
            self._tab_btns[key] = btn
            layout.addWidget(btn)

        layout.addSpacing(20)

        # ── Character info (hidden until a save is loaded)
        self._char_info = QWidget()
        char_row = QHBoxLayout(self._char_info)
        char_row.setContentsMargins(0, 0, 0, 0)
        char_row.setSpacing(10)

        self._char_name_lbl = QLabel("—")
        self._char_name_lbl.setObjectName("char-title")
        self._char_name_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 13px; font-weight: bold;"
        )

        self._lvl_badge = QLabel("Lv —")
        self._lvl_badge.setObjectName("lvl-badge")

        char_row.addWidget(self._char_name_lbl)
        char_row.addWidget(self._lvl_badge)
        char_row.addSpacing(14)

        # Stat icons with values
        self._stat_value_lbls: dict[str, QLabel] = {}
        for stat in _STAT_ORDER:
            icon_pm = icons.stat_icon(stat, 16)
            if not icon_pm.isNull():
                ic_lbl = QLabel()
                ic_lbl.setPixmap(icon_pm)
                char_row.addWidget(ic_lbl)
            val_lbl = QLabel("—")
            val_lbl.setObjectName("stat-value")
            val_lbl.setToolTip(stat)
            self._stat_value_lbls[stat] = val_lbl
            char_row.addWidget(val_lbl)
            char_row.addSpacing(4)

        self._char_info.hide()
        layout.addWidget(self._char_info)

        layout.addStretch(1)

        # ── Action buttons
        self._backup_btn = QPushButton("Backups")
        self._backup_btn.setToolTip("View and restore backups")
        self._reset_btn  = QPushButton("Reset")
        self._reset_btn.setToolTip("Revert all unsaved changes")
        self._save_btn   = QPushButton("Save Changes")
        self._save_btn.setObjectName("save-btn")

        for btn in (self._backup_btn, self._reset_btn):
            btn.setEnabled(False)
        self._save_btn.setEnabled(False)

        layout.addWidget(self._backup_btn)
        layout.addSpacing(6)
        layout.addWidget(self._reset_btn)
        layout.addSpacing(8)
        layout.addWidget(self._save_btn)

    # ── Public ────────────────────────────────────────────────────────────

    def set_active_tab(self, key: str) -> None:
        for k, btn in self._tab_btns.items():
            active = (k == key)
            btn.setProperty("active", "true" if active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_character(
        self,
        name: str,
        level: int,
        stat_values: dict[str, int],
    ) -> None:
        self._char_name_lbl.setText(name)
        self._lvl_badge.setText(f"Lv {level}")
        for stat, val in stat_values.items():
            if stat in self._stat_value_lbls:
                self._stat_value_lbls[stat].setText(str(val))
        self._char_info.show()
        self._backup_btn.setEnabled(True)
        self._reset_btn.setEnabled(True)
        self._save_btn.setEnabled(True)

    def clear_character(self) -> None:
        self._char_info.hide()
        self._backup_btn.setEnabled(False)
        self._reset_btn.setEnabled(False)
        self._save_btn.setEnabled(False)

    @property
    def tab_buttons(self) -> dict[str, QPushButton]:
        return self._tab_btns

    @property
    def save_button(self) -> QPushButton:
        return self._save_btn

    @property
    def reset_button(self) -> QPushButton:
        return self._reset_btn

    @property
    def backup_button(self) -> QPushButton:
        return self._backup_btn


# ─────────────────────────────────────────────────────────────────────────────
# Path bar
# ─────────────────────────────────────────────────────────────────────────────

class _PathBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pathbar")
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)

        path_icon = QLabel("📁")
        path_icon.setStyleSheet("font-size: 12px;")
        layout.addWidget(path_icon)

        self._path_lbl = QLabel("No save loaded — use Open to select a save file")
        self._path_lbl.setObjectName("muted")
        self._path_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        layout.addWidget(self._path_lbl, 1)

        open_btn = QPushButton("Open…")
        open_btn.setFixedHeight(22)
        open_btn.setStyleSheet("font-size: 11px; padding: 0 10px;")
        self._open_btn = open_btn
        layout.addWidget(open_btn)

    def set_path(self, path: str) -> None:
        self._path_lbl.setText(path)
        self._path_lbl.setStyleSheet(f"color: {C_TEXT}; font-size: 11px;")

    def clear_path(self) -> None:
        self._path_lbl.setText("No save loaded — use Open to select a save file")
        self._path_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")

    @property
    def open_button(self) -> QPushButton:
        return self._open_btn


# ─────────────────────────────────────────────────────────────────────────────
# Left panel — equipment
# ─────────────────────────────────────────────────────────────────────────────

class _EquipmentSlot(QFrame):
    """Single equipment slot icon placeholder."""

    def __init__(self, slot_type: str, size: int = 44) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(slot_type)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        pm = icons.slot_type_icon(slot_type, size - 6)
        if not pm.isNull():
            lbl = QLabel()
            lbl.setPixmap(pm)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
        else:
            lbl = QLabel(slot_type[:2].upper())
            lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 9px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)


class _LeftPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("left-panel")
        self.setFixedWidth(230)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # CHARACTER / SHIP tab buttons
        tab_bar = QFrame()
        tab_bar.setStyleSheet(
            f"QFrame {{ background: transparent; border-bottom: 1px solid {C_BORDER}; }}"
        )
        tab_row = QHBoxLayout(tab_bar)
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(0)

        char_btn = QPushButton("CHARACTER")
        char_btn.setObjectName("tab-btn")
        char_btn.setProperty("active", "true")
        char_btn.setFixedHeight(38)
        ship_btn = QPushButton("SHIP")
        ship_btn.setObjectName("tab-btn")
        ship_btn.setProperty("active", "false")
        ship_btn.setFixedHeight(38)

        tab_row.addWidget(char_btn)
        tab_row.addWidget(ship_btn)
        outer.addWidget(tab_bar)

        # Scrollable equipment content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._section("WEAPON LOADOUT", _WEAPON_SLOTS, cols=2))
        layout.addWidget(self._section("ARMOR",          _ARMOR_SLOTS,   cols=3))
        layout.addWidget(self._section("ACCESSORIES",    _ACC_SLOTS,     cols=3))

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    @staticmethod
    def _section(title: str, slot_types: list[str], cols: int = 3) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        hdr = QLabel(title)
        hdr.setObjectName("section-header")
        vbox.addWidget(hdr)

        grid = QGridLayout()
        grid.setSpacing(6)
        for i, slot_type in enumerate(slot_types):
            grid.addWidget(_EquipmentSlot(slot_type), i // cols, i % cols)
        vbox.addLayout(grid)

        return w


# ─────────────────────────────────────────────────────────────────────────────
# Center panel — skill tree + inventory
# ─────────────────────────────────────────────────────────────────────────────

class _CenterPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Skill tree takes ~60% of height
        self._skills_tab = SkillsTab()
        layout.addWidget(self._skills_tab, 3)

        # Thin separator
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Action bar
        layout.addWidget(self._build_action_bar())

        # Thin separator
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        # Inventory grid takes ~40% of height
        layout.addWidget(self._build_inventory(), 2)

    def _build_action_bar(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame {{ background: transparent; padding: 4px 0; }}"
        )
        bar.setFixedHeight(42)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 4, 16, 4)
        row.setSpacing(8)

        hdr = QLabel("ACTION BAR")
        hdr.setObjectName("section-header")
        row.addWidget(hdr)
        row.addSpacing(12)

        for i in range(8):
            slot = QFrame()
            slot.setObjectName("card")
            slot.setFixedSize(34, 34)
            row.addWidget(slot)

        row.addStretch()
        return bar

    def _build_inventory(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 10, 16, 10)
        outer.setSpacing(8)

        hdr = QLabel("MAIN INVENTORY")
        hdr.setObjectName("section-header")
        outer.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(5)
        grid.setContentsMargins(0, 0, 0, 0)

        cols = 10
        rows = 4
        for r in range(rows):
            for c in range(cols):
                slot = QFrame()
                slot.setObjectName("card")
                slot.setFixedSize(40, 40)
                grid.addWidget(slot, r, c)

        scroll.setWidget(grid_widget)
        outer.addWidget(scroll, 1)
        return w

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def skills_tab(self) -> SkillsTab:
        return self._skills_tab


# ─────────────────────────────────────────────────────────────────────────────
# Right panel — derived stats + stat allocation
# ─────────────────────────────────────────────────────────────────────────────

class _StatBar(QWidget):
    """One stat allocation row: icon + name + coloured bar + value."""

    def __init__(self, stat: str) -> None:
        super().__init__()
        color = _STAT_COLORS.get(stat, C_GOLD)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        # Icon
        pm = icons.stat_icon(stat, 16)
        if not pm.isNull():
            ic = QLabel()
            ic.setPixmap(pm)
            ic.setFixedSize(16, 16)
            row.addWidget(ic)
        else:
            ic = QLabel(stat[:3].upper())
            ic.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
            ic.setFixedWidth(28)
            row.addWidget(ic)

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        self._bar.setStyleSheet(
            f"QProgressBar {{ background: #1a1f28; border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
        )
        row.addWidget(self._bar, 1)

        # Value label
        self._val_lbl = QLabel("0")
        self._val_lbl.setObjectName("stat-value")
        self._val_lbl.setFixedWidth(28)
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._val_lbl)

    def set_value(self, value: int, max_value: int = 100) -> None:
        self._val_lbl.setText(str(value))
        self._bar.setMaximum(max(max_value, 1))
        self._bar.setValue(min(value, max_value))


class _RightPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("right-panel")
        self.setFixedWidth(255)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._build_derived_stats())
        layout.addWidget(self._build_stat_allocation())

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    # ── Derived stats section ──────────────────────────────────────────────

    def _build_derived_stats(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(10)

        hdr = QLabel("DERIVED STATS")
        hdr.setObjectName("section-header")
        vbox.addWidget(hdr)

        for section, rows in (
            ("Vitals",  [("Max HP", "—"), ("Max Stamina", "—"), ("Temp HP", "—")]),
            ("Combat",  [("Melee Dmg", "—"), ("Range Dmg", "—"), ("Crit %", "—")]),
            ("Defence", [("Phys Resist", "—"), ("All Resist", "—")]),
        ):
            vbox.addWidget(self._stat_group(section, rows))

        return w

    @staticmethod
    def _stat_group(title: str, rows: list[tuple[str, str]]) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 4)
        vbox.setSpacing(4)

        sub = QLabel(title)
        sub.setStyleSheet(f"color: {C_HEADER}; font-size: 10px; font-weight: bold;")
        vbox.addWidget(sub)

        for label, value in rows:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setObjectName("muted")
            val = QLabel(value)
            val.setObjectName("stat-value")
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            vbox.addLayout(row)

        return w

    # ── Stat allocation section ───────────────────────────────────────────

    def _build_stat_allocation(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        hdr = QLabel("STAT ALLOCATION")
        hdr.setObjectName("section-header")
        vbox.addWidget(hdr)

        self._stat_bars: dict[str, _StatBar] = {}
        for stat in _STAT_ORDER:
            bar = _StatBar(stat)
            self._stat_bars[stat] = bar
            vbox.addWidget(bar)

        return w

    # ── Public API ────────────────────────────────────────────────────────

    def set_stat(self, stat: str, value: int, max_value: int = 100) -> None:
        if stat in self._stat_bars:
            self._stat_bars[stat].set_value(value, max_value)


# ─────────────────────────────────────────────────────────────────────────────
# Character editor view (3-column body)
# ─────────────────────────────────────────────────────────────────────────────

class _CharacterEditorView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._left   = _LeftPanel()
        self._center = _CenterPanel()
        self._right  = _RightPanel()

        layout.addWidget(self._left)
        layout.addWidget(self._center, 1)
        layout.addWidget(self._right)

    @property
    def skills_tab(self) -> SkillsTab:
        return self._center.skills_tab

    @property
    def right_panel(self) -> _RightPanel:
        return self._right


# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Windrose Save Editor  —  v{__version__}")
        self.setMinimumSize(1100, 680)
        self.resize(1380, 840)
        self._setup_ui()
        self._switch_page("dashboard")

    # ── Setup ────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root_widget = QWidget()
        self.setCentralWidget(root_widget)

        root = QVBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        self._topbar = _TopBar()
        root.addWidget(self._topbar)

        # Path bar
        self._pathbar = _PathBar()
        root.addWidget(self._pathbar)

        # Main content stack
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        # Page 0: Dashboard
        self._dashboard = DashboardTab()
        self._stack.addWidget(self._dashboard)          # index 0

        # Page 1: Character editor (3-column)
        self._editor = _CharacterEditorView()
        self._stack.addWidget(self._editor)             # index 1

        # Wire nav buttons
        for key, btn in self._topbar.tab_buttons.items():
            btn.clicked.connect(lambda _checked, k=key: self._switch_page(k))

        self.statusBar().showMessage(
            "No save loaded — click Open to begin editing"
        )

    # ── Navigation ───────────────────────────────────────────────────────

    def _switch_page(self, key: str) -> None:
        self._topbar.set_active_tab(key)
        page = 0 if key == "dashboard" else 1
        self._stack.setCurrentIndex(page)

    # ── Public API (called when a save is loaded) ─────────────────────────

    def on_save_loaded(
        self,
        path: str,
        char_name: str,
        level: int,
        stat_values: dict[str, int],
        skills: dict,
    ) -> None:
        """Populate all panels from a loaded save and switch to the editor."""
        self._pathbar.set_path(path)
        self._topbar.set_character(char_name, level, stat_values)
        self._editor.skills_tab.load_skills(skills)
        for stat, val in stat_values.items():
            self._editor.right_panel.set_stat(stat, val)
        self._switch_page("editor")
        self.statusBar().showMessage(f"Loaded: {path}")

    def on_save_cleared(self) -> None:
        """Reset UI when a save is closed."""
        self._pathbar.clear_path()
        self._topbar.clear_character()
        self._editor.skills_tab.clear_skills()
        self._switch_page("dashboard")
        self.statusBar().showMessage("No save loaded — click Open to begin editing")

    @property
    def open_button(self) -> QPushButton:
        return self._pathbar.open_button

    @property
    def save_button(self) -> QPushButton:
        return self._topbar.save_button

    @property
    def skills_tab(self) -> SkillsTab:
        return self._editor.skills_tab
