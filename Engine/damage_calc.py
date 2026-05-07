"""Damage calculations"""
import random
import numpy as np
from Utils.helper import stage_to_multiplier, get_type_effectiveness
from Models.idx_const import Pok, Move, Flags
from Models.helper import MoveCategory, Status, Types, AbilityActivation
from Models.pokemon import Pokemon
from Models.move import Move as Move_
from DataBase.AbilitiesDB import AbilityNames


MULTIPLIERS = [i / 100 for i in range(85, 101)]
STARTER_AB = (AbilityNames.BLAZE, AbilityNames.TORRENT, AbilityNames.OVERGROW)


def base_power_ability(attacker, defender, move) -> float:  # pylint: disable=W0613
    """Calculate what the ability does in relation to damage
    Returns:
        1 if nothing happens\n
        multiplier if it does something, like Blaze"""
    mult = 1
    att_ab = attacker[Pok.AB_ID]

    # Starter Abilities
    if (
        att_ab in STARTER_AB
        and attacker[Pok.CURRENT_HP] / attacker[Pok.MAX_HP] <= 1 / 3
    ):
        if att_ab == AbilityNames.BLAZE and move[Move.TYPE] == Types.FIRE:
            mult = 1.5
        if att_ab == AbilityNames.TORRENT and move[Move.TYPE] == Types.WATER:
            mult = 1.5
        if att_ab == AbilityNames.OVERGROW and move[Move.TYPE] == Types.GRASS:
            mult = 1.5
        return mult

    # Iron Fist
    if att_ab == AbilityNames.IRON_FIST and move[Flags.PUNCH]:
        mult = 1.199951172  # 4915/4096 beacuse there isn't 1.2 in game engine

    return mult


def multipliers(
        move: np.float32, attacker: np.float32, defender: np.float32, crit: bool, roll_mult: int, damage
):
    """Calc Multiplers for bas formula damage"""

    # Burn
    if attacker[Pok.STATUS] == Status.BURN:
        if move[Move.CATEGORY] == MoveCategory.PHYSICAL:
            damage = int(0.5 * damage)

    # TODO: Screen

    # TODO: Targets

    # TODO: Weather

    # TODO: Flash Fire

    # Adding 2 after the above
    damage += 2

    # Crit
    if crit is True:
        damage *= 2

    # TODO: Item

    # TODO: Me First

    # Roll Multiplier
    if roll_mult is None:
        roll_mult = MULTIPLIERS[random.getrandbits(4)]
    damage = int(roll_mult * damage)

    # STAB
    if move[Move.TYPE] in [attacker[Pok.TYPE1], attacker[Pok.TYPE2]]:
        damage = int(1.5 * damage)

    # Effectiveness type 1
    effectiveness = get_type_effectiveness(move[Move.TYPE], defender[Pok.TYPE1], 0)
    if effectiveness != 1:
        damage = int(effectiveness * damage)

    # Effectiveness type 2
    if defender[Pok.TYPE2]:
        effectiveness2 = get_type_effectiveness(move[Move.TYPE], defender[Pok.TYPE2], 0)
        if effectiveness2 != 1:
            damage = int(effectiveness2 * damage)

    # TODO: Solid Rock and Filter

    # TODO: Expert belt

    # TODO: Tinted Lens

    # TODO: Berry

    return damage


def calculate_damage(
        attacker: Pokemon, defender: Pokemon, move: Move_, crit: bool=False, roll_multiplier: float=None
) -> int:
    """Calculate damage based on current stats of the attacker and the defender,
       giving back the damage and its effectiveness"""
    if move[Move.CATEGORY] == MoveCategory.STATUS or move[Move.CATEGORY] == 0:
        # Status moves don't deal damage(Trainer AI needs this)
        return 0

    atk = attacker
    defn = defender
    mv = move

    if mv[Move.CATEGORY] == MoveCategory.PHYSICAL:
        raw_attack = atk[Pok.ATTACK]
        raw_defense = defn[Pok.DEFENSE]
        atk_stage = atk[Pok.ATTACK_STAT_STAGE]
        def_stage = defn[Pok.DEFENSE_STAT_STAGE]
    else:
        raw_attack = atk[Pok.SPECIAL_ATTACK]
        raw_defense = defn[Pok.SPECIAL_DEFENSE]
        atk_stage = atk[Pok.SPECIAL_ATTACK_STAT_STAGE]
        def_stage = defn[Pok.SPECIAL_DEFENSE_STAT_STAGE]

    if crit is True:
        def_stage = min(def_stage, 0)
        atk_stage = max(atk_stage, 0)

    # apply stage multipliers
    attack = int(raw_attack * stage_to_multiplier(atk_stage))
    defense = int(raw_defense * stage_to_multiplier(def_stage))

    # Ability TODO: change everything to accomodate activation changes
    power = mv[Move.POWER]
    if atk[Pok.AB_WHEN] == AbilityActivation.ON_BASE_POWER:
        power *= base_power_ability(atk, defn, mv)

    level = atk[Pok.LEVEL]

    # Base damage formula
    damage = int((((2 * level / 5) + 2) * power * (attack / defense)) / 50)
    if damage < 0:
        raise ValueError("There shouldn't be negative damage")

    damage = multipliers(mv, atk, defn, crit, roll_multiplier, damage)
    return damage


def calculate_damage_confusion(pok):
    """Calculate the damage for Confusion self hit"""
    raw_attack = pok[Pok.ATTACK]
    raw_defense = pok[Pok.DEFENSE]
    atk_stage = pok[Pok.ATTACK_STAT_STAGE]
    def_stage = pok[Pok.DEFENSE_STAT_STAGE]
    # apply stage multipliers
    attack = int(raw_attack * stage_to_multiplier(atk_stage))
    defense = int(raw_defense * stage_to_multiplier(def_stage))
    # Base damage formula, confusion counts as a 40 power move
    damage = int(int(((2 * pok[Pok.LEVEL] / 5) + 2) * 40 * (attack / defense)) / 50 + 2)
    if pok[Pok.STATUS] == Status.BURN:
        damage *= 0.5
    return damage
