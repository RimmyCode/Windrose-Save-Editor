from __future__ import annotations

import math
from dataclasses import dataclass, field

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGraphicsScene,
    QGraphicsView, QGraphicsObject, QGraphicsItem,
    QLabel, QPushButton, QSpinBox, QFrame, QSizePolicy,
    QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsPathItem,
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QLineF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QRadialGradient, QLinearGradient,
)

# ── Layout constants ──────────────────────────────────────────────────────────
# Math angles: 0° = right, 90° = up (standard).  Screen y-axis is inverted.
_QUAD_ANGLE: dict[str, float] = {
    "Fencer":   90.0,
    "Crusher":   0.0,
    "Marksman": 270.0,
    "Toughguy": 180.0,
}
# UISlotTag category numbers → quadrant name
_CAT_NAME: dict[int, str] = {1: "Fencer", 2: "Crusher", 3: "Marksman", 4: "Toughguy"}

# Ring number → radius in scene pixels
_RING_R: dict[int, float] = {1: 118.0, 2: 205.0, 3: 288.0}

# Position (1–4) within a quadrant → angular offset from quadrant centre (degrees)
_POS_OFFSET: dict[int, float] = {1: -33.0, 2: -11.0, 3: 11.0, 4: 33.0}

# Node visual radius (pixels)
_NODE_R: float = 27.0

# Colours
_C_BG         = QColor("#080c13")
_C_RING_LINE  = QColor("#1e2a3a")
_C_DIV_LINE   = QColor("#182030")
_C_OUTER_RING = QColor("#253040")
_C_LABEL      = QColor("#7a6840")
_C_COMPASS    = QColor("#4a3e28")
_C_LOCKED     = QColor("#2d3a4a")
_C_PARTIAL    = QColor("#4a7a9b")
_C_MAXED      = QColor("#c9a84c")
_C_NODE_FILL  = QColor("#111827")
_C_NODE_TEXT  = QColor("#9a8860")
_C_BADGE_BG   = QColor("#080c13")
_C_BADGE_TEXT = QColor("#e8d5a3")

