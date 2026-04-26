# Aspyria

A small desktop RPG inspired by old browser-game progression: fight cursed necromancers, get items, build weird stat stacks, complete gear sets, die badly, spend permanent gold, and come back stronger.

## Run

Desktop version:

```bash
pip install -r requirements.txt
python -B main.py
```

Console version:

```bash
python -B main.py --console
```

## Content and mods

Base game content lives in `content/en/core.json`. Mods go into `mods/<mod_id>/` with a `mod.json` manifest and one or more JSON content files. English text is the default; optional translations can live in `translations/` or `mods/<mod_id>/translations/`.

JSON content can define stats, item name pools, sets, enemies, bosses, locations, and encounters. Encounter effects currently support messages, coins, gold, item rewards, stat buffs/debuffs, choice lists, shop/scout/crafting hooks, and combat hooks.

See `MODDING.md` for examples.

## License and credits

Aspyria is source-available under the custom terms in `LICENSE.md`. The short human-readable version is in `COMMERCIAL_USE.md`.

Splash art: Grok Imagine.

Music: Suno AI.

Sound effects: Kenney Interface Sounds by Kenney, CC0 1.0 Universal. Details are in `ASSETS.md`.

Fonts: Tiny5 by Stefan Schmidt and Pixelify Sans by Stefie Justprince. Details are in `ASSETS.md`.

## What is in v1

- Endless location loop: Highcrown Fields -> Chapel of Broken Bells -> Old Court Road -> Ashen Foundries -> Veyr's Black Citadel -> harder Highcrown Fields.
- Gear-defined builds instead of classes.
- Attack/flee combat flow with automated turn logs.
- Level-up stat choices and milestone/boss perks.
- Location iLvl ranges with gear advantage bonuses.
- Named relic effects for level rewards, fleeing, boss perks, and necromancer loot.
- Full item sets with weak partial bonuses and huge complete-set bonuses.
- Permanent menu upgrades with half-cost refunds.
- Limited inventory slots, also bought and refunded from the menu.
- Coins for shops during a run, gold for permanent power after a run.
- Post-fight enhancement choices after lesser mobs and story dialogue for enemies and bosses.
- Wishing well events with strong buffs and ugly tradeoffs.
- Crafting table for improving quality or fusing three lesser items into one better random item.
- Four-step defeat curse: lose best gear, lose coins, get stat scars, then die and cash out.

## Tests

```bash
python -m unittest
```
