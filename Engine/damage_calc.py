"""Damage calculations"""
import random
import numpy as np
from Utils.helper import stage_to_multiplier, get_type_effectiveness
from Models.idx_const import Pok, Move, Flags
from Models.helper import MoveCategory, Status, Types, AbilityActivation, Weather
from DataBase.AbilitiesDB import AbilityNames


MULTIPLIERS = [i for i in range(85, 101)]
STARTER_AB = {AbilityNames.BLAZE, AbilityNames.TORRENT, AbilityNames.OVERGROW}
STAGES_TABLE = (
    (2, 8), (2, 7), (2, 6), (2, 5), (2, 4), (2, 3), # -6 to -1
    (2, 2),                                         # 0
    (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2)  # +1 to +6
)


def raw_atk_def(move, attacker, defender, weather=0, crit=False):
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
    if not atk_stage | def_stage:
        return raw_attack, raw_defense
    table = STAGES_TABLE
    n_atk, d_atk = table[atk_stage + 6]
    n_def, d_def = table[def_stage + 6]

    # Integer-only math: (Value * Numerator) // Denominator
    return (raw_attack * n_atk) // d_atk, (raw_defense * n_def) // d_def

def base_power_ability(attacker, move) -> float:
    """Calculate what the ability does in relation to power
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
        return 4915  # 1.2

    return 0.0


def multipliers(
        move: np.int32, attacker: np.int32, defender: np.int32,
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

    attack, defense = raw_atk_def(move, attacker, defender, weather, crit)

    # Ability
    power = move[Move.POWER]
    if attacker[Pok.AB_WHEN] == AbilityActivation.ON_BASE_POWER:
        base_power_mult = base_power_ability(attacker, move)
        if base_power_mult:
            power = base_power_mult*power//4096

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


def struggle(attacker, defender, rec=True):
    """
    Struggle damage for the opponent and recoil
    Not implemented
    """
    attack = attacker[Pok.ATTACK]
    defense = defender[Pok.DEFENSE]
    def_stage = defender[Pok.DEFENSE_STAT_STAGE]
    atk_stage = attacker[Pok.ATTACK_STAT_STAGE]
    level = attacker[Pok.LEVEL]
    atk_max_hp = attacker[Pok.MAX_HP]
    cur_hup = attacker[Pok.CURRENT_HP]

    if random.random() < 0.0625:
        def_stage = min(def_stage, 0)
        atk_stage = max(atk_stage, 0)

    # apply stage multipliers
    if atk_stage | def_stage:
        table = STAGES_TABLE
        n_atk, d_atk = table[atk_stage + 6]
        n_def, d_def = table[def_stage + 6]
        attack = (attack * n_atk) // d_atk
        defense = (defense * n_def) // d_def

    # Base damage formula for Struggle with power 50
    damage = (((2 * level / 5) + 2) * 50 * (attack / defense)) // 50

    # Burn
    if attacker[Pok.STATUS] == Status.BURN:
        damage //= 2

    # TODO: Screen

    # Adding 2 after the above
    damage += 2

    if rec:
        recoil = atk_max_hp//4
        if recoil >= cur_hup:
            attacker[Pok.CURRENT_HP] = 0
        else:
            attacker[Pok.CURRENT_HP] -= recoil

    return damage


def calculate_ai_logic_damage(effectivenes, attacker, defender, move, weather):
    """
    AI calculates damges from its damage a little differente, so here i do it
    like in the games
    """
    power = move[Move.POWER]
    attack, defense = raw_atk_def(move, attacker, defender, weather)

    # Ability
    power = move[Move.POWER]
    if attacker[Pok.AB_WHEN] == AbilityActivation.ON_BASE_POWER:
        base_power_mult = base_power_ability(attacker, move)
        if base_power_mult:
            power = base_power_mult*power//4096

    level = attacker[Pok.LEVEL]

    # Base damage formula
    damage = (((2 * level / 5) + 2) * power * (attack / defense)) // 50

    # Burn
    if attacker[Pok.STATUS] == Status.BURN:
        if move[Move.CATEGORY] == MoveCategory.PHYSICAL:
            damage //= 2

    # TODO: Screen

    # TODO: Targets

    # Weather
    if weather:
        w = weather
        m_type = move[Move.TYPE]
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

    return int(damage*effectivenes)
