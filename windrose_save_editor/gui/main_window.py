from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QStackedWidget, QFrame, QLabel, QScrollArea,
    QSpinBox, QDialog, QListWidget, QListWidgetItem, QMessageBox,
    QProgressDialog, QSizePolicy, QAbstractItemView,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from windrose_save_editor import __version__
from windrose_save_editor.gui import icons
from windrose_save_editor.gui.style import (
    C_GOLD, C_MUTED, C_TEXT, C_BORDER, C_HEADER,
)
from windrose_save_editor.gui.gui_save import (
    is_game_running, gui_commit_changes,
    gui_create_backup, gui_restore_backup,
)
from windrose_save_editor.gui.save_loader import (
    CharacterPickerDialog, LoadedSave, load_save_session,
)
from windrose_save_editor.gui.tabs.dashboard import DashboardTab
from windrose_save_editor.gui.tabs.skills_tab import SkillsTab
from windrose_save_editor.gui.tabs.inventory_tab import InventoryTab

_STAT_ORDER = ["Strength", "Agility", "Precision", "Mastery", "Vitality", "Endurance"]
_STAT_COLORS: dict[str, str] = {
    "Strength":  "#c0392b",
    "Agility":   "#27ae60",
    "Precision": "#2980b9",
    "Mastery":   "#8e44ad",
    "Vitality":  "#e74c3c",
    "Endurance": "#16a085",
}
_ARMOR_SLOTS  = ["Head", "Torso", "Gloves", "Legs", "Feet"]
_ACC_SLOTS    = ["Ring", "Necklace", "Backpack"]
_MODULE_SLOTS = ["MainHand", "OffHand", "RangedMainHand", "RangedOffHand"]


# ─────────────────────────────────────────────────────────────────────────────
# Background worker for save
# ─────────────────────────────────────────────────────────────────────────────

