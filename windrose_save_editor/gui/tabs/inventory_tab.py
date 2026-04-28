from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMenu,
    QInputDialog, QMessageBox, QStackedWidget, QScrollArea, QFrame,
    QGridLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from windrose_save_editor.gui import icons
from windrose_save_editor.gui.style import C_MUTED, C_BORDER
from windrose_save_editor.inventory.reader import get_all_items, ItemRecord
from windrose_save_editor.inventory.writer import (
    max_all_levels, max_safe_stacks,
)
from windrose_save_editor.save.commit import SaveSession

_COL_NAME   = 0
_COL_LEVEL  = 1
_COL_COUNT  = 2
_COL_MODULE = 3

_ICON_COLS  = 5
_ICON_CELL_W = 72
_ICON_CELL_H = 88
_ICON_SIZE   = 56


class _IconCell(QFrame):
    def __init__(self, item: ItemRecord) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setFixedSize(_ICON_CELL_W, _ICON_CELL_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(item.get('item_params', ''))

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)

        pm = icons.item_icon(item.get('item_params', ''), _ICON_SIZE)
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        if not pm.isNull():
            icon_lbl.setPixmap(pm)
        else:
            icon_lbl.setText("?")
            icon_lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 18px; font-weight: bold;"
                f"border: 1px solid {C_BORDER}; border-radius: 4px;"
            )
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        name = item['item_name']
        name_lbl = QLabel(name[:14] + "…" if len(name) > 14 else name)
        name_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 9px;")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setFixedWidth(_ICON_CELL_W - 8)
        vbox.addWidget(name_lbl, 0, Qt.AlignmentFlag.AlignHCenter)


