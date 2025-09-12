"""Calculate Status effects moves"""
import math
import random


def apply_status(status, pok, badly_p, sec=False):
    """Apply status effects"""
    if status != 'sleep':
        if not pok.status:
            pok.status = status
            print(f"{pok.name}'s was afflicted by {status}")
            if badly_p:
                pok.badly_poison = 1
            return
        if not sec:
            print('But it failed.')
        return
    if pok.status == 'sleep':
        if not sec:
            print('But it failed.')
        return
    pok.status = status
    pok.sleep_counter = random.randint(1, 4)
    print(f"{pok.name} is fast asleep")
    return


def drain_effect(attacker, dmg):
    """Calculates how much should it drain"""
    drain_hp = math.floor(dmg / 2)
    if drain_hp <= 0:
        drain_hp = 1
    if attacker.current_hp + drain_hp > attacker.max_hp:
        drain_hp = attacker.max_hp - attacker.current_hp
    if drain_hp <= 0:
        return
    attacker.current_hp += drain_hp
    print(f"{attacker.name} drained {drain_hp} HP")


def calculate_effects(attacker, defender, move):
    """Calculate the effect parts of the moves"""
    if move['category'] != "Status":
        return

    for eff in move['effects']:
        eff_t = eff.get('effect_type', 0)
        target = eff.get('target', 0)
        stat = eff.get('stat', 0)
        stages = int(eff.get('stages', 0))
        status = eff.get('status', 0)
        badly_p = eff.get('badly_posion', 0)
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
            raise ValueError("Target isn't defined in calculate effects")
        # Status
        if eff_t == 'status_inducing':
            if target == 'target':
                apply_status(status, defender, badly_p)
            raise ValueError("Shouldn't have self status change")


def sec_effects(move, attacker, defender, dmg):
    """Calculate the secondary effects, like 10% of burning,
    30% of increasing attacking, Drain moves etc."""
    effects = move['effects']
    for e in effects:
        chance = e.get('chance', 100)
        roll = random.randint(1, 100) if chance < 100 else 0
        if roll <= chance:
            target = e.get('target', 0)
            status = e.get('status', 0)
            stat = e.get('stat', 0)
            stages = e.get('stages', 0)
            drain = e.get('drain', 0)
            badly_p = e.get('badly_posion', 0)
            if target == 'target':
                if status:
                    apply_status(status, defender, badly_p, sec=True)
                    continue
            if target == 'self':
                if stat:
                    attacker.stat_stages[stat] += stages
                    print(f"{attacker.name}'s {stat} changed by {stages} stages.")
                    continue
                if drain:
                    drain_effect(attacker, dmg)


def after_turn_status(pok):
    """Calculate damage after turn like burn, poison, curse*, leech seed*"""
    if pok.status:
        s = pok.status
        if s in ('burn', 'poison'):
            if pok.badly_poison >= 1:
                dmg = math.floor(pok.max_hp * pok.badly_poison * (1 / 16))
            else:
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


def freeze():
    """Check if it thaws"""
    if random.randint(1, 5) <= 1:
        return False
    return True
