"""Calculate Status effects moves"""
import random
import numpy as np
from Models.idx_nparray import PokArray, MoveArray, MoveFlags, SecondaryArray
from Models.helper import Status, MoveCategory, Target, StatusIdToName
from DataBase.PkDB import PokemonName


def apply_status(move, pok, sec=False):
    """Apply status effects"""
    if sec:
        offset = len(MoveArray) + len(MoveFlags)
        if move[offset + SecondaryArray.STATUS] != Status.SLEEP:
            if pok[PokArray.STATUS] == 0:
                pok[PokArray.STATUS] = move[offset + SecondaryArray.STATUS]
                print(
                    f"{PokemonName(pok[PokArray.ID]).name.capitalize()}'s "
                    f"was afflicted by {StatusIdToName[move[offset + SecondaryArray.STATUS]].lower()}"
                )
                if move[offset + SecondaryArray.STATUS] == Status.TOXIC:
                    pok[PokArray.BADLY_POISON] = 1
                return
            return
        if pok[PokArray.STATUS] == Status.SLEEP:
            return
        pok[PokArray.STATUS] = move[offset + SecondaryArray.STATUS]
        pok[PokArray.SLEEP_COUNTER] = np.random.randint(1,5)  # End not inclusive thats why to 5
        print(f"{PokemonName(pok[PokArray.ID]).name.capitalize()} is fast asleep")
        return
    if move[MoveArray.STATUS] != Status.SLEEP:
        if pok[PokArray.STATUS] == 0:
            pok[PokArray.STATUS] = move[MoveArray.STATUS]
            print(
                f"{PokemonName(pok[PokArray.ID]).name.capitalize()}'s "
                f"was afflicted by {StatusIdToName[move[offset + SecondaryArray.STATUS]].lower()}"
            )
            if move[MoveArray.STATUS] == Status.TOXIC:
                pok[PokArray.BADLY_POISON] = 1
            return
        print('But it failed.')
        return
    if pok[PokArray.STATUS] == Status.SLEEP:
        print('But it failed.')
        return
    pok[PokArray.STATUS] = move[MoveArray.STATUS]
    pok[PokArray.SLEEP_COUNTER] = np.random.randint(1,5)  # End not inclusive thats why to 5
    print(f"{PokemonName(pok[PokArray.ID]).name.capitalize()} is fast asleep")
    return


def drain_effect(attacker, dmg, drain_amount):
    """Calculates how much should it drain"""
    drain_hp = np.floor(dmg * drain_amount)
    if drain_hp <= 0:
        drain_hp = 1
    if attacker[PokArray.CURRENT_HP] + drain_hp > attacker[PokArray.MAX_HP]:
        drain_hp = attacker[PokArray.MAX_HP] - attacker[PokArray.CURRENT_HP]
    if drain_hp <= 0:
        return
    attacker[PokArray.CURRENT_HP] += drain_hp
    print(f"{PokemonName(attacker[PokArray.ID]).name.capitalize()} drained {drain_hp} HP")