class InventoryTab(QWidget):
    """
    Item list with list/icon layout toggle.
    Wire item_changed to mark session.modified = True in the parent.
    """

    item_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: SaveSession | None = None
        self._items: list[ItemRecord] = []
        self._layout_mode = 'list'
        self._setup_ui()

    # ── Build UI ─────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 6, 12, 6)
        toolbar.setSpacing(6)

        hdr = QLabel("MAIN INVENTORY")
        hdr.setObjectName("section-header")
        toolbar.addWidget(hdr)
        toolbar.addSpacing(6)

        self._layout_btns: dict[str, QLabel] = {}
        for mode in ('list', 'icon'):
            lbl = QLabel(mode)
            lbl.setObjectName("layout-btn")
            lbl.setProperty("active", "true" if mode == self._layout_mode else "false")
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.mousePressEvent = lambda _e, m=mode: self._switch_layout(m)
            self._layout_btns[mode] = lbl
            toolbar.addWidget(lbl)

        toolbar.addStretch()

        self._set_lv_btn  = self._tb_btn("Set Level",  self._on_set_level)
        self._set_qty_btn = self._tb_btn("Set Count",  self._on_set_count)
        self._max_lv_btn  = self._tb_btn("Max Level",  self._on_max_level)
        sep_lbl = QLabel("|")
        sep_lbl.setStyleSheet(f"color: {C_BORDER};")
        self._max_all_btn       = self._tb_btn("Max All Levels",  self._on_max_all_levels)
        self._max_stack_btn     = self._tb_btn("Max All Stacks",  self._on_max_all_stacks)
        self._max_all_items_btn = self._tb_btn("Max Everything",  self._on_max_everything)

        for w in (self._set_lv_btn, self._set_qty_btn, self._max_lv_btn,
                  sep_lbl,
                  self._max_all_btn, self._max_stack_btn, self._max_all_items_btn):
            toolbar.addWidget(w)

        self._set_lv_btn.setEnabled(False)
        self._set_qty_btn.setEnabled(False)
        self._max_lv_btn.setEnabled(False)

        root.addLayout(toolbar)

        # ── Stacked view
        self._view_stack = QStackedWidget()

        # Stack 0 — list view (table)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Item", "Lv", "Qty", "Mod"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(
            "QTableWidget { background: #0c0d10; alternate-background-color: #111318;"
            "               border: none; gridline-color: #1e2229; }"
            "QTableWidget::item { padding: 4px 8px; color: #c9d1d9; border: none; }"
            "QTableWidget::item:selected { background: #1e2229; color: #c9a84c; }"
            "QHeaderView::section { background: #111318; color: #6b7685;"
            "    border: none; border-bottom: 1px solid #1e2229; padding: 4px 8px;"
            "    font-size: 10px; font-weight: bold; }"
        )
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        self._table.currentCellChanged.connect(lambda r, c, pr, pc: self._on_row_changed(r))
        self._view_stack.addWidget(self._table)   # index 0

        # Stack 1 — icon grid view
        self._icon_scroll = QScrollArea()
        self._icon_scroll.setWidgetResizable(True)
        self._icon_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._icon_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._icon_container = QWidget()
        self._icon_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._icon_grid = QGridLayout(self._icon_container)
        self._icon_grid.setContentsMargins(12, 8, 12, 8)
        self._icon_grid.setSpacing(8)
        self._icon_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Phantom stretch column fills remaining horizontal space
        self._icon_grid.setColumnStretch(_ICON_COLS, 1)
        self._icon_scroll.setWidget(self._icon_container)
        self._view_stack.addWidget(self._icon_scroll)  # index 1

        root.addWidget(self._view_stack, 1)

        # ── Footer count
        self._count_lbl = QLabel("No save loaded")
        self._count_lbl.setObjectName("muted")
        self._count_lbl.setContentsMargins(12, 4, 12, 4)
        root.addWidget(self._count_lbl)

    @staticmethod
    def _tb_btn(label: str, slot: Callable) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedHeight(24)
        btn.setStyleSheet("font-size: 11px; padding: 0 10px;")
        btn.clicked.connect(slot)
        return btn

    # ── Layout toggle ─────────────────────────────────────────────────────

    def _switch_layout(self, mode: str) -> None:
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        for m, lbl in self._layout_btns.items():
            lbl.setProperty("active", "true" if m == mode else "false")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)
        if mode == 'list':
            self._view_stack.setCurrentIndex(0)
        else:
            self._populate_icon_grid()
            self._view_stack.setCurrentIndex(1)

    # ── Public API ────────────────────────────────────────────────────────

    def load_items(self, session: SaveSession) -> None:
        self._session = session
        self.reload()

    def reload(self) -> None:
        if self._session is None:
            return
        self._items = get_all_items(self._session.doc)
        self._populate_table()
        if self._layout_mode == 'icon':
            self._populate_icon_grid()

    def clear(self) -> None:
        self._session = None
        self._items = []
        self._table.setRowCount(0)
        self._count_lbl.setText("No save loaded")

    # ── Populate list ─────────────────────────────────────────────────────

    def _populate_table(self) -> None:
        self._table.setRowCount(0)
        for item in self._items:
            row = self._table.rowCount()
            self._table.insertRow(row)

            name_cell = QTableWidgetItem(item["item_name"])
            name_cell.setToolTip(item.get("item_params", ""))

            lv = item["level"]
            ml = item["max_level"]
            if lv is not None and ml is not None:
                lv_cell = QTableWidgetItem(f"{lv}/{ml}")
                if lv >= ml:
                    lv_cell.setForeground(QColor("#c9a84c"))
            else:
                lv_cell = QTableWidgetItem("—")
                lv_cell.setForeground(QColor("#3a4555"))

            cnt = item["count"]
            qty_cell = QTableWidgetItem(str(cnt) if cnt > 1 else "")
            mod_cell = QTableWidgetItem(str(item["module"]))

            for cell in (name_cell, lv_cell, qty_cell, mod_cell):
                cell.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            self._table.setItem(row, _COL_NAME,   name_cell)
            self._table.setItem(row, _COL_LEVEL,  lv_cell)
            self._table.setItem(row, _COL_COUNT,  qty_cell)
            self._table.setItem(row, _COL_MODULE, mod_cell)

        self._count_lbl.setText(f"{len(self._items)} items")

    # ── Populate icon grid ────────────────────────────────────────────────

    def _populate_icon_grid(self) -> None:
        while self._icon_grid.count():
            child = self._icon_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for idx, item in enumerate(self._items):
            cell = _IconCell(item)
            self._icon_grid.addWidget(cell, idx // _ICON_COLS, idx % _ICON_COLS)

        # Fill last row with spacers so cells align left
        remaining = len(self._items) % _ICON_COLS
        if remaining:
            for i in range(_ICON_COLS - remaining):
                spacer = QWidget()
                spacer.setFixedSize(_ICON_CELL_W, _ICON_CELL_H)
                last_row = len(self._items) // _ICON_COLS
                self._icon_grid.addWidget(spacer, last_row, remaining + i)

    # ── Selection ─────────────────────────────────────────────────────────

    def _on_row_changed(self, row: int) -> None:
        has_sel = 0 <= row < len(self._items)
        item    = self._items[row] if has_sel else None
        has_lv  = has_sel and item is not None and item["level"] is not None
        self._set_lv_btn.setEnabled(has_lv)
        self._max_lv_btn.setEnabled(has_lv)
        self._set_qty_btn.setEnabled(has_sel)

    def _selected_item(self) -> ItemRecord | None:
        row = self._table.currentRow()
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    # ── Context menu ──────────────────────────────────────────────────────

    def _context_menu(self, pos) -> None:
        item = self._selected_item()
        if item is None:
            return
        menu = QMenu(self)
        if item["level"] is not None:
            menu.addAction("Set Level…",  self._on_set_level)
            menu.addAction("Max Level",   self._on_max_level)
        menu.addAction("Set Count…", self._on_set_count)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    # ── Item editing ──────────────────────────────────────────────────────

    def _on_set_level(self) -> None:
        it = self._selected_item()
        if it is None or it["level"] is None:
            return
        val, ok = QInputDialog.getInt(
            self, "Set Level",
            f"New level for '{it['item_name']}':",
            it["level"], 0, it["max_level"] or 99,
        )
        if not ok:
            return
        for a in it["attrs_ref"].values():
            if isinstance(a, dict) and "Level" in a.get("Tag", {}).get("TagName", ""):
                a["Value"] = val
                break
        self._mark_changed(f"Level: {it['item_name']} → {val}")

    def _on_set_count(self) -> None:
        it = self._selected_item()
        if it is None:
            return
        val, ok = QInputDialog.getInt(
            self, "Set Count",
            f"New count for '{it['item_name']}':",
            it["count"], 1, 99999,
        )
        if not ok:
            return
        it["stack_ref"]["Count"] = val
        self._mark_changed(f"Count: {it['item_name']} → {val}")

    def _on_max_level(self) -> None:
        it = self._selected_item()
        if it is None or it["level"] is None or it["max_level"] is None:
            return
        for a in it["attrs_ref"].values():
            if isinstance(a, dict) and "Level" in a.get("Tag", {}).get("TagName", ""):
                a["Value"] = it["max_level"]
                break
        self._mark_changed(f"Max level: {it['item_name']} → {it['max_level']}")

    def _on_max_all_levels(self) -> None:
        if self._session is None:
            return
        msgs = max_all_levels(self._session.doc)
        if msgs:
            self._mark_changed(f"Max all levels ({len(msgs)} items)")

    def _on_max_all_stacks(self) -> None:
        if self._session is None:
            return
        changed, _skipped, fixed = max_safe_stacks(self._session.doc)
        if changed or fixed:
            self._mark_changed(f"Max stacks: {changed} maxed, {fixed} fixed")

    def _on_max_everything(self) -> None:
        if self._session is None:
            return
        lvl_msgs = max_all_levels(self._session.doc)
        changed, _skipped, fixed = max_safe_stacks(self._session.doc)
        if lvl_msgs or changed or fixed:
            self._mark_changed(
                f"Max everything: {len(lvl_msgs)} levels, {changed} stacks"
            )

    def _mark_changed(self, msg: str) -> None:
        if self._session:
            self._session.modified = True
        self.reload()
        self.item_changed.emit(msg)
