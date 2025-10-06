"""Calculate Status effects moves"""
import random
import numpy as np
from Models.idx_const import Pok, Move, Sec, OFFSET_SEC
from Models.helper import Status, MoveCategory, Target, StatusIdToName
from DataBase.PkDB import PokemonName


def apply_status(move, pok, sec=False):
    """Apply status effects"""
    if sec:
        offset = OFFSET_SEC
        if move[offset + Sec.STATUS] != Status.SLEEP:
            if pok[Pok.STATUS] == 0:
                pok[Pok.STATUS] = move[offset + Sec.STATUS]
                print(
                    f"{PokemonName(pok[Pok.ID]).name.capitalize()}'s "
                    f"was afflicted by {StatusIdToName[move[offset + Sec.STATUS]].lower()}"
                )
                if move[offset + Sec.STATUS] == Status.TOXIC:
                    pok[Pok.BADLY_POISON] = 1
                return
            return
        if pok[Pok.STATUS] == Status.SLEEP:
            return
        pok[Pok.STATUS] = move[offset + Sec.STATUS]
        pok[Pok.SLEEP_COUNTER] = np.random.randint(1,5)  # End not inclusive thats why to 5
        print(f"{PokemonName(pok[Pok.ID]).name.capitalize()} is fast asleep")
        return
    if move[Move.STATUS] != Status.SLEEP:
        if pok[Pok.STATUS] == 0:
            pok[Pok.STATUS] = move[Move.STATUS]
            print(
                f"{PokemonName(pok[Pok.ID]).name.capitalize()}'s "
                f"was afflicted by {StatusIdToName[move[offset + Sec.STATUS]].lower()}"
            )
            if move[Move.STATUS] == Status.TOXIC:
                pok[Pok.BADLY_POISON] = 1
            return
        print('But it failed.')
        return
    if pok[Pok.STATUS] == Status.SLEEP:
        print('But it failed.')
        return
    pok[Pok.STATUS] = move[Move.STATUS]
    pok[Pok.SLEEP_COUNTER] = np.random.randint(1,5)  # End not inclusive thats why to 5
    print(f"{PokemonName(pok[Pok.ID]).name.capitalize()} is fast asleep")
    return


def drain_effect(attacker, dmg, drain_amount):
    """Calculates how much should it drain"""
    drain_hp = np.floor(dmg * drain_amount)
    if drain_hp <= 0:
        drain_hp = 1
    if attacker[Pok.CURRENT_HP] + drain_hp > attacker[Pok.MAX_HP]:
        drain_hp = attacker[Pok.MAX_HP] - attacker[Pok.CURRENT_HP]
    if drain_hp <= 0:
        return
    attacker[Pok.CURRENT_HP] += drain_hp
    print(f"{PokemonName(attacker[Pok.ID]).name.capitalize()} drained {drain_hp} HP")


