"""Damage calculations"""
import random
import numpy as np
from numba import njit
from Utils.helper import get_type_effectiveness
from Models.constants import (
    _ABILITYNAMES_BLAZE, _ABILITYNAMES_TORRENT, _ABILITYNAMES_OVERGROW,
    _POK_AB_ID, _ABILITYNAMES_GUTS, _POK_STATUS, _ABILITYNAMES_HUGE_POWER,
    _ABILITYNAMES_HUSTLE, _MOVE_OH_KO, _MOVE_CATEGORY, _MOVECATEGORY_PHYSICAL,
    _POK_ATTACK, _POK_DEFENSE, _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE,
    _POK_SPECIAL_ATTACK, _POK_SPECIAL_DEFENSE, _POK_SPECIAL_ATTACK_STAT_STAGE,
    _POK_SPECIAL_DEFENSE_STAT_STAGE, _WEATHER_SANDSTORM, _POK_TYPE1, _TYPES_ROCK,
    _POK_TYPE2, _POK_AB_WHEN, _ABILITYACTIVATION_ON_MODIFY_STAT, _POK_CURRENT_HP,
    _POK_MAX_HP, _MOVE_TYPE, _TYPES_FIRE, _TYPES_WATER, _TYPES_GRASS, _ABILITYNAMES_IRON_FIST,
    _FLAGS_PUNCH, _STATUS_BURN, _WEATHER_SUN, _WEATHER_RAIN, _MOVE_POWER,
    _ABILITYACTIVATION_ON_BASE_POWER, _POK_LEVEL, _ABILITYNAMES_RECKLESS, _MOVE_RECOIL,
    _MOVE_HAS_CRASH_DAMAGE, _ABILITYNAMES_SIMPLE, _ABILITYNAMES_SOLAR_POWER,
    _ABILITYNAMES_THICK_FAT, _TYPES_ICE, _ABILITYNAMES_TINTED_LENS
)

# ==========================================
# 1. CONSTANTS & LOOKUPS
# ==========================================
MULTIPLIERS = (85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100)
STARTER_AB = (_ABILITYNAMES_BLAZE, _ABILITYNAMES_TORRENT, _ABILITYNAMES_OVERGROW)
THICK_F_TYPES = (_TYPES_FIRE, _TYPES_ICE)
STAGES_TABLE = (
    (2, 8), (2, 7), (2, 6), (2, 5), (2, 4), (2, 3), # -6 to -1
    (2, 2),                                         # 0
    (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2)  # +1 to +6
)


# ==========================================
# 2. MATH HELPERS
# ==========================================
@njit
def apply_stat_stage(raw_stat: int, stage: int, is_simple: bool) -> int:
    """Applies Gen IV stage multipliers to a stat, returning the integer math."""
    if is_simple:
        stage = max(-6, min(6, stage * 2))

    if stage == 0:
        return raw_stat

    n_stat, d_stat = STAGES_TABLE[stage + 6]
    return (raw_stat * n_stat) // d_stat


# ==========================================
# 3. MODIFIERS (ABILITIES, WEATHER, ETC.)
# ==========================================
@njit
def ab_modify_stat(attacker, atk, physical, move, weather):
    """
    Applies base stat changes
    """
    atk_ab = attacker[_POK_AB_ID]
    if physical:
        if atk_ab == _ABILITYNAMES_GUTS and attacker[_POK_STATUS] != 0:
            atk = (atk * 3) // 2
        elif atk_ab == _ABILITYNAMES_HUGE_POWER:
            atk *= 2
        elif atk_ab == _ABILITYNAMES_HUSTLE and not move[_MOVE_OH_KO]:
            atk = (atk * 3) // 2
    else:
        if atk_ab == _ABILITYNAMES_SOLAR_POWER and weather == _WEATHER_SUN:
            atk = (atk * 3) // 2

    if atk_ab == _ABILITYNAMES_THICK_FAT and move[_MOVE_TYPE] in THICK_F_TYPES:
        atk //= 2
    return atk


