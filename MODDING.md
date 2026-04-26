# Modding Aspyria

Aspyria loads English base content from `content/en/core.json`. Custom mods live in `mods/<mod_id>/`.

## Folder shape

```text
mods/my_mod/
  mod.json
  content.json
  translations/
    ru.json
```

`mod.json`:

```json
{
  "id": "my_mod",
  "name": "My Mod",
  "author": "You",
  "version": "1.0",
  "description": "Adds a new enemy and a post-fight event."
}
```

## Add or replace enemies

Use the same id as a base enemy to override it. Use a new id to add something new.

```json
{
  "enemies": {
    "Copper Saint": {
      "name": "Copper Saint",
      "family": "Street Scraps",
      "base_hp": 90,
      "base_atk": 12,
      "xp": 35,
      "coins": 30,
      "abilities": ["rage"]
    }
  }
}
```

Bosses are enemies with `"boss": true`.

## Add locations

Locations are the route. If a mod defines `locations`, it replaces the current route while the mod is enabled.

```json
{
  "locations": [
    {
      "name": "Copper Yard",
      "min_ilevel": 1,
      "max_ilevel": 5,
      "difficulty": 1.1,
      "fights_to_boss": 3,
      "enemy_names": ["Copper Saint"],
      "boss_name": "Rust Alley Boss"
    }
  ]
}
```

## Add item naming and stat pools

```json
{
  "rarity_names": {
    "rare": ["Grand", "Neon", "Copper"]
  },
  "slot_names": {
    "weapon": ["Knife", "Hammer", "Saber"]
  },
  "slot_stat_pools": {
    "weapon": ["ATK", "CR%", "CD%"]
  }
}
```

## Add level rewards, perks, and relics

```json
{
  "level_rewards": {
    "copper_training": {
      "title": "Copper Training",
      "stat": "ATK",
      "amount": 3,
      "weight": 1
    }
  },
  "perks": {
    "copper_purse": {
      "title": "Copper Purse",
      "effect": "bonus_coins",
      "params": {"coins": 40}
    }
  },
  "relics": {
    "copper_lens": {
      "name": "Copper Lens",
      "effect_id": "level_reward_multiplier",
      "description": "Level-up stat choices are stronger.",
      "params": {"multiplier": 1.5}
    }
  }
}
```

## Add encounters

Encounters can trigger after fights. English text is required; translations are optional.

```json
{
  "encounters": {
    "copper_cache": {
      "title": "Copper Cache",
      "trigger": "post_fight",
      "chance": 0.15,
      "weight": 1,
      "effects": [
        {"type": "message", "text": "A warm cache clicks open."},
        {"type": "reward_coins", "amount": 20},
        {"type": "stat_buff", "stat": "Luck%", "amount": 4}
      ]
    }
  }
}
```

Supported effect types: `message`, `reward_coins`, `reward_gold`, `reward_item`, `stat_buff`, `stat_debuff`, `choice_list`, `shop`, `scout`, `crafting`, `combat`.

## Translation fallback

English is always the default. If Russian or another language does not include a key, the game shows English. If no English text exists, the raw id is shown.
