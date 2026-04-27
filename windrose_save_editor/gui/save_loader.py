from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QWidget,
    QComboBox, QMessageBox,
)
from PySide6.QtCore import Qt

from windrose_save_editor.bson.parser import parse_bson
from windrose_save_editor.save.commit import SaveSession
from windrose_save_editor.save.location import (
    find_profiles_root, find_accounts, find_player_dirs,
    peek_player_name, resolve_save_dir, find_wal,
)


@dataclass
class LoadedSave:
    session: SaveSession
    player_name: str


def load_save_session(player_dir: Path) -> LoadedSave:
    """
    Load a complete SaveSession from a player directory (the folder
    containing CURRENT).  Tries WAL first, falls back to SST scan.
    Raises RuntimeError on failure.
    """
    save_dir = resolve_save_dir(player_dir)
    wal_path = find_wal(save_dir)

    from windrose_save_editor.rocksdb.wal import read_wal
    result = read_wal(wal_path)

    if result is not None:
        seq         = result.sequence
        cf_id       = result.cf_id
        player_key  = result.player_key
        bson_bytes  = result.bson_bytes
        batch_count = result.batch_count
    else:
        from windrose_save_editor.rocksdb.sst import scan_sst_for_player
        sst = scan_sst_for_player(save_dir)
        if sst is None:
            raise RuntimeError(
                "Could not find player data in WAL or SST files.\n"
                f"Folder: {save_dir}"
            )
        player_key, bson_bytes = sst
        seq         = 99999
        cf_id       = 2
        batch_count = 1

    doc         = parse_bson(bson_bytes)
    player_name = str(doc.get("PlayerName", save_dir.name))

    session = SaveSession(
        save_dir     = save_dir,
        wal_path     = wal_path,
        player_key   = player_key,
        doc          = doc,
        original_bson= bson_bytes,
        seq          = seq,
        cf_id        = cf_id,
        batch_count  = batch_count,
        modified     = False,
        backed_up    = False,
    )
    return LoadedSave(session=session, player_name=player_name)


# ─────────────────────────────────────────────────────────────────────────────
# Character picker dialog  (reference-style)
# ─────────────────────────────────────────────────────────────────────────────

