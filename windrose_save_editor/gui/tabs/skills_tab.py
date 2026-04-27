from __future__ import annotations

import math
from dataclasses import dataclass, field

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGraphicsScene,
    QGraphicsView, QGraphicsObject, QGraphicsItem,
    QLabel, QPushButton, QSpinBox, QFrame,
    QGraphicsLineItem,
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QLineF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont,
)

from windrose_save_editor.gui import icons

# ── Layout constants ──────────────────────────────────────────────────────────
# Math angles: 0° = right, 90° = up (standard).  Screen y-axis is inverted.
_QUAD_ANGLE: dict[str, float] = {
    "Fencer":   90.0,
    "Crusher":   0.0,
    "Marksman": 270.0,
    "Toughguy": 180.0,
}
_CAT_NAME: dict[int, str] = {1: "Fencer", 2: "Crusher", 3: "Marksman", 4: "Toughguy"}
_RING_R: dict[int, float] = {1: 118.0, 2: 205.0, 3: 288.0}
_POS_OFFSET: dict[int, float] = {1: -33.0, 2: -11.0, 3: 11.0, 4: 33.0}
_NODE_R: float = 27.0

# Fallback colours (used when icon assets are missing)
_C_BG        = QColor("#080c13")
_C_DIV_LINE  = QColor("#1e2a3a")
_C_LOCKED    = QColor("#2d3a4a")
_C_PARTIAL   = QColor("#4a7a9b")
_C_MAXED     = QColor("#c9a84c")
_C_NODE_FILL = QColor("#111827")
_C_BADGE_BG  = QColor("#080c13")
_C_BADGE_TEXT = QColor("#e8d5a3")

# ── Slot layout data ──────────────────────────────────────────────────────────
_SLOT_TABLE: list[tuple[str, int, int, int]] = [
    # Fencer (cat=1)
    ("DA_Talent_Fencer_SlashDamage",                         1, 1, 1),
    ("DA_Talent_Fencer_LessStaminaForDash",                  1, 1, 2),
    ("DA_Talent_Fencer_OneHandedMeleeCritChance",             1, 1, 3),
    ("DA_Talent_Fencer_OneHandedDamage",                     1, 2, 1),
    ("DA_Talent_Fencer_CritChanceForPerfectBlock",           1, 2, 2),
    ("DA_Talent_Fencer_DamageForSoloEnemy",                  1, 2, 3),
    ("DA_Talent_Fencer_HealForKill",                         1, 3, 2),
    # 1.3.3 — two perks share one visual node
    ("DA_Talent_Fencer_PassiveReloadBoostForPerfectBlock",   1, 3, 3),
    ("DA_Talent_Fencer_PassiveReloadBoostForPerfectDodge",   1, 3, 3),
    ("DA_Talent_Fencer_ConsecutiveMeleeHitsBonus",           1, 3, 4),
    # Crusher (cat=2)
    ("DA_Talent_Crusher_CrudeDamage",                        2, 1, 2),
    ("DA_Talent_Crusher_TemporalHPHealBuff",                 2, 1, 3),
    ("DA_Talent_Crusher_TwoHandedDamage",                    2, 2, 1),
    ("DA_Talent_Crusher_TwoHandedStaminaReduced",            2, 2, 2),
    ("DA_Talent_Crusher_TwoHandedMeleeCritChance",           2, 2, 3),
    ("DA_Talent_Crusher_Berserk",                            2, 3, 1),
    ("DA_Talent_Crusher_DamageForDeathNearby",               2, 3, 2),
    ("DA_Talent_Crusher_DamageForMultipleTargets",           2, 3, 3),
    # Marksman (cat=3)
    ("DA_Talent_Marksman_PassiveReloadBonus",                3, 1, 1),
    ("DA_Talent_Marksman_PierceDamage",                      3, 1, 2),
    ("DA_Talent_Marksman_RangeCritDamageBonus",              3, 1, 3),
    ("DA_Talent_Marksman_RangeDamageBonus",                  3, 2, 1),
    ("DA_Talent_Marksman_ActiveReloadSpeedBonus",            3, 2, 2),
    # 3.2.3 — two perks share one visual node
    ("DA_Talent_Marksman_DamageForDistance",                 3, 2, 3),
    ("DA_Talent_Marksman_DamageForPointBlank",               3, 2, 3),
    ("DA_Talent_Marksman_ConsecutiveRangeHitsBonus",         3, 3, 1),
    ("DA_Talent_Marksman_DamageForAimingState",              3, 3, 2),
    ("DA_Talent_Marksman_ReloadForKill",                     3, 3, 3),
    ("DA_Talent_Marksman_Overpenetration",                   3, 3, 4),
    # Toughguy (cat=4)
    ("DA_Talent_Toughguy_HealEffectiveness",                 4, 1, 1),
    ("DA_Talent_Toughguy_TempHPForDamageRecivedBonus",       4, 1, 2),
    ("DA_Talent_Toughguy_StaminaBonus",                      4, 1, 3),
    ("DA_Talent_Toughguy_GlobalDamageResist",                4, 2, 1),
    ("DA_Talent_Toughguy_BlockPostureConsumptionBonus",      4, 2, 2),
    ("DA_Talent_Toughguy_DamageForManyEnemies",              4, 2, 3),
    ("DA_Talent_Toughguy_SaveOnLowHP",                       4, 3, 2),
    ("DA_Talent_Toughguy_ExtraHP",                           4, 3, 3),
]


