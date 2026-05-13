"""Damage calculations"""
import random
import numpy as np
from Utils.helper import stage_to_multiplier, get_type_effectiveness
from Models.idx_const import Pok, Move, Flags
from Models.helper import MoveCategory, Status, Types, AbilityActivation, Weather
from DataBase.AbilitiesDB import AbilityNames


MULTIPLIERS = [i for i in range(85, 101)]
STARTER_AB = {AbilityNames.BLAZE, AbilityNames.TORRENT, AbilityNames.OVERGROW}


def raw_atk_def(move, attacker, defender, weather, crit=False):
    """
    Getting the right attack and defense and applying the right modifiers
    """
    if move[Move.CATEGORY] == MoveCategory.PHYSICAL:
        raw_attack = attacker[Pok.ATTACK]
        raw_defense = defender[Pok.DEFENSE]
        atk_stage = attacker[Pok.ATTACK_STAT_STAGE]
        def_stage = defender[Pok.DEFENSE_STAT_STAGE]
    else:
        raw_attack = attacker[Pok.SPECIAL_ATTACK]
        raw_defense = defender[Pok.SPECIAL_DEFENSE]
        atk_stage = attacker[Pok.SPECIAL_ATTACK_STAT_STAGE]
        def_stage = defender[Pok.SPECIAL_DEFENSE_STAT_STAGE]
        if (
            weather == Weather.SANDSTORM
            and (
                attacker[Pok.TYPE1] == Types.ROCK or  #pylint: disable=consider-using-in
                attacker[Pok.TYPE2] == Types.ROCK
            )
        ):
            raw_defense = (raw_defense*3)//2
    if crit:
        def_stage = min(def_stage, 0)
        atk_stage = max(atk_stage, 0)
    # apply stage multipliers
    if atk_stage != 0:
        attack =  stage_to_multiplier(atk_stage, raw_attack)
    else:
        attack = raw_attack
    if def_stage != 0:
        defense = stage_to_multiplier(def_stage, raw_defense)
    else:
        defense = raw_defense


    return attack, defense

def base_power_ability(attacker, defender, move) -> float:  # pylint: disable=W0613
    """Calculate what the ability does in relation to damage
    Returns:
        1 if nothing happens\n
        multiplier based on 4096 if it does something, like Blaze"""
    mult = 4096
    att_ab = attacker[Pok.AB_ID]

    # Starter Abilities
    if (
        att_ab in STARTER_AB
        and attacker[Pok.CURRENT_HP] / attacker[Pok.MAX_HP] <= 1 / 3
    ):
        if att_ab == AbilityNames.BLAZE and move[Move.TYPE] == Types.FIRE:
            mult = 6144  # 1.5
        if att_ab == AbilityNames.TORRENT and move[Move.TYPE] == Types.WATER:
            mult = 6144  # 1.5
        if att_ab == AbilityNames.OVERGROW and move[Move.TYPE] == Types.GRASS:
            mult = 6144  # 1.5
        return mult

    # Iron Fist
    if att_ab == AbilityNames.IRON_FIST and move[Flags.PUNCH]:
        mult = 4915  # 1.2

    return mult


def multipliers(
        move: np.float32, attacker: np.float32, defender: np.float32,
        weather:int, crit: bool, roll_mult: int, damage
) -> int:
    """Calc Multiplers for bas formula damage"""
    m_type = move[Move.TYPE]
    atk_type1 = attacker[Pok.TYPE1]
    atk_type2 = attacker[Pok.TYPE2]
    def_type2 = defender[Pok.TYPE2]

    # Burn
    if attacker[Pok.STATUS] == Status.BURN:
        if move[Move.CATEGORY] == MoveCategory.PHYSICAL:
            damage //= 2

    # TODO: Screen

    # TODO: Targets

    # Weather
    if weather:
        w = weather
        if w == Weather.SUN:
            if m_type == Types.FIRE:
                damage = (damage*3) // 2
            elif m_type == Types.WATER:
                damage //= 2
        if w == Weather.RAIN:
            if m_type == Types.WATER:
                damage = (damage*3) // 2
            elif m_type == Types.FIRE:
                damage //= 2

    # TODO: Flash Fire

    # Adding 2 after the above
    damage += 2

    # Crit
    if crit:
        damage *= 2

    # TODO: Item

    # TODO: Me First

    # Roll Multiplier
    if roll_mult is None:
        roll_mult = MULTIPLIERS[random.getrandbits(4)]
    damage = (damage * roll_mult) // 100

    # STAB
    if m_type == atk_type1 or m_type == atk_type2:  # pylint: disable=R1714
        damage = (damage*3) // 2

    # Effectiveness type 1
    effectiveness, _ = get_type_effectiveness(m_type, defender[Pok.TYPE1], 0)
    if effectiveness != 2:
        damage = (effectiveness * damage)//2

    # Effectiveness type 2
    if def_type2:
        effectiveness2, _ = get_type_effectiveness(m_type, def_type2, 0)
        if effectiveness2 != 2:
            damage = (effectiveness2 * damage)//2

    # TODO: Solid Rock and Filter

    # TODO: Expert belt

    # TODO: Tinted Lens

    # TODO: Berry

    return damage


def calculate_damage(
        attacker, defender, move,
        weather: int=0,
        crit: bool=False,
        roll_multiplier: float=None,
) -> int:
    """Calculate damage based on current stats of the attacker and the defender,
       giving back the damage and its effectiveness"""
    if move[Move.CATEGORY] == MoveCategory.STATUS or move[Move.CATEGORY] == 0:
        # Status moves don't deal damage(Trainer AI needs this)
        return 0

    attack, defense = raw_atk_def(move, attacker, defender, weather, crit)

    # Ability TODO: change everything to accomodate activation changes
    power = move[Move.POWER]
    if attacker[Pok.AB_WHEN] == AbilityActivation.ON_BASE_POWER:
        power = (base_power_ability(attacker, defender, move)*power) // 4096

    level = attacker[Pok.LEVEL]

    # Base damage formula
    damage = (((2 * level / 5) + 2) * power * (attack / defense)) // 50
    if damage < 0:
        raise ValueError("There shouldn't be negative damage")

    damage = multipliers(move, attacker, defender, weather, crit, roll_multiplier, damage)
    return damage


def calculate_damage_confusion(pok):
    """Calculate the damage for Confusion self hit"""
    raw_attack = pok[Pok.ATTACK]
    raw_defense = pok[Pok.DEFENSE]
    atk_stage = pok[Pok.ATTACK_STAT_STAGE]
    def_stage = pok[Pok.DEFENSE_STAT_STAGE]
    # apply stage multipliers
    if atk_stage != 0:
        attack =  stage_to_multiplier(atk_stage, raw_attack)
    else:
        attack = raw_attack
    if def_stage != 0:
        defense = stage_to_multiplier(def_stage, raw_defense)
    else:
        defense = raw_defense
    # Base damage formula, confusion counts as a 40 power move
    damage = ((2 * pok[Pok.LEVEL] / 5) + 2) * 40 * (attack / defense) // 50 + 2
    if pok[Pok.STATUS] == Status.BURN:
        damage //= 2
    return damage


def struggle(attacker, defender):
    """
    Struggle damage for the opponent and recoil
    Not implemented
    """
    atk = attacker[Pok.ATTACK]
    defense = defender[Pok.DEFENSE]
    power = 50
    return atk, defense, power