def calculate_effects(attacker, defender, move):
    """Calculate the effect parts of the moves"""
    if move[Move.CATEGORY] != MoveCategory.STATUS:
        return

    # Stat boost and reducing
    if any(move[Move.BOOST_ATK: Move.BOOST_EV + 1]):
        if move[Move.TARGET] in (
            Target.ADJACENT_ALLY,
            Target.ADJACENT_ALLY_OR_SELF,
            Target.ALLIES,
            Target.ALLY_SIDE,
            Target.SELF
        ):
            if move[Move.BOOST_ATK]:
                attacker[Pok.ATTACK_STAT_STAGE] += move[Move.BOOST_ATK]
                print(
                    f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                    f"attack changed by {int(move[Move.BOOST_ATK])} stages."
                )
            if move[Move.BOOST_DEF]:
                attacker[Pok.DEFENSE_STAT_STAGE] += move[Move.BOOST_DEF]
                print(
                    f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                    f"defense changed by {int(move[Move.BOOST_DEF])} stages."
                )
            if move[Move.BOOST_SPATK]:
                attacker[Pok.SPECIAL_ATTACK_STAT_STAGE] += move[Move.BOOST_SPATK]
                print(
                    f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                    f"special attack changed by {int(move[Move.BOOST_SPATK])} stages."
                )
            if move[Move.BOOST_SPDEF]:
                attacker[Pok.SPECIAL_DEFENSE_STAT_STAGE] += move[Move.BOOST_SPDEF]
                print(
                    f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                    f"special defense changed by {int(move[Move.BOOST_SPDEF])} stages."
                )
            if move[Move.BOOST_SPEED]:
                attacker[Pok.SPEED_STAT_STAGE] += move[Move.BOOST_SPEED]
                print(
                    f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                    f"speed changed by {int(move[Move.BOOST_SPEED])} stages."
                )
            if move[Move.BOOST_ACC]:
                attacker[Pok.ACCURACY_STAT_STAGE] += move[Move.BOOST_ACC]
                print(
                    f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                    f"accuracy changed by {int(move[Move.BOOST_ACC])} stages."
                )
            if move[Move.BOOST_EV]:
                attacker[Pok.EVASION_STAT_STAGE] += move[Move.BOOST_EV]
                print(
                    f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                    f"evasion changed by {int(move[Move.BOOST_EV])} stages."
                )

        if move[Move.TARGET] in (
            Target.NORMAL,
            Target.ADJACENT_FOE,
            Target.ALL_ADJACENT_FOES,
            Target.ANY,
            Target.FOE_SIDE,
            Target.RANDOM_NORMAL,
            Target.SCRIPTED
        ):
            if move[Move.BOOST_ATK]:
                defender[Pok.ATTACK_STAT_STAGE] += move[Move.BOOST_ATK]
                print(
                    f"{PokemonName(defender[Pok.ID]).name.capitalize()}'s "
                    f"attack changed by {int(move[Move.BOOST_ATK])} stages."
                )
            if move[Move.BOOST_DEF]:
                defender[Pok.DEFENSE_STAT_STAGE] += move[Move.BOOST_DEF]
                print(
                    f"{PokemonName(defender[Pok.ID]).name.capitalize()}'s "
                    f"defense changed by {int(move[Move.BOOST_DEF])} stages."
                )
            if move[Move.BOOST_SPATK]:
                defender[Pok.SPECIAL_ATTACK_STAT_STAGE] += move[Move.BOOST_SPATK]
                print(
                    f"{PokemonName(defender[Pok.ID]).name.capitalize()}'s "
                    f"special attack changed by {int(move[Move.BOOST_SPATK])} stages."
                )
            if move[Move.BOOST_SPDEF]:
                defender[Pok.SPECIAL_DEFENSE_STAT_STAGE] += move[Move.BOOST_SPDEF]
                print(
                    f"{PokemonName(defender[Pok.ID]).name.capitalize()}'s "
                    f"special defense changed by {int(move[Move.BOOST_SPDEF])} stages."
                )
            if move[Move.BOOST_SPEED]:
                defender[Pok.SPEED_STAT_STAGE] += move[Move.BOOST_SPEED]
                print(
                    f"{PokemonName(defender[Pok.ID]).name.capitalize()}'s "
                    f"speed changed by {int(move[Move.BOOST_SPEED])} stages."
                )
            if move[Move.BOOST_ACC]:
                defender[Pok.ACCURACY_STAT_STAGE] += move[Move.BOOST_ACC]
                print(
                    f"{PokemonName(defender[Pok.ID]).name.capitalize()}'s "
                    f"accuracy changed by {int(move[Move.BOOST_ACC])} stages."
                )
            if move[Move.BOOST_EV]:
                defender[Pok.EVASION_STAT_STAGE] += move[Move.BOOST_EV]
                print(
                    f"{PokemonName(defender[Pok.ID]).name.capitalize()}'s "
                    f"evasion changed by {int(move[Move.BOOST_EV])} stages."
                )
    # Status
    if move[Move.STATUS] != 0:
        if move[Move.TARGET] in (
            Target.NORMAL,
            Target.ADJACENT_FOE,
            Target.ALL_ADJACENT_FOES,
            Target.ANY,
            Target.FOE_SIDE,
            Target.RANDOM_NORMAL,
            Target.SCRIPTED
        ):
            apply_status(move, defender)
        raise ValueError("Shouldn't have self status change")