class _SaveWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, loaded: LoadedSave) -> None:
        super().__init__()
        self._loaded = loaded

    def run(self) -> None:
        try:
            ok, msg = gui_create_backup(self._loaded.session.save_dir)
            if not ok:
                self.finished.emit(False, f"Backup failed: {msg}")
                return
            self._loaded.session.backed_up = True
            ok2, msg2 = gui_commit_changes(self._loaded.session)
            self.finished.emit(ok2, msg2)
        except Exception as exc:
            self.finished.emit(False, str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Backup dialog  (reference-style)
# ─────────────────────────────────────────────────────────────────────────────

class _BackupDialog(QDialog):
    def __init__(self, save_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._save_dir = save_dir
        self._backups: list[Path] = []
        self.setWindowTitle("Save Backups")
        self.setMinimumWidth(540)
        self.setMinimumHeight(400)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(18, 18, 18, 16)

        title = QLabel("Save Backups")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #c9d1d9;")
        lay.addWidget(title)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #6b7685; font-size: 11px;")
        lay.addWidget(self._status_lbl)

        bk_hdr = QLabel("AVAILABLE BACKUPS")
        bk_hdr.setObjectName("section-header")
        lay.addWidget(bk_hdr)

        self._list = QListWidget()
        self._list.setMinimumHeight(180)
        self._list.setStyleSheet(
            "QListWidget { background: #111318; border: 1px solid #1e2229;"
            "               border-radius: 4px; }"
            "QListWidget::item { padding: 10px 14px; color: #c9d1d9; }"
            "QListWidget::item:selected { background: #1e2229; color: #c9a84c; }"
            "QListWidget::item:hover { background: #16191f; }"
        )
        lay.addWidget(self._list, 1)

        self._path_lbl = QLabel("")
        self._path_lbl.setStyleSheet("color: #3a4555; font-size: 10px;")
        lay.addWidget(self._path_lbl)

        btn_row = QHBoxLayout()
        create_btn = QPushButton("Create Backup Now")
        create_btn.clicked.connect(self._create_now)
        btn_row.addWidget(create_btn)
        btn_row.addStretch()

        self._restore_btn = QPushButton("Restore Selected")
        self._restore_btn.setObjectName("save-btn")
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._restore)
        btn_row.addWidget(self._restore_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._list.currentRowChanged.connect(self._on_row_changed)

    def _on_row_changed(self, row: int) -> None:
        enabled = 0 <= row < len(self._backups)
        self._restore_btn.setEnabled(enabled)
        if enabled:
            self._path_lbl.setText(str(self._backups[row]))
        else:
            self._path_lbl.setText("")

    def _refresh(self) -> None:
        from windrose_save_editor.save.backup import list_backups
        from windrose_save_editor.save.location import find_save_root
        self._backups = list_backups(self._save_dir)
        self._list.clear()
        self._path_lbl.setText("")
        self._restore_btn.setEnabled(False)
        if not self._backups:
            self._status_lbl.setText("No backups found.")
            return
        try:
            root = find_save_root(self._save_dir)
            root_prefix = root.name + "_backup_"
        except Exception:
            root_prefix = ""
        for b in self._backups:
            ts  = b.name.split("_backup_")[-1]
            tag = "  [full save]" if (root_prefix and b.name.startswith(root_prefix)) else "  [players]"
            self._list.addItem(QListWidgetItem(f"  {ts}{tag}"))
        self._status_lbl.setText(f"{len(self._backups)} backup(s) found.")

    def _create_now(self) -> None:
        ok, msg = gui_create_backup(self._save_dir)
        if ok:
            QMessageBox.information(self, "Backup Created", msg)
        else:
            QMessageBox.critical(self, "Backup Failed", msg)
        self._refresh()

    def _restore(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._backups):
            return
        chosen = self._backups[row]
        reply = QMessageBox.question(
            self, "Restore Backup",
            f"Restore:\n  {chosen.name}\n\n"
            "The current save will be renamed to *_broken as a safety net.\n"
            "You will need to re-open the editor after restoring.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, msg = gui_restore_backup(self._save_dir, chosen)
        if ok:
            QMessageBox.information(self, "Restored", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Restore Failed", msg)


# ─────────────────────────────────────────────────────────────────────────────
# Bulk operations dialog
# ─────────────────────────────────────────────────────────────────────────────

class _BulkOpsDialog(QDialog):
    changes_made = Signal(list)

    def __init__(self, loaded: LoadedSave, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loaded = loaded
        self.setWindowTitle("Bulk Operations")
        self.setMinimumWidth(380)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        title = QLabel("Bulk Operations")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #c9d1d9;")
        layout.addWidget(title)

        layout.addWidget(self._section("STATS", [
            ("Max All Stats (all 6 to max)",    self._max_all_stats),
        ]))
        layout.addWidget(self._section("SKILLS", [
            ("Max All Skills",                  self._max_skills_all),
            ("Max Fencer",                      lambda: self._max_skills_cat("Fencer")),
            ("Max Crusher",                     lambda: self._max_skills_cat("Crusher")),
            ("Max Marksman",                    lambda: self._max_skills_cat("Marksman")),
            ("Max Toughguy",                    lambda: self._max_skills_cat("Toughguy")),
        ]))
        layout.addWidget(self._section("INVENTORY", [
            ("Max All Item Levels",             self._max_all_levels),
            ("Max All Stack Counts",            self._max_all_stacks),
            ("Max Everything (levels + stacks)", self._max_everything),
        ]))

        layout.addSpacing(8)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._log_lbl = QLabel("")
        self._log_lbl.setStyleSheet("color: #c9a84c; font-size: 11px;")
        self._log_lbl.setWordWrap(True)
        layout.addWidget(self._log_lbl)

    @staticmethod
    def _section(title: str, buttons: list[tuple[str, object]]) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 4, 0, 4)
        vbox.setSpacing(4)
        hdr = QLabel(title)
        hdr.setObjectName("section-header")
        vbox.addWidget(hdr)
        for label, slot in buttons:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            vbox.addWidget(btn)
        return w

    def _max_all_stats(self) -> None:
        from windrose_save_editor.editors.stats import max_all_stats
        self._emit(max_all_stats(self._loaded.session.doc) or ["Stats already maxed."])

    def _max_skills_all(self) -> None:
        from windrose_save_editor.editors.skills import max_all_skills
        self._emit(max_all_skills(self._loaded.session.doc) or ["Skills already maxed."])

    def _max_skills_cat(self, cat: str) -> None:
        from windrose_save_editor.editors.skills import max_all_skills
        self._emit(max_all_skills(self._loaded.session.doc, cat) or [f"{cat} already maxed."])

    def _max_all_levels(self) -> None:
        from windrose_save_editor.inventory.writer import max_all_levels
        self._emit(max_all_levels(self._loaded.session.doc) or ["Inventory already at max levels."])

    def _max_all_stacks(self) -> None:
        from windrose_save_editor.inventory.writer import max_safe_stacks
        c, _s, f = max_safe_stacks(self._loaded.session.doc)
        self._emit([f"Stacks: {c} maxed, {f} fixed." if c or f else "Stacks already maxed."])

    def _max_everything(self) -> None:
        self._max_all_stats()
        self._max_skills_all()
        self._max_all_levels()
        self._max_all_stacks()

    def _emit(self, msgs: list[str]) -> None:
        self._loaded.session.modified = True
        self._log_lbl.setText(msgs[-1] if msgs else "")
        self.changes_made.emit(msgs)


# ─────────────────────────────────────────────────────────────────────────────
# Interactive stat row (right panel)
# ─────────────────────────────────────────────────────────────────────────────

class _InteractiveStatRow(QWidget):
    changed = Signal(str, int)

    def __init__(self, stat: str) -> None:
        super().__init__()
        self._stat      = stat
        self._node_key  = ""
        self._max_level = 60
        color = _STAT_COLORS.get(stat, C_GOLD)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)

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

        name_lbl = QLabel(stat)
        name_lbl.setStyleSheet(f"color: {C_TEXT}; font-size: 11px;")
        name_lbl.setFixedWidth(70)
        row.addWidget(name_lbl)

        self._spin = QSpinBox()
        self._spin.setRange(0, 60)
        self._spin.setFixedWidth(58)
        self._spin.setStyleSheet(
            f"QSpinBox {{ border-color: {color}; }} "
            f"QSpinBox:focus {{ border-color: {color}; }}"
        )
        self._spin.valueChanged.connect(self._on_changed)
        row.addWidget(self._spin)

        max_btn = QPushButton("Max")
        max_btn.setFixedSize(38, 22)
        max_btn.setStyleSheet("font-size: 10px; padding: 0;")
        max_btn.clicked.connect(lambda: self._spin.setValue(self._max_level))
        row.addWidget(max_btn)

    def _on_changed(self, value: int) -> None:
        if self._node_key:
            self.changed.emit(self._node_key, value)

    def configure(self, node_key: str, level: int, max_level: int) -> None:
        self._node_key  = node_key
        self._max_level = max_level
        self._spin.setMaximum(max_level)
        self._spin.blockSignals(True)
        self._spin.setValue(level)
        self._spin.blockSignals(False)

    def reset(self) -> None:
        self._node_key = ""
        self._spin.blockSignals(True)
        self._spin.setValue(0)
        self._spin.blockSignals(False)


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

        # App identity
        logo = QLabel("⚓")
        logo.setStyleSheet(f"color: {C_GOLD}; font-size: 20px; padding-right: 8px;")
        title = QLabel("Windrose Save Editor")
        title.setStyleSheet(
            f"color: {C_TEXT}; font-size: 13px; font-weight: bold; letter-spacing: 1px;"
        )
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addSpacing(24)

        # Nav tabs
        self._tab_btns: dict[str, QPushButton] = {}
        for key, label in (("dashboard", "Dashboard"), ("editor", "Character Editor")):
            btn = QPushButton(label)
            btn.setObjectName("tab-btn")
            btn.setProperty("active", "false")
            btn.setFixedHeight(56)
            self._tab_btns[key] = btn
            layout.addWidget(btn)

        layout.addSpacing(20)

        # Character summary (hidden until load)
        self._char_info = QWidget()
        char_row = QHBoxLayout(self._char_info)
        char_row.setContentsMargins(0, 0, 0, 0)
        char_row.setSpacing(10)

        self._char_name_lbl = QLabel("—")
        self._char_name_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 13px; font-weight: bold;"
        )
        self._lvl_badge = QLabel("")
        self._lvl_badge.setObjectName("lvl-badge")
        char_row.addWidget(self._char_name_lbl)
        char_row.addWidget(self._lvl_badge)
        char_row.addSpacing(14)

        self._stat_value_lbls: dict[str, QLabel] = {}
        for stat in _STAT_ORDER:
            pm = icons.stat_icon(stat, 16)
            if not pm.isNull():
                ic = QLabel()
                ic.setPixmap(pm)
                char_row.addWidget(ic)
            val_lbl = QLabel("—")
            val_lbl.setObjectName("stat-value")
            val_lbl.setToolTip(stat)
            self._stat_value_lbls[stat] = val_lbl
            char_row.addWidget(val_lbl)
            char_row.addSpacing(2)

        self._char_info.hide()
        layout.addWidget(self._char_info)
        layout.addStretch(1)

        # ── "No save loaded" zone — shown before any save is opened
        self._no_save_zone = QWidget()
        nsl = QHBoxLayout(self._no_save_zone)
        nsl.setContentsMargins(0, 0, 0, 0)
        nsl.setSpacing(10)

        no_save_lbl = QLabel("No save loaded")
        no_save_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        nsl.addWidget(no_save_lbl)

        self._open_btn = QPushButton("Open Save…")
        self._open_btn.setObjectName("save-btn")
        self._open_btn.setFixedHeight(30)
        self._open_btn.setStyleSheet(
            "font-size: 12px; font-weight: bold; padding: 0 18px;"
        )
        nsl.addWidget(self._open_btn)
        layout.addWidget(self._no_save_zone)

        # ── Action buttons zone — hidden until save loaded
        self._action_zone = QWidget()
        self._action_zone.hide()
        al = QHBoxLayout(self._action_zone)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(6)

        self._bulk_btn   = QPushButton("Bulk Ops")
        self._backup_btn = QPushButton("Backups")
        self._reset_btn  = QPushButton("Reset")
        self._save_btn   = QPushButton("Save Changes")
        self._save_btn.setObjectName("save-btn")

        for btn in (self._bulk_btn, self._backup_btn, self._reset_btn,
                    self._save_btn):
            al.addWidget(btn)

        layout.addWidget(self._action_zone)

    # ── Public ────────────────────────────────────────────────────────────

    def set_active_tab(self, key: str) -> None:
        for k, btn in self._tab_btns.items():
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_character(self, name: str, stat_totals: dict[str, int]) -> None:
        self._char_name_lbl.setText(name)
        total_pts = sum(stat_totals.values())
        self._lvl_badge.setText(f"{total_pts} pts")
        for stat, val in stat_totals.items():
            if stat in self._stat_value_lbls:
                self._stat_value_lbls[stat].setText(str(val))
        self._char_info.show()
        # Swap zones
        self._no_save_zone.hide()
        self._action_zone.show()

    def clear_character(self) -> None:
        self._char_info.hide()
        self._action_zone.hide()
        self._no_save_zone.show()

    @property
    def tab_buttons(self) -> dict[str, QPushButton]:
        return self._tab_btns

    @property
    def open_button(self) -> QPushButton:
        return self._open_btn

    @property
    def save_button(self) -> QPushButton:
        return self._save_btn

    @property
    def reset_button(self) -> QPushButton:
        return self._reset_btn

    @property
    def backup_button(self) -> QPushButton:
        return self._backup_btn

    @property
    def bulk_button(self) -> QPushButton:
        return self._bulk_btn


# ─────────────────────────────────────────────────────────────────────────────
# Left panel — equipment
# ─────────────────────────────────────────────────────────────────────────────

class _EquipmentSlot(QFrame):
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

        tab_bar = QFrame()
        tab_bar.setStyleSheet(
            f"QFrame {{ background: transparent; border-bottom: 1px solid {C_BORDER}; }}"
        )
        tab_row = QHBoxLayout(tab_bar)
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(0)
        for label, active in (("CHARACTER", True), ("SHIP", False)):
            btn = QPushButton(label)
            btn.setObjectName("tab-btn")
            btn.setProperty("active", "true" if active else "false")
            btn.setFixedHeight(38)
            tab_row.addWidget(btn)
        outer.addWidget(tab_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._section("MODULES", _MODULE_SLOTS, cols=2))
        layout.addWidget(self._section("ARMOR",          _ARMOR_SLOTS,  cols=3))
        layout.addWidget(self._section("ACCESSORIES",    _ACC_SLOTS,    cols=3))

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    @staticmethod
    def _section(title: str, slots: list[str], cols: int = 3) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)
        hdr = QLabel(title)
        hdr.setObjectName("section-header")
        vbox.addWidget(hdr)
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, s in enumerate(slots):
            grid.addWidget(_EquipmentSlot(s), i // cols, i % cols)
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

        self._skills_tab = SkillsTab()
        layout.addWidget(self._skills_tab, 3)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        self._inventory_tab = InventoryTab()
        layout.addWidget(self._inventory_tab, 2)

    @property
    def skills_tab(self) -> SkillsTab:
        return self._skills_tab

    @property
    def inventory_tab(self) -> InventoryTab:
        return self._inventory_tab


# ─────────────────────────────────────────────────────────────────────────────
# Right panel — derived stats + interactive stat allocation
# ─────────────────────────────────────────────────────────────────────────────

class _RightPanel(QFrame):
    stat_changed = Signal(str, int)

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
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(20)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._layout.addWidget(self._build_derived_stats())
        self._layout.addWidget(self._build_stat_allocation())

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

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
            lbl = QLabel(label)
            lbl.setObjectName("muted")
            val = QLabel(value)
            val.setObjectName("stat-value")
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            vbox.addLayout(row)
        return w

    def _build_stat_allocation(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        hdr_row = QHBoxLayout()
        hdr = QLabel("STAT ALLOCATION")
        hdr.setObjectName("section-header")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        self._max_all_stats_btn = QPushButton("Max All")
        self._max_all_stats_btn.setFixedHeight(20)
        self._max_all_stats_btn.setStyleSheet("font-size: 10px; padding: 0 8px;")
        self._max_all_stats_btn.setEnabled(False)
        self._max_all_stats_btn.clicked.connect(self._on_max_all_stats)
        hdr_row.addWidget(self._max_all_stats_btn)
        vbox.addLayout(hdr_row)

        self._stat_rows: dict[str, _InteractiveStatRow] = {}
        for stat in _STAT_ORDER:
            row = _InteractiveStatRow(stat)
            row.changed.connect(self.stat_changed)
            self._stat_rows[stat] = row
            vbox.addWidget(row)

        return w

    def _on_max_all_stats(self) -> None:
        for row in self._stat_rows.values():
            row._spin.setValue(row._max_level)

    def update_stats(self, entries) -> None:
        name_map = {e.name: e for e in entries}
        for stat, row in self._stat_rows.items():
            entry = name_map.get(stat)
            if entry:
                row.configure(entry.node_key, entry.level, entry.max_level)
        self._max_all_stats_btn.setEnabled(True)

    def clear_stats(self) -> None:
        for row in self._stat_rows.values():
            row.reset()
        self._max_all_stats_btn.setEnabled(False)


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
    def inventory_tab(self) -> InventoryTab:
        return self._center.inventory_tab

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
        self._loaded: LoadedSave | None = None
        self._changelog: list[str] = []
        self._save_worker: _SaveWorker | None = None
        self._setup_ui()
        self._switch_page("dashboard")

    def _setup_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        self._topbar = _TopBar()
        vbox.addWidget(self._topbar)
        vbox.addWidget(self._stack_widget(), 1)

        # Nav tabs
        for key, btn in self._topbar.tab_buttons.items():
            btn.clicked.connect(lambda _c, k=key: self._switch_page(k))

        # Open / save / reset / backup / bulk
        self._topbar.open_button.clicked.connect(self._on_open_save)
        self._topbar.save_button.clicked.connect(self._on_save)
        self._topbar.reset_button.clicked.connect(self._on_reset)
        self._topbar.backup_button.clicked.connect(self._on_backup)
        self._topbar.bulk_button.clicked.connect(self._on_bulk_ops)

        # Wire stat / skill / inventory changes
        self._editor.right_panel.stat_changed.connect(self._on_stat_changed)
        self._editor.skills_tab.skill_changed.connect(self._on_skills_changed)
        self._editor.inventory_tab.item_changed.connect(self._on_item_changed)

        self.statusBar().showMessage("No save loaded — click Open Save to begin")

    def _stack_widget(self) -> QStackedWidget:
        self._stack   = QStackedWidget()
        self._dashboard = DashboardTab()
        self._editor    = _CharacterEditorView()
        self._stack.addWidget(self._dashboard)   # index 0
        self._stack.addWidget(self._editor)      # index 1
        return self._stack

    # ── Navigation ───────────────────────────────────────────────────────

    def _switch_page(self, key: str) -> None:
        self._topbar.set_active_tab(key)
        self._stack.setCurrentIndex(0 if key == "dashboard" else 1)

    # ── Open save ────────────────────────────────────────────────────────

    def _on_open_save(self) -> None:
        dlg = CharacterPickerDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        player_dir = dlg.selected_player_dir
        if player_dir is None:
            return

        prog = QProgressDialog("Loading save…", None, 0, 0, self)
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(200)
        prog.setValue(0)

        try:
            loaded = load_save_session(player_dir)
        except Exception as exc:
            prog.close()
            QMessageBox.critical(self, "Load Failed", str(exc))
            return
        prog.close()

        self._loaded = loaded
        self._changelog.clear()
        self._populate_from_load(loaded)

    # ── Populate all panels ───────────────────────────────────────────────

    def _populate_from_load(self, loaded: LoadedSave) -> None:
        from windrose_save_editor.editors.stats import get_stats
        from windrose_save_editor.editors.skills import get_skills

        session = loaded.session
        stats   = get_stats(session.doc)
        skills  = get_skills(session.doc)

        stat_totals = {e.name: e.level for e in stats}
        self._topbar.set_character(loaded.player_name, stat_totals)

        self._editor.skills_tab.set_session(session)
        self._editor.skills_tab.load_skills(skills)
        self._editor.right_panel.update_stats(stats)
        self._editor.inventory_tab.load_items(session)

        self._switch_page("editor")
        self._update_status()

    # ── Save ─────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        if self._loaded is None:
            return

        if not self._loaded.session.modified:
            QMessageBox.information(self, "No Changes", "Nothing has been modified.")
            return

        if is_game_running():
            QMessageBox.warning(
                self, "Game is Running",
                "Windrose appears to be running.\n\n"
                "Please quit the game via the in-game menu (Esc → Quit) "
                "before saving, otherwise the game will overwrite your changes.",
            )
            return

        log_text = (
            "\n".join(f"  • {c}" for c in self._changelog[-20:])
            if self._changelog else "  (modifications tracked)"
        )
        reply = QMessageBox.question(
            self, "Save Changes",
            f"Write these changes to the save file?\n\n{log_text}\n\n"
            "A backup will be created automatically before writing.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._topbar.save_button.setEnabled(False)
        self._topbar.save_button.setText("Saving…")

        self._save_worker = _SaveWorker(self._loaded)
        self._save_worker.finished.connect(self._on_save_finished)
        self._save_worker.start()

    def _on_save_finished(self, success: bool, message: str) -> None:
        self._topbar.save_button.setText("Save Changes")
        self._topbar.save_button.setEnabled(True)
        if success:
            self._changelog.clear()
            QMessageBox.information(self, "Saved", message)
        else:
            QMessageBox.critical(self, "Save Failed", message)
        self._update_status()

    # ── Reset ─────────────────────────────────────────────────────────────

    def _on_reset(self) -> None:
        if self._loaded is None:
            return
        if not self._loaded.session.modified:
            QMessageBox.information(self, "No Changes", "Nothing to reset.")
            return
        reply = QMessageBox.question(
            self, "Reset Changes",
            "Discard all unsaved changes and reload the original save data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from windrose_save_editor.bson.parser import parse_bson
        session = self._loaded.session
        session.doc = parse_bson(session.original_bson)
        session.modified = False
        self._changelog.clear()
        self._populate_from_load(self._loaded)
        self.statusBar().showMessage("Reset to original save data.")

    # ── Backup ───────────────────────────────────────────────────────────

    def _on_backup(self) -> None:
        if self._loaded is None:
            return
        dlg = _BackupDialog(self._loaded.session.save_dir, self)
        dlg.exec()

    # ── Bulk ops ──────────────────────────────────────────────────────────

    def _on_bulk_ops(self) -> None:
        if self._loaded is None:
            return
        dlg = _BulkOpsDialog(self._loaded, self)
        dlg.changes_made.connect(self._on_bulk_changes)
        dlg.exec()

    def _on_bulk_changes(self, msgs: list[str]) -> None:
        self._changelog.extend(msgs)
        if self._loaded:
            from windrose_save_editor.editors.stats import get_stats
            from windrose_save_editor.editors.skills import get_skills
            stats  = get_stats(self._loaded.session.doc)
            skills = get_skills(self._loaded.session.doc)
            self._editor.right_panel.update_stats(stats)
            self._editor.skills_tab.load_skills(skills)
            self._editor.inventory_tab.reload()
            self._topbar.set_character(
                self._loaded.player_name,
                {e.name: e.level for e in stats},
            )
        self._update_status()

    # ── Change handlers ───────────────────────────────────────────────────

    def _on_stat_changed(self, node_key: str, new_level: int) -> None:
        if self._loaded is None or not node_key:
            return
        from windrose_save_editor.editors.stats import get_stats, set_stat_level
        set_stat_level(self._loaded.session.doc, node_key, new_level)
        self._loaded.session.modified = True
        stats = get_stats(self._loaded.session.doc)
        self._topbar.set_character(
            self._loaded.player_name,
            {e.name: e.level for e in stats},
        )
        stat_name = next(
            (e.name for e in stats if e.node_key == node_key), node_key
        )
        self._log(f"Stat: {stat_name} → {new_level}")

    def _on_skills_changed(self, msgs: list[str]) -> None:
        self._changelog.extend(msgs)
        self._update_status()

    def _on_item_changed(self, msg: str) -> None:
        self._log(msg)

    def _log(self, msg: str) -> None:
        self._changelog.append(msg)
        self._update_status()

    # ── Status bar ────────────────────────────────────────────────────────

    def _update_status(self) -> None:
        if self._loaded is None:
            self.statusBar().showMessage("No save loaded — click Open Save to begin")
            return
        if self._loaded.session.modified:
            n = len(self._changelog)
            self.statusBar().showMessage(
                f"{self._loaded.player_name}  —  {n} unsaved change(s)  ·  "
                f"{self._loaded.session.save_dir}"
            )
        else:
            self.statusBar().showMessage(
                f"{self._loaded.player_name}  —  No unsaved changes  ·  "
                f"{self._loaded.session.save_dir}"
            )

    # ── Public surface ────────────────────────────────────────────────────

    @property
    def skills_tab(self) -> SkillsTab:
        return self._editor.skills_tab