def calculate_effects(attacker, defender, move):
    """Calculate the effect parts of the moves"""
    if move[MoveArray.CATEGORY] != MoveCategory.STATUS:
        return

    # Stat boost and reducing
    if any(move[MoveArray.BOOST_ATK: MoveArray.BOOST_EV + 1]):
        if move[MoveArray.TARGET] in (
            Target.ADJACENT_ALLY,
            Target.ADJACENT_ALLY_OR_SELF,
            Target.ALLIES,
            Target.ALLY_SIDE,
            Target.SELF
        ):
            if move[MoveArray.BOOST_ATK]:
                attacker[PokArray.ATTACK_STAT_STAGE] += move[MoveArray.BOOST_ATK]
                print(
                    f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                    f"attack changed by {int(move[MoveArray.BOOST_ATK])} stages."
                )
            if move[MoveArray.BOOST_DEF]:
                attacker[PokArray.DEFENSE_STAT_STAGE] += move[MoveArray.BOOST_DEF]
                print(
                    f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                    f"defense changed by {int(move[MoveArray.BOOST_DEF])} stages."
                )
            if move[MoveArray.BOOST_SPATK]:
                attacker[PokArray.SPECIAL_ATTACK_STAT_STAGE] += move[MoveArray.BOOST_SPATK]
                print(
                    f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                    f"special attack changed by {int(move[MoveArray.BOOST_SPATK])} stages."
                )
            if move[MoveArray.BOOST_SPDEF]:
                attacker[PokArray.SPECIAL_DEFENSE_STAT_STAGE] += move[MoveArray.BOOST_SPDEF]
                print(
                    f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                    f"special defense changed by {int(move[MoveArray.BOOST_SPDEF])} stages."
                )
            if move[MoveArray.BOOST_SPEED]:
                attacker[PokArray.SPEED_STAT_STAGE] += move[MoveArray.BOOST_SPEED]
                print(
                    f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                    f"speed changed by {int(move[MoveArray.BOOST_SPEED])} stages."
                )
            if move[MoveArray.BOOST_ACC]:
                attacker[PokArray.ACCURACY_STAT_STAGE] += move[MoveArray.BOOST_ACC]
                print(
                    f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                    f"accuracy changed by {int(move[MoveArray.BOOST_ACC])} stages."
                )
            if move[MoveArray.BOOST_EV]:
                attacker[PokArray.EVASION_STAT_STAGE] += move[MoveArray.BOOST_EV]
                print(
                    f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                    f"evasion changed by {int(move[MoveArray.BOOST_EV])} stages."
                )

        if move[MoveArray.TARGET] in (
            Target.NORMAL,
            Target.ADJACENT_FOE,
            Target.ALL_ADJACENT_FOES,
            Target.ANY,
            Target.FOE_SIDE,
            Target.RANDOM_NORMAL,
            Target.SCRIPTED
        ):
            if move[MoveArray.BOOST_ATK]:
                defender[PokArray.ATTACK_STAT_STAGE] += move[MoveArray.BOOST_ATK]
                print(
                    f"{PokemonName(defender[PokArray.ID]).name.capitalize()}'s "
                    f"attack changed by {int(move[MoveArray.BOOST_ATK])} stages."
                )
            if move[MoveArray.BOOST_DEF]:
                defender[PokArray.DEFENSE_STAT_STAGE] += move[MoveArray.BOOST_DEF]
                print(
                    f"{PokemonName(defender[PokArray.ID]).name.capitalize()}'s "
                    f"defense changed by {int(move[MoveArray.BOOST_DEF])} stages."
                )
            if move[MoveArray.BOOST_SPATK]:
                defender[PokArray.SPECIAL_ATTACK_STAT_STAGE] += move[MoveArray.BOOST_SPATK]
                print(
                    f"{PokemonName(defender[PokArray.ID]).name.capitalize()}'s "
                    f"special attack changed by {int(move[MoveArray.BOOST_SPATK])} stages."
                )
            if move[MoveArray.BOOST_SPDEF]:
                defender[PokArray.SPECIAL_DEFENSE_STAT_STAGE] += move[MoveArray.BOOST_SPDEF]
                print(
                    f"{PokemonName(defender[PokArray.ID]).name.capitalize()}'s "
                    f"special defense changed by {int(move[MoveArray.BOOST_SPDEF])} stages."
                )
            if move[MoveArray.BOOST_SPEED]:
                defender[PokArray.SPEED_STAT_STAGE] += move[MoveArray.BOOST_SPEED]
                print(
                    f"{PokemonName(defender[PokArray.ID]).name.capitalize()}'s "
                    f"speed changed by {int(move[MoveArray.BOOST_SPEED])} stages."
                )
            if move[MoveArray.BOOST_ACC]:
                defender[PokArray.ACCURACY_STAT_STAGE] += move[MoveArray.BOOST_ACC]
                print(
                    f"{PokemonName(defender[PokArray.ID]).name.capitalize()}'s "
                    f"accuracy changed by {int(move[MoveArray.BOOST_ACC])} stages."
                )
            if move[MoveArray.BOOST_EV]:
                defender[PokArray.EVASION_STAT_STAGE] += move[MoveArray.BOOST_EV]
                print(
                    f"{PokemonName(defender[PokArray.ID]).name.capitalize()}'s "
                    f"evasion changed by {int(move[MoveArray.BOOST_EV])} stages."
                )
    # Status
    if move[MoveArray.STATUS] != 0:
        if move[MoveArray.TARGET] in (
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
    offset = len(MoveArray) + len(MoveFlags)
    chance = move[offset + SecondaryArray.CHANCE]
    roll = random.randint(1, 100) if chance < 100 else 0
    if roll <= chance:
        if move[MoveArray.TARGET] in (
            Target.NORMAL,
            Target.ADJACENT_FOE,
            Target.ALL_ADJACENT_FOES,
            Target.ANY,
            Target.FOE_SIDE,
            Target.RANDOM_NORMAL,
            Target.SCRIPTED
        ):
            a = move[offset + SecondaryArray.STATUS]
            if a != 0:
                apply_status(move, defender, sec=True)
        if move[MoveArray.TARGET] in (
            Target.ADJACENT_ALLY,
            Target.ADJACENT_ALLY_OR_SELF,
            Target.ALLIES,
            Target.ALLY_SIDE,
            Target.SELF
        ):
            if any(move[offset + SecondaryArray.SEC_BOOST_ATK: offset + SecondaryArray.SEC_BOOST_EV + 1]):
                if move[offset + SecondaryArray.SEC_BOOST_ATK]:
                    attacker[PokArray.ATTACK_STAT_STAGE] += move[offset + SecondaryArray.SEC_BOOST_ATK]
                    print(
                        f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                        f"attack changed by {int(move[offset + SecondaryArray.SEC_BOOST_ATK])} stages."
                    )
                if move[offset + SecondaryArray.SEC_BOOST_DEF]:
                    attacker[PokArray.DEFENSE_STAT_STAGE] += move[offset + SecondaryArray.SEC_BOOST_DEF]
                    print(
                        f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                        f"defense changed by {int(move[offset + SecondaryArray.SEC_BOOST_DEF])} stages."
                    )
                if move[offset + SecondaryArray.SEC_BOOST_SPATK]:
                    attacker[PokArray.SPECIAL_ATTACK_STAT_STAGE] += move[offset + SecondaryArray.SEC_BOOST_SPATK]
                    print(
                        f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                        f"special attack changed by {int(move[offset + SecondaryArray.SEC_BOOST_SPATK])} stages."
                    )
                if move[offset + SecondaryArray.SEC_BOOST_SPDEF]:
                    attacker[PokArray.SPECIAL_DEFENSE_STAT_STAGE] += move[offset + SecondaryArray.SEC_BOOST_SPDEF]
                    print(
                        f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                        f"special defense changed by {int(move[offset + SecondaryArray.SEC_BOOST_SPDEF])} stages."
                    )
                if move[offset + SecondaryArray.SEC_BOOST_SPEED]:
                    attacker[PokArray.SPEED_STAT_STAGE] += move[offset + SecondaryArray.SEC_BOOST_SPEED]
                    print(
                        f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                        f"speed changed by {int(move[offset + SecondaryArray.SEC_BOOST_SPEED])} stages."
                    )
                if move[offset + SecondaryArray.SEC_BOOST_ACC]:
                    attacker[PokArray.ACCURACY_STAT_STAGE] += move[offset + SecondaryArray.SEC_BOOST_ACC]
                    print(
                        f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                        f"accuracy changed by {int(move[offset + SecondaryArray.SEC_BOOST_ACC])} stages."
                    )
                if move[offset + SecondaryArray.SEC_BOOST_EV]:
                    attacker[PokArray.EVASION_STAT_STAGE] += move[offset + SecondaryArray.SEC_BOOST_EV]
                    print(
                        f"{PokemonName(attacker[PokArray.ID]).name.capitalize()}'s "
                        f"evasion changed by {int(move[offset + SecondaryArray.SEC_BOOST_EV])} stages."
                    )
            if move[MoveArray.DRAIN]:
                drain_effect(attacker, dmg, move[MoveArray.DRAIN])


def after_turn_status(pok):
    """Calculate damage after turn like burn, poison, volatile status"""
    # TODO:
    if pok[PokArray.STATUS]:
        if pok[PokArray.STATUS] in (Status.BURN, Status.POISON):
            if pok[PokArray.BADLY_POISON] >= 1:
                dmg = np.floor(pok[PokArray.MAX_HP] * pok[PokArray.BADLY_POISON] * (1 / 16))
                pok[PokArray.BADLY_POISON] += 1
            else:
                dmg = np.floor(pok[PokArray.MAX_HP] / 8)
            pok[PokArray.CURRENT_HP] -= dmg
            print(f'{PokemonName(pok[PokArray.ID]).name.capitalize()} suffered {dmg} HP from {StatusIdToName[pok[PokArray.STATUS]].lower()}')
            if pok[PokArray.CURRENT_HP] <= 0:
                print(f'{PokemonName(pok[PokArray.ID]).name.capitalize()} has fainted.')
                pok[PokArray.CURRENT_HP] = 0
            else:
                print(f'{PokemonName(pok[PokArray.ID]).name.capitalize()} has {pok[PokArray.CURRENT_HP]} left.')


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