class CharacterPickerDialog(QDialog):
    """
    Auto-detects Windrose save profiles, shows an account combo and a
    character list.  Falls back to a manual folder browser.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open Save")
        self.setMinimumWidth(520)
        self.setMinimumHeight(360)
        self._profiles_root: Path | None = None
        self._accounts: list[tuple[Path, str]] = []   # [(dir, account_type)]
        self._selected_dir: Path | None = None
        self._build_ui()
        self._detect()

    @property
    def selected_player_dir(self) -> Path | None:
        return self._selected_dir

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(18, 18, 18, 16)

        title = QLabel("Select Character Save")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #c9d1d9;")
        lay.addWidget(title)

        self._status_lbl = QLabel("Searching for save folder…")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet("color: #6b7685; font-size: 11px;")
        lay.addWidget(self._status_lbl)

        # Account row (hidden when ≤1 account)
        self._acct_row = QWidget()
        acct_lay = QHBoxLayout(self._acct_row)
        acct_lay.setContentsMargins(0, 0, 0, 0)
        acct_lay.setSpacing(8)
        acct_lay.addWidget(QLabel("Account:"))
        self._acct_combo = QComboBox()
        self._acct_combo.currentIndexChanged.connect(self._on_account_changed)
        acct_lay.addWidget(self._acct_combo, 1)
        lay.addWidget(self._acct_row)

        char_lbl = QLabel("Character:")
        char_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: bold;")
        lay.addWidget(char_lbl)

        self._char_list = QListWidget()
        self._char_list.setMinimumHeight(160)
        self._char_list.setStyleSheet(
            "QListWidget { background: #111318; border: 1px solid #1e2229;"
            "               border-radius: 4px; }"
            "QListWidget::item { padding: 10px 14px; color: #c9d1d9; }"
            "QListWidget::item:selected { background: #1e2229; color: #c9a84c; }"
            "QListWidget::item:hover { background: #16191f; }"
        )
        self._char_list.itemDoubleClicked.connect(self._accept_selection)
        self._char_list.currentRowChanged.connect(self._on_row_changed)
        lay.addWidget(self._char_list, 1)

        self._path_lbl = QLabel("")
        self._path_lbl.setStyleSheet("color: #3a4555; font-size: 10px;")
        lay.addWidget(self._path_lbl)

        # Button row
        btn_row = QHBoxLayout()

        browse_btn = QPushButton("Browse manually…")
        browse_btn.clicked.connect(self._browse_manually)
        btn_row.addWidget(browse_btn)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._ok_btn = QPushButton("Open")
        self._ok_btn.setObjectName("save-btn")
        self._ok_btn.setDefault(True)
        self._ok_btn.setEnabled(False)
        self._ok_btn.clicked.connect(self._accept_selection)
        btn_row.addWidget(self._ok_btn)

        lay.addLayout(btn_row)

    # ── Auto-detect ───────────────────────────────────────────────────────

    def _detect(self) -> None:
        profiles_root = find_profiles_root()
        if not profiles_root or not profiles_root.exists():
            self._status_lbl.setText(
                "Could not auto-detect save folder.  Use 'Browse manually…' to locate it."
            )
            self._acct_row.hide()
            return

        self._profiles_root = profiles_root
        self._status_lbl.setText(f"Detected:  {profiles_root}")

        try:
            self._accounts = find_accounts(profiles_root)
        except Exception as exc:
            self._status_lbl.setText(f"Scan error: {exc}")
            self._acct_row.hide()
            return

        if not self._accounts:
            self._status_lbl.setText(
                f"No account folders found in:\n{profiles_root}\n"
                "Use 'Browse manually…' instead."
            )
            self._acct_row.hide()
            return

        self._acct_combo.blockSignals(True)
        for acc_dir, acc_type in self._accounts:
            label = f"[{acc_type or 'Unknown'}]  {acc_dir.name}"
            self._acct_combo.addItem(label, userData=acc_dir)
        self._acct_combo.blockSignals(False)

        self._acct_row.setVisible(len(self._accounts) > 1)
        self._load_characters(self._accounts[0][0])

    def _load_characters(self, account_dir: Path) -> None:
        self._char_list.clear()
        self._ok_btn.setEnabled(False)
        self._path_lbl.setText("")

        player_dirs = list(find_player_dirs(account_dir))
        if not player_dirs:
            item = QListWidgetItem("  (No characters found)")
            item.setData(Qt.ItemDataRole.UserRole, None)
            self._char_list.addItem(item)
            return

        for pd in sorted(player_dirs):
            name = peek_player_name(pd)
            label = f"  {name}   |   {pd.name}" if name else f"  {pd.name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, pd)
            self._char_list.addItem(item)

        self._char_list.setCurrentRow(0)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_account_changed(self, idx: int) -> None:
        if 0 <= idx < len(self._accounts):
            self._load_characters(self._accounts[idx][0])

    def _on_row_changed(self, row: int) -> None:
        item = self._char_list.item(row) if row >= 0 else None
        enabled = item is not None and item.data(Qt.ItemDataRole.UserRole) is not None
        self._ok_btn.setEnabled(enabled)
        if item:
            pd = item.data(Qt.ItemDataRole.UserRole)
            self._path_lbl.setText(str(pd) if pd else "")

    def _accept_selection(self) -> None:
        item = self._char_list.currentItem()
        if item is None:
            return
        pd = item.data(Qt.ItemDataRole.UserRole)
        if pd:
            self._selected_dir = pd
            self.accept()

    def _browse_manually(self) -> None:
        start = str(self._profiles_root) if self._profiles_root else ""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select the player save folder (containing CURRENT)",
            start,
        )
        if not path:
            return
        try:
            resolved = resolve_save_dir(Path(path))
        except Exception:
            resolved = Path(path)
        if not (resolved / "CURRENT").exists():
            QMessageBox.critical(
                self, "Not a save folder",
                f"No RocksDB save found in:\n{path}\n\n"
                "Select the folder that contains CURRENT, MANIFEST-*, and *.log files.\n"
                "Typically: …\\SaveProfiles\\<ID>\\RocksDB\\0.10.0\\Players\\<GUID>",
            )
            return
        self._selected_dir = resolved
        self.accept()