# ── Slot layout data ──────────────────────────────────────────────────────────
# Parsed from _TALENT_NODE_DATA UISlotTags.
# Each entry: (DA_key, category, ring, position)
# Shared slots (same cat/ring/pos) are merged into one visual node.
_SLOT_TABLE: list[tuple[str, int, int, int]] = [
    # Fencer (cat=1)
    ("DA_Talent_Fencer_SlashDamage",                         1, 1, 1),
    ("DA_Talent_Fencer_LessStaminaForDash",                  1, 1, 2),
    ("DA_Talent_Fencer_OneHandedMeleeCritChance",             1, 1, 3),
    ("DA_Talent_Fencer_OneHandedDamage",                     1, 2, 1),
    ("DA_Talent_Fencer_CritChanceForPerfectBlock",           1, 2, 2),
    ("DA_Talent_Fencer_DamageForSoloEnemy",                  1, 2, 3),
    ("DA_Talent_Fencer_HealForKill",                         1, 3, 2),
    # 1.3.3 — two perks on the same node
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
    # 3.2.3 — two perks on the same node
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
    """Convert a UISlotTag (cat, ring, pos) to scene coordinates."""
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
    da_keys:  list[str]    = field(default_factory=list)
    names:    list[str]    = field(default_factory=list)
    descs:    list[str]    = field(default_factory=list)
    level:    int          = 0
    max_level: int         = 3

    @property
    def slot_id(self) -> tuple[int, int, int]:
        return (self.cat, self.ring, self.pos)

    @property
    def primary_name(self) -> str:
        if len(self.names) == 1:
            return self.names[0]
        return " / ".join(w.split()[0] for w in self.names if w)  # first word each

    @property
    def abbrev(self) -> str:
        words = self.primary_name.split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        return self.primary_name[:2].upper()

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
    """Group _SLOT_TABLE entries by (cat, ring, pos) into _SlotInfo objects."""
    from windrose_save_editor.game_data import TALENT_NAMES, TALENT_DESCS

    index: dict[tuple[int, int, int], _SlotInfo] = {}
    for da_key, cat, ring, pos in _SLOT_TABLE:
        sid = (cat, ring, pos)
        if sid not in index:
            index[sid] = _SlotInfo(cat=cat, ring=ring, pos=pos)
        slot = index[sid]
        slot.da_keys.append(da_key)

        talent_key = da_key[3:] if da_key.startswith("DA_") else da_key  # strip "DA_"
        slot.names.append(TALENT_NAMES.get(talent_key, da_key))
        slot.descs.append(TALENT_DESCS.get(talent_key, ""))

    return list(index.values())


# ── TalentNode QGraphicsObject ────────────────────────────────────────────────

class TalentNode(QGraphicsObject):
    """One circular node on the talent tree."""

    clicked = Signal(object)   # emits the _SlotInfo

    def __init__(self, slot: _SlotInfo, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.slot = slot
        self.setAcceptHoverEvents(True)
        self.setToolTip(slot.tooltip_html)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False

    # ── Qt interface ─────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        pad = 4.0
        r = _NODE_R + pad
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter, _option, _widget) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = _NODE_R
        level, max_lv = self.slot.level, self.slot.max_level

        # ── Choose ring colour
        if level == 0:
            ring_col = _C_LOCKED
        elif level >= max_lv:
            ring_col = _C_MAXED
        else:
            ring_col = _C_PARTIAL

        if self._hovered:
            ring_col = ring_col.lighter(150)

        # ── Radial gradient fill (coin / medallion feel)
        grad = QRadialGradient(QPointF(-r * 0.3, -r * 0.3), r * 1.4)
        if level == 0:
            grad.setColorAt(0.0, QColor("#182030"))
            grad.setColorAt(1.0, QColor("#0c1018"))
        elif level >= max_lv:
            grad.setColorAt(0.0, QColor("#2a2010"))
            grad.setColorAt(1.0, QColor("#0f0c06"))
        else:
            grad.setColorAt(0.0, QColor("#162030"))
            grad.setColorAt(1.0, QColor("#090e18"))

        # ── Outer glow ring (only when active / hovered)
        if level > 0 or self._hovered:
            glow_pen = QPen(ring_col, 1.5)
            glow_pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(-r - 4, -r - 4, (r + 4) * 2, (r + 4) * 2))

        # ── Main circle
        painter.setPen(QPen(ring_col, 2.5))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QRectF(-r, -r, r * 2, r * 2))

        # ── Inner accent ring
        inner_col = ring_col.darker(160) if level == 0 else ring_col.darker(130)
        painter.setPen(QPen(inner_col, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(-r + 4, -r + 4, (r - 4) * 2, (r - 4) * 2))

        # ── Abbreviation text (or lock symbol when locked)
        painter.setPen(QPen(_C_LOCKED if level == 0 else _C_NODE_TEXT))
        if level == 0:
            # Draw a simple padlock shape
            _draw_padlock(painter, 0, 0)
        else:
            abbrev_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
            painter.setFont(abbrev_font)
            text_rect = QRectF(-r + 2, -r + 2, (r - 2) * 2, (r - 2) * 2 - 12)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.slot.abbrev)

        # ── Level badge at bottom
        badge_rect = QRectF(-13, r - 13, 26, 13)
        painter.setBrush(QBrush(_C_BADGE_BG))
        badge_pen = QPen(ring_col, 1.0)
        painter.setPen(badge_pen)
        painter.drawRoundedRect(badge_rect, 3, 3)
        painter.setPen(QPen(_C_BADGE_TEXT))
        badge_font = QFont("Segoe UI", 7)
        painter.setFont(badge_font)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter,
                         f"{level}/{max_lv}")

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


def _draw_padlock(painter: QPainter, cx: float, cy: float) -> None:
    """Draw a minimal padlock at (cx, cy) using the current pen."""
    path = QPainterPath()
    # Shackle arc
    path.addEllipse(QRectF(cx - 5, cy - 11, 10, 10))
    # Body rectangle
    path.addRoundedRect(QRectF(cx - 7, cy - 4, 14, 11), 2, 2)
    painter.drawPath(path)


# ── Background compass rose ───────────────────────────────────────────────────

def _make_compass_path(cx: float, cy: float, r_outer: float) -> QPainterPath:
    """Eight-pointed star (compass rose) centred at (cx, cy)."""
    path = QPainterPath()
    r_inner = r_outer * 0.42
    for i in range(8):
        angle = math.radians(i * 45)
        r = r_outer if i % 2 == 0 else r_inner
        px = cx + r * math.cos(angle)
        py = cy - r * math.sin(angle)
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    path.closeSubpath()
    return path


# ── Scene ─────────────────────────────────────────────────────────────────────