def _slot_pos(cat: int, ring: int, pos: int) -> QPointF:
    angle_deg = _QUAD_ANGLE[_CAT_NAME[cat]] + _POS_OFFSET[pos]
    angle_rad = math.radians(angle_deg)
    r = _RING_R[ring]
    return QPointF(r * math.cos(angle_rad), -r * math.sin(angle_rad))


# ── Slot data structure ───────────────────────────────────────────────────────

@dataclass
class _SlotInfo:
    cat:      int
    ring:     int
    pos:      int
    da_keys:  list[str] = field(default_factory=list)
    names:    list[str] = field(default_factory=list)
    descs:    list[str] = field(default_factory=list)
    level:    int       = 0
    max_level: int      = 3

    @property
    def slot_id(self) -> tuple[int, int, int]:
        return (self.cat, self.ring, self.pos)

    @property
    def primary_name(self) -> str:
        if len(self.names) == 1:
            return self.names[0]
        return " / ".join(w.split()[0] for w in self.names if w)

    @property
    def tooltip_html(self) -> str:
        parts: list[str] = []
        for name, desc in zip(self.names, self.descs):
            parts.append(f"<b>{name}</b><br><span style='color:#8b949e'>{desc}</span>")
        body = "<hr style='border-color:#30363d'>".join(parts)
        level_line = (
            f"<br><span style='color:#c9a84c'>{self.level} / {self.max_level}</span>"
        )
        return body + level_line


def _build_slots() -> list[_SlotInfo]:
    from windrose_save_editor.game_data import TALENT_NAMES, TALENT_DESCS

    index: dict[tuple[int, int, int], _SlotInfo] = {}
    for da_key, cat, ring, pos in _SLOT_TABLE:
        sid = (cat, ring, pos)
        if sid not in index:
            index[sid] = _SlotInfo(cat=cat, ring=ring, pos=pos)
        slot = index[sid]
        slot.da_keys.append(da_key)
        talent_key = da_key[3:] if da_key.startswith("DA_") else da_key
        slot.names.append(TALENT_NAMES.get(talent_key, da_key))
        slot.descs.append(TALENT_DESCS.get(talent_key, ""))

    return list(index.values())


# ── TalentNode ────────────────────────────────────────────────────────────────

