from __future__ import annotations

import random
import sys
import time
from pathlib import Path
from typing import Iterable

try:
    from PyQt6.QtCore import QMimeData, QPoint, QSize, Qt, QTimer
    from PyQt6.QtGui import QBrush, QColor, QCursor, QDrag, QFont, QFontDatabase, QIcon, QPainter, QPixmap
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSlider,
        QStackedWidget,
        QStyledItemDelegate,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QToolTip,
        QVBoxLayout,
        QWidget,
    )

    QT_MAJOR = 6
except ModuleNotFoundError:
    from PyQt5.QtCore import QMimeData, QPoint, QSize, Qt, QTimer
    from PyQt5.QtGui import QBrush, QColor, QCursor, QDrag, QFont, QFontDatabase, QIcon, QPainter, QPixmap
    from PyQt5.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSlider,
        QStackedWidget,
        QStyledItemDelegate,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QToolTip,
        QVBoxLayout,
        QWidget,
    )

    QT_MAJOR = 5

from ascii_climb.combat import (
    DEFEAT_PRICE_COINS,
    DEFEAT_PRICE_ITEM,
    DEFEAT_PRICE_STATS,
    STANCE_DESCRIPTIONS,
    flee_from_combat,
    resolve_defeat_penalty,
    run_combat,
    run_combat_turn,
    scout_preview,
)
from ascii_climb.content import (
    CONTENT_CONFLICTS,
    CONTENT_WARNINGS,
    LOCATIONS,
    STORY,
    list_available_mods,
    reload_content,
)
from ascii_climb.encounters import random_event
from ascii_climb.i18n import Translator
from ascii_climb.leveling import apply_level_reward, describe_level_reward_for_run, generate_level_reward_options
from ascii_climb.loot import caravan_price, repair_cost, roll_item, sell_value
from ascii_climb.meta import (
    buy_inventory_slot as buy_meta_inventory_slot,
    buy_upgrade,
    effective_stats,
    final_gold_payout,
    refund_inventory_slot as refund_meta_inventory_slot,
    refund_upgrade,
    upgrade_cost,
    upgrade_bonus_for_level,
)
from ascii_climb.models import EQUIPMENT_SLOTS, GameSettings, Item, RARITIES, RunState, STAT_DESCRIPTIONS, STAT_KEYS, SaveData
from ascii_climb.progression import (
    apply_enhancement,
    describe_enhancement,
    generate_stage_enhancements,
)
from ascii_climb.save import (
    create_save_slot,
    delete_save_slot,
    list_save_slots,
    load_profile,
    load_save_slot,
    load_settings,
    missing_mods_for_save,
    rename_save_slot,
    save_profile,
    save_save_slot,
    save_settings,
)
from ascii_climb.shops import (
    add_item_to_inventory,
    buy_medkit as buy_shop_medkit,
    buy_random_gear as buy_shop_random_gear,
    craft_fusion,
    drop_item,
    equip_item,
    replace_equipped_item,
    repair_item,
    medkit_cost,
    scouting_cost,
    sell_item,
    unequip_item,
)
from ascii_climb.sound import SoundManager
from ascii_climb.visuals import enhancement_color, item_colors, readable_text_for_backgrounds
from ascii_climb.stats import (
    RARITY_RANK,
    add_play_time,
    record_combat_result,
    record_item_collected,
    start_run_timer,
)

RESOLUTIONS = ["1280x720", "1366x768", "1600x900", "1920x1080", "Fullscreen"]
ROOT = Path(__file__).resolve().parent.parent
SOUND_ROOT = ROOT / "assets" / "sounds"
MUSIC_ROOT = ROOT / "assets" / "music"
FONT_ROOT = ROOT / "assets" / "fonts"
ICON_ROOT = ROOT / "assets" / "icons"
LICENSE_PATH = ROOT / "LICENSE.md"
PIXEL_BODY_FONT = "Tiny5"
PIXEL_DISPLAY_FONT = "Pixelify Sans"
INVENTORY_ICON_SHEET = ICON_ROOT / "vendor" / "opengameart-rpg-inventory-icons.png"
KENNEY_ICON_ROOT = ICON_ROOT / "vendor" / "kenney-game-icons" / "PNG" / "White" / "2x"
ITEM_ICON_ROOT = ICON_ROOT / "items"
ITEM_ICON_PATHS = {
    slot: {rarity: ITEM_ICON_ROOT / slot / f"{rarity}.png" for rarity in RARITIES}
    for slot in EQUIPMENT_SLOTS
}
ITEM_ICON_FALLBACKS = {
    slot: ITEM_ICON_ROOT / f"{slot}.png"
    for slot in EQUIPMENT_SLOTS
}
ITEM_ICON_RECTS = {
    "weapon": (0, 0, 32, 32),
    "armor": (96, 0, 32, 32),
    "charm": (64, 32, 32, 32),
    "boots": (32, 32, 32, 32),
    "ring": (64, 32, 32, 32),
    "relic": (96, 32, 32, 32),
    "fallback": (64, 32, 32, 32),
}


def _user_role():
    return Qt.ItemDataRole.UserRole if QT_MAJOR == 6 else Qt.UserRole


def _role_offset(offset: int):
    base = Qt.ItemDataRole.UserRole if QT_MAJOR == 6 else Qt.UserRole
    return base + offset


def _stretch_mode():
    return QHeaderView.ResizeMode.Stretch if QT_MAJOR == 6 else QHeaderView.Stretch


def _select_rows():
    return QAbstractItemView.SelectionBehavior.SelectRows if QT_MAJOR == 6 else QAbstractItemView.SelectRows


def _single_select():
    return QAbstractItemView.SelectionMode.SingleSelection if QT_MAJOR == 6 else QAbstractItemView.SingleSelection


def _multi_select():
    return QAbstractItemView.SelectionMode.MultiSelection if QT_MAJOR == 6 else QAbstractItemView.MultiSelection


def _left_button():
    return Qt.MouseButton.LeftButton if QT_MAJOR == 6 else Qt.LeftButton


def _move_action():
    return Qt.DropAction.MoveAction if QT_MAJOR == 6 else Qt.MoveAction


def _control_modifier():
    return Qt.KeyboardModifier.ControlModifier if QT_MAJOR == 6 else Qt.ControlModifier


def _no_edits():
    return QAbstractItemView.EditTrigger.NoEditTriggers if QT_MAJOR == 6 else QAbstractItemView.NoEditTriggers


def _horizontal():
    return Qt.Orientation.Horizontal if QT_MAJOR == 6 else Qt.Horizontal


def _align_center():
    return Qt.AlignmentFlag.AlignCenter if QT_MAJOR == 6 else Qt.AlignCenter


def _align_right():
    return Qt.AlignmentFlag.AlignRight if QT_MAJOR == 6 else Qt.AlignRight


def _tooltip_window_flag():
    return Qt.WindowType.ToolTip if QT_MAJOR == 6 else Qt.ToolTip


def _dialog_accepted():
    return QDialog.DialogCode.Accepted if QT_MAJOR == 6 else QDialog.Accepted


def _run_dialog(dialog: QDialog) -> int:
    return dialog.exec() if QT_MAJOR == 6 else dialog.exec_()


def _table_item(value: object) -> QTableWidgetItem:
    text = str(value)
    item = QTableWidgetItem(text)
    item.setToolTip(text)
    return item


def _set_label_text(label: QLabel, text: str) -> None:
    label.setText(text)
    label.setToolTip(text)


def _enable_table_hover_text(table: QTableWidget) -> None:
    table.setMouseTracking(True)
    table.viewport().setMouseTracking(True)

    def show_item_text(item: QTableWidgetItem) -> None:
        text = item.toolTip() or item.text()
        if text:
            QToolTip.showText(QCursor.pos(), text, table.viewport())

    table.itemEntered.connect(show_item_text)


def _monospace_font(point_size: int = 12) -> QFont:
    font = QFont(PIXEL_BODY_FONT)
    font.setStyleHint(QFont.StyleHint.Monospace if QT_MAJOR == 6 else QFont.Monospace)
    font.setPointSize(point_size)
    return font


def _pixel_font(point_size: int, bold: bool = False, family: str = PIXEL_DISPLAY_FONT) -> QFont:
    font = QFont(family)
    font.setPointSize(point_size)
    font.setBold(bold)
    return font


def _message_button(name: str):
    if QT_MAJOR == 6:
        return getattr(QMessageBox.StandardButton, name)
    return getattr(QMessageBox, name)


class ChoiceDialog(QDialog):
    def __init__(self, title: str, body: Iterable[str], choices: list[tuple], parent=None):
        super().__init__(parent)
        self.choice = None
        self.sound = getattr(parent, "sound", None)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)
        for row_text in body:
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel if QT_MAJOR == 6 else QFrame.StyledPanel)
            card_layout = QVBoxLayout(card)
            text = QLabel(str(row_text))
            text.setWordWrap(True)
            card_layout.addWidget(text)
            layout.addWidget(card)
        for choice in choices:
            label, value = choice[0], choice[1]
            colors = choice[2] if len(choice) > 2 else None
            button = QPushButton(label)
            button.setMinimumHeight(48)
            if colors:
                top, bottom = colors
                fg = readable_text_for_backgrounds(top, bottom)
                button.setStyleSheet(
                    "QPushButton {"
                    f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {top}, stop:0.5 {top}, stop:0.501 {bottom}, stop:1 {bottom});"
                    f"color: {fg}; text-align: left; padding: 10px; font-weight: 700;"
                    "}"
                )
            else:
                button.setStyleSheet("QPushButton { text-align: left; padding: 10px; }")
            button.clicked.connect(lambda checked=False, selected=value: self._choose(selected))
            layout.addWidget(button)

    def _choose(self, value: object) -> None:
        if self.sound is not None:
            self.sound.play("click")
        self.choice = value
        self.accept()


class FightReplayDialog(QDialog):
    def __init__(
        self,
        result=None,
        player_pixmap: QPixmap | None = None,
        enemy_pixmap: QPixmap | None = None,
        parent=None,
        rng: random.Random | None = None,
        meta=None,
        run: RunState | None = None,
        initial_stance: str = "steady",
    ):
        super().__init__(parent)
        self.result = result
        self.sound = getattr(parent, "sound", None)
        self.rng = rng
        self.meta = meta
        self.run = run
        self.round_no = 1
        self.auto = False
        self.events = result.events or [] if result else []
        self.index = 0
        self.setWindowTitle("Battle")
        self.resize(720, 520)
        layout = QVBoxLayout(self)
        sprites = QHBoxLayout()
        self.player_sprite = QLabel()
        self.player_sprite.setPixmap(player_pixmap or make_sprite_pixmap("player"))
        self.enemy_sprite = QLabel()
        self.enemy_sprite.setPixmap(enemy_pixmap or make_sprite_pixmap("enemy"))
        sprites.addWidget(self.player_sprite)
        sprites.addStretch(1)
        sprites.addWidget(self.enemy_sprite)
        layout.addLayout(sprites)
        bars = QGridLayout()
        self.player_hp = QProgressBar()
        self.enemy_hp = QProgressBar()
        bars.addWidget(QLabel("You"), 0, 0)
        bars.addWidget(self.player_hp, 0, 1)
        self.enemy_name = QLabel(result.enemy.name if result else "Enemy")
        bars.addWidget(self.enemy_name, 1, 0)
        bars.addWidget(self.enemy_hp, 1, 1)
        layout.addLayout(bars)
        controls = QHBoxLayout()
        self.stance_combo = QComboBox()
        self.stance_combo.addItems(["steady", "guarded", "reckless"])
        self.stance_combo.setCurrentText(initial_stance)
        self.stance_combo.currentTextChanged.connect(self.update_stance_description)
        self.turn_button = QPushButton("Attack Turn")
        self.auto_button = QPushButton("Auto")
        self.turn_button.clicked.connect(self.play_turn)
        self.auto_button.clicked.connect(self.start_auto)
        controls.addWidget(QLabel("Stance"))
        controls.addWidget(self.stance_combo)
        controls.addWidget(self.turn_button)
        controls.addWidget(self.auto_button)
        layout.addLayout(controls)
        self.action = QLabel("The fight begins.")
        self.action.setWordWrap(True)
        layout.addWidget(self.action)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(_monospace_font())
        layout.addWidget(self.log)
        self.close_button = QPushButton("Flee" if result is None else "Close")
        self.close_button.setEnabled(result is None)
        self.close_button.clicked.connect(self._maybe_click_close)
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button)
        if result:
            self.turn_button.setEnabled(False)
            self.auto_button.setEnabled(False)
            QTimer.singleShot(100, self.play_next)
        else:
            self.update_stance_description(initial_stance)
            self.close_button.clicked.disconnect()
            self.close_button.clicked.connect(self.reject)

    def update_stance_description(self, stance: str) -> None:
        if self.result is None:
            self.action.setText(STANCE_DESCRIPTIONS.get(stance, "Choose stance for this turn."))

    def play_next(self) -> None:
        if self.index >= len(self.events):
            for line in self.result.summary or []:
                self.log.append(line)
            self.close_button.setText("Close")
            self.close_button.setEnabled(True)
            return
        event = self.events[self.index]
        self.index += 1
        self.player_hp.setMaximum(int(event.get("player_max_hp", 1)))
        self.player_hp.setValue(max(0, int(event.get("player_hp", 0))))
        self.enemy_hp.setMaximum(int(event.get("enemy_max_hp", 1)))
        self.enemy_hp.setValue(max(0, int(event.get("enemy_hp", 0))))
        message = str(event.get("message", ""))
        self.action.setText(message)
        self.log.append(message)
        if event.get("item_broken"):
            QMessageBox.information(self, "Item Broken", message, _message_button("Ok"))
        QTimer.singleShot(350, self.play_next)

    def play_turn(self) -> None:
        if self.rng is None or self.meta is None or self.run is None or self.result is not None:
            return
        if self.sound is not None:
            self.sound.play("attack")
        self.turn_button.setEnabled(False)
        stance = self.stance_combo.currentText()
        result = run_combat_turn(self.rng, self.meta, self.run, stance, self.round_no)
        self.round_no += 1
        self.enemy_name.setText(result.enemy.name)
        for event in result.events or []:
            self._show_event(event)
        if result.ongoing:
            self.turn_button.setEnabled(True)
            if self.auto:
                QTimer.singleShot(350, self.play_turn)
            return
        self.result = result
        for line in result.summary or []:
            self.log.append(line)
        self.close_button.setText("Close")
        try:
            self.close_button.clicked.disconnect()
        except TypeError:
            pass
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(True)

    def start_auto(self) -> None:
        if self.sound is not None:
            self.sound.play("click")
        self.auto = True
        self.auto_button.setEnabled(False)
        self.play_turn()

    def _show_event(self, event: dict) -> None:
        self.player_hp.setMaximum(int(event.get("player_max_hp", 1)))
        self.player_hp.setValue(max(0, int(event.get("player_hp", 0))))
        self.enemy_hp.setMaximum(int(event.get("enemy_max_hp", 1)))
        self.enemy_hp.setValue(max(0, int(event.get("enemy_hp", 0))))
        message = str(event.get("message", ""))
        self.action.setText(message)
        self.log.append(message)

    def _maybe_click_close(self) -> None:
        if self.sound is not None and self.result is not None:
            self.sound.play("click")

    def reject(self) -> None:
        if self.result is None:
            if self.rng is not None and self.meta is not None and self.run is not None:
                if self.sound is not None:
                    self.sound.play("event")
                self.result = flee_from_combat(self.rng, self.meta, self.run)
                for line in self.result.logs:
                    self.log.append(line)
                self.close_button.setText("Close")
            super().reject()
            return
        super().reject()


class ItemGradientDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index) -> None:
        top = index.data(_role_offset(1))
        bottom = index.data(_role_offset(2))
        if not top or not bottom:
            super().paint(painter, option, index)
            return
        painter.save()
        rect = option.rect
        midpoint = rect.top() + rect.height() // 2
        painter.fillRect(rect.left(), rect.top(), rect.width(), max(1, midpoint - rect.top()), QColor(top))
        painter.fillRect(rect.left(), midpoint, rect.width(), max(1, rect.bottom() - midpoint + 1), QColor(bottom))
        painter.setPen(QColor(readable_text_for_backgrounds(str(top), str(bottom))))
        painter.drawText(rect.adjusted(6, 0, -6, 0), _align_center(), str(index.data()))
        painter.restore()


def item_tooltip(item: Item) -> str:
    rows = [
        item.label(),
        f"Slot: {item.slot}",
        f"Value: {item.value}",
        item.stat_line(),
    ]
    if item.set_name:
        rows.append(f"Set: {item.set_name}")
    if item.drawback:
        rows.append(f"Drawback: {item.drawback}")
    return "\n".join(rows)


def item_icon_pixmap(item: Item | None, size: int = 36) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor("#201b16"))
    if item is None:
        return pixmap
    slot_icons = ITEM_ICON_PATHS.get(item.slot, {})
    icon_path = slot_icons.get(item.rarity) or slot_icons.get("common") or ITEM_ICON_FALLBACKS.get(item.slot)
    if icon_path and icon_path.exists():
        icon = QPixmap(str(icon_path))
        if not icon.isNull():
            aspect_ratio = Qt.AspectRatioMode.KeepAspectRatio if QT_MAJOR == 6 else Qt.KeepAspectRatio
            transform = Qt.TransformationMode.FastTransformation if QT_MAJOR == 6 else Qt.FastTransformation
            return icon.scaled(size, size, aspect_ratio, transform)
    if not INVENTORY_ICON_SHEET.exists():
        return pixmap
    sheet = QPixmap(str(INVENTORY_ICON_SHEET))
    rect = ITEM_ICON_RECTS.get(item.slot, ITEM_ICON_RECTS["fallback"])
    icon = sheet.copy(*rect)
    return icon.scaled(size, size)


class ItemHoverCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, _tooltip_window_flag())
        self.setObjectName("itemHoverCard")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating if QT_MAJOR == 6 else Qt.WA_ShowWithoutActivating)
        self.setFrameShape(QFrame.Shape.StyledPanel if QT_MAJOR == 6 else QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        self.icon = QLabel()
        self.icon.setFixedSize(64, 64)
        self.icon.setAlignment(_align_center())
        layout.addWidget(self.icon, 0, _align_center())
        details = QVBoxLayout()
        details.setSpacing(5)
        self.name = QLabel()
        self.name.setAlignment(_align_right())
        self.name.setFont(_pixel_font(13, bold=True))
        self.name.setWordWrap(True)
        self.name.setMaximumWidth(280)
        details.addWidget(self.name)
        self.meta_row = QHBoxLayout()
        self.meta_row.setSpacing(6)
        self.rarity = QLabel()
        self.quality = QLabel()
        for chip in (self.rarity, self.quality):
            chip.setAlignment(_align_center())
            chip.setFont(_pixel_font(9, bold=True, family=PIXEL_BODY_FONT))
            chip.setMinimumHeight(20)
        self.meta_row.addStretch(1)
        self.meta_row.addWidget(self.rarity)
        self.meta_row.addWidget(self.quality)
        details.addLayout(self.meta_row)
        self.enhancements = QLabel()
        self.enhancements.setAlignment(_align_right())
        self.enhancements.setWordWrap(True)
        self.enhancements.setFont(_pixel_font(11, family=PIXEL_BODY_FONT))
        self.enhancements.setMaximumWidth(280)
        details.addWidget(self.enhancements)
        layout.addLayout(details, 1)
        self.setMaximumWidth(380)
        self.setStyleSheet(
            """
            QFrame#itemHoverCard {
                background: #17130f;
                border: 2px solid #c4952d;
            }
            QLabel {
                background: transparent;
                color: #f2f2f2;
            }
            """
        )

    def refresh(self, item: Item) -> None:
        self.icon.setPixmap(item_icon_pixmap(item, 64))
        self.name.setText(item.name)
        rarity_color, quality_color = item_colors(item)
        self._style_chip(self.rarity, item.rarity, rarity_color)
        self._style_chip(self.quality, item.quality, quality_color)
        rows = [item.stat_line()]
        if item.set_name:
            rows.append(f"Set: {item.set_name}")
        rows.append(f"Slot: {item.slot}  |  iLvl {item.ilevel}  |  Value {sell_value(item)}")
        self.enhancements.setText("\n".join(rows))
        self.adjustSize()

    def _style_chip(self, label: QLabel, text: str, color: str) -> None:
        label.setText(text)
        label.setStyleSheet(
            "QLabel {"
            f"background: {color};"
            f"color: {readable_text_for_backgrounds(color)};"
            "border: 1px solid #0d0b09;"
            "padding: 2px 7px;"
            "}"
        )


def slot_placeholder_pixmap(slot: str = "", size: int = 36) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor("#201b16"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing if QT_MAJOR == 6 else QPainter.Antialiasing, False)
    painter.setPen(QColor("#050505"))
    painter.setBrush(QColor("#050505"))
    inset = max(4, size // 8)
    if slot == "weapon":
        painter.drawRect(size // 2 - 2, inset, 4, size - inset * 2)
        painter.drawRect(size // 3, size - inset * 2, size // 3, 4)
    elif slot == "armor":
        painter.drawRect(size // 4, inset, size // 2, size - inset * 2)
        painter.drawRect(size // 5, inset + 4, size // 5, size // 4)
        painter.drawRect(size * 3 // 5, inset + 4, size // 5, size // 4)
    elif slot == "boots":
        painter.drawRect(inset, size // 2, size // 3, size // 3)
        painter.drawRect(size // 2, size // 2, size // 3, size // 3)
    elif slot == "ring":
        painter.drawEllipse(inset, inset, size - inset * 2, size - inset * 2)
        painter.setBrush(QColor("#201b16"))
        painter.drawEllipse(inset * 2, inset * 2, size - inset * 4, size - inset * 4)
    elif slot == "charm":
        painter.drawLine(size // 2, inset, size - inset, size // 2)
        painter.drawLine(size - inset, size // 2, size // 2, size - inset)
        painter.drawLine(size // 2, size - inset, inset, size // 2)
        painter.drawLine(inset, size // 2, size // 2, inset)
        painter.drawRect(size // 2 - 2, size // 2 - 2, 4, 4)
    elif slot == "relic":
        painter.drawEllipse(inset, inset, size - inset * 2, size - inset * 2)
        painter.drawRect(size // 2 - 2, inset * 2, 4, size - inset * 4)
    else:
        painter.drawRect(inset, inset, size - inset * 2, size - inset * 2)
    painter.end()
    return pixmap


class ItemSlotWidget(QFrame):
    def __init__(self, owner, area: str, index: int = -1, equipment_slot: str = ""):
        super().__init__(owner)
        self.owner = owner
        self.area = area
        self.index = index
        self.equipment_slot = equipment_slot
        self.item_id = ""
        self.current_item: Item | None = None
        self.selected = False
        self.sell_visible = False
        self.drag_target_state = ""
        self.drag_start = None
        self.drag_started = False
        self.setAcceptDrops(True)
        self.setMinimumSize(112, 116)
        self.setMaximumSize(142, 132)
        self.setFrameShape(QFrame.Shape.StyledPanel if QT_MAJOR == 6 else QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(3)
        self.icon = QLabel()
        self.icon.setAlignment(_align_center())
        self.icon.setFixedSize(48, 48)
        self.sell_button = QPushButton(self.owner.t("game.sell"))
        self.sell_button.setFixedHeight(24)
        self.sell_button.setVisible(False)
        self.sell_button.clicked.connect(lambda checked=False: self.owner.sell_slot_item(self))
        self.take_off_button = QPushButton("Take off")
        self.take_off_button.setFixedHeight(24)
        self.take_off_button.setVisible(False)
        self.take_off_button.clicked.connect(lambda checked=False: self.owner.take_off_slot_item(self))
        self.label = QLabel("")
        self.label.setAlignment(_align_center())
        self.label.setWordWrap(True)
        self.label.setFont(_pixel_font(11, family=PIXEL_BODY_FONT))
        layout.addWidget(self.icon, alignment=_align_center())
        layout.addWidget(self.sell_button)
        layout.addWidget(self.take_off_button)
        layout.addWidget(self.label)
        self.icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents if QT_MAJOR == 6 else Qt.WA_TransparentForMouseEvents)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents if QT_MAJOR == 6 else Qt.WA_TransparentForMouseEvents)
        self.refresh(None, False)

    def refresh(self, item: Item | None, selected: bool = False, sell_visible: bool = False) -> None:
        self.current_item = item
        self.selected = selected
        self.sell_visible = bool(item and sell_visible)
        self.drag_target_state = ""
        self.item_id = item.id if item else ""
        if item:
            self.icon.setPixmap(item_icon_pixmap(item, 48))
            self.label.setText(item.name)
            self.setToolTip("")
        else:
            label = self.equipment_slot if self.equipment_slot else f"Slot {self.index + 1}"
            self.icon.setPixmap(slot_placeholder_pixmap(self.equipment_slot, 48))
            self.label.setText(label)
            self.setToolTip("")
        self.sell_button.setVisible(self.sell_visible)
        self.take_off_button.setVisible(self.sell_visible and self.area == "equipment")
        self._apply_style()

    def _apply_style(self) -> None:
        if self.current_item:
            top, bottom = item_colors(self.current_item)
            fg = readable_text_for_backgrounds(top, bottom)
            border = "#ffe08a" if self.selected else top
            if self.drag_target_state == "valid":
                border = "#7dff9a"
            elif self.drag_target_state == "invalid":
                border = "#5b4a3d"
            opacity_overlay = "rgba(0,0,0,0.42)" if self.drag_target_state == "invalid" else "transparent"
            background = f"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {top},stop:1 {bottom})"
            label_color = fg
        else:
            border = "#ffe08a" if self.selected else "#4a3a2d"
            if self.drag_target_state == "valid":
                border = "#7dff9a"
            elif self.drag_target_state == "invalid":
                border = "#3b3127"
            opacity_overlay = "transparent"
            background = "#17130f"
            label_color = "#a99b8a"
        self.setStyleSheet(
            "QFrame {"
            f"background: {background};"
            f"border: 2px solid {border};"
            "}"
            "QFrame:hover { border-color: #ffd166; }"
            f"QLabel {{ background: {opacity_overlay}; color: {label_color}; }}"
            "QPushButton {"
            "background: #b32626;"
            "border: 1px solid #ff7474;"
            "color: #ffffff;"
            "padding: 1px 5px;"
            "font-size: 12px;"
            "text-align: center;"
            "}"
            "QPushButton:hover, QPushButton:focus {"
            "background: #d63a3a;"
            "color: #ffffff;"
            "}"
        )

    def set_drag_target_state(self, state: str) -> None:
        self.drag_target_state = state
        self._apply_style()

    def drag_distance_reached(self, position: QPoint) -> bool:
        if self.drag_start is None:
            return False
        return (position - self.drag_start).manhattanLength() >= QApplication.startDragDistance()

    def mousePressEvent(self, event) -> None:
        if event.button() == _left_button():
            self.drag_start = event.pos()
            self.drag_started = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & _left_button()):
            return
        if not self.item_id:
            return
        if not self.drag_distance_reached(event.pos()):
            return
        self.drag_started = True
        self.owner.begin_slot_drag(self)
        mime = QMimeData()
        payload = f"{self.area}|{self.index}|{self.item_id}|{self.equipment_slot}"
        mime.setText(payload)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.icon.pixmap() or QPixmap())
        drag.exec(_move_action())
        self.owner.end_slot_drag()
        self.drag_start = None
        self.drag_row = -1

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == _left_button():
            if not self.drag_started and self.drag_start is not None and not self.drag_distance_reached(event.pos()):
                self.owner.slot_clicked(self)
            self.drag_start = None
            self.drag_started = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == _left_button() and self.area == "equipment" and self.current_item:
            self.owner.take_off_slot_item(self)
        else:
            super().mouseDoubleClickEvent(event)

    def enterEvent(self, event) -> None:
        if self.current_item:
            self.owner.show_item_hover(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.owner.hide_item_hover(self)
        super().leaveEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if self.owner.handle_slot_drop(event.mimeData().text(), self):
            event.acceptProposedAction()


class InventoryTableWidget(QTableWidget):
    COLUMNS = ["Name", "Set", "Rarity", "Quality", "iLvl", "Selling Cost", "Stat 1", "Stat 2", "Stat 3", "Stat 4", "Stat 5", "Stat 6"]

    def __init__(self, owner, area: str):
        super().__init__(0, len(self.COLUMNS), owner)
        self.owner = owner
        self.area = area
        self.drag_start = None
        self.drag_started = False
        self.drag_row = -1
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setSectionResizeMode(_stretch_mode())
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(_select_rows())
        self.setSelectionMode(_single_select())
        self.setEditTriggers(_no_edits())
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def item_id_for_row(self, row: int) -> str:
        if row < 0:
            return ""
        cell = self.item(row, 0)
        return str(cell.data(_user_role()) or "") if cell else ""

    def mousePressEvent(self, event) -> None:
        if event.button() == _left_button():
            self.drag_start = event.pos()
            self.drag_started = False
            self.drag_row = self.indexAt(event.pos()).row()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        row = self.indexAt(event.pos()).row()
        item_id = self.item_id_for_row(row)
        if item_id and not (event.buttons() & _left_button()):
            item = self.owner.item_by_id(item_id)
            if item:
                self.owner.show_item_hover_for_item(item, self.viewport().mapToGlobal(event.pos()))
        if not (event.buttons() & _left_button()) or self.drag_start is None:
            if QT_MAJOR == 6:
                pos = event.position().toPoint()
            else:
                pos = event.pos()
            row = self.indexAt(pos).row()
            super().mouseMoveEvent(event)
            return
        if (event.pos() - self.drag_start).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        row = self.drag_row
        item_id = self.item_id_for_row(row)
        if not item_id:
            return
        self.drag_started = True
        self.owner.begin_inventory_table_drag(self, row)
        mime = QMimeData()
        mime.setText(f"{self.area}|{row}|{item_id}|")
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(_move_action())
        self.owner.end_slot_drag()
        self.drag_start = None

    def leaveEvent(self, event) -> None:
        self.owner.hide_item_hover()
        super().leaveEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        """Handle dropping items into the inventory table."""
        if QT_MAJOR == 6:
            pos = event.position().toPoint()      # QPointF -> QPoint
        else:
            pos = event.pos()

        index = self.indexAt(pos)
        row = index.row() if index.isValid() else self.rowCount()

        if self.owner.handle_inventory_table_drop(event.mimeData().text(), row):
            event.acceptProposedAction()

class AspyriaWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._register_fonts()
        self.settings = load_settings()
        reload_content(self.settings.enabled_mods, self.settings.mod_choices)
        self.t = Translator(self.settings.language, self.settings.enabled_mods).t
        self.profile_meta = load_profile()
        self.data: SaveData | None = None
        self.current_slot_id = ""
        self.current_slot_name = ""
        self.pending_loot: Item | None = None
        self.last_scout_lines: list[str] = []
        self.selected_inventory_ids: set[str] = set()
        self.selected_equipment_slot = ""
        self.active_sell_key: tuple[str, str, str] | None = None
        self.refreshing_inventory_tables = False
        self.dragged_item_slot = ""
        self.item_hover: ItemHoverCard | None = None
        self.session_started_at = time.time()
        self.setWindowTitle(self.t("app.title"))
        self.logo_path = self.find_logo_path()
        self.menu_logo_width = 640
        if self.logo_path:
            self.setWindowIcon(QIcon(str(self.logo_path)))
        self.sound = SoundManager(
            SOUND_ROOT,
            self.settings.sfx_volume,
            MUSIC_ROOT,
            self.settings.music_volume,
        )
        self._build_ui()
        self.apply_theme()
        self.apply_resolution()
        self.refresh_all()
        self.stack.setCurrentWidget(self.disclaimer_page)

    def _register_fonts(self) -> None:
        for path in (
            FONT_ROOT / "Tiny5-Regular.ttf",
            FONT_ROOT / "PixelifySans-Regular.ttf",
            FONT_ROOT / "PixelifySans-Bold.ttf",
            FONT_ROOT / "PixelifySans-VariableFont_wght.ttf",
        ):
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))

    def apply_theme(self) -> None:
        self.setFont(_pixel_font(14, family=PIXEL_BODY_FONT))
        self.setStyleSheet(
            """
            QWidget {
                background-color: #121212;
                color: #f2f2f2;
            }
            QLabel, QCheckBox, QTableWidget, QTextEdit, QGroupBox, QProgressBar {
                font-family: 'Tiny5';
            }
            QPushButton {
                background: transparent;
                border: none;
                color: #d8d0c2;
                padding: 8px 10px;
                font-family: 'Pixelify Sans';
                font-size: 20px;
                font-weight: 700;
                text-align: left;
            }
            QPushButton:hover, QPushButton:focus {
                color: #ffd166;
            }
            QPushButton:pressed {
                color: #fff2b3;
            }
            QComboBox, QLineEdit, QTextEdit, QTableWidget {
                background-color: #1b1b1b;
                border: 1px solid #3b3127;
                color: #f2f2f2;
            }
            QHeaderView::section {
                background-color: #2a231d;
                color: #f2f2f2;
                border: 1px solid #3b3127;
                padding: 4px;
                font-family: 'Pixelify Sans';
            }
            QProgressBar {
                border: 1px solid #3b3127;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #c4952d;
            }
            QTabBar::tab {
                min-width: 96px;
                min-height: 30px;
                padding: 8px 16px;
                font-family: 'Pixelify Sans';
                font-size: 20px;
                font-weight: 700;
            }
            """
        )

    def _build_ui(self) -> None:
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.disclaimer_page = self._build_disclaimer_page()
        self.brand_page = self._build_brand_page()
        self.menu_page = self._build_main_menu()
        self.game_page = self._build_game_page()
        self.slots_page = self._build_slots_page()
        self.stats_page = self._build_stats_page()
        self.mods_page = self._build_mods_page()
        self.settings_page = self._build_settings_page()
        self.enhancements_page = self._build_enhancements_page()
        self.credits_page = self._build_credits_page()
        for page in (
            self.disclaimer_page,
            self.brand_page,
            self.menu_page,
            self.game_page,
            self.slots_page,
            self.stats_page,
            self.mods_page,
            self.settings_page,
            self.enhancements_page,
            self.credits_page,
        ):
            self.stack.addWidget(page)

    def _build_disclaimer_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        text = QLabel(
            "This game is currently under development. Preservation of features and format of saves between versions is not guaranteed."
        )
        text.setWordWrap(True)
        text.setAlignment(_align_center())
        text.setFont(_pixel_font(18, bold=True))
        layout.addWidget(text)
        button = QPushButton("OK")
        button.setMinimumHeight(52)
        button.clicked.connect(self.show_brand_splash)
        layout.addWidget(button, alignment=_align_center())
        layout.addStretch(1)
        return page

    def _build_brand_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: #000000; color: #ffffff; }")
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        brand = QLabel("DigitalGarbage")
        brand.setAlignment(_align_center())
        brand.setFont(_pixel_font(28, bold=True))
        layout.addWidget(brand)
        layout.addStretch(1)
        return page

    def show_brand_splash(self) -> None:
        self.sound.play("click")
        self.stack.setCurrentWidget(self.brand_page)
        QTimer.singleShot(1200, self.show_menu)

    def _build_main_menu(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        if self.logo_path:
            logo = QLabel()
            pixmap = QPixmap(str(self.logo_path))
            logo.setPixmap(pixmap.scaledToWidth(self.menu_logo_width))
            logo.setAlignment(_align_center())
            layout.addWidget(logo)
        else:
            title = QLabel(self.t("app.title"))
            font = _pixel_font(30, bold=True)
            title.setFont(font)
            title.setAlignment(_align_center())
            layout.addWidget(title)
        self.menu_status = QLabel()
        self.menu_status.setAlignment(_align_center())
        layout.addWidget(self.menu_status)
        menu_column = QWidget()
        menu_column.setMaximumWidth(self.menu_logo_width)
        menu_column.setSizePolicy(QSizePolicy.Policy.Preferred if QT_MAJOR == 6 else QSizePolicy.Preferred, QSizePolicy.Policy.Maximum if QT_MAJOR == 6 else QSizePolicy.Maximum)
        menu_buttons = QVBoxLayout(menu_column)
        menu_buttons.setContentsMargins(0, 0, 0, 0)
        menu_buttons.setSpacing(2)
        for label, handler in (
            (self.t("menu.new_run"), self.new_run_from_menu),
            (self.t("menu.continue"), self.continue_last_save),
            (self.t("menu.load"), self.show_slots),
            (self.t("menu.stats"), self.show_stats),
            (self.t("menu.enhancements"), self.show_enhancements),
            (self.t("menu.mods"), self.show_mods),
            (self.t("menu.settings"), self.show_settings),
            (self.t("menu.credits"), self.show_credits),
            (self.t("menu.quit"), self.close),
        ):
            button = QPushButton(label)
            button.setMinimumHeight(46)
            button.clicked.connect(lambda checked=False, fn=handler: self._menu_action(fn))
            menu_buttons.addWidget(button)
        layout.addWidget(menu_column, alignment=_align_center())
        layout.addStretch(2)
        return page

    def _menu_action(self, handler) -> None:
        self.sound.play("click")
        handler()

    def _button_action(self, handler, sound_key: str = "click"):
        def wrapped(*_args, **_kwargs):
            self.sound.play(sound_key)
            return handler()
        return wrapped

    def find_logo_path(self) -> Path | None:
        for name in ("logo.jpg", "logo.jpeg", "logo.png", "logo"):
            path = ROOT / name
            if path.exists():
                return path
        return None

    def _build_page_header(self, title: str, back_handler) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        label = QLabel(title)
        font = _pixel_font(20, bold=True)
        label.setFont(font)
        back = QPushButton(self.t("menu.back"))
        back.clicked.connect(self._button_action(back_handler))
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(back)
        layout.addLayout(row)
        return page, layout

    def _build_game_page(self) -> QWidget:
        page, layout = self._build_page_header(self.t("game.run"), self.show_menu)
        action_bar = QHBoxLayout()
        self.save_button = QPushButton(self.t("menu.save"))
        self.retire_button = QPushButton(self.t("menu.retire"))
        self.save_button.clicked.connect(self._button_action(self.save_current_slot))
        self.retire_button.clicked.connect(self._button_action(self.retire_run))
        action_bar.addWidget(self.save_button)
        action_bar.addWidget(self.retire_button)
        action_bar.addStretch(1)
        layout.addLayout(action_bar)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._build_run_tab()
        self._build_inventory_tab()
        self._build_shop_tab()
        return page

    def _build_run_tab(self) -> None:
        tab = QWidget()
        layout = QGridLayout(tab)
        self.run_summary = QLabel()
        self.run_summary.setWordWrap(True)
        self.run_summary.setFrameShape(QFrame.Shape.StyledPanel if QT_MAJOR == 6 else QFrame.StyledPanel)
        self.run_summary.setMinimumHeight(92)
        layout.addWidget(self.run_summary, 0, 0, 1, 2)
        self.xp_status = QLabel()
        self.xp_bar = QProgressBar()
        self.xp_bar.setRange(0, 100)
        xp_box = QGroupBox("XP")
        xp_layout = QVBoxLayout(xp_box)
        xp_layout.addWidget(self.xp_status)
        xp_layout.addWidget(self.xp_bar)
        layout.addWidget(xp_box, 1, 0, 1, 2)
        stance_box = QGroupBox(self.t("game.fight"))
        stance_layout = QHBoxLayout(stance_box)
        stance_row = QHBoxLayout()
        self.fight_button = QPushButton(self.t("game.fight"))
        self.scout_button = QPushButton(self.t("game.scout"))
        self.fight_button.clicked.connect(self.fight)
        self.scout_button.clicked.connect(self._button_action(self.scout_next_fight))
        stance_row.addWidget(self.fight_button)
        stance_row.addWidget(self.scout_button)
        stance_layout.addLayout(stance_row)
        layout.addWidget(stance_box, 2, 0)
        self.next_threat = QLabel()
        self.next_threat.setWordWrap(True)
        self.next_threat.setFrameShape(QFrame.Shape.StyledPanel if QT_MAJOR == 6 else QFrame.StyledPanel)
        layout.addWidget(self.next_threat, 2, 1)
        self.result_panel = QLabel()
        self.result_panel.setWordWrap(True)
        self.result_panel.setFrameShape(QFrame.Shape.StyledPanel if QT_MAJOR == 6 else QFrame.StyledPanel)
        self.result_panel.setText("No fight resolved yet.")
        layout.addWidget(self.result_panel, 3, 0, 1, 2)
        self.stats_table = QTableWidget(0, 3)
        self.stats_table.setHorizontalHeaderLabels(["Stat", "Value", "Description"])
        self.stats_table.horizontalHeader().setSectionResizeMode(_stretch_mode())
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setEditTriggers(_no_edits())
        _enable_table_hover_text(self.stats_table)
        layout.addWidget(self.stats_table, 4, 0)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(_monospace_font())
        layout.addWidget(self.log_view, 4, 1)
        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 3)
        self.tabs.addTab(tab, self.t("game.run"))

    def _build_inventory_tab(self) -> None:
        tab = QWidget()
        layout = QGridLayout(tab)
        equipment_box = QGroupBox("Equipment")
        equipment_layout = QGridLayout(equipment_box)
        self.equipment_slots = {}
        for index, slot in enumerate(EQUIPMENT_SLOTS):
            widget = ItemSlotWidget(self, "equipment", index, slot)
            self.equipment_slots[slot] = widget
            equipment_layout.addWidget(widget, index // 3, index % 3)
        layout.addWidget(equipment_box, 0, 0, 1, 4)
        inventory_box, self.inventory_table = self._make_inventory_table_box("inventory")
        layout.addWidget(inventory_box, 1, 0, 1, 4)
        self.drop_button = QPushButton()
        self.drop_button.setToolTip(self.t("game.drop"))
        trash_icon = KENNEY_ICON_ROOT / "trashcan.png"
        if trash_icon.exists():
            self.drop_button.setIcon(QIcon(str(trash_icon)))
            self.drop_button.setIconSize(QSize(34, 34))
        else:
            self.drop_button.setText("X")
        self.drop_button.setMinimumHeight(46)
        self.drop_button.setStyleSheet("QPushButton { color: #ff4d4d; font-size: 26px; text-align: center; }")
        self.drop_button.clicked.connect(self._button_action(self.drop_selected))
        layout.addWidget(self.drop_button, 2, 0, 1, 4, _align_center())
        self.tabs.addTab(tab, self.t("game.inventory"))

    def _build_shop_tab(self) -> None:
        tab = QWidget()
        layout = QGridLayout(tab)
        self.shop_status = QLabel()
        self.shop_status.setWordWrap(True)
        layout.addWidget(self.shop_status, 0, 0, 1, 5)
        button_specs = [
            ("buy_random_button", self.t("game.buy_random_gear"), self.buy_random_gear),
            ("shop_sell_button", self.t("game.sell"), self.sell_selected),
            ("fuse_button", self.t("game.fuse"), self.fuse_selected),
        ]
        for index, (attr, label, handler) in enumerate(button_specs):
            button = QPushButton(label)
            setattr(self, attr, button)
            button.clicked.connect(handler)
            layout.addWidget(button, 1, index)
        medkit_row = QHBoxLayout()
        self.medkit_buttons = {}
        for size, label in (("small", "Small Medkit"), ("medium", "Medium Medkit"), ("large", "Large Medkit")):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, selected=size: self.buy_medkit(selected))
            self.medkit_buttons[size] = button
            medkit_row.addWidget(button)
        layout.addLayout(medkit_row, 2, 0, 1, 5)
        shop_inventory_box, self.shop_inventory_table = self._make_inventory_table_box("shop_inventory")
        layout.addWidget(shop_inventory_box, 3, 0, 1, 5)
        self.tabs.addTab(tab, self.t("game.shop"))

    def _make_inventory_table_box(self, area: str = "inventory") -> tuple[QGroupBox, InventoryTableWidget]:
        box = QGroupBox("Inventory")
        layout = QVBoxLayout(box)
        action_row = QHBoxLayout()
        improve_button = QPushButton(self.t("game.improve"))
        sell_button = QPushButton(self.t("game.sell"))
        improve_button.clicked.connect(self._button_action(self.repair_selected))
        sell_button.clicked.connect(self._button_action(self.sell_selected))
        action_row.addStretch(1)
        action_row.addWidget(improve_button)
        action_row.addWidget(sell_button)
        layout.addLayout(action_row)
        table = InventoryTableWidget(self, area)
        table.setMinimumHeight(300)
        table.itemSelectionChanged.connect(lambda selected_area=area: self.inventory_table_selection_changed(selected_area))
        table.itemDoubleClicked.connect(lambda item, selected_area=area: self.inventory_table_double_clicked(selected_area))
        layout.addWidget(table)
        if area == "inventory":
            self.inventory_action_bar = action_row
            self.inventory_improve_button = improve_button
            self.inventory_sell_button = sell_button
        else:
            self.shop_inventory_action_bar = action_row
            self.shop_inventory_improve_button = improve_button
            self.shop_inventory_sell_button = sell_button
        return box, table

    def _build_slots_page(self) -> QWidget:
        page, layout = self._build_page_header(self.t("slot.title"), self.show_menu)
        self.slots_table = QTableWidget(0, 5)
        self.slots_table.setHorizontalHeaderLabels(
            [
                self.t("table.name"),
                self.t("table.status"),
                self.t("table.gold"),
                self.t("table.play_time"),
                self.t("table.last_played"),
            ]
        )
        self.slots_table.horizontalHeader().setSectionResizeMode(_stretch_mode())
        self.slots_table.verticalHeader().setVisible(False)
        self.slots_table.setSelectionBehavior(_select_rows())
        self.slots_table.setSelectionMode(_single_select())
        self.slots_table.setEditTriggers(_no_edits())
        _enable_table_hover_text(self.slots_table)
        layout.addWidget(self.slots_table)
        row = QHBoxLayout()
        for label, handler in (
            (self.t("slot.create"), self.create_slot_dialog),
            (self.t("slot.load"), self.load_selected_slot),
            (self.t("slot.rename"), self.rename_selected_slot),
            (self.t("slot.delete"), self.delete_selected_slot),
        ):
            button = QPushButton(label)
            button.clicked.connect(self._button_action(handler))
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    def _build_stats_page(self) -> QWidget:
        page, layout = self._build_page_header(self.t("stats.title"), self.show_menu)
        self.stats_summary = QLabel()
        self.stats_summary.setWordWrap(True)
        layout.addWidget(self.stats_summary)
        self.record_summary = QLabel()
        self.record_summary.setWordWrap(True)
        layout.addWidget(self.record_summary)
        self.codex_table = QTableWidget(0, 6)
        self.codex_table.setHorizontalHeaderLabels(
            [
                self.t("table.item"),
                self.t("table.count"),
                self.t("table.rarity"),
                self.t("table.slot"),
                self.t("table.quality"),
                self.t("table.value"),
            ]
        )
        self.codex_table.horizontalHeader().setSectionResizeMode(_stretch_mode())
        self.codex_table.verticalHeader().setVisible(False)
        self.codex_table.setEditTriggers(_no_edits())
        _enable_table_hover_text(self.codex_table)
        layout.addWidget(self.codex_table)
        return page

    def _build_mods_page(self) -> QWidget:
        page, layout = self._build_page_header(self.t("mods.title"), self.show_menu)
        self.mods_table = QTableWidget(0, 5)
        self.mods_table.setHorizontalHeaderLabels(["Enabled", "ID", "Name", "Version", "Description"])
        self.mods_table.horizontalHeader().setSectionResizeMode(_stretch_mode())
        self.mods_table.verticalHeader().setVisible(False)
        self.mods_table.setSelectionBehavior(_select_rows())
        self.mods_table.setSelectionMode(_single_select())
        self.mods_table.setEditTriggers(_no_edits())
        _enable_table_hover_text(self.mods_table)
        layout.addWidget(self.mods_table)
        row = QHBoxLayout()
        self.toggle_mod_button = QPushButton(self.t("mods.enable"))
        self.toggle_mod_button.clicked.connect(self._button_action(self.toggle_selected_mod))
        row.addWidget(self.toggle_mod_button)
        row.addStretch(1)
        layout.addLayout(row)
        self.conflict_label = QLabel()
        self.conflict_label.setWordWrap(True)
        layout.addWidget(self.conflict_label)
        self.conflict_table = QTableWidget(0, 3)
        self.conflict_table.setHorizontalHeaderLabels(["Kind", "ID", "Mods"])
        self.conflict_table.horizontalHeader().setSectionResizeMode(_stretch_mode())
        self.conflict_table.verticalHeader().setVisible(False)
        self.conflict_table.setSelectionBehavior(_select_rows())
        self.conflict_table.setSelectionMode(_single_select())
        self.conflict_table.setEditTriggers(_no_edits())
        _enable_table_hover_text(self.conflict_table)
        layout.addWidget(self.conflict_table)
        conflict_buttons = QHBoxLayout()
        for label, action in (
            ("Use first", "use_first"),
            ("Use second", "use_second"),
            ("Disable first", "disable_first"),
            ("Disable second", "disable_second"),
            ("Disable both", "disable_both"),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, selected=action: self._button_action(lambda: self.resolve_selected_conflict(selected))())
            conflict_buttons.addWidget(button)
        layout.addLayout(conflict_buttons)
        return page

    def _build_settings_page(self) -> QWidget:
        page, layout = self._build_page_header(self.t("menu.settings"), self.show_menu)
        form = QGridLayout()
        self.language_combo = QComboBox()
        self.language_combo.addItems(["en", "ru"])
        self.language_combo.setCurrentText(self.settings.language)
        self.sfx_volume_slider = QSlider(_horizontal())
        self.sfx_volume_slider.setRange(0, 100)
        self.sfx_volume_slider.setValue(self.settings.sfx_volume)
        self.music_volume_slider = QSlider(_horizontal())
        self.music_volume_slider.setRange(0, 100)
        self.music_volume_slider.setValue(self.settings.music_volume)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTIONS)
        self.resolution_combo.setCurrentText("Fullscreen" if self.settings.fullscreen else self.settings.resolution)
        self.fullscreen_check = QCheckBox(self.t("settings.fullscreen"))
        self.fullscreen_check.setChecked(self.settings.fullscreen)
        form.addWidget(QLabel(self.t("settings.language")), 0, 0)
        form.addWidget(self.language_combo, 0, 1)
        form.addWidget(QLabel(self.t("settings.sfx_volume")), 1, 0)
        form.addWidget(self.sfx_volume_slider, 1, 1)
        form.addWidget(QLabel(self.t("settings.music_volume")), 2, 0)
        form.addWidget(self.music_volume_slider, 2, 1)
        form.addWidget(QLabel(self.t("settings.resolution")), 3, 0)
        form.addWidget(self.resolution_combo, 3, 1)
        form.addWidget(self.fullscreen_check, 4, 1)
        layout.addLayout(form)
        apply_button = QPushButton(self.t("settings.apply"))
        apply_button.clicked.connect(self._button_action(self.apply_settings))
        layout.addWidget(apply_button)
        layout.addStretch(1)
        return page

    def _build_enhancements_page(self) -> QWidget:
        page, layout = self._build_page_header(self.t("menu.enhancements"), self.show_menu)
        self.enhancement_summary = QLabel()
        layout.addWidget(self.enhancement_summary)
        self.upgrade_table = QTableWidget(0, 4)
        self.upgrade_table.setHorizontalHeaderLabels(
            [self.t("table.name"), self.t("table.level"), self.t("table.next_cost"), self.t("table.bonus")]
        )
        self.upgrade_table.horizontalHeader().setSectionResizeMode(_stretch_mode())
        self.upgrade_table.verticalHeader().setVisible(False)
        self.upgrade_table.setSelectionBehavior(_select_rows())
        self.upgrade_table.setSelectionMode(_single_select())
        self.upgrade_table.setEditTriggers(_no_edits())
        self.upgrade_table.itemDoubleClicked.connect(lambda item: self.buy_selected_upgrade())
        layout.addWidget(self.upgrade_table)
        row = QHBoxLayout()
        buy = QPushButton(self.t("game.buy_upgrade"))
        refund = QPushButton(self.t("game.refund_upgrade"))
        slot = QPushButton(self.t("game.buy_slot"))
        refund_slot = QPushButton(self.t("game.refund_slot"))
        buy.clicked.connect(self.buy_selected_upgrade)
        refund.clicked.connect(self.refund_selected_upgrade)
        slot.clicked.connect(self.buy_inventory_slot)
        refund_slot.clicked.connect(self.refund_inventory_slot)
        for button in (buy, refund, slot, refund_slot):
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    def _build_credits_page(self) -> QWidget:
        page, layout = self._build_page_header(self.t("menu.credits"), self.show_menu)
        credit_title = QLabel("Aspyria Credits")
        credit_title.setFont(_pixel_font(22, bold=True))
        layout.addWidget(credit_title)
        credit = QLabel(
            "Aspyria is brought to you by:\n"
            "- Ideas, coding, testing - DigitalGarbage\n"
            "- Coding - ChatGPT Codex\n"
            "- Sound effects - Kenney\n"
            "- Main menu splash art - Grok Imagine\n"
            "- Music - Suno AI\n"
            "- Fonts - Tiny5 by Stefan Schmidt\n"
            "- Fonts - Pixelify Sans by Stefie Justprince\n\n"
            "This is a project made in one evening just for fun and entertainment, as an open-source PyQt game you can use as a base to make your own similar open-source games or just enjoy the game itself as is.\n\n"
            "Images, music and sound effects are used in-game and provided alongside strictly for non-commercial purposes."
        )
        credit.setWordWrap(True)
        credit.setFont(_pixel_font(13, family=PIXEL_BODY_FONT))
        layout.addWidget(credit)
        license_title = QLabel("License")
        license_title.setFont(_pixel_font(18, bold=True))
        layout.addWidget(license_title)
        self.license_text = QTextEdit()
        self.license_text.setReadOnly(True)
        self.license_text.setPlainText(read_license_text())
        layout.addWidget(self.license_text)
        return page

    def rng_for_run(self) -> random.Random:
        run = self.data.run if self.data else None
        if run is None:
            return random.Random()
        rng = random.Random()
        rng.seed(
            run.seed
            + run.completed_bosses * 997
            + run.fights_in_location * 53
            + run.loop_tier * 8191
            + run.rng_counter * 131071
        )
        run.rng_counter += 1
        return rng

    def peek_rng_for_run(self) -> random.Random:
        run = self.data.run if self.data else None
        if run is None:
            return random.Random()
        rng = random.Random()
        rng.seed(
            run.seed
            + run.completed_bosses * 997
            + run.fights_in_location * 53
            + run.loop_tier * 8191
            + run.rng_counter * 131071
        )
        return rng

    def show_menu(self) -> None:
        self.refresh_all()
        self.stack.setCurrentWidget(self.menu_page)
        self.sound.set_music("menu")

    def show_slots(self) -> None:
        self.refresh_slots()
        self.stack.setCurrentWidget(self.slots_page)
        self.sound.set_music("menu")

    def show_stats(self) -> None:
        self.refresh_stats_page()
        self.stack.setCurrentWidget(self.stats_page)
        self.sound.set_music("menu")

    def show_mods(self) -> None:
        self.refresh_mods_page()
        self.stack.setCurrentWidget(self.mods_page)
        self.sound.set_music("menu")

    def show_settings(self) -> None:
        self.stack.setCurrentWidget(self.settings_page)
        self.sound.set_music("menu")

    def show_enhancements(self) -> None:
        if self.data is None:
            self.data = SaveData(meta=self.profile_meta, enabled_mods=list(self.settings.enabled_mods), required_mods=list(self.settings.enabled_mods))
        else:
            self.data.meta = self.profile_meta
        self.refresh_enhancements()
        self.stack.setCurrentWidget(self.enhancements_page)
        self.sound.set_music("menu")

    def show_credits(self) -> None:
        self.stack.setCurrentWidget(self.credits_page)
        self.sound.set_music("menu")

    def show_game(self) -> None:
        self.refresh_all()
        self.stack.setCurrentWidget(self.game_page)
        self.sound.set_music("idle")

    def new_run_from_menu(self) -> None:
        if not self.current_slot_id:
            slot_id = create_save_slot("New Save", SaveData(enabled_mods=list(self.settings.enabled_mods)))
            self.current_slot_id = slot_id
            self.current_slot_name = "New Save"
            self.settings.last_slot = slot_id
            save_settings(self.settings)
        if self.data is None:
            self.data = load_save_slot(self.current_slot_id)
        self.data.meta = self.profile_meta
        self.start_new_run()
        self.show_game()

    def start_new_run(self) -> None:
        if self.data is None:
            self.data = SaveData(meta=self.profile_meta)
        else:
            self.data.meta = self.profile_meta
        seed = int(time.time())
        self.data.enabled_mods = list(self.settings.enabled_mods)
        self.data.required_mods = list(self.settings.enabled_mods)
        self.data.run = RunState(seed=seed, coins=25)
        start_run_timer(self.data.run)
        self.data.run.current_hp = int(effective_stats(self.data.meta, self.data.run)["HP"])
        self.pending_loot = None
        self.last_scout_lines = []
        if hasattr(self, "log_view"):
            self.log_view.clear()
        if hasattr(self, "result_panel"):
            self.result_panel.setText("No fight resolved yet.")
        self.log(STORY.get("intro", "The King sends you into Aspyria's war."))
        self.log(f"Seed: {seed}")
        self.save_current_slot()

    def continue_last_save(self, load_only: bool = False) -> None:
        slot_id = self.settings.last_slot
        if not slot_id:
            slots = list_save_slots()
            slot_id = slots[0].slot_id if slots else ""
        if not slot_id:
            if not load_only:
                self.warn("No save slots yet.")
            return
        self.load_slot(slot_id)
        if not load_only:
            self.show_game()

    def load_selected_slot(self) -> None:
        slot_id = self.selected_slot_id()
        if not slot_id:
            self.warn("Select a save slot first.")
            return
        self.load_slot(slot_id)
        self.show_game()

    def load_slot(self, slot_id: str) -> None:
        data = load_save_slot(slot_id)
        missing = missing_mods_for_save(data, self.settings.enabled_mods)
        if missing and not self.handle_missing_mods(missing):
            return
        self.data = data
        self.profile_meta = data.meta
        self.last_scout_lines = []
        if self.data.run and self.data.run.location_index >= len(LOCATIONS):
            self.warn("The saved location is unavailable with the current mod setup. Moving the run back to Rust Alley.")
            self.data.run.location_index = 0
            self.data.run.fights_in_location = 0
        self.current_slot_id = slot_id
        summary = next((slot for slot in list_save_slots() if slot.slot_id == slot_id), None)
        self.current_slot_name = summary.name if summary else slot_id
        self.settings.last_slot = slot_id
        save_settings(self.settings)
        self.log(f"Loaded {self.current_slot_name}.")
        self.refresh_all()

    def handle_missing_mods(self, missing: list[str]) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(self.t("mods.warning_missing"))
        box.setText(f"{self.t('mods.warning_missing')}\n\n{', '.join(missing)}")
        enable = box.addButton("Enable missing mods", QMessageBox.ButtonRole.AcceptRole if QT_MAJOR == 6 else QMessageBox.AcceptRole)
        load_anyway = box.addButton("Load anyway", QMessageBox.ButtonRole.DestructiveRole if QT_MAJOR == 6 else QMessageBox.DestructiveRole)
        cancel = box.addButton(self.t("dialog.cancel"), QMessageBox.ButtonRole.RejectRole if QT_MAJOR == 6 else QMessageBox.RejectRole)
        box.exec() if QT_MAJOR == 6 else box.exec_()
        clicked = box.clickedButton()
        if clicked == enable:
            for mod in missing:
                if mod not in self.settings.enabled_mods:
                    self.settings.enabled_mods.append(mod)
            self.apply_mod_settings()
            return True
        return clicked == load_anyway and clicked != cancel

    def save_current_slot(self) -> None:
        if self.data is None:
            return
        self.data.meta = self.profile_meta
        if not self.current_slot_id:
            self.current_slot_id = create_save_slot("New Save", self.data)
            self.current_slot_name = "New Save"
        self.flush_play_time()
        save_save_slot(self.current_slot_id, self.current_slot_name or self.current_slot_id, self.data)
        self.settings.last_slot = self.current_slot_id
        save_settings(self.settings)

    def save_profile_state(self) -> None:
        save_profile(self.profile_meta)
        if self.data is not None:
            self.data.meta = self.profile_meta

    def create_slot_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, self.t("slot.create"), self.t("slot.name"))
        if not ok:
            return
        slot_id = create_save_slot(
            name or "New Save",
            SaveData(meta=self.profile_meta, enabled_mods=list(self.settings.enabled_mods), required_mods=list(self.settings.enabled_mods)),
        )
        self.load_slot(slot_id)
        self.refresh_slots()

    def rename_selected_slot(self) -> None:
        slot_id = self.selected_slot_id()
        if not slot_id:
            self.warn("Select a save slot first.")
            return
        name, ok = QInputDialog.getText(self, self.t("slot.rename"), self.t("slot.name"))
        if ok:
            rename_save_slot(slot_id, name)
            if slot_id == self.current_slot_id:
                self.current_slot_name = name
            self.refresh_slots()

    def delete_selected_slot(self) -> None:
        slot_id = self.selected_slot_id()
        if not slot_id:
            self.warn("Select a save slot first.")
            return
        delete_save_slot(slot_id)
        if slot_id == self.current_slot_id:
            self.data = None
            self.current_slot_id = ""
            self.current_slot_name = ""
        self.refresh_slots()

    def delete_failed_current_slot(self) -> None:
        if self.current_slot_id:
            delete_save_slot(self.current_slot_id)
        self.current_slot_id = ""
        self.current_slot_name = ""
        self.settings.last_slot = ""
        save_settings(self.settings)
        self.save_profile_state()
        self.data = None

    def fight(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            self.warn(self.t("game.no_active_run"))
            return
        if self.pending_loot is not None:
            self.handle_loot(self.pending_loot)
            return
        self.last_scout_lines = []
        self.sound.play("attack")
        preview = scout_preview(self.peek_rng_for_run(), self.data.meta, run)
        self.sound.set_music("bossfight" if preview.enemy.boss else "regular_fight")
        result = self.show_fight_replay(run)
        if result is None:
            self.sound.set_music("idle")
            return
        self.log("\n".join(result.logs[-14:]))
        self.show_combat_result(result)
        self.sound.play("victory" if result.victory else "event" if result.fled else "defeat")
        if result.run_success:
            self.sound.play("level")
        if result.run_failure:
            self.sound.play("defeat")
        self.sound.set_music("idle" if run.active else "menu")
        record_combat_result(self.data.stats, result, run)
        if result.victory and not result.enemy.boss and run.active:
            self.choose_enhancement(generate_stage_enhancements(self.rng_for_run(), run), "Stage Enhancement")
        if result.victory and run.active:
            self.choose_random_event()
        if result.loot:
            self.pending_loot = result.loot
            self.handle_loot(result.loot)
        if result.consolation_item:
            self.pending_loot = result.consolation_item
            self.handle_loot(result.consolation_item)
        if self.data.run and self.data.run.pending_defeat_penalty:
            self.handle_pending_defeat_penalty()
        if self.data is None or self.data.run is None:
            return
        if result.run_failure and self.data.run and not self.data.run.active:
            summary = self.run_loss_summary(self.data.run)
            self.show_run_loss_screen(summary)
            self.data.run = None
            self.pending_loot = None
            self.delete_failed_current_slot()
            self.refresh_all()
            self.show_menu()
            return
        if self.data.run and not self.data.run.active:
            self.data.run = None
            self.pending_loot = None
        self.handle_pending_level_rewards()
        self.normalize_current_hp()
        self.save_current_slot()
        self.refresh_all()

    def flee(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            self.warn(self.t("game.no_active_run"))
            return
        result = flee_from_combat(self.rng_for_run(), self.data.meta, run)
        self.last_scout_lines = []
        self.log("\n".join(result.logs))
        self.show_combat_result(result)
        self.sound.play("event")
        self.sound.set_music("idle")
        if result.consolation_item:
            self.pending_loot = result.consolation_item
            self.handle_loot(result.consolation_item)
        self.normalize_current_hp()
        self.save_current_slot()
        self.refresh_all()

    def handle_pending_defeat_penalty(self) -> None:
        run = self.data.run if self.data else None
        if run is None or not run.pending_defeat_penalty:
            return
        pending = run.pending_defeat_penalty
        options = pending.get("options", [])
        stats = pending.get("stats", [])
        choices = []
        if DEFEAT_PRICE_ITEM in options:
            all_items = run.inventory + run.equipped_items()
            strongest = max(all_items, key=lambda item: item.value).name if all_items else "no gear"
            choices.append((f"Give away most powerful item ({strongest})", DEFEAT_PRICE_ITEM))
        if DEFEAT_PRICE_COINS in options:
            choices.append((f"Give away all coins ({run.coins})", DEFEAT_PRICE_COINS))
        if DEFEAT_PRICE_STATS in options:
            stat_text = ", ".join(stats) if stats else "no available stats"
            choices.append((f"Disable stat increases: {stat_text}", DEFEAT_PRICE_STATS))
        if not choices:
            logs: list[str] = []
            resolve_defeat_penalty(self.profile_meta, run, "", logs)
            self.log("\n".join(logs))
            return
        dialog = ChoiceDialog(
            "King's healers managed to save you, but everything comes with the price. What do you choose?",
            ["Choose one price. A chosen price cannot be chosen again in this run."],
            choices,
            self,
        )
        if _run_dialog(dialog) != _dialog_accepted() or dialog.choice is None:
            dialog.choice = choices[0][1]
        logs = []
        resolve_defeat_penalty(self.profile_meta, run, str(dialog.choice), logs)
        self.data.meta = self.profile_meta
        self.log("\n".join(logs))
        if not run.active:
            summary = self.run_loss_summary(run)
            self.show_run_loss_screen(summary)
            self.data.run = None
            self.pending_loot = None
            self.delete_failed_current_slot()
            self.refresh_all()
            self.show_menu()

    def show_fight_replay(self, run: RunState):
        dialog = FightReplayDialog(
            None,
            make_sprite_pixmap("player"),
            make_sprite_pixmap("enemy"),
            self,
            rng=self.rng_for_run(),
            meta=self.data.meta,
            run=run,
            initial_stance="steady",
        )
        _run_dialog(dialog)
        return dialog.result

    def show_combat_result(self, result) -> None:
        summary = result.summary or result.logs[-3:]
        self.result_panel.setText("\n".join(summary))
        if result.enemy.boss or (not result.victory and not result.fled):
            QMessageBox.information(self, "Battle Result", "\n".join(summary), _message_button("Ok"))

    def run_loss_summary(self, run: RunState) -> list[str]:
        location = LOCATIONS[run.location_index]
        all_items = run.inventory + run.equipped_items()
        rarest = max(
            all_items,
            key=lambda item: (RARITY_RANK.get(item.rarity, 0), item.value),
            default=None,
        )
        duration = time.time() - (run.started_at or time.time())
        return [
            "The run is lost.",
            f"Time spent: {format_duration(duration)}",
            f"Progress: {location.name}, fight {run.fights_in_location}/{location.fights_to_boss}",
            f"Rarest item: {rarest.label() if rarest else 'none'}",
            f"Enemies killed: {run.enemies_killed}",
            f"Ended at: loop {run.loop_tier}, stage {run.location_index + 1} ({location.name})",
        ]

    def show_run_loss_screen(self, rows: list[str]) -> None:
        QMessageBox.information(self, "Run Lost", "\n".join(rows), _message_button("Ok"))

    def normalize_current_hp(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            return
        max_hp = int(effective_stats(self.data.meta, run)["HP"])
        run.current_hp = max(1, min(run.current_hp, max_hp))

    def handle_pending_level_rewards(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            return
        while run.pending_level_rewards:
            pending = run.pending_level_rewards.pop(0)
            options = generate_level_reward_options(self.rng_for_run(), run, pending)
            if not options:
                continue
            rows = [
                describe_level_reward_for_run(run, option)
                for option in options
            ]
            choices = [
                (row, option, reward_button_colors(option))
                for row, option in zip(rows, options)
            ]
            dialog = ChoiceDialog(f"Level Reward ({pending.get('source', 'level')})", [], choices, self)
            if _run_dialog(dialog) != _dialog_accepted() or dialog.choice is None:
                run.pending_level_rewards.insert(0, pending)
                return
            self.sound.play("level")
            self.log(apply_level_reward(run, dialog.choice))

    def choose_enhancement(self, options, title: str) -> None:
        run = self.data.run if self.data else None
        if run is None or not options:
            return
        choices = [(option.title, option) for option in options] + [(self.t("game.skip"), None)]
        labels = [
            (
                f"{option.title}: {describe_enhancement(option, run)}",
                option,
                (enhancement_color(option.rarity), enhancement_color(option.rarity)),
            )
            for option in options
        ]
        dialog = ChoiceDialog(title, [], labels + [(self.t("game.skip"), None)], self)
        if _run_dialog(dialog) != _dialog_accepted():
            return
        if dialog.choice is None:
            self.log("Skipped.")
            return
        self.sound.play("event")
        self.log(apply_enhancement(run, dialog.choice))
        self.normalize_current_hp()

    def choose_random_event(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            return
        rng = self.rng_for_run()
        preview = random_event(rng, self.data.meta, run, preview=True)
        if preview is None:
            return
        choice_index = 0
        if preview.choices:
            labels = [(choice.get("label", "Choice"), index) for index, choice in enumerate(preview.choices)]
            dialog = ChoiceDialog(preview.title, preview.logs, labels, self)
            if _run_dialog(dialog) != _dialog_accepted() or dialog.choice is None:
                return
            choice_index = int(dialog.choice)
        result = random_event(rng, self.data.meta, run, event=preview.event, choice_index=choice_index)
        if result:
            self.log(f"{result.title}\n" + "\n".join(result.logs))
            self.sound.play("event")
            if result.loot:
                self.pending_loot = result.loot
                self.handle_loot(result.loot)
            if run.pending_defeat_penalty:
                self.handle_pending_defeat_penalty()
                return
            if not run.active:
                summary = self.run_loss_summary(run)
                self.show_run_loss_screen(summary)
                self.data.run = None
                self.pending_loot = None
                self.delete_failed_current_slot()
                self.refresh_all()
                self.show_menu()

    def handle_loot(self, loot: Item) -> None:
        run = self.data.run if self.data else None
        if run is None:
            self.pending_loot = None
            return
        equipped = run.equipment.get(loot.slot)
        if equipped:
            body = [
                loot.label(),
                loot.stat_line(),
                f"Currently equipped: {equipped.label()}",
                equipped.stat_line(),
                f"Sell value: {sell_value(loot)} coins",
            ]
            choices = [
                ("Replace and store old item", "replace_store"),
                ("Replace and drop old item", "replace_drop"),
                ("Keep equipped and store new item", "store"),
                (self.t("game.sell"), "sell"),
                (self.t("game.drop"), "drop"),
            ]
            if len(run.inventory) >= self.data.meta.inventory_capacity():
                choices = [choice for choice in choices if choice[1] not in {"replace_store", "store"}]
                body.append("Inventory is full. Store choices are unavailable.")
        else:
            body = [loot.label(), loot.stat_line(), f"Sell value: {sell_value(loot)} coins"]
            choices = [
                (self.t("game.equip"), "equip"),
                (self.t("game.store"), "store"),
                (self.t("game.sell"), "sell"),
                (self.t("game.ignore"), "ignore"),
            ]
        loot_colors = item_colors(loot)
        choices = [(label, value, loot_colors) for label, value in choices]
        dialog = ChoiceDialog(
            self.t("game.loot"),
            body,
            choices,
            self,
        )
        if _run_dialog(dialog) != _dialog_accepted():
            return
        if dialog.choice == "equip":
            self.sound.play("loot")
            self.log(equip_item(run, loot))
            self.normalize_current_hp()
            record_item_collected(self.data.stats, loot)
            self.pending_loot = None
        elif dialog.choice == "replace_store":
            self.sound.play("loot")
            old = replace_equipped_item(run, loot, keep_old=True)
            self.log(f"Equipped {loot.name}; stored {old.name if old else 'old item'}.")
            self.normalize_current_hp()
            record_item_collected(self.data.stats, loot)
            self.pending_loot = None
        elif dialog.choice == "replace_drop":
            self.sound.play("loot")
            old = replace_equipped_item(run, loot, keep_old=False)
            self.log(f"Equipped {loot.name}; dropped {old.name if old else 'old item'}.")
            self.normalize_current_hp()
            record_item_collected(self.data.stats, loot)
            self.pending_loot = None
        elif dialog.choice == "store":
            ok, message = add_item_to_inventory(self.data.meta, run, loot)
            self.log(message)
            if ok:
                self.sound.play("loot")
                record_item_collected(self.data.stats, loot)
                self.pending_loot = None
        elif dialog.choice == "sell":
            self.sound.play("coin")
            run.coins += sell_value(loot)
            self.log(f"Sold {loot.name} for {sell_value(loot)} coins.")
            self.pending_loot = None
        elif dialog.choice == "ignore":
            self.log(f"Left {loot.name} behind.")
            self.pending_loot = None
        elif dialog.choice == "drop":
            self.log(f"Dropped {loot.name}.")
            self.pending_loot = None

    def buy_random_gear(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            self.warn(self.t("game.no_active_run"))
            return
        before = set(item.id for item in run.inventory)
        stats = effective_stats(self.data.meta, run)
        ok, message = buy_shop_random_gear(
            self.rng_for_run(), self.data.meta, run, stats["Luck%"], stats["Enemy Scaling%"]
        )
        self.log(message)
        self.sound.play("loot" if ok else "error")
        QMessageBox.information(
            self,
            "Caravan Delivery",
            message,
            _message_button("Ok"),
        )
        if ok:
            for item in run.inventory:
                if item.id not in before:
                    record_item_collected(self.data.stats, item)
        self.save_current_slot()
        self.refresh_all()

    def buy_medkit(self, size: str) -> None:
        run = self.data.run if self.data else None
        if run is None:
            self.warn(self.t("game.no_active_run"))
            return
        max_hp = int(effective_stats(self.data.meta, run)["HP"])
        ok, message = buy_shop_medkit(run, max_hp, size)
        self.log(message)
        self.sound.play("coin" if ok else "error")
        self.save_current_slot()
        self.refresh_all()

    def scout_next_fight(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            self.warn(self.t("game.no_active_run"))
            return
        cost = scouting_cost(run)
        if run.coins < cost:
            self.warn(f"Need {cost} coins.")
            return
        run.coins -= cost
        preview = scout_preview(self.peek_rng_for_run(), self.data.meta, run)
        self.last_scout_lines = list(preview.lines)
        self.log("\n".join(preview.lines))
        self.next_threat.setText("\n".join(preview.lines))
        self.sound.play("event")
        self.save_current_slot()
        self.refresh_all()

    def equip_selected(self) -> None:
        item = self.selected_inventory_item()
        run = self.data.run if self.data else None
        if run is None or item is None:
            self.warn("Select an inventory item first.")
            return
        self.log(equip_item(run, item))
        self.normalize_current_hp()
        self.save_current_slot()
        self.refresh_all()

    def sell_selected(self) -> None:
        items = self.selected_inventory_items()
        run = self.data.run if self.data else None
        if run is None or not items:
            self.warn("Select at least one inventory item first.")
            return
        for item in items:
            if item in run.inventory:
                self.log(sell_item(run, item))
        self.normalize_current_hp()
        self.save_current_slot()
        self.refresh_all()

    def drop_selected(self) -> None:
        items = self.selected_inventory_items()
        run = self.data.run if self.data else None
        if run is None or not items:
            self.warn("Select at least one inventory item first.")
            return
        for item in items:
            if item in run.inventory:
                self.log(drop_item(run, item))
        self.save_current_slot()
        self.refresh_all()

    def repair_selected(self) -> None:
        item = self.selected_inventory_item()
        run = self.data.run if self.data else None
        if run is None or item is None:
            self.warn("Select one inventory item first.")
            return
        ok, message = repair_item(run, item)
        self.log(message)
        self.save_current_slot()
        self.refresh_all()

    def fuse_selected(self) -> None:
        items = self.selected_inventory_items()
        run = self.data.run if self.data else None
        if run is None:
            self.warn(self.t("game.no_active_run"))
            return
        if len(items) != 3:
            self.warn("Select exactly three inventory items.")
            return
        stats = effective_stats(self.data.meta, run)
        ok, message, crafted = craft_fusion(
            self.rng_for_run(), self.data.meta, run, items, stats["Luck%"], stats["Enemy Scaling%"]
        )
        self.log(message)
        if ok and crafted:
            record_item_collected(self.data.stats, crafted)
        self.save_current_slot()
        self.refresh_all()

    def retire_run(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            self.warn(self.t("game.no_active_run"))
            return
        gold = final_gold_payout(self.data.meta, run)
        QMessageBox.information(
            self,
            self.t("app.title"),
            "You had retired. Maybe Aspyria believed in wrong hero...",
            _message_button("Ok"),
        )
        self.profile_meta.gold += gold
        self.data.meta = self.profile_meta
        self.data.run = None
        self.pending_loot = None
        self.log(f"Retired run. The run pays out {gold} gold.")
        self.save_current_slot()
        self.refresh_all()
        self.show_menu()

    def buy_selected_upgrade(self) -> None:
        if self.data is None:
            self.data = SaveData(meta=self.profile_meta)
        stat = self.selected_upgrade_stat()
        if not stat:
            self.warn("Select a stat first.")
            return
        ok, message = buy_upgrade(self.profile_meta, stat)
        self.log(message)
        self.sound.play("coin" if ok else "error")
        self.save_profile_state()
        self.refresh_all()

    def refund_selected_upgrade(self) -> None:
        if self.data is None:
            self.data = SaveData(meta=self.profile_meta)
        stat = self.selected_upgrade_stat()
        if not stat:
            self.warn("Select a stat first.")
            return
        ok, message = refund_upgrade(self.profile_meta, stat)
        self.log(message)
        self.sound.play("coin" if ok else "error")
        self.save_profile_state()
        self.refresh_all()

    def buy_inventory_slot(self) -> None:
        if self.data is None:
            self.data = SaveData(meta=self.profile_meta)
        ok, message = buy_meta_inventory_slot(self.profile_meta)
        self.log(message)
        self.sound.play("coin" if ok else "error")
        self.save_profile_state()
        self.refresh_all()

    def refund_inventory_slot(self) -> None:
        if self.data is None:
            self.data = SaveData(meta=self.profile_meta)
        run = self.data.run
        if run and len(run.inventory) > self.profile_meta.inventory_capacity() - 1:
            self.warn("Inventory is too full to refund a slot right now.")
            return
        ok, message = refund_meta_inventory_slot(self.profile_meta)
        self.log(message)
        self.sound.play("coin" if ok else "error")
        self.save_profile_state()
        self.refresh_all()

    def apply_settings(self) -> None:
        self.settings.language = self.language_combo.currentText()
        self.settings.sfx_volume = self.sfx_volume_slider.value()
        self.settings.music_volume = self.music_volume_slider.value()
        selected_resolution = self.resolution_combo.currentText()
        self.settings.fullscreen = self.fullscreen_check.isChecked() or selected_resolution == "Fullscreen"
        if selected_resolution != "Fullscreen":
            self.settings.resolution = selected_resolution
        save_settings(self.settings)
        self.t = Translator(self.settings.language, self.settings.enabled_mods).t
        self.sound.set_sfx_volume(self.settings.sfx_volume)
        self.sound.set_music_volume(self.settings.music_volume)
        self.apply_resolution()
        self.warn("Settings saved. Restart the window to refresh every translated label.")

    def apply_resolution(self) -> None:
        if self.settings.fullscreen:
            self.showFullScreen()
            return
        self.showNormal()
        width, height = (int(part) for part in self.settings.resolution.split("x"))
        self.resize(width, height)

    def toggle_selected_mod(self) -> None:
        row = self.mods_table.currentRow()
        if row < 0:
            self.warn("Select a mod first.")
            return
        item = self.mods_table.item(row, 1)
        mod_id = item.text()
        if mod_id in self.settings.enabled_mods:
            self.settings.enabled_mods.remove(mod_id)
        else:
            self.settings.enabled_mods.append(mod_id)
        self.apply_mod_settings()

    def resolve_selected_conflict(self, action: str) -> None:
        row = self.conflict_table.currentRow()
        if row < 0 or row >= len(CONTENT_CONFLICTS):
            self.warn("Select a conflict first.")
            return
        conflict = CONTENT_CONFLICTS[row]
        first = conflict.mods[0]
        second = conflict.mods[1] if len(conflict.mods) > 1 else first
        if action == "use_first":
            self.settings.mod_choices[conflict.key] = first
        elif action == "use_second":
            self.settings.mod_choices[conflict.key] = second
        elif action == "disable_first":
            self._disable_mod(first)
        elif action == "disable_second":
            self._disable_mod(second)
        elif action == "disable_both":
            self._disable_mod(first)
            self._disable_mod(second)
        self.apply_mod_settings()

    def _disable_mod(self, mod_id: str) -> None:
        if mod_id in self.settings.enabled_mods:
            self.settings.enabled_mods.remove(mod_id)

    def apply_mod_settings(self) -> None:
        save_settings(self.settings)
        reload_content(self.settings.enabled_mods, self.settings.mod_choices)
        self.t = Translator(self.settings.language, self.settings.enabled_mods).t
        self.refresh_mods_page()
        self.refresh_all()

    def selected_inventory_item(self) -> Item | None:
        items = self.selected_inventory_items()
        return items[0] if items else None

    def selected_inventory_items(self) -> list[Item]:
        run = self.data.run if self.data else None
        if run is None:
            return []
        return [item for item in run.inventory if item.id in self.selected_inventory_ids]

    def item_by_id(self, item_id: str) -> Item | None:
        run = self.data.run if self.data else None
        if run is None:
            return None
        for item in run.inventory + run.equipped_items():
            if item.id == item_id:
                return item
        return None

    def inventory_table_selection_changed(self, area: str) -> None:
        if self.refreshing_inventory_tables:
            return
        table = self.inventory_table if area == "inventory" else self.shop_inventory_table
        item_id = table.item_id_for_row(table.currentRow())
        if item_id:
            self.selected_inventory_ids = {item_id}
            self.selected_equipment_slot = ""
            self.active_sell_key = (area, item_id, "")
        else:
            self.selected_inventory_ids.clear()
            self.active_sell_key = None
        self.refresh_inventory_action_buttons()
        self.refresh_shop_tab()

    def inventory_table_double_clicked(self, area: str) -> None:
        item = self.selected_inventory_item()
        run = self.data.run if self.data else None
        if run is None or item is None:
            return
        self.log(equip_item(run, item))
        self.selected_inventory_ids.clear()
        self.selected_equipment_slot = item.slot
        self.active_sell_key = None
        self.normalize_current_hp()
        self.save_current_slot()
        self.refresh_all()

    def slot_clicked(self, slot: ItemSlotWidget) -> None:
        modifiers = QApplication.keyboardModifiers()
        multi = bool(modifiers & _control_modifier())
        if slot.area == "equipment":
            self.selected_equipment_slot = slot.equipment_slot
            self.active_sell_key = (slot.area, slot.item_id, slot.equipment_slot) if slot.item_id else None
            if not multi:
                self.selected_inventory_ids.clear()
        elif slot.item_id:
            if not multi:
                self.selected_inventory_ids = {slot.item_id}
            elif slot.item_id in self.selected_inventory_ids:
                self.selected_inventory_ids.remove(slot.item_id)
            else:
                self.selected_inventory_ids.add(slot.item_id)
            self.selected_equipment_slot = ""
            self.active_sell_key = (slot.area, slot.item_id, "")
        elif not multi:
            self.selected_inventory_ids.clear()
            self.selected_equipment_slot = ""
            self.active_sell_key = None
        self.refresh_inventory_tables()
        self.refresh_shop_tab()

    def should_show_slot_sell(self, area: str, item: Item | None, equipment_slot: str = "") -> bool:
        if item is None or self.active_sell_key is None:
            return False
        active_area, active_item_id, active_equipment_slot = self.active_sell_key
        return active_area == area and active_item_id == item.id and active_equipment_slot == equipment_slot

    def sell_slot_item(self, slot: ItemSlotWidget) -> None:
        run = self.data.run if self.data else None
        if run is None:
            return
        item = None
        if slot.area == "equipment":
            item = run.equipment.get(slot.equipment_slot)
        elif slot.item_id:
            item = next((row for row in run.inventory if row.id == slot.item_id), None)
        if item is None:
            self.warn("Select an item first.")
            return
        self.log(sell_item(run, item))
        self.sound.play("coin")
        self.selected_inventory_ids.discard(item.id)
        if self.selected_equipment_slot == slot.equipment_slot:
            self.selected_equipment_slot = ""
        self.active_sell_key = None
        self.normalize_current_hp()
        self.save_current_slot()
        self.refresh_all()

    def take_off_slot_item(self, slot: ItemSlotWidget) -> None:
        run = self.data.run if self.data else None
        if run is None or slot.area != "equipment":
            return
        ok, message = unequip_item(self.data.meta, run, slot.equipment_slot)
        self.log(message)
        if not ok:
            self.warn(message)
            return
        moved = run.inventory[-1] if run.inventory else None
        self.selected_inventory_ids = {moved.id} if moved else set()
        self.selected_equipment_slot = ""
        self.active_sell_key = None
        self.normalize_current_hp()
        self.save_current_slot()
        self.refresh_all()

    def begin_slot_drag(self, slot: ItemSlotWidget) -> None:
        item = slot.current_item
        self.dragged_item_slot = item.slot if item else ""
        self.hide_item_hover(slot)
        for equipment_slot, widget in self.equipment_slots.items():
            if not self.dragged_item_slot:
                state = ""
            elif equipment_slot == self.dragged_item_slot:
                state = "valid"
            else:
                state = "invalid"
            widget.set_drag_target_state(state)
        self.refresh_inventory_action_buttons()

    def begin_inventory_table_drag(self, table: InventoryTableWidget, row: int) -> None:
        item = self.item_by_id(table.item_id_for_row(row))
        self.dragged_item_slot = item.slot if item else ""
        self.hide_item_hover()
        for equipment_slot, widget in self.equipment_slots.items():
            if not self.dragged_item_slot:
                state = ""
            elif equipment_slot == self.dragged_item_slot:
                state = "valid"
            else:
                state = "invalid"
            widget.set_drag_target_state(state)

    def end_slot_drag(self) -> None:
        self.dragged_item_slot = ""
        for widget in list(self.equipment_slots.values()):
            widget.set_drag_target_state("")

    def show_item_hover(self, slot: ItemSlotWidget) -> None:
        if slot.current_item is None:
            return
        self.show_item_hover_for_item(slot.current_item, slot.mapToGlobal(slot.rect().topRight()), slot)

    def show_item_hover_for_item(self, item: Item, anchor: QPoint, source_widget: QWidget | None = None) -> None:
        if self.item_hover is None:
            self.item_hover = ItemHoverCard(self)
        self.item_hover.refresh(item)
        self.item_hover.adjustSize()
        width = self.item_hover.width()
        height = self.item_hover.height()
        position = QPoint(anchor.x() + 12, anchor.y())
        if source_widget is not None:
            position.setY(anchor.y() + max(0, (source_widget.height() - height) // 2))
        window_top_left = self.mapToGlobal(self.rect().topLeft())
        window_bottom_right = self.mapToGlobal(self.rect().bottomRight())
        margin = 12
        right_limit = window_bottom_right.x() - margin
        left_limit = window_top_left.x() + margin
        top_limit = window_top_left.y() + margin
        bottom_limit = window_bottom_right.y() - margin
        if position.x() + width > right_limit:
            position.setX(anchor.x() - width - margin)
        position.setX(max(left_limit, min(position.x(), right_limit - width)))
        position.setY(max(top_limit, min(position.y(), bottom_limit - height)))
        self.item_hover.move(position)
        self.item_hover.show()

    def hide_item_hover(self, slot: ItemSlotWidget | None = None) -> None:
        if self.item_hover is not None:
            self.item_hover.hide()

    def handle_slot_drop(self, payload: str, target: ItemSlotWidget) -> bool:
        run = self.data.run if self.data else None
        if run is None:
            return False
        self.active_sell_key = None
        parts = payload.split("|")
        if len(parts) != 4:
            return False
        source_area, source_index_text, item_id, source_slot = parts
        try:
            source_index = int(source_index_text)
        except ValueError:
            source_index = -1
        if source_area in {"inventory", "shop_inventory"}:
            item = next((row for row in run.inventory if row.id == item_id), None)
            if item is None:
                return False
            if target.area == "equipment":
                if target.equipment_slot != item.slot:
                    self.warn(f"{item.name} belongs in {item.slot}.")
                    return False
                self.log(equip_item(run, item))
                self.selected_inventory_ids.clear()
                self.selected_equipment_slot = target.equipment_slot
            elif target.area in {"inventory", "shop_inventory"}:
                if source_index < 0 or source_index >= len(run.inventory):
                    source_index = run.inventory.index(item)
                target_index = max(0, min(target.index, len(run.inventory) - 1))
                run.inventory.pop(source_index)
                run.inventory.insert(target_index, item)
                self.selected_inventory_ids = {item.id}
            else:
                return False
        elif source_area == "equipment":
            if target.area not in {"inventory", "shop_inventory"}:
                return False
            ok, message = unequip_item(self.data.meta, run, source_slot)
            self.log(message)
            if not ok:
                self.warn(message)
                return False
            item = run.inventory[-1]
            target_index = max(0, min(target.index, len(run.inventory) - 1))
            run.inventory.remove(item)
            run.inventory.insert(target_index, item)
            self.selected_inventory_ids = {item.id}
            self.selected_equipment_slot = ""
        else:
            return False
        self.normalize_current_hp()
        self.save_current_slot()
        self.refresh_all()
        return True

    def handle_inventory_table_drop(self, payload: str, target_index: int) -> bool:
        run = self.data.run if self.data else None
        if run is None:
            return False
        self.active_sell_key = None
        parts = payload.split("|")
        if len(parts) != 4:
            return False
        source_area, source_index_text, item_id, source_slot = parts
        try:
            source_index = int(source_index_text)
        except ValueError:
            source_index = -1
        if source_area in {"inventory", "shop_inventory"}:
            item = next((row for row in run.inventory if row.id == item_id), None)
            if item is None:
                return False
            if source_index < 0 or source_index >= len(run.inventory):
                source_index = run.inventory.index(item)
            target_index = max(0, min(target_index, len(run.inventory) - 1))
            run.inventory.pop(source_index)
            run.inventory.insert(target_index, item)
            self.selected_inventory_ids = {item.id}
            self.selected_equipment_slot = ""
        elif source_area == "equipment":
            ok, message = unequip_item(self.data.meta, run, source_slot)
            self.log(message)
            if not ok:
                self.warn(message)
                return False
            item = run.inventory[-1]
            target_index = max(0, min(target_index, len(run.inventory) - 1))
            run.inventory.remove(item)
            run.inventory.insert(target_index, item)
            self.selected_inventory_ids = {item.id}
            self.selected_equipment_slot = ""
        else:
            return False
        self.normalize_current_hp()
        self.save_current_slot()
        self.refresh_all()
        return True

    def selected_upgrade_stat(self) -> str | None:
        row = self.upgrade_table.currentRow()
        if row < 0:
            return None
        item = self.upgrade_table.item(row, 0)
        return item.data(_user_role()) if item else None

    def selected_slot_id(self) -> str | None:
        row = self.slots_table.currentRow()
        if row < 0:
            return None
        item = self.slots_table.item(row, 0)
        return item.data(_user_role()) if item else None

    def refresh_all(self) -> None:
        self.menu_status.setText(
            f"Current slot: {self.current_slot_name or '-'}    Mods: {', '.join(self.settings.enabled_mods) or 'base'}"
        )
        self.refresh_game_page()
        self.refresh_enhancements()

    def refresh_game_page(self) -> None:
        run = self.data.run if self.data else None
        scout_label = self.t("game.scout")
        if run is not None:
            scout_label = f"{scout_label} ({scouting_cost(run)} coins)"
        self.scout_button.setText(scout_label)
        for button in (
            self.save_button,
            self.retire_button,
            self.fight_button,
            self.scout_button,
            self.drop_button,
        ):
            button.setEnabled(self.data is not None and (button == self.save_button or run is not None))
        self.refresh_run_tab()
        self.refresh_inventory_tables()
        self.refresh_shop_tab()

    def refresh_run_tab(self) -> None:
        self.stats_table.setRowCount(0)
        run = self.data.run if self.data else None
        if run is None:
            _set_label_text(self.run_summary, self.t("game.no_active_run"))
            self.xp_status.setText("")
            self.xp_bar.setValue(0)
            self.xp_bar.parentWidget().setStyleSheet("")
            _set_label_text(self.next_threat, "")
            return
        location = LOCATIONS[run.location_index]
        stats = effective_stats(self.data.meta, run)
        _set_label_text(
            self.run_summary,
            f"Location: {location.name} | Loop tier {run.loop_tier} | "
            f"Fight {run.fights_in_location}/{location.fights_to_boss}\n"
            f"HP: {run.current_hp}/{int(stats['HP'])} | "
            f"Coins: {run.coins} | Defeats: {run.defeats}/4 | Bosses defeated: {run.completed_bosses} | "
            f"Inventory: {len(run.inventory)}/{self.data.meta.inventory_capacity()}"
        )
        xp_needed = run.level * 100
        next_level = run.level + 1
        reward_text = "Next reward: milestone perk" if next_level % 5 == 0 else "Next reward: stat choice"
        pending_text = f" | Pending rewards: {len(run.pending_level_rewards)}" if run.pending_level_rewards else ""
        _set_label_text(
            self.xp_status,
            f"Level {run.level} | XP {run.xp}/{xp_needed} | {xp_needed - run.xp} XP to next level | "
            f"{reward_text}{pending_text}"
        )
        self.xp_bar.setMaximum(xp_needed)
        self.xp_bar.setValue(min(run.xp, xp_needed))
        milestone_style = "QGroupBox { border: 2px solid #c4952d; }" if next_level % 5 == 0 else ""
        self.xp_bar.parentWidget().setStyleSheet(milestone_style)
        if self.last_scout_lines:
            _set_label_text(self.next_threat, "\n".join(self.last_scout_lines))
        else:
            _set_label_text(
                self.next_threat,
                f"Next fight: {'boss' if run.fights_in_location >= location.fights_to_boss else 'mob'}\n"
                f"Route: {location.name}\nScout cost: {scouting_cost(run)} coins"
            )
        rows = []
        rows.append(("Current HP", f"{run.current_hp:.0f}/{stats.get('HP', 1.0):.0f}", "Your current health and maximum health."))
        for stat in STAT_KEYS:
            suffix = "" if stat in {"ATK", "HP"} else "%"
            rows.append((stat, f"{stats.get(stat, 0.0):.1f}{suffix}", STAT_DESCRIPTIONS.get(stat, "")))
        for stat in ("Damage Reduction%", "Damage Taken%", "Gold Payout%"):
            if stats.get(stat):
                rows.append((stat, f"{stats[stat]:.1f}%", STAT_DESCRIPTIONS.get(stat, "")))
        self.fill_table(self.stats_table, rows)

    def refresh_inventory_tables(self) -> None:
        self.hide_item_hover()
        run = self.data.run if self.data else None
        if run is None:
            for widget in self.equipment_slots.values():
                widget.refresh(None, False)
            for table in (self.inventory_table, self.shop_inventory_table):
                table.setRowCount(0)
            self.refresh_inventory_action_buttons()
            return
        for slot, widget in self.equipment_slots.items():
            item = run.equipment.get(slot)
            widget.refresh(item, self.selected_equipment_slot == slot, self.should_show_slot_sell("equipment", item, slot))
        self.selected_inventory_ids = {
            item_id for item_id in self.selected_inventory_ids if any(item.id == item_id for item in run.inventory)
        }
        if self.active_sell_key and not any(
            self.should_show_slot_sell("equipment", item, slot)
            for slot, item in ((slot, run.equipment.get(slot)) for slot in EQUIPMENT_SLOTS)
        ) and not any(item.id == self.active_sell_key[1] for item in run.inventory):
            self.active_sell_key = None
        self.refreshing_inventory_tables = True
        try:
            self.populate_inventory_table(self.inventory_table, run)
            self.populate_inventory_table(self.shop_inventory_table, run)
        finally:
            self.refreshing_inventory_tables = False
        self.refresh_inventory_action_buttons()

    def populate_inventory_table(self, table: InventoryTableWidget, run: RunState) -> None:
        table.setRowCount(len(run.inventory))
        selected_row = -1
        for row, item in enumerate(run.inventory):
            stat_parts = [
                part.strip()
                for part in item.stat_line().split(",")
                if part.strip() and not part.strip().startswith("Drawback:")
            ][:6]
            values = [
                item.name,
                item.set_name or "-",
                item.rarity,
                item.quality,
                str(item.ilevel),
                str(sell_value(item)),
                *stat_parts,
            ]
            values.extend(["-"] * (len(InventoryTableWidget.COLUMNS) - len(values)))
            rarity_top, rarity_bottom = item_colors(item)
            for col, value in enumerate(values[: len(InventoryTableWidget.COLUMNS)]):
                cell = _table_item(value)
                if col == 0:
                    cell.setData(_user_role(), item.id)
                if col in {0, 2, 3}:
                    cell.setForeground(QBrush(QColor(readable_text_for_backgrounds(rarity_top, rarity_bottom))))
                    cell.setBackground(QBrush(QColor(rarity_bottom)))
                table.setItem(row, col, cell)
            if item.id in self.selected_inventory_ids:
                selected_row = row
        if selected_row >= 0:
            table.selectRow(selected_row)
        elif table.currentRow() >= table.rowCount():
            table.clearSelection()

    def refresh_inventory_action_buttons(self) -> None:
        item = self.selected_inventory_item()
        cost = repair_cost(item) if item else 0
        for improve_button, sell_button in (
            (getattr(self, "inventory_improve_button", None), getattr(self, "inventory_sell_button", None)),
            (getattr(self, "shop_inventory_improve_button", None), getattr(self, "shop_inventory_sell_button", None)),
        ):
            if not improve_button or not sell_button:
                continue
            improve_button.setVisible(item is not None)
            sell_button.setVisible(item is not None)
            if item is None:
                continue
            improve_button.setText(f"{self.t('game.improve')} ({cost} coins)" if cost > 0 else f"{self.t('game.improve')} (max)")
            sell_button.setText(f"{self.t('game.sell')} ({sell_value(item)} coins)")

    def refresh_shop_tab(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            _set_label_text(self.shop_status, self.t("game.no_active_run"))
            if hasattr(self, "buy_random_button"):
                self.buy_random_button.setText(self.t("game.buy_random_gear"))
            if hasattr(self, "medkit_buttons"):
                for size, button in self.medkit_buttons.items():
                    button.setText(f"{size.title()} Medkit")
            return
        stats = effective_stats(self.data.meta, run)
        caravan_item, caravan_cost = self.caravan_offer_preview(run, stats["Luck%"], stats["Enemy Scaling%"])
        if hasattr(self, "buy_random_button"):
            self.buy_random_button.setText(f"{self.t('game.buy_random_gear')} ({caravan_cost} coins)")
        if hasattr(self, "medkit_buttons"):
            labels = {"small": "Small Medkit", "medium": "Medium Medkit", "large": "Large Medkit"}
            for size, button in self.medkit_buttons.items():
                button.setText(f"{labels[size]} ({medkit_cost(run, size)} coins)")
        _set_label_text(
            self.shop_status,
            f"Coins: {run.coins} | Caravan item: {caravan_item.label()} | Cost: {caravan_cost} coins | "
            f"Random gear caravan failure: 25% | "
            f"Failure pity: +{run.random_gear_failures}% rarity/+{run.random_gear_failures}% quality"
        )

    def caravan_offer_preview(self, run: RunState, luck: float, enemy_scaling: float) -> tuple[Item, int]:
        if run.random_gear_offer and run.random_gear_offer_cost > 0:
            return Item.from_dict(run.random_gear_offer), run.random_gear_offer_cost
        item = roll_item(
            self.peek_rng_for_run(),
            run,
            luck,
            enemy_scaling,
            merchant_pity=float(run.random_gear_failures),
        )
        return item, caravan_price(item)

    def refresh_enhancements(self) -> None:
        if self.data is None:
            _set_label_text(self.enhancement_summary, "Load or create a save slot first.")
            self.upgrade_table.setRowCount(0)
            return
        meta = self.data.meta
        locked = ", ".join(self.data.run.locked_stats) if self.data.run and self.data.run.locked_stats else "-"
        _set_label_text(
            self.enhancement_summary,
            f"Gold: {meta.gold} | Inventory capacity: {meta.inventory_capacity()} | Locked stats: {locked}"
        )
        self.upgrade_table.setRowCount(len(STAT_KEYS))
        for row, stat in enumerate(STAT_KEYS):
            level = meta.upgrades.get(stat, 0)
            values = [stat, str(level), "MAX" if level >= 50 else str(upgrade_cost(stat, level + 1)), f"+{upgrade_bonus_for_level(level):g}"]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if col == 0:
                    cell.setData(_user_role(), stat)
                self.upgrade_table.setItem(row, col, cell)

    def refresh_slots(self) -> None:
        slots = list_save_slots()
        self.slots_table.setRowCount(len(slots))
        for row, slot in enumerate(slots):
            values = [
                slot.name,
                "active run" if slot.has_run else "no run",
                str(slot.gold),
                format_duration(slot.play_time_seconds),
                time.strftime("%Y-%m-%d %H:%M", time.localtime(slot.last_played_at)) if slot.last_played_at else "-",
            ]
            for col, value in enumerate(values):
                cell = _table_item(value)
                if col == 0:
                    cell.setData(_user_role(), slot.slot_id)
                self.slots_table.setItem(row, col, cell)

    def refresh_stats_page(self) -> None:
        stats = self.data.stats if self.data else None
        if stats is None:
            _set_label_text(self.stats_summary, "Load a save slot first.")
            _set_label_text(self.record_summary, "")
            self.codex_table.setRowCount(0)
            return
        _set_label_text(
            self.stats_summary,
            f"{self.t('stats.enemies')}: {stats.enemies_defeated}    "
            f"{self.t('stats.bosses')}: {stats.bosses_defeated}    "
            f"{self.t('stats.play_time')}: {format_duration(stats.play_time_seconds)}"
        )
        _set_label_text(
            self.record_summary,
            f"{self.t('stats.quickest_failed')}: {format_record(stats.quickest_failed_run)}\n"
            f"{self.t('stats.longest_failed')}: {format_record(stats.longest_failed_run)}\n"
            f"{self.t('stats.quickest_success')}: {format_record(stats.quickest_successful_run)}\n"
            f"{self.t('stats.longest_success')}: {format_record(stats.longest_successful_run)}"
        )
        records = sorted(stats.item_codex.values(), key=lambda item: (-item.count, item.name))
        self.codex_table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = [
                record.name,
                str(record.count),
                record.highest_rarity,
                ", ".join(sorted(record.slots)),
                ", ".join(sorted(record.qualities)),
                str(record.highest_value),
            ]
            for col, value in enumerate(values):
                self.codex_table.setItem(row, col, _table_item(value))

    def refresh_mods_page(self) -> None:
        mods = list_available_mods()
        self.mods_table.setRowCount(len(mods))
        for row, mod in enumerate(mods):
            values = [
                "yes" if mod.id in self.settings.enabled_mods else "no",
                mod.id,
                mod.name,
                mod.version,
                mod.description,
            ]
            for col, value in enumerate(values):
                self.mods_table.setItem(row, col, _table_item(value))
        warnings = "\n".join(CONTENT_WARNINGS)
        conflicts = "\n".join(f"{conflict.kind}:{conflict.content_id} -> {', '.join(conflict.mods)}" for conflict in CONTENT_CONFLICTS)
        _set_label_text(self.conflict_label, warnings or conflicts or self.t("mods.conflicts"))
        self.conflict_table.setRowCount(len(CONTENT_CONFLICTS))
        for row, conflict in enumerate(CONTENT_CONFLICTS):
            for col, value in enumerate([conflict.kind, conflict.content_id, ", ".join(conflict.mods)]):
                self.conflict_table.setItem(row, col, _table_item(value))

    def flush_play_time(self) -> None:
        if self.data is None:
            return
        now = time.time()
        add_play_time(self.data.stats, now - self.session_started_at)
        self.session_started_at = now

    def fill_table(self, table: QTableWidget, rows: list[tuple[str, str]]) -> None:
        table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                table.setItem(row, col, _table_item(value))

    def log(self, text: str) -> None:
        if hasattr(self, "log_view") and text:
            self.log_view.append(text)

    def warn(self, text: str) -> None:
        self.log(text)
        QMessageBox.information(self, self.t("app.title"), text, _message_button("Ok"))

    def closeEvent(self, event) -> None:
        self.save_current_slot()
        event.accept()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        enter_keys = {
            Qt.Key.Key_Return if QT_MAJOR == 6 else Qt.Key_Return,
            Qt.Key.Key_Enter if QT_MAJOR == 6 else Qt.Key_Enter,
            Qt.Key.Key_Space if QT_MAJOR == 6 else Qt.Key_Space,
        }
        if self.stack.currentWidget() == self.disclaimer_page and key in enter_keys:
            self.show_brand_splash()
            return
        super().keyPressEvent(event)


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_record(record) -> str:
    if not record:
        return "-"
    return f"{format_duration(record.duration_seconds)} (seed {record.seed})"


def read_license_text() -> str:
    if LICENSE_PATH.exists():
        return LICENSE_PATH.read_text(encoding="utf-8")
    return (
        "Aspyria Source-Available Noncommercial License\n\n"
        "The full license text should be available in LICENSE.md."
    )


def reward_button_colors(reward: dict) -> tuple[str, str]:
    if reward.get("type") == "perk" or reward.get("effect"):
        color = enhancement_color("legendary")
        return color, color
    stat = reward.get("stat", "")
    if stat in {"Luck%", "Evasion%", "Multi-Attack Chance%"}:
        color = enhancement_color("uncommon")
    elif stat in {"Megacrit Chance%", "Megacrit Damage%"}:
        color = enhancement_color("mythical")
    else:
        color = enhancement_color("rare")
    return color, color


def make_sprite_pixmap(kind: str, scale: int = 8) -> QPixmap:
    palettes = {
        "player": ["000000", "d9d9d9", "3d7bff", "f2c28b", "7a4f2a"],
        "enemy": ["000000", "2d2d35", "6f42a5", "d9d9d9", "4d7f45"],
        "boss": ["000000", "262027", "d94444", "f59f2a", "d9d9d9"],
        "corrupted": ["000000", "1a1118", "d94444", "a05cff", "f2f2f2"],
    }
    color = palettes.get(kind, palettes["enemy"])
    grid = [
        "00011000",
        "00133100",
        "01133110",
        "00222200",
        "04222240",
        "00022000",
        "00100100",
        "01000010",
    ]
    if kind == "player":
        grid = [
            "00033000",
            "00133100",
            "01133110",
            "00022000",
            "04422440",
            "00022000",
            "00100100",
            "01000010",
        ]
    pixmap = QPixmap(8 * scale, 8 * scale)
    pixmap.fill(QColor("#00000000"))
    painter = QPainter(pixmap)
    for y, row in enumerate(grid):
        for x, index in enumerate(row):
            if index == "0":
                continue
            painter.fillRect(x * scale, y * scale, scale, scale, QColor(f"#{color[int(index)]}"))
    painter.end()
    return pixmap


def launch() -> int:
    app = QApplication(sys.argv)
    window = AspyriaWindow()
    window.show()
    return app.exec() if QT_MAJOR == 6 else app.exec_()


if __name__ == "__main__":
    raise SystemExit(launch())