class SkillTreeScene(QGraphicsScene):
    node_clicked = Signal(object)   # passes _SlotInfo

    def __init__(self) -> None:
        super().__init__()
        self.setSceneRect(-380, -380, 760, 760)
        self.setBackgroundBrush(QBrush(_C_BG))

        self._nodes: dict[tuple[int, int, int], TalentNode] = {}
        self._slots: list[_SlotInfo] = _build_slots()

        self._draw_background()
        self._draw_nodes()

    # ── Background layers ─────────────────────────────────────────────────

    def _draw_background(self) -> None:
        # Quadrant dividers at 45°, 135°, 225°, 315°
        div_pen = QPen(_C_DIV_LINE, 1.0, Qt.PenStyle.SolidLine)
        max_r = 340.0
        for angle_deg in (45, 135, 225, 315):
            a = math.radians(angle_deg)
            line = QGraphicsLineItem(
                QLineF(0, 0, max_r * math.cos(a), -max_r * math.sin(a))
            )
            line.setPen(div_pen)
            self.addItem(line)

        # Concentric ring circles
        ring_pen = QPen(_C_RING_LINE, 0.8, Qt.PenStyle.SolidLine)
        for r in _RING_R.values():
            item = QGraphicsEllipseItem(QRectF(-r, -r, r * 2, r * 2))
            item.setPen(ring_pen)
            item.setBrush(Qt.BrushStyle.NoBrush)
            self.addItem(item)

        # Outer boundary circle
        outer_r = 325.0
        outer_item = QGraphicsEllipseItem(
            QRectF(-outer_r, -outer_r, outer_r * 2, outer_r * 2)
        )
        outer_item.setPen(QPen(_C_OUTER_RING, 1.5))
        outer_item.setBrush(Qt.BrushStyle.NoBrush)
        self.addItem(outer_item)

        # Compass rose at centre
        compass = QGraphicsPathItem(_make_compass_path(0, 0, 22))
        compass.setPen(QPen(_C_COMPASS, 1.0))
        compass.setBrush(QBrush(_C_COMPASS.darker(140)))
        self.addItem(compass)

        # Small centre dot
        dot = QGraphicsEllipseItem(QRectF(-5, -5, 10, 10))
        dot.setPen(Qt.PenStyle.NoPen)
        dot.setBrush(QBrush(_C_COMPASS))
        self.addItem(dot)

        # Quadrant label text
        label_r = 348.0
        quad_labels = {
            "FENCER":    ( 90.0, Qt.AlignmentFlag.AlignHCenter),
            "CRUSHER":   (  0.0, Qt.AlignmentFlag.AlignLeft),
            "MARKSMAN":  (270.0, Qt.AlignmentFlag.AlignHCenter),
            "TOUGHGUY":  (180.0, Qt.AlignmentFlag.AlignRight),
        }
        for label, (angle_deg, _align) in quad_labels.items():
            a = math.radians(angle_deg)
            lx = label_r * math.cos(a)
            ly = -label_r * math.sin(a)
            txt = self.addText(label, QFont("Segoe UI", 8, QFont.Weight.Bold))
            txt.setDefaultTextColor(_C_LABEL)
            br = txt.boundingRect()
            txt.setPos(lx - br.width() / 2, ly - br.height() / 2)

        # Radial connector lines (centre → each ring, along quadrant-centre angle)
        connector_pen = QPen(_C_DIV_LINE, 0.6, Qt.PenStyle.SolidLine)
        for quad_angle in _QUAD_ANGLE.values():
            a = math.radians(quad_angle)
            line = QGraphicsLineItem(
                QLineF(0, 0, max_r * math.cos(a), -max_r * math.sin(a))
            )
            line.setPen(connector_pen)
            self.addItem(line)

        # Node-to-node radial connections (same cat+pos, adjacent rings)
        self._draw_connections()

    def _draw_connections(self) -> None:
        conn_pen = QPen(_C_DIV_LINE, 0.7, Qt.PenStyle.SolidLine)
        slot_set: set[tuple[int, int, int]] = {
            (cat, ring, pos) for _, cat, ring, pos in _SLOT_TABLE
        }
        for cat, ring, pos in slot_set:
            if ring < 3 and (cat, ring + 1, pos) in slot_set:
                p1 = _slot_pos(cat, ring, pos)
                p2 = _slot_pos(cat, ring + 1, pos)
                line = QGraphicsLineItem(QLineF(p1, p2))
                line.setPen(conn_pen)
                self.addItem(line)
        # Tangential connections (same cat+ring, adjacent positions)
        for cat, ring, pos in slot_set:
            if (cat, ring, pos + 1) in slot_set:
                p1 = _slot_pos(cat, ring, pos)
                p2 = _slot_pos(cat, ring, pos + 1)
                line = QGraphicsLineItem(QLineF(p1, p2))
                line.setPen(conn_pen)
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
        """Apply live skill levels from a loaded save.

        *skills* is the return value of ``editors.skills.get_skills(doc)``.
        Each value is a list of ``SkillEntry`` dataclass instances.
        """
        from windrose_save_editor.editors.skills import SkillEntry

        da_to_level: dict[str, int] = {}
        for entries in skills.values():
            for entry in entries:
                da_key = "DA_" + entry._talent_key   # e.g. DA_Talent_Fencer_SlashDamage
                da_to_level[da_key] = entry.level

        for slot in self._slots:
            # Use the level of whichever perk is active (first non-zero, else 0)
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
        """Reset all nodes to level 0 (no save loaded)."""
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

        # ── Left: tree view
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

        # ── Right: detail panel
        panel = self._build_detail_panel()
        layout.addWidget(panel)

    def _build_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("card")
        panel.setFixedWidth(260)
        panel.setStyleSheet(
            "QFrame#card { background-color: #0f1520; border-left: 1px solid #21262d;"
            "border-radius: 0; }"
        )
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(20, 24, 20, 20)
        vbox.setSpacing(12)

        # Title
        title = QLabel("Talent Details")
        title.setObjectName("section-title")
        title.setStyleSheet("color: #c9a84c; font-size: 15px; font-weight: bold;")
        vbox.addWidget(title)

        # Name
        self._name_lbl = QLabel("Select a node")
        self._name_lbl.setWordWrap(True)
        self._name_lbl.setStyleSheet("color: #c9d1d9; font-size: 14px; font-weight: bold;")
        vbox.addWidget(self._name_lbl)

        # Description
        self._desc_lbl = QLabel("")
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
        vbox.addWidget(self._desc_lbl)

        # Separator
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        vbox.addWidget(sep)

        # Level control
        level_row = QHBoxLayout()
        level_row.setSpacing(10)
        lbl = QLabel("Level:")
        lbl.setStyleSheet("color: #8b949e;")
        self._level_spin = QSpinBox()
        self._level_spin.setRange(0, 3)
        self._level_spin.setFixedWidth(65)
        self._level_spin.setEnabled(False)
        set_btn = QPushButton("Set")
        set_btn.setObjectName("accent-btn")
        set_btn.setFixedWidth(55)
        set_btn.clicked.connect(self._on_set_level)
        level_row.addWidget(lbl)
        level_row.addWidget(self._level_spin)
        level_row.addWidget(set_btn)
        level_row.addStretch()
        vbox.addLayout(level_row)

        # Max button
        max_btn = QPushButton("Max This Node")
        max_btn.clicked.connect(self._on_max_node)
        max_btn.setEnabled(False)
        self._max_node_btn = max_btn
        vbox.addWidget(max_btn)

        vbox.addSpacing(8)

        # Max all
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        vbox.addWidget(sep2)

        max_all = QPushButton("Max All Skills")
        max_all.setObjectName("accent-btn")
        max_all.setEnabled(False)
        max_all.setToolTip("Requires a save to be loaded")
        self._max_all_btn = max_all
        vbox.addWidget(max_all)

        vbox.addStretch()

        # Hint at the bottom
        hint = QLabel("Click a node to select it.\nScroll to zoom · Drag to pan.")
        hint.setStyleSheet("color: #30363d; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(hint)

        return panel

    # ── Event handlers ────────────────────────────────────────────────────

    def _on_node_clicked(self, slot: _SlotInfo) -> None:
        self._selected_slot = slot
        self._name_lbl.setText(slot.primary_name)
        # Show first desc (or both if shared slot)
        desc = "\n\n".join(
            f"{n}:\n{d}" for n, d in zip(slot.names, slot.descs) if d
        ) if len(slot.names) > 1 else (slot.descs[0] if slot.descs else "")
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

    # ── Zoom on resize ────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        margin = 20
        vr = self._view.rect().adjusted(margin, margin, -margin, -margin)
        self._view.fitInView(
            self._scene.sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    # ── Public API ────────────────────────────────────────────────────────

    def load_skills(self, skills: dict) -> None:
        """Forward to the scene; call with result of get_skills(doc)."""
        self._scene.load_skills(skills)
        self._max_all_btn.setEnabled(True)

    def clear_skills(self) -> None:
        self._scene.clear_skills()
        self._max_all_btn.setEnabled(False)
