from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


STAT_KEYS = [
    "ATK",
    "CR%",
    "CD%",
    "HP",
    "Luck%",
    "Evasion%",
    "Multi-Attack Chance%",
    "Megacrit Chance%",
    "Megacrit Damage%",
    "XP Boost%",
    "Enemy Scaling%",
    "Coin Acquisition Boost%",
]

STAT_DESCRIPTIONS = {
    "ATK": "Increases the damage you deal with each attack.",
    "CR%": "Chance for a hit to become a critical hit.",
    "CD%": "Extra damage dealt by critical hits.",
    "HP": "Maximum health for the current run.",
    "Luck%": "Improves chances for higher item rarity and quality. Corrupted and top-quality rolls start at 1%, then gain +0.25 percentage points per Luck%.",
    "Evasion%": "Chance to dodge enemy attacks.",
    "Multi-Attack Chance%": "Chance to attack two or three times during your turn.",
    "Megacrit Chance%": "Chance for a critical hit to become a megacrit.",
    "Megacrit Damage%": "Extra damage dealt by megacrits.",
    "XP Boost%": "Increases XP gained from defeated enemies.",
    "Enemy Scaling%": "Raises enemy pressure, rewards, and possible item levels.",
    "Coin Acquisition Boost%": "Increases coins gained during a run.",
    "Damage Reduction%": "Reduces incoming damage before other penalties.",
    "Damage Taken%": "Increases incoming damage from curses and risky effects.",
    "Gold Payout%": "Increases gold paid out when a run ends.",
}

STAT_LABELS = {
    "ATK": "Attack",
    "CR%": "Critical Chance",
    "CD%": "Critical Damage",
    "HP": "HP",
    "Luck%": "Luck",
    "Evasion%": "Evasion",
    "Multi-Attack Chance%": "Multi-Attack",
    "Megacrit Chance%": "Megacrit Chance",
    "Megacrit Damage%": "Megacrit Damage",
    "XP Boost%": "XP Boost",
    "Enemy Scaling%": "Enemy Scaling",
    "Coin Acquisition Boost%": "Coin Acquisition",
    "Damage Reduction%": "Damage Reduction",
    "Damage Taken%": "Damage Taken",
    "Gold Payout%": "Gold Payout",
}


def stat_label(stat: str) -> str:
    return STAT_LABELS.get(stat, stat.replace("%", ""))


def format_stat_bonus(stat: str, amount: float) -> str:
    suffix = "" if stat in {"ATK", "HP"} else "%"
    return f"{stat_label(stat)}: +{amount:g}{suffix}"

EQUIPMENT_SLOTS = ["weapon", "armor", "charm", "boots", "ring", "relic"]
RARITIES = ["common", "uncommon", "rare", "mythical", "legendary", "corrupted"]
QUALITIES = ["trash", "worn", "used", "polished", "new", "special craft"]


def blank_stats(value: float = 0.0) -> Dict[str, float]:
    return {stat: value for stat in STAT_KEYS}


@dataclass
class Item:
    id: str
    name: str
    slot: str
    rarity: str
    quality: str
    ilevel: int
    stats: Dict[str, float]
    set_name: Optional[str] = None
    value: int = 0
    drawback: str = ""

    def label(self) -> str:
        set_part = f" [{self.set_name}]" if self.set_name else ""
        return f"{self.name}{set_part} | {self.rarity}/{self.quality} iLvl {self.ilevel}"

    def stat_line(self) -> str:
        parts = []
        for stat, amount in self.stats.items():
            if amount:
                suffix = "" if stat in {"ATK", "HP"} else "%"
                sign = "+" if amount > 0 else ""
                parts.append(f"{stat_label(stat)} {sign}{amount:g}{suffix}")
        if self.drawback:
            parts.append(f"Drawback: {self.drawback}")
        return ", ".join(parts) if parts else "No stats"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slot": self.slot,
            "rarity": self.rarity,
            "quality": self.quality,
            "ilevel": self.ilevel,
            "stats": self.stats,
            "set_name": self.set_name,
            "value": self.value,
            "drawback": self.drawback,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        return cls(
            id=data["id"],
            name=data["name"],
            slot=data["slot"],
            rarity=data["rarity"],
            quality=data["quality"],
            ilevel=int(data["ilevel"]),
            stats={key: float(value) for key, value in data["stats"].items()},
            set_name=data.get("set_name"),
            value=int(data.get("value", 0)),
            drawback=data.get("drawback", ""),
        )


@dataclass(frozen=True)
class SetDefinition:
    name: str
    required_slots: List[str]
    partial_stat: str
    partial_bonus: float
    full_bonuses: Dict[str, float]
    drawback: str = ""
    source_mod: str = "base"