def sec_effects(move, attacker, defender, dmg):
    """Calculate the secondary effects, like 10% of burning,
    30% of increasing attacking, Drain moves etc."""
    offset = OFFSET_SEC
    chance = move[offset + Sec.CHANCE]
    roll = random.randint(1, 100) if chance < 100 else 0
    if roll <= chance:
        if move[Move.TARGET] in (
            Target.NORMAL,
            Target.ADJACENT_FOE,
            Target.ALL_ADJACENT_FOES,
            Target.ANY,
            Target.FOE_SIDE,
            Target.RANDOM_NORMAL,
            Target.SCRIPTED
        ):
            a = move[offset + Sec.STATUS]
            if a != 0:
                apply_status(move, defender, sec=True)
        if move[Move.TARGET] in (
            Target.ADJACENT_ALLY,
            Target.ADJACENT_ALLY_OR_SELF,
            Target.ALLIES,
            Target.ALLY_SIDE,
            Target.SELF
        ):
            if any(move[offset + Sec.SEC_BOOST_ATK: offset + Sec.SEC_BOOST_EV + 1]):
                if move[offset + Sec.SEC_BOOST_ATK]:
                    attacker[Pok.ATTACK_STAT_STAGE] += move[offset + Sec.SEC_BOOST_ATK]
                    print(
                        f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                        f"attack changed by {int(move[offset + Sec.SEC_BOOST_ATK])} stages."
                    )
                if move[offset + Sec.SEC_BOOST_DEF]:
                    attacker[Pok.DEFENSE_STAT_STAGE] += move[offset + Sec.SEC_BOOST_DEF]
                    print(
                        f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                        f"defense changed by {int(move[offset + Sec.SEC_BOOST_DEF])} stages."
                    )
                if move[offset + Sec.SEC_BOOST_SPATK]:
                    attacker[Pok.SPECIAL_ATTACK_STAT_STAGE] += move[offset + Sec.SEC_BOOST_SPATK]
                    print(
                        f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                        f"special attack changed by {int(move[offset + Sec.SEC_BOOST_SPATK])} stages."
                    )
                if move[offset + Sec.SEC_BOOST_SPDEF]:
                    attacker[Pok.SPECIAL_DEFENSE_STAT_STAGE] += move[offset + Sec.SEC_BOOST_SPDEF]
                    print(
                        f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                        f"special defense changed by {int(move[offset + Sec.SEC_BOOST_SPDEF])} stages."
                    )
                if move[offset + Sec.SEC_BOOST_SPEED]:
                    attacker[Pok.SPEED_STAT_STAGE] += move[offset + Sec.SEC_BOOST_SPEED]
                    print(
                        f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                        f"speed changed by {int(move[offset + Sec.SEC_BOOST_SPEED])} stages."
                    )
                if move[offset + Sec.SEC_BOOST_ACC]:
                    attacker[Pok.ACCURACY_STAT_STAGE] += move[offset + Sec.SEC_BOOST_ACC]
                    print(
                        f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                        f"accuracy changed by {int(move[offset + Sec.SEC_BOOST_ACC])} stages."
                    )
                if move[offset + Sec.SEC_BOOST_EV]:
                    attacker[Pok.EVASION_STAT_STAGE] += move[offset + Sec.SEC_BOOST_EV]
                    print(
                        f"{PokemonName(attacker[Pok.ID]).name.capitalize()}'s "
                        f"evasion changed by {int(move[offset + Sec.SEC_BOOST_EV])} stages."
                    )
            if move[Move.DRAIN]:
                drain_effect(attacker, dmg, move[Move.DRAIN])


def after_turn_status(pok):
    """Calculate damage after turn like burn, poison, volatile status"""
    # TODO:
    if pok[Pok.STATUS]:
        if pok[Pok.STATUS] in (Status.BURN, Status.POISON):
            if pok[Pok.BADLY_POISON] >= 1:
                dmg = np.floor(pok[Pok.MAX_HP] * pok[Pok.BADLY_POISON] * (1 / 16))
                pok[Pok.BADLY_POISON] += 1
            else:
                dmg = np.floor(pok[Pok.MAX_HP] / 8)
            pok[Pok.CURRENT_HP] -= dmg
            print(f'{PokemonName(pok[Pok.ID]).name.capitalize()} suffered '
                  f'{dmg} HP from {StatusIdToName[pok[Pok.STATUS]].lower()}')
            if pok[Pok.CURRENT_HP] <= 0:
                print(f'{PokemonName(pok[Pok.ID]).name.capitalize()} has fainted.')
                pok[Pok.CURRENT_HP] = 0
            else:
                print(f'{PokemonName(pok[Pok.ID]).name.capitalize()} has '
                      f'{pok[Pok.CURRENT_HP]} left.')


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
