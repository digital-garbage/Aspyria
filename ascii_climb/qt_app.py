from __future__ import annotations

import random
import sys
import time
from pathlib import Path
from typing import Iterable

try:
    from PyQt6.QtCore import QMimeData, Qt, QTimer
    from PyQt6.QtGui import QBrush, QColor, QDrag, QFont, QFontDatabase, QIcon, QPainter, QPixmap
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
        QVBoxLayout,
        QWidget,
    )

    QT_MAJOR = 6
except ModuleNotFoundError:
    from PyQt5.QtCore import QMimeData, Qt, QTimer
    from PyQt5.QtGui import QBrush, QColor, QDrag, QFont, QFontDatabase, QIcon, QPainter, QPixmap
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
        QVBoxLayout,
        QWidget,
    )

    QT_MAJOR = 5

from ascii_climb.combat import STANCE_DESCRIPTIONS, flee_from_combat, run_combat, run_combat_turn, scout_preview
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
from ascii_climb.loot import sell_value
from ascii_climb.meta import (
    buy_inventory_slot as buy_meta_inventory_slot,
    buy_upgrade,
    effective_stats,
    final_gold_payout,
    refund_inventory_slot as refund_meta_inventory_slot,
    refund_upgrade,
    upgrade_cost,
)
from ascii_climb.models import EQUIPMENT_SLOTS, GameSettings, Item, RunState, STAT_DESCRIPTIONS, STAT_KEYS, SaveData
from ascii_climb.progression import (
    apply_enhancement,
    describe_enhancement,
    generate_stage_enhancements,
)
from ascii_climb.save import (
    create_save_slot,
    delete_save_slot,
    list_save_slots,
    load_save_slot,
    load_settings,
    missing_mods_for_save,
    rename_save_slot,
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


def _dialog_accepted():
    return QDialog.DialogCode.Accepted if QT_MAJOR == 6 else QDialog.Accepted


def _run_dialog(dialog: QDialog) -> int:
    return dialog.exec() if QT_MAJOR == 6 else dialog.exec_()


def _monospace_font(point_size: int = 11) -> QFont:
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
    if item is None or not INVENTORY_ICON_SHEET.exists():
        return pixmap
    sheet = QPixmap(str(INVENTORY_ICON_SHEET))
    rect = ITEM_ICON_RECTS.get(item.slot, ITEM_ICON_RECTS["fallback"])
    icon = sheet.copy(*rect)
    return icon.scaled(size, size)


class ItemSlotWidget(QFrame):
    def __init__(self, owner, area: str, index: int = -1, equipment_slot: str = ""):
        super().__init__(owner)
        self.owner = owner
        self.area = area
        self.index = index
        self.equipment_slot = equipment_slot
        self.item_id = ""
        self.drag_start = None
        self.setAcceptDrops(True)
        self.setMinimumSize(88, 88)
        self.setMaximumSize(118, 100)
        self.setFrameShape(QFrame.Shape.StyledPanel if QT_MAJOR == 6 else QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        self.icon = QLabel()
        self.icon.setAlignment(_align_center())
        self.icon.setFixedSize(42, 42)
        self.label = QLabel("")
        self.label.setAlignment(_align_center())
        self.label.setWordWrap(True)
        self.label.setFont(_pixel_font(9, family=PIXEL_BODY_FONT))
        layout.addWidget(self.icon, alignment=_align_center())
        layout.addWidget(self.label)
        self.refresh(None, False)

    def refresh(self, item: Item | None, selected: bool = False) -> None:
        self.item_id = item.id if item else ""
        self.icon.setPixmap(item_icon_pixmap(item))
        if item:
            self.label.setText(item.name)
            self.setToolTip(item_tooltip(item))
            top, bottom = item_colors(item)
            fg = readable_text_for_backgrounds(top, bottom)
            border = "#ffd166" if selected else top
            self.setStyleSheet(
                "QFrame {"
                f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {top},stop:1 {bottom});"
                f"border: 2px solid {border};"
                "}"
                f"QLabel {{ background: transparent; color: {fg}; }}"
            )
        else:
            label = self.equipment_slot if self.equipment_slot else f"Slot {self.index + 1}"
            self.label.setText(label)
            self.setToolTip("Empty slot")
            border = "#ffd166" if selected else "#3b3127"
            self.setStyleSheet(
                "QFrame { background: #17130f; border: 1px solid "
                f"{border}; }}"
                "QLabel { background: transparent; color: #8b8174; }"
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == _left_button():
            self.drag_start = event.pos()
            self.owner.slot_clicked(self)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & _left_button()):
            return
        if not self.item_id and self.area != "equipment":
            return
        mime = QMimeData()
        payload = f"{self.area}|{self.index}|{self.item_id}|{self.equipment_slot}"
        mime.setText(payload)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.icon.pixmap() or QPixmap())
        drag.exec(_move_action())

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if self.owner.handle_slot_drop(event.mimeData().text(), self):
            event.acceptProposedAction()


class AspyriaWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._register_fonts()
        self.settings = load_settings()
        reload_content(self.settings.enabled_mods, self.settings.mod_choices)
        self.t = Translator(self.settings.language, self.settings.enabled_mods).t
        self.data: SaveData | None = None
        self.current_slot_id = ""
        self.current_slot_name = ""
        self.pending_loot: Item | None = None
        self.last_scout_lines: list[str] = []
        self.selected_inventory_ids: set[str] = set()
        self.selected_equipment_slot = ""
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
        self.setFont(_pixel_font(12, family=PIXEL_BODY_FONT))
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
                font-size: 19px;
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
        inventory_box, self.inventory_slot_grid = self._make_inventory_slot_grid()
        layout.addWidget(inventory_box, 1, 0, 1, 4)
        self.equip_button = QPushButton(self.t("game.equip"))
        self.unequip_button = QPushButton("Take Off")
        self.sell_button = QPushButton(self.t("game.sell"))
        self.drop_button = QPushButton(self.t("game.drop"))
        self.equip_button.clicked.connect(self._button_action(self.equip_selected))
        self.unequip_button.clicked.connect(self._button_action(self.unequip_selected))
        self.sell_button.clicked.connect(self._button_action(self.sell_selected))
        self.drop_button.clicked.connect(self._button_action(self.drop_selected))
        layout.addWidget(self.equip_button, 2, 0)
        layout.addWidget(self.unequip_button, 2, 1)
        layout.addWidget(self.sell_button, 2, 2)
        layout.addWidget(self.drop_button, 2, 3)
        self.tabs.addTab(tab, self.t("game.inventory"))

    def _build_shop_tab(self) -> None:
        tab = QWidget()
        layout = QGridLayout(tab)
        self.shop_status = QLabel()
        self.shop_status.setWordWrap(True)
        layout.addWidget(self.shop_status, 0, 0, 1, 5)
        buttons = [
            (self.t("game.buy_random_gear"), self.buy_random_gear),
            (self.t("game.sell"), self.sell_selected),
            (self.t("game.improve"), self.repair_selected),
            (self.t("game.fuse"), self.fuse_selected),
        ]
        for index, (label, handler) in enumerate(buttons):
            button = QPushButton(label)
            button.clicked.connect(handler)
            layout.addWidget(button, 1, index)
        medkit_row = QHBoxLayout()
        for size, label in (("small", "Small Medkit"), ("medium", "Medium Medkit"), ("large", "Large Medkit")):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, selected=size: self.buy_medkit(selected))
            medkit_row.addWidget(button)
        layout.addLayout(medkit_row, 2, 0, 1, 5)
        shop_inventory_box, self.shop_inventory_slot_grid = self._make_inventory_slot_grid("shop_inventory")
        layout.addWidget(shop_inventory_box, 3, 0, 1, 5)
        self.tabs.addTab(tab, self.t("game.shop"))

    def _make_inventory_slot_grid(self, area: str = "inventory") -> tuple[QGroupBox, QGridLayout]:
        box = QGroupBox("Inventory")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(230)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(8)
        scroll.setWidget(container)
        layout = QVBoxLayout(box)
        layout.addWidget(scroll)
        if area == "inventory":
            self.inventory_slots = []
        else:
            self.shop_inventory_slots = []
        return box, grid

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
            self.continue_last_save(load_only=True)
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
        self.start_new_run()
        self.show_game()

    def start_new_run(self) -> None:
        if self.data is None:
            self.data = SaveData()
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
        if not self.current_slot_id:
            self.current_slot_id = create_save_slot("New Save", self.data)
            self.current_slot_name = "New Save"
        self.flush_play_time()
        save_save_slot(self.current_slot_id, self.current_slot_name or self.current_slot_id, self.data)
        self.settings.last_slot = self.current_slot_id
        save_settings(self.settings)

    def create_slot_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, self.t("slot.create"), self.t("slot.name"))
        if not ok:
            return
        slot_id = create_save_slot(name or "New Save", SaveData(enabled_mods=list(self.settings.enabled_mods), required_mods=list(self.settings.enabled_mods)))
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
        if result.run_failure and self.data.run and not self.data.run.active:
            summary = self.run_loss_summary(self.data.run)
            self.show_run_loss_screen(summary)
            self.data.run = None
            self.pending_loot = None
            self.save_current_slot()
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

    def unequip_selected(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            self.warn(self.t("game.no_active_run"))
            return
        slot = self.selected_equipment_slot
        if not slot:
            self.warn("Select an equipped item first.")
            return
        ok, message = unequip_item(self.data.meta, run, slot)
        self.log(message)
        self.sound.play("loot" if ok else "error")
        if not ok:
            self.warn(message)
            return
        self.selected_equipment_slot = ""
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
        self.data.meta.gold += gold
        self.data.run = None
        self.pending_loot = None
        self.log(f"Retired run. The run pays out {gold} gold.")
        self.save_current_slot()
        self.refresh_all()
        self.show_menu()

    def buy_selected_upgrade(self) -> None:
        if self.data is None:
            self.data = SaveData()
        stat = self.selected_upgrade_stat()
        if not stat:
            self.warn("Select a stat first.")
            return
        ok, message = buy_upgrade(self.data.meta, stat)
        self.log(message)
        self.sound.play("coin" if ok else "error")
        self.save_current_slot()
        self.refresh_all()

    def refund_selected_upgrade(self) -> None:
        if self.data is None:
            self.data = SaveData()
        stat = self.selected_upgrade_stat()
        if not stat:
            self.warn("Select a stat first.")
            return
        ok, message = refund_upgrade(self.data.meta, stat)
        self.log(message)
        self.sound.play("coin" if ok else "error")
        self.save_current_slot()
        self.refresh_all()

    def buy_inventory_slot(self) -> None:
        if self.data is None:
            self.data = SaveData()
        ok, message = buy_meta_inventory_slot(self.data.meta)
        self.log(message)
        self.sound.play("coin" if ok else "error")
        self.save_current_slot()
        self.refresh_all()

    def refund_inventory_slot(self) -> None:
        if self.data is None:
            self.data = SaveData()
        run = self.data.run
        if run and len(run.inventory) > self.data.meta.inventory_capacity() - 1:
            self.warn("Inventory is too full to refund a slot right now.")
            return
        ok, message = refund_meta_inventory_slot(self.data.meta)
        self.log(message)
        self.sound.play("coin" if ok else "error")
        self.save_current_slot()
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

    def slot_clicked(self, slot: ItemSlotWidget) -> None:
        modifiers = QApplication.keyboardModifiers()
        multi = bool(modifiers & _control_modifier())
        if slot.area == "equipment":
            self.selected_equipment_slot = slot.equipment_slot
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
        elif not multi:
            self.selected_inventory_ids.clear()
            self.selected_equipment_slot = ""
        self.refresh_inventory_tables()

    def handle_slot_drop(self, payload: str, target: ItemSlotWidget) -> bool:
        run = self.data.run if self.data else None
        if run is None:
            return False
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
        for button in (
            self.save_button,
            self.retire_button,
            self.fight_button,
            self.scout_button,
            self.equip_button,
            self.unequip_button,
            self.sell_button,
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
            self.run_summary.setText(self.t("game.no_active_run"))
            self.xp_status.setText("")
            self.xp_bar.setValue(0)
            self.xp_bar.parentWidget().setStyleSheet("")
            self.next_threat.setText("")
            return
        location = LOCATIONS[run.location_index]
        stats = effective_stats(self.data.meta, run)
        self.run_summary.setText(
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
        self.xp_status.setText(
            f"Level {run.level} | XP {run.xp}/{xp_needed} | {xp_needed - run.xp} XP to next level | "
            f"{reward_text}{pending_text}"
        )
        self.xp_bar.setMaximum(xp_needed)
        self.xp_bar.setValue(min(run.xp, xp_needed))
        milestone_style = "QGroupBox { border: 2px solid #c4952d; }" if next_level % 5 == 0 else ""
        self.xp_bar.parentWidget().setStyleSheet(milestone_style)
        if self.last_scout_lines:
            self.next_threat.setText("\n".join(self.last_scout_lines))
        else:
            self.next_threat.setText(
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
        for grid in (self.inventory_slot_grid, self.shop_inventory_slot_grid):
            while grid.count():
                item = grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        run = self.data.run if self.data else None
        if run is None:
            for widget in self.equipment_slots.values():
                widget.refresh(None, False)
            return
        for slot, widget in self.equipment_slots.items():
            item = run.equipment.get(slot)
            widget.refresh(item, self.selected_equipment_slot == slot)
        capacity = self.data.meta.inventory_capacity()
        self.selected_inventory_ids = {
            item_id for item_id in self.selected_inventory_ids if any(item.id == item_id for item in run.inventory)
        }
        for area, grid in (("inventory", self.inventory_slot_grid), ("shop_inventory", self.shop_inventory_slot_grid)):
            for index in range(capacity):
                widget = ItemSlotWidget(self, area, index)
                item = run.inventory[index] if index < len(run.inventory) else None
                widget.refresh(item, bool(item and item.id in self.selected_inventory_ids))
                grid.addWidget(widget, index // 6, index % 6)

    def refresh_shop_tab(self) -> None:
        run = self.data.run if self.data else None
        if run is None:
            self.shop_status.setText(self.t("game.no_active_run"))
            return
        stats = effective_stats(self.data.meta, run)
        self.shop_status.setText(
            f"Coins: {run.coins} | Random gear caravan failure: 25% | "
            f"Failure pity: +{run.random_gear_failures}% rarity/+{run.random_gear_failures}% quality | "
            f"Current offer price: {run.random_gear_offer_cost or 'rolls on next purchase'} | "
            f"Medkits: small {medkit_cost(run, 'small')}, medium {medkit_cost(run, 'medium')}, large {medkit_cost(run, 'large')} | "
            f"Luck: {stats['Luck%']:.1f}% | Enemy Scaling: {stats['Enemy Scaling%']:.1f}%"
        )

    def refresh_enhancements(self) -> None:
        if self.data is None:
            self.enhancement_summary.setText("Load or create a save slot first.")
            self.upgrade_table.setRowCount(0)
            return
        meta = self.data.meta
        locked = ", ".join(self.data.run.locked_stats) if self.data.run and self.data.run.locked_stats else "-"
        self.enhancement_summary.setText(
            f"Gold: {meta.gold} | Inventory capacity: {meta.inventory_capacity()} | Locked stats: {locked}"
        )
        self.upgrade_table.setRowCount(len(STAT_KEYS))
        for row, stat in enumerate(STAT_KEYS):
            level = meta.upgrades.get(stat, 0)
            values = [stat, str(level), "MAX" if level >= 50 else str(upgrade_cost(stat, level + 1)), f"+{level * (level + 1) // 2:g}"]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
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
                cell = QTableWidgetItem(value)
                if col == 0:
                    cell.setData(_user_role(), slot.slot_id)
                self.slots_table.setItem(row, col, cell)

    def refresh_stats_page(self) -> None:
        stats = self.data.stats if self.data else None
        if stats is None:
            self.stats_summary.setText("Load a save slot first.")
            self.record_summary.setText("")
            self.codex_table.setRowCount(0)
            return
        self.stats_summary.setText(
            f"{self.t('stats.enemies')}: {stats.enemies_defeated}    "
            f"{self.t('stats.bosses')}: {stats.bosses_defeated}    "
            f"{self.t('stats.play_time')}: {format_duration(stats.play_time_seconds)}"
        )
        self.record_summary.setText(
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
                self.codex_table.setItem(row, col, QTableWidgetItem(value))

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
                self.mods_table.setItem(row, col, QTableWidgetItem(value))
        warnings = "\n".join(CONTENT_WARNINGS)
        conflicts = "\n".join(f"{conflict.kind}:{conflict.content_id} -> {', '.join(conflict.mods)}" for conflict in CONTENT_CONFLICTS)
        self.conflict_label.setText(warnings or conflicts or self.t("mods.conflicts"))
        self.conflict_table.setRowCount(len(CONTENT_CONFLICTS))
        for row, conflict in enumerate(CONTENT_CONFLICTS):
            for col, value in enumerate([conflict.kind, conflict.content_id, ", ".join(conflict.mods)]):
                self.conflict_table.setItem(row, col, QTableWidgetItem(value))

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
                table.setItem(row, col, QTableWidgetItem(value))

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