@dataclass(frozen=True)
class EnemyTemplate:
    name: str
    family: str
    base_hp: int
    base_atk: int
    xp: int
    coins: int
    abilities: List[str]
    boss: bool = False
    corrupted: bool = False
    source_mod: str = "base"
    multi_attack_chance: float = 0.0
    evasion_chance: float = 0.0
    dialogue: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Location:
    name: str
    min_ilevel: int
    max_ilevel: int
    difficulty: float
    fights_to_boss: int
    enemy_names: List[str]
    boss_name: str
    source_mod: str = "base"
    story: Dict[str, str] = field(default_factory=dict)

    @property
    def ilevel_threshold(self) -> int:
        return self.min_ilevel


@dataclass
class MetaState:
    gold: int = 0
    upgrades: Dict[str, int] = field(default_factory=lambda: {stat: 0 for stat in STAT_KEYS})
    inventory_slots_purchased: int = 0

    def inventory_capacity(self) -> int:
        return 12 + self.inventory_slots_purchased

    def to_dict(self) -> dict:
        return {
            "gold": self.gold,
            "upgrades": self.upgrades,
            "inventory_slots_purchased": self.inventory_slots_purchased,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MetaState":
        upgrades = {stat: int(data.get("upgrades", {}).get(stat, 0)) for stat in STAT_KEYS}
        return cls(
            gold=int(data.get("gold", 0)),
            upgrades=upgrades,
            inventory_slots_purchased=int(data.get("inventory_slots_purchased", 0)),
        )


@dataclass
class RunState:
    active: bool = True
    seed: int = 0
    rng_counter: int = 0
    location_index: int = 0
    loop_tier: int = 1
    fights_in_location: int = 0
    defeats: int = 0
    coins: int = 0
    xp: int = 0
    level: int = 1
    current_hp: int = 100
    inventory: List[Item] = field(default_factory=list)
    equipment: Dict[str, Optional[Item]] = field(
        default_factory=lambda: {slot: None for slot in EQUIPMENT_SLOTS}
    )
    completed_bosses: int = 0
    best_item_value: int = 0
    strongest_enemy_power: int = 0
    corrupted_kills: int = 0
    run_buffs: Dict[str, float] = field(default_factory=dict)
    run_debuffs: Dict[str, float] = field(default_factory=dict)
    locked_stats: List[str] = field(default_factory=list)
    started_at: float = 0.0
    first_loop_clear_recorded: bool = False
    pending_level_rewards: List[dict] = field(default_factory=list)
    chosen_perks: List[str] = field(default_factory=list)
    favored_stat: str = ""
    relic_charges_used: Dict[str, int] = field(default_factory=dict)
    level_reward_multiplier: float = 1.0
    extra_level_options: int = 0
    loot_bonus_chance: float = 0.0
    post_fight_heal_bonus: float = 0.0
    random_gear_failures: int = 0
    active_fight: dict | None = None
    random_gear_offer: dict | None = None
    random_gear_offer_cost: int = 0
    timed_stat_modifiers: List[dict] = field(default_factory=list)
    medkits_bought: int = 0

    def equipped_items(self) -> List[Item]:
        return [item for item in self.equipment.values() if item is not None]

    def average_ilevel(self) -> float:
        equipped = self.equipped_items()
        if not equipped:
            return 0.0
        return sum(item.ilevel for item in equipped) / len(equipped)

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "seed": self.seed,
            "rng_counter": self.rng_counter,
            "location_index": self.location_index,
            "loop_tier": self.loop_tier,
            "fights_in_location": self.fights_in_location,
            "defeats": self.defeats,
            "coins": self.coins,
            "xp": self.xp,
            "level": self.level,
            "current_hp": self.current_hp,
            "inventory": [item.to_dict() for item in self.inventory],
            "equipment": {
                slot: item.to_dict() if item else None for slot, item in self.equipment.items()
            },
            "completed_bosses": self.completed_bosses,
            "best_item_value": self.best_item_value,
            "strongest_enemy_power": self.strongest_enemy_power,
            "corrupted_kills": self.corrupted_kills,
            "run_buffs": self.run_buffs,
            "run_debuffs": self.run_debuffs,
            "locked_stats": self.locked_stats,
            "started_at": self.started_at,
            "first_loop_clear_recorded": self.first_loop_clear_recorded,
            "pending_level_rewards": self.pending_level_rewards,
            "chosen_perks": self.chosen_perks,
            "favored_stat": self.favored_stat,
            "relic_charges_used": self.relic_charges_used,
            "level_reward_multiplier": self.level_reward_multiplier,
            "extra_level_options": self.extra_level_options,
            "loot_bonus_chance": self.loot_bonus_chance,
            "post_fight_heal_bonus": self.post_fight_heal_bonus,
            "random_gear_failures": self.random_gear_failures,
            "active_fight": self.active_fight,
            "random_gear_offer": self.random_gear_offer,
            "random_gear_offer_cost": self.random_gear_offer_cost,
            "timed_stat_modifiers": self.timed_stat_modifiers,
            "medkits_bought": self.medkits_bought,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunState":
        equipment = {}
        for slot in EQUIPMENT_SLOTS:
            item_data = data.get("equipment", {}).get(slot)
            equipment[slot] = Item.from_dict(item_data) if item_data else None
        return cls(
            active=bool(data.get("active", True)),
            seed=int(data.get("seed", 0)),
            rng_counter=int(data.get("rng_counter", 0)),
            location_index=int(data.get("location_index", 0)),
            loop_tier=int(data.get("loop_tier", 1)),
            fights_in_location=int(data.get("fights_in_location", 0)),
            defeats=int(data.get("defeats", 0)),
            coins=int(data.get("coins", 0)),
            xp=int(data.get("xp", 0)),
            level=int(data.get("level", 1)),
            current_hp=int(data.get("current_hp", 100)),
            inventory=[Item.from_dict(item) for item in data.get("inventory", [])],
            equipment=equipment,
            completed_bosses=int(data.get("completed_bosses", 0)),
            best_item_value=int(data.get("best_item_value", 0)),
            strongest_enemy_power=int(data.get("strongest_enemy_power", 0)),
            corrupted_kills=int(data.get("corrupted_kills", 0)),
            run_buffs={key: float(value) for key, value in data.get("run_buffs", {}).items()},
            run_debuffs={key: float(value) for key, value in data.get("run_debuffs", {}).items()},
            locked_stats=[str(stat) for stat in data.get("locked_stats", [])],
            started_at=float(data.get("started_at", 0.0)),
            first_loop_clear_recorded=bool(data.get("first_loop_clear_recorded", False)),
            pending_level_rewards=list(data.get("pending_level_rewards", [])),
            chosen_perks=list(data.get("chosen_perks", [])),
            favored_stat=data.get("favored_stat", ""),
            relic_charges_used={
                key: int(value) for key, value in data.get("relic_charges_used", {}).items()
            },
            level_reward_multiplier=float(data.get("level_reward_multiplier", 1.0)),
            extra_level_options=int(data.get("extra_level_options", 0)),
            loot_bonus_chance=float(data.get("loot_bonus_chance", 0.0)),
            post_fight_heal_bonus=float(data.get("post_fight_heal_bonus", 0.0)),
            random_gear_failures=int(data.get("random_gear_failures", 0)),
            active_fight=data.get("active_fight"),
            random_gear_offer=data.get("random_gear_offer"),
            random_gear_offer_cost=int(data.get("random_gear_offer_cost", 0)),
            timed_stat_modifiers=list(data.get("timed_stat_modifiers", [])),
            medkits_bought=int(data.get("medkits_bought", 0)),
        )


@dataclass
class ItemCollectionRecord:
    name: str
    count: int = 0
    highest_value: int = 0
    highest_rarity: str = ""
    slots: Dict[str, int] = field(default_factory=dict)
    rarities: Dict[str, int] = field(default_factory=dict)
    qualities: Dict[str, int] = field(default_factory=dict)
    sets: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "count": self.count,
            "highest_value": self.highest_value,
            "highest_rarity": self.highest_rarity,
            "slots": self.slots,
            "rarities": self.rarities,
            "qualities": self.qualities,
            "sets": self.sets,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ItemCollectionRecord":
        return cls(
            name=data.get("name", ""),
            count=int(data.get("count", 0)),
            highest_value=int(data.get("highest_value", 0)),
            highest_rarity=data.get("highest_rarity", ""),
            slots={key: int(value) for key, value in data.get("slots", {}).items()},
            rarities={key: int(value) for key, value in data.get("rarities", {}).items()},
            qualities={key: int(value) for key, value in data.get("qualities", {}).items()},
            sets={key: int(value) for key, value in data.get("sets", {}).items()},
        )


@dataclass
class RunRecord:
    duration_seconds: float
    seed: int
    loop_tier: int
    completed_bosses: int
    ended_at: float

    def to_dict(self) -> dict:
        return {
            "duration_seconds": self.duration_seconds,
            "seed": self.seed,
            "loop_tier": self.loop_tier,
            "completed_bosses": self.completed_bosses,
            "ended_at": self.ended_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunRecord":
        return cls(
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            seed=int(data.get("seed", 0)),
            loop_tier=int(data.get("loop_tier", 1)),
            completed_bosses=int(data.get("completed_bosses", 0)),
            ended_at=float(data.get("ended_at", 0.0)),
        )


@dataclass
class LifetimeStats:
    play_time_seconds: float = 0.0
    enemies_defeated: int = 0
    bosses_defeated: int = 0
    enemy_counts: Dict[str, int] = field(default_factory=dict)
    boss_counts: Dict[str, int] = field(default_factory=dict)
    item_codex: Dict[str, ItemCollectionRecord] = field(default_factory=dict)
    rarest_items: List[dict] = field(default_factory=list)
    quickest_failed_run: Optional[RunRecord] = None
    longest_failed_run: Optional[RunRecord] = None
    quickest_successful_run: Optional[RunRecord] = None
    longest_successful_run: Optional[RunRecord] = None

    def to_dict(self) -> dict:
        return {
            "play_time_seconds": self.play_time_seconds,
            "enemies_defeated": self.enemies_defeated,
            "bosses_defeated": self.bosses_defeated,
            "enemy_counts": self.enemy_counts,
            "boss_counts": self.boss_counts,
            "item_codex": {key: value.to_dict() for key, value in self.item_codex.items()},
            "rarest_items": self.rarest_items,
            "quickest_failed_run": self.quickest_failed_run.to_dict()
            if self.quickest_failed_run
            else None,
            "longest_failed_run": self.longest_failed_run.to_dict()
            if self.longest_failed_run
            else None,
            "quickest_successful_run": self.quickest_successful_run.to_dict()
            if self.quickest_successful_run
            else None,
            "longest_successful_run": self.longest_successful_run.to_dict()
            if self.longest_successful_run
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LifetimeStats":
        return cls(
            play_time_seconds=float(data.get("play_time_seconds", 0.0)),
            enemies_defeated=int(data.get("enemies_defeated", 0)),
            bosses_defeated=int(data.get("bosses_defeated", 0)),
            enemy_counts={key: int(value) for key, value in data.get("enemy_counts", {}).items()},
            boss_counts={key: int(value) for key, value in data.get("boss_counts", {}).items()},
            item_codex={
                key: ItemCollectionRecord.from_dict(value)
                for key, value in data.get("item_codex", {}).items()
            },
            rarest_items=list(data.get("rarest_items", [])),
            quickest_failed_run=RunRecord.from_dict(data["quickest_failed_run"])
            if data.get("quickest_failed_run")
            else None,
            longest_failed_run=RunRecord.from_dict(data["longest_failed_run"])
            if data.get("longest_failed_run")
            else None,
            quickest_successful_run=RunRecord.from_dict(data["quickest_successful_run"])
            if data.get("quickest_successful_run")
            else None,
            longest_successful_run=RunRecord.from_dict(data["longest_successful_run"])
            if data.get("longest_successful_run")
            else None,
        )


@dataclass
class SaveData:
    meta: MetaState = field(default_factory=MetaState)
    run: Optional[RunState] = None
    stats: LifetimeStats = field(default_factory=LifetimeStats)
    enabled_mods: List[str] = field(default_factory=list)
    required_mods: List[str] = field(default_factory=list)
    last_played_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "meta": self.meta.to_dict(),
            "run": self.run.to_dict() if self.run else None,
            "stats": self.stats.to_dict(),
            "enabled_mods": self.enabled_mods,
            "required_mods": self.required_mods,
            "last_played_at": self.last_played_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SaveData":
        return cls(
            meta=MetaState.from_dict(data.get("meta", {})),
            run=RunState.from_dict(data["run"]) if data.get("run") else None,
            stats=LifetimeStats.from_dict(data.get("stats", {})),
            enabled_mods=list(data.get("enabled_mods", [])),
            required_mods=list(data.get("required_mods", [])),
            last_played_at=float(data.get("last_played_at", 0.0)),
        )


@dataclass
class GameSettings:
    language: str = "en"
    sound_volume: int = 70
    resolution: str = "1280x720"
    fullscreen: bool = False
    enabled_mods: List[str] = field(default_factory=list)
    mod_choices: Dict[str, str] = field(default_factory=dict)
    last_slot: str = ""

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "sound_volume": self.sound_volume,
            "resolution": self.resolution,
            "fullscreen": self.fullscreen,
            "enabled_mods": self.enabled_mods,
            "mod_choices": self.mod_choices,
            "last_slot": self.last_slot,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameSettings":
        return cls(
            language=data.get("language", "en"),
            sound_volume=int(data.get("sound_volume", 70)),
            resolution=data.get("resolution", "1280x720"),
            fullscreen=bool(data.get("fullscreen", False)),
            enabled_mods=list(data.get("enabled_mods", [])),
            mod_choices=dict(data.get("mod_choices", {})),
            last_slot=data.get("last_slot", ""),
        )