@njit
def raw_atk_def(move, attacker, defender, weather=0, crit=False):
    """
    Getting the right attack and defense and applying the right modifiers
    """
    physical = move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL
    atk_is_simple = attacker[_POK_AB_ID] == _ABILITYNAMES_SIMPLE
    def_is_simple = defender[_POK_AB_ID] == _ABILITYNAMES_SIMPLE
    if physical:
        raw_attack = attacker[_POK_ATTACK]
        raw_defense = defender[_POK_DEFENSE]
        atk_stage = attacker[_POK_ATTACK_STAT_STAGE]
        def_stage = defender[_POK_DEFENSE_STAT_STAGE]
    else:
        raw_attack = attacker[_POK_SPECIAL_ATTACK]
        raw_defense = defender[_POK_SPECIAL_DEFENSE]
        atk_stage = attacker[_POK_SPECIAL_ATTACK_STAT_STAGE]
        def_stage = defender[_POK_SPECIAL_DEFENSE_STAT_STAGE]
        # Sandstorm Sp.Def boost for Rock types
        if weather == (
            _WEATHER_SANDSTORM
            and (
                attacker[_POK_TYPE1] == _TYPES_ROCK
                or attacker[_POK_TYPE2] == _TYPES_ROCK
            )
        ):
            raw_defense = (raw_defense * 3) // 2
    if crit:
        def_stage = min(def_stage, 0)
        atk_stage = max(atk_stage, 0)

    if (
        attacker[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_MODIFY_STAT
        or defender[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_MODIFY_STAT
    ):
        raw_attack = ab_modify_stat(attacker, raw_attack, physical, move, weather)

    attack = apply_stat_stage(raw_attack, atk_stage, atk_is_simple)
    defense = apply_stat_stage(raw_defense, def_stage, def_is_simple)

    return attack, defense


@njit
def base_power_ability(attacker, move) -> float:
    """
    Calculate what the ability does in relation to power
    Returns:
        0 if nothing happens\n
        multiplier based on 4096 if it does something, like Blaze
    """
    att_ab = attacker[_POK_AB_ID]

    # Starter Abilities
    if (
        att_ab in STARTER_AB
        and attacker[_POK_CURRENT_HP] / attacker[_POK_MAX_HP] <= 1 / 3
    ):
        if att_ab == _ABILITYNAMES_BLAZE and move[_MOVE_TYPE] == _TYPES_FIRE:
            return 6144  # 1.5
        if att_ab == _ABILITYNAMES_TORRENT and move[_MOVE_TYPE] == _TYPES_WATER:
            return 6144  # 1.5
        if att_ab == _ABILITYNAMES_OVERGROW and move[_MOVE_TYPE] == _TYPES_GRASS:
            return 6144  # 1.5
        return 0

    # Iron Fist
    if att_ab == _ABILITYNAMES_IRON_FIST and move[_FLAGS_PUNCH]:
        return 4915  # 1.2

    # Reckless
    if (
        att_ab == _ABILITYNAMES_RECKLESS
        and (
            move[_MOVE_RECOIL]
            or move[_MOVE_HAS_CRASH_DAMAGE]
        )
    ):
        return 4915  #1.2

    return 0


@njit
def multipliers(
        move: np.ndarray, attacker: np.ndarray, defender: np.ndarray,
        weather:int, crit: bool, roll_mult: int, damage: int
) -> int:
    """Calc Multiplers for bas formula damage"""
    m_type = move[_MOVE_TYPE]
    atk_type1 = attacker[_POK_TYPE1]
    atk_type2 = attacker[_POK_TYPE2]
    def_type2 = defender[_POK_TYPE2]

    # Burn
    if attacker[_POK_STATUS] == _STATUS_BURN:
        if (
            move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL
            and attacker[_POK_AB_ID] != _ABILITYNAMES_GUTS
        ):
            damage //= 2

    # TODO: Screen

    # TODO: Targets

    # Weather
    if weather:
        w = weather
        if w == _WEATHER_SUN:
            if m_type == _TYPES_FIRE:
                damage = (damage*3) // 2
            elif m_type == _TYPES_WATER:
                damage //= 2
        if w == _WEATHER_RAIN:
            if m_type == _TYPES_WATER:
                damage = (damage*3) // 2
            elif m_type == _TYPES_FIRE:
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
    effectiveness, _ = get_type_effectiveness(m_type, defender[_POK_TYPE1], 0)
    if effectiveness != 2:
        damage = (effectiveness * damage)//2

    # Effectiveness type 2
    effectiveness2 = 2  # Base is 2 since later //2
    if def_type2:
        effectiveness2, _ = get_type_effectiveness(m_type, def_type2, 0)
        if effectiveness2 != 2:
            damage = (effectiveness2 * damage)//2

    # TODO: Solid Rock and Filter

    # TODO: Expert belt

    # Tinted Lens
    if (
        attacker[_POK_AB_ID] == _ABILITYNAMES_TINTED_LENS
        and (effectiveness * effectiveness2 // 4) == 0
    ):
        damage *= 2

    # TODO: Berry

    return damage


# ==========================================
# 4. CORE DAMAGE FUNCTIONS
# ==========================================
@njit
def calculate_damage(
        attacker: np.ndarray, defender: np.ndarray, move: np.ndarray,
        weather: int=0, crit: bool=False, roll_multiplier: int=None,
) -> int:
    """Standard damage calculation"""

    attack, defense = raw_atk_def(move, attacker, defender, weather, crit)

    # Ability
    power = move[_MOVE_POWER]
    if attacker[_POK_AB_WHEN] == _ABILITYACTIVATION_ON_BASE_POWER:
        base_power_mult = base_power_ability(attacker, move)
        if base_power_mult:
            power = base_power_mult*power // 4096

    level = attacker[_POK_LEVEL]

    # Base damage formula
    damage = (((2 * level / 5) + 2) * power * (attack / defense)) // 50

    return multipliers(move, attacker, defender, weather, crit, roll_multiplier, damage)


@njit
def calculate_damage_confusion(pok):
    """Calculate the damage for Confusion self hit"""
    is_simple = pok[_POK_AB_ID] == _ABILITYNAMES_SIMPLE

    attack = apply_stat_stage(pok[_POK_ATTACK], pok[_POK_ATTACK_STAT_STAGE], is_simple)
    defense = apply_stat_stage(pok[_POK_DEFENSE], pok[_POK_DEFENSE_STAT_STAGE], is_simple)

    # Abilities affecting stat(equal logic to ab_mod_stat but without move)
    pok_ab = pok[_POK_AB_ID]
    if pok_ab == _ABILITYNAMES_GUTS and pok[_POK_STATUS] != 0:
        attack = (attack*3)//2
    elif pok_ab == _ABILITYNAMES_HUGE_POWER:
        attack *= 2
    elif pok_ab == _ABILITYNAMES_HUSTLE:
        attack = (attack*3)//2

    # Base damage formula, confusion counts as a 40 power move
    damage = ((2 * pok[_POK_LEVEL] / 5) + 2) * 40 * (attack / defense) // 50
    if pok[_POK_STATUS] == _STATUS_BURN:
        damage //= 2
    # Adding 2 after the above
    damage += 2
    # Random Multiplier
    damage = (damage * MULTIPLIERS[random.getrandbits(4)]) // 100
    #TODO: Helping Hand
    #TODO: Silk Scarf
    #TODO: Choice Band, Thick Club
    #TODO: Power TRick, Power Split, Guard Split
    #TODO: Rivalry

    return damage




@njit
def calculate_ai_logic_damage(effectivenes, attacker, defender, move, weather):
    """
    AI calculates damges from its damage a little differente, so here i do it
    like in the games
    """
    attack, defense = raw_atk_def(move, attacker, defender, weather)

    # Ability
    power = move[_MOVE_POWER]
    if attacker[_POK_AB_WHEN] == _ABILITYACTIVATION_ON_BASE_POWER:
        base_power_mult = base_power_ability(attacker, move)
        if base_power_mult:
            power = base_power_mult*power//4096

    level = attacker[_POK_LEVEL]

    # Base damage formula
    damage = (((2 * level / 5) + 2) * power * (attack / defense)) // 50

    # Burn
    if attacker[_POK_STATUS] == _STATUS_BURN:
        if move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL:
            damage //= 2

    # TODO: Screen

    # TODO: Targets

    # Weather
    if weather:
        w = weather
        m_type = move[_MOVE_TYPE]
        if w == _WEATHER_SUN:
            if m_type == _TYPES_FIRE:
                damage = (damage*3) // 2
            elif m_type == _TYPES_WATER:
                damage //= 2
        if w == _WEATHER_RAIN:
            if m_type == _TYPES_WATER:
                damage = (damage*3) // 2
            elif m_type == _TYPES_FIRE:
                damage //= 2

    # TODO: Flash Fire

    # Adding 2 after the above
    damage += 2

    return int(damage*effectivenes)
