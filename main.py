from __future__ import annotations

import random
import sys
import time

from ascii_climb.combat import run_combat
from ascii_climb.content import LOCATIONS
from ascii_climb.loot import sell_value
from ascii_climb.meta import (
    buy_inventory_slot,
    buy_upgrade,
    effective_stats,
    final_gold_payout,
    refund_inventory_slot,
    refund_upgrade,
)
from ascii_climb.models import EQUIPMENT_SLOTS, RunState, STAT_KEYS
from ascii_climb.progression import (
    apply_enhancement,
    generate_stage_enhancements,
    generate_wishing_well_options,
)
from ascii_climb.save import load_game, save_game
from ascii_climb.shops import (
    add_item_to_inventory,
    buy_random_gear,
    craft_fusion,
    drop_item,
    equip_item,
    repair_item,
    sell_item,
)
from ascii_climb.ui import ask, choose_item, item_rows, panel, print_logs, show_character, show_equipment, show_meta


def rng_for_run(run: RunState) -> random.Random:
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


def start_new_run(data) -> None:
    seed = int(time.time())
    data.run = RunState(seed=seed, coins=25)
    data.run.current_hp = int(effective_stats(data.meta, data.run)["HP"])
    save_game(data)
    print(panel("New Run", ["You step into Rust Alley with empty pockets and bad ideas.", f"Seed: {seed}"]))


def meta_menu(data) -> None:
    while True:
        show_meta(data.meta)
        print("1. Buy stat upgrade")
        print("2. Refund stat upgrade")
        print("3. Buy inventory slot")
        print("4. Refund inventory slot")
        print("5. Back")
        choice = ask("> ", {"1", "2", "3", "4", "5"})
        if choice == "1":
            stat = choose_stat()
            ok, message = buy_upgrade(data.meta, stat)
            print(message)
        elif choice == "2":
            stat = choose_stat()
            ok, message = refund_upgrade(data.meta, stat)
            print(message)
        elif choice == "3":
            ok, message = buy_inventory_slot(data.meta)
            print(message)
        elif choice == "4":
            if data.run and len(data.run.inventory) > data.meta.inventory_capacity() - 1:
                print("Inventory is too full to refund a slot right now.")
            else:
                ok, message = refund_inventory_slot(data.meta)
                print(message)
        else:
            save_game(data)
            return
        save_game(data)


def choose_stat() -> str:
    for index, stat in enumerate(STAT_KEYS, 1):
        print(f"{index}. {stat}")
    answer = ask("Stat number: ")
    if answer.isdigit() and 1 <= int(answer) <= len(STAT_KEYS):
        return STAT_KEYS[int(answer) - 1]
    print("Defaulting to ATK.")
    return "ATK"


def handle_loot(data, loot) -> None:
    run = data.run
    if loot is None or run is None:
        return
    print(panel("Loot", [loot.label(), loot.stat_line(), f"Sell value: {sell_value(loot)} coins"]))
    while True:
        print("1. Equip")
        print("2. Store")
        print("3. Sell immediately")
        print("4. Ignore")
        choice = ask("> ", {"1", "2", "3", "4"})
        if choice == "1":
            print(equip_item(run, loot))
            break
        if choice == "2":
            ok, message = add_item_to_inventory(data.meta, run, loot)
            print(message)
            if ok:
                break
            inventory_pressure_menu(data, loot)
            break
        if choice == "3":
            run.coins += sell_value(loot)
            print(f"Sold {loot.name} for {sell_value(loot)} coins.")
            break
        if choice == "4":
            print(f"Left {loot.name} behind.")
            break
    save_game(data)


def inventory_pressure_menu(data, incoming) -> None:
    run = data.run
    if run is None:
        return
    while True:
        print(panel("Inventory Full", ["Make room, equip the drop, or walk away."]))
        print("1. Sell an inventory item")
        print("2. Drop an inventory item")
        print("3. Equip incoming item")
        print("4. Ignore incoming item")
        choice = ask("> ", {"1", "2", "3", "4"})
        if choice == "1":
            item = choose_item(run.inventory)
            if item:
                print(sell_item(run, item))
                ok, message = add_item_to_inventory(data.meta, run, incoming)
                print(message)
                if ok:
                    return
        elif choice == "2":
            item = choose_item(run.inventory)
            if item:
                print(drop_item(run, item))
                ok, message = add_item_to_inventory(data.meta, run, incoming)
                print(message)
                if ok:
                    return
        elif choice == "3":
            print(equip_item(run, incoming))
            return
        else:
            print(f"Left {incoming.name} behind.")
            return


def fight_menu(data) -> None:
    run = data.run
    if run is None:
        print("No active run.")
        return
    print("Choose stance: 1 steady, 2 guarded, 3 reckless")
    choice = ask("> ", {"1", "2", "3"})
    stance = {"1": "steady", "2": "guarded", "3": "reckless"}[choice]
    combat_rng = rng_for_run(run)
    result = run_combat(combat_rng, data.meta, run, stance)
    print_logs(result.logs)
    if result.victory and not result.enemy.boss and run.active:
        enhancement_menu(data, generate_stage_enhancements(rng_for_run(run), run), "Stage Enhancement")
    if result.victory and run.active and rng_for_run(run).random() < 0.2:
        print(panel("Wishing Well", ["You found a wishing well. Ask carefully."]))
        enhancement_menu(data, generate_wishing_well_options(rng_for_run(run), run), "Wishing Well")
    if result.loot:
        handle_loot(data, result.loot)
    if not run.active:
        data.run = None
    save_game(data)