class TalentNode(QGraphicsObject):
    clicked = Signal(object)

    def __init__(self, slot: _SlotInfo, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.slot = slot
        self.setAcceptHoverEvents(True)
        self.setToolTip(slot.tooltip_html)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False

    def boundingRect(self) -> QRectF:
        pad = 6.0
        r = _NODE_R + pad
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter, _option, _widget) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        r = _NODE_R
        level, max_lv = self.slot.level, self.slot.max_level

        # Determine visual state
        if level == 0:
            frame_state, icon_opacity = "nonlearn", 0.25
        elif level >= max_lv:
            frame_state, icon_opacity = "learn", 1.0
        else:
            frame_state, icon_opacity = "default", 0.70

        frame_rect = QRectF(-r, -r, r * 2, r * 2)

        # ── Slot frame
        frame_pm = icons.slot_frame(frame_state)
        if not frame_pm.isNull():
            painter.drawPixmap(frame_rect, frame_pm, QRectF(frame_pm.rect()))
        else:
            # Fallback drawn circle when asset is missing
            col = _C_LOCKED if level == 0 else (_C_MAXED if level >= max_lv else _C_PARTIAL)
            if self._hovered:
                col = col.lighter(140)
            painter.setPen(QPen(col, 2.5))
            painter.setBrush(QBrush(_C_NODE_FILL))
            painter.drawEllipse(frame_rect)

        # ── Talent icon
        if self.slot.da_keys:
            icon_pm = icons.talent_icon(self.slot.da_keys[0])
            if not icon_pm.isNull():
                painter.setOpacity(icon_opacity)
                icon_r = r * 1.3
                painter.drawPixmap(
                    QRectF(-icon_r, -icon_r, icon_r * 2, icon_r * 2),
                    icon_pm,
                    QRectF(icon_pm.rect()),
                )
                painter.setOpacity(1.0)

        # ── Partial progress arc (teal ring)
        if 0 < level < max_lv:
            painter.setPen(QPen(QColor("#4a8fa8"), 2.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            span = int(360 * level / max_lv * 16)
            painter.drawArc(
                QRectF(-r + 3, -r + 3, (r - 3) * 2, (r - 3) * 2),
                90 * 16, -span,
            )

        # ── Hover select overlay
        if self._hovered:
            select_pm = icons.slot_frame("select")
            if not select_pm.isNull():
                painter.setOpacity(0.85)
                painter.drawPixmap(frame_rect, select_pm, QRectF(select_pm.rect()))
                painter.setOpacity(1.0)
            else:
                painter.setPen(QPen(QColor(255, 255, 255, 100), 2.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                outer = r + 4
                painter.drawEllipse(QRectF(-outer, -outer, outer * 2, outer * 2))

        # ── Level badge
        if level > 0 or self._hovered:
            badge_rect = QRectF(-13, r - 11, 26, 12)
            col = _C_MAXED if level >= max_lv else _C_PARTIAL
            painter.setBrush(QBrush(_C_BADGE_BG))
            painter.setPen(QPen(col, 0.8))
            painter.drawRoundedRect(badge_rect, 3, 3)
            painter.setPen(QPen(_C_BADGE_TEXT))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"{level}/{max_lv}")

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.slot)
        super().mousePressEvent(event)

    def update_level(self, level: int) -> None:
        self.slot.level = level
        self.setToolTip(self.slot.tooltip_html)
        self.update()


# ── Scene ─────────────────────────────────────────────────────────────────────

class SkillTreeScene(QGraphicsScene):
    node_clicked = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setSceneRect(-380, -380, 760, 760)
        self.setBackgroundBrush(QBrush(_C_BG))

        self._nodes: dict[tuple[int, int, int], TalentNode] = {}
        self._slots: list[_SlotInfo] = _build_slots()

        # Background image (contains rings, dividers, compass, labels)
        bg_pm = icons.talent_tree_bg(760)
        if not bg_pm.isNull():
            bg_item = self.addPixmap(bg_pm)
            bg_item.setPos(-380, -380)
            bg_item.setZValue(-10)
        else:
            self._draw_fallback_background()

        self._draw_connections()
        self._draw_nodes()

    def _draw_fallback_background(self) -> None:
        """Minimal fallback rings when the background image file is missing."""
        ring_pen = QPen(_C_DIV_LINE, 0.8)
        for r in _RING_R.values():
            from PySide6.QtWidgets import QGraphicsEllipseItem
            item = QGraphicsEllipseItem(QRectF(-r, -r, r * 2, r * 2))
            item.setPen(ring_pen)
            item.setBrush(Qt.BrushStyle.NoBrush)
            item.setZValue(-5)
            self.addItem(item)

    def _draw_connections(self) -> None:
        conn_pen = QPen(QColor("#1e2a3a"), 0.8)
        slot_set: set[tuple[int, int, int]] = {
            (cat, ring, pos) for _, cat, ring, pos in _SLOT_TABLE
        }
        for cat, ring, pos in slot_set:
            # Radial (ring to ring)
            if ring < 3 and (cat, ring + 1, pos) in slot_set:
                p1 = _slot_pos(cat, ring, pos)
                p2 = _slot_pos(cat, ring + 1, pos)
                line = QGraphicsLineItem(QLineF(p1, p2))
                line.setPen(conn_pen)
                line.setZValue(-2)
                self.addItem(line)
            # Tangential (position to position within same ring)
            if (cat, ring, pos + 1) in slot_set:
                p1 = _slot_pos(cat, ring, pos)
                p2 = _slot_pos(cat, ring, pos + 1)
                line = QGraphicsLineItem(QLineF(p1, p2))
                line.setPen(conn_pen)
                line.setZValue(-2)
                self.addItem(line)

    def _draw_nodes(self) -> None:
        for slot in self._slots:
            pt = _slot_pos(slot.cat, slot.ring, slot.pos)
            node = TalentNode(slot)
            node.setPos(pt)
            node.clicked.connect(self.node_clicked)
            self.addItem(node)
            self._nodes[slot.slot_id] = node

    # ── Public API ────────────────────────────────────────────────────────

    def load_skills(self, skills: dict[str, list]) -> None:
        from windrose_save_editor.editors.skills import SkillEntry

        da_to_level: dict[str, int] = {}
        for entries in skills.values():
            for entry in entries:
                da_key = "DA_" + entry._talent_key
                da_to_level[da_key] = entry.level

        for slot in self._slots:
            level = 0
            for da_key in slot.da_keys:
                lv = da_to_level.get(da_key, 0)
                if lv > 0:
                    level = lv
                    break
            node = self._nodes.get(slot.slot_id)
            if node:
                node.update_level(level)

    def clear_skills(self) -> None:
        for node in self._nodes.values():
            node.update_level(0)


# ── Skills tab ────────────────────────────────────────────────────────────────

class SkillsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_slot: _SlotInfo | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Skill tree view
        self._scene = SkillTreeScene()
        self._scene.node_clicked.connect(self._on_node_clicked)

        view = QGraphicsView(self._scene)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._view = view

        layout.addWidget(view, 1)
        layout.addWidget(self._build_detail_panel())

    def _build_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("right-panel")
        panel.setFixedWidth(260)
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(20, 24, 20, 20)
        vbox.setSpacing(12)

        title = QLabel("TALENT DETAILS")
        title.setObjectName("section-header")
        vbox.addWidget(title)

        self._name_lbl = QLabel("Select a node")
        self._name_lbl.setWordWrap(True)
        self._name_lbl.setStyleSheet(
            "color: #c9d1d9; font-size: 14px; font-weight: bold;"
        )
        vbox.addWidget(self._name_lbl)

        self._desc_lbl = QLabel("")
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setObjectName("muted")
        vbox.addWidget(self._desc_lbl)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        vbox.addWidget(sep)

        level_row = QHBoxLayout()
        level_row.setSpacing(10)
        lbl = QLabel("Level:")
        lbl.setObjectName("muted")
        self._level_spin = QSpinBox()
        self._level_spin.setRange(0, 3)
        self._level_spin.setFixedWidth(65)
        self._level_spin.setEnabled(False)
        set_btn = QPushButton("Set")
        set_btn.setFixedWidth(55)
        set_btn.clicked.connect(self._on_set_level)
        level_row.addWidget(lbl)
        level_row.addWidget(self._level_spin)
        level_row.addWidget(set_btn)
        level_row.addStretch()
        vbox.addLayout(level_row)

        self._max_node_btn = QPushButton("Max This Node")
        self._max_node_btn.clicked.connect(self._on_max_node)
        self._max_node_btn.setEnabled(False)
        vbox.addWidget(self._max_node_btn)

        vbox.addSpacing(8)
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        vbox.addWidget(sep2)

        self._max_all_btn = QPushButton("Max All Skills")
        self._max_all_btn.setEnabled(False)
        self._max_all_btn.setToolTip("Requires a save to be loaded")
        vbox.addWidget(self._max_all_btn)

        vbox.addStretch()

        hint = QLabel("Click a node to select it.\nScroll to zoom · Drag to pan.")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(hint)

        return panel

    def _on_node_clicked(self, slot: _SlotInfo) -> None:
        self._selected_slot = slot
        self._name_lbl.setText(slot.primary_name)
        if len(slot.names) > 1:
            desc = "\n\n".join(
                f"{n}:\n{d}" for n, d in zip(slot.names, slot.descs) if d
            )
        else:
            desc = slot.descs[0] if slot.descs else ""
        self._desc_lbl.setText(desc)
        self._level_spin.setMaximum(slot.max_level)
        self._level_spin.setValue(slot.level)
        self._level_spin.setEnabled(True)
        self._max_node_btn.setEnabled(True)

    def _on_set_level(self) -> None:
        if self._selected_slot is None:
            return
        new_level = self._level_spin.value()
        self._selected_slot.level = new_level
        node = self._scene._nodes.get(self._selected_slot.slot_id)
        if node:
            node.update_level(new_level)

    def _on_max_node(self) -> None:
        if self._selected_slot is None:
            return
        self._level_spin.setValue(self._selected_slot.max_level)
        self._on_set_level()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._view.fitInView(
            self._scene.sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    # ── Public API ────────────────────────────────────────────────────────

    def load_skills(self, skills: dict) -> None:
        self._scene.load_skills(skills)
        self._max_all_btn.setEnabled(True)

    def clear_skills(self) -> None:
        self._scene.clear_skills()
        self._max_all_btn.setEnabled(False)
