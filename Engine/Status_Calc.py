"""Calculate Status effects moves"""
import math
import random


def calculate_status(attacker, defender, move):
    """Calculate the effect parts of the moves"""
    if move['category'] != "Status":
        return

    for eff in move['effects']:
        eff_t = eff.get('effect_type', 0)
        target = eff.get('target', 0)
        stat = eff.get('stat', 0)
        stages = int(eff.get('stages', 0))
        status = eff.get('status', 0)
        # Stat boost and reducing
        if eff_t == 'stat_change':
            if target in ['self']:
                attacker.stat_stages[stat] += stages
                print(f"{attacker.name}'s {stat} changed by {stages} stages.")
                continue
            if target in ['target', 'all_adjacent_opponents']:
                defender.stat_stages[stat] += stages
                print(f"{defender.name}'s {stat} changed by {stages} stages.")
                continue
            print("Something went Wrong")
            continue
        # Status
        if eff_t == 'status_inducing':
            if target == 'target':
                if status != 'sleep':
                    if not defender.status:
                        defender.status = status
                        print(f"{defender.name}'s was afflicted by {status}")
                        continue
                    print('But it failed.')
                    continue
                if defender.status == 'sleep':
                    print('But it failed.')
                    continue
                defender.status = status
                defender.sleep_counter = random.randint(1, 4)
                print(f"{defender.name} is fast asleep")
                continue
            print('Something went wrong')


def sec_stat_change(move, attacker, defender):
    """Calculate the secondary effects, like 10% of burning, 30% of incrising attacking, etc."""
    effects = move['effects']
    for e in effects:
        chance = e.get('chance', 100)
        roll = random.randint(1, 100)
        if roll <= chance:
            target = e.get('target', 0)
            status = e.get('status', 0)
            stat = e.get('stat', 0)
            stages = e.get('stages', 0)
            if target == 'target':
                if status:
                    if status != 'sleep':
                        if not defender.status:
                            defender.status = status
                            print(f"{defender.name}'s was afflicted by {status}")
                            return
                    if status == 'sleep':
                        defender.status = status
                        print(f"{defender.name} is fast asleep")
                        return
            if target == 'self':
                attacker.stat_stages[stat] += stages
                print(f"{attacker.name}'s {stat} changed by {stages} stages.")


def after_turn_status(pok):
    """Calculate damage after turn like burn, poison, curse*, leech seed*"""
    if pok.status:
        s = pok.status
        if s == 'burn' or (s == 'poison' and not pok.badly_poison):
            dmg = math.floor(pok.max_hp / 8)
            pok.current_hp -= dmg
            print(f'{pok.name} suffered {dmg} HP from {s}')
            if pok.current_hp <= 0:
                print(f'{pok.name} has fainted.')
                pok.fainted = True
            else:
                print(f'{pok.name} has {pok.current_hp} left.')


def paralysis():
    """Check if Pokemon is fully paralysed"""
    if random.randint(1, 4) <= 1:
        return True
    return False