def enhancement_menu(data, options, title: str) -> None:
    run = data.run
    if run is None or not options:
        return
    rows = [f"{index}. {option.title}: {option.describe()}" for index, option in enumerate(options, 1)]
    rows.append(f"{len(options) + 1}. Skip")
    print(panel(title, rows))
    valid = {str(index) for index in range(1, len(options) + 2)}
    choice = ask("> ", valid)
    if int(choice) == len(options) + 1:
        print("Skipped.")
        return
    print(apply_enhancement(run, options[int(choice) - 1]))
    run.current_hp = min(int(effective_stats(data.meta, run)["HP"]), run.current_hp)
    save_game(data)


def inventory_menu(data) -> None:
    run = data.run
    if run is None:
        return
    while True:
        show_equipment(run)
        print(panel("Inventory", item_rows(run.inventory)))
        print("1. Equip item")
        print("2. Sell item")
        print("3. Drop item")
        print("4. Back")
        choice = ask("> ", {"1", "2", "3", "4"})
        if choice == "1":
            item = choose_item(run.inventory)
            if item:
                print(equip_item(run, item))
        elif choice == "2":
            item = choose_item(run.inventory)
            if item:
                print(sell_item(run, item))
        elif choice == "3":
            item = choose_item(run.inventory)
            if item:
                print(drop_item(run, item))
        else:
            save_game(data)
            return
        save_game(data)


def shop_menu(data) -> None:
    run = data.run
    if run is None:
        return
    while True:
        stats = effective_stats(data.meta, run)
        print(panel("Shopkeeper", [f"Coins: {run.coins}", "The shop smells like dust and math."]))
        print("1. Buy random gear")
        print("2. Sell item")
        print("3. Crafting table")
        print("4. Scout next fight")
        print("5. Back")
        choice = ask("> ", {"1", "2", "3", "4", "5"})
        if choice == "1":
            ok, message = buy_random_gear(
                rng_for_run(run), data.meta, run, stats["Luck%"], stats["Enemy Scaling%"]
            )
            print(message)
        elif choice == "2":
            item = choose_item(run.inventory)
            if item:
                print(sell_item(run, item))
        elif choice == "3":
            crafting_menu(data)
        elif choice == "4":
            cost = 10 + run.loop_tier * 6
            if run.coins < cost:
                print(f"Need {cost} coins.")
            else:
                run.coins -= cost
                location = LOCATIONS[run.location_index]
                next_name = location.boss_name if run.fights_in_location >= location.fights_to_boss else ", ".join(location.enemy_names)
                print(panel("Scouting", [f"Possible next threat: {next_name}"]))
        else:
            save_game(data)
            return
        save_game(data)


def choose_three_inventory_items(run: RunState):
    if len(run.inventory) < 3:
        print("Fusion needs at least three inventory items.")
        return []
    print(panel("Inventory", item_rows(run.inventory)))
    raw = input("Choose three item numbers, separated by spaces: ").strip().replace(",", " ")
    indexes = []
    for part in raw.split():
        if part.isdigit():
            indexes.append(int(part) - 1)
    if len(indexes) != 3 or len(set(indexes)) != 3:
        print("Choose exactly three different items.")
        return []
    if any(index < 0 or index >= len(run.inventory) for index in indexes):
        print("One of those items does not exist.")
        return []
    return [run.inventory[index] for index in indexes]


def crafting_menu(data) -> None:
    run = data.run
    if run is None:
        return
    while True:
        print(panel("Crafting Table", ["1. Improve one item's quality", "2. Fuse three inventory items", "3. Back"]))
        choice = ask("> ", {"1", "2", "3"})
        if choice == "1":
            item = choose_item(run.inventory + [item for item in run.equipment.values() if item])
            if item:
                ok, message = repair_item(run, item)
                print(message)
        elif choice == "2":
            stats = effective_stats(data.meta, run)
            items = choose_three_inventory_items(run)
            if items:
                ok, message, crafted = craft_fusion(
                    rng_for_run(run),
                    data.meta,
                    run,
                    items,
                    stats["Luck%"],
                    stats["Enemy Scaling%"],
                )
                print(message)
        else:
            save_game(data)
            return
        save_game(data)


def retire_run(data) -> None:
    run = data.run
    if run is None:
        return
    gold = final_gold_payout(data.meta, run)
    data.meta.gold += gold
    data.run = None
    save_game(data)
    print(panel("Retired", [f"The run pays out {gold} gold."]))


def run_menu(data) -> None:
    while data.run and data.run.active:
        show_character(data.meta, data.run)
        print("1. Fight")
        print("2. Inventory")
        print("3. Shop")
        print("4. Save and quit to main menu")
        print("5. Retire run for gold")
        choice = ask("> ", {"1", "2", "3", "4", "5"})
        if choice == "1":
            fight_menu(data)
        elif choice == "2":
            inventory_menu(data)
        elif choice == "3":
            shop_menu(data)
        elif choice == "4":
            save_game(data)
            return
        else:
            retire_run(data)
            return


def main() -> None:
    data = load_game()
    while True:
        print(panel("Aspyria", [f"Gold: {data.meta.gold}", f"Active run: {'yes' if data.run else 'no'}"]))
        print("1. Continue run")
        print("2. New run")
        print("3. Permanent upgrades / refunds")
        print("4. Quit")
        choice = ask("> ", {"1", "2", "3", "4"})
        if choice == "1":
            if data.run:
                run_menu(data)
            else:
                print("No active run.")
        elif choice == "2":
            start_new_run(data)
            run_menu(data)
        elif choice == "3":
            meta_menu(data)
        else:
            save_game(data)
            print("Saved. Bye.")
            return


if __name__ == "__main__":
    if "--console" in sys.argv:
        main()
    else:
        from ascii_climb.qt_app import launch

        raise SystemExit(launch())
