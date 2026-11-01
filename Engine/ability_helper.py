"""Ability checks shared by damage_calc and engine_helper"""
from Utils.jit import njit
from Models.idx_const import POK_LEN
from Models.constants import (
    _POK_AB_BREAKABLE, _POK_AB_ID, _ABILITYNAMES_MOLD_BREAKER, _ABILITYNAMES_LEVITATE,
    _POK_VOL_STATUS, _VOLSTATUS_INGRAIN, _POK_AB_KNOWN, _POK_CURRENT_HP, _FIELD_MY_POK,
    _FIELD_OPP_POK, _FIELD_WEATHER, _ABILITYNAMES_CLOUD_NINE, _ABILITYNAMES_AIR_LOCK,
    _ABILITYNAMES_NORMALIZE, _MOVE_ID, _MOVE_TYPE, _MOVENAME_STRUGGLE, _TYPES_NORMAL,
)

# Abilities that switch the weather's effects off while their holder is out
WEATHER_SUPPRESSORS = (_ABILITYNAMES_CLOUD_NINE, _ABILITYNAMES_AIR_LOCK)


@njit
def ignorable_ability(defender, attacker):
    """
    Whether the defender's ability takes effect against this attacker. Mold Breaker ignores
    every breakable one (pokeplatinum Battler_IgnorableAbility)
    """
    return not (defender[_POK_AB_BREAKABLE] and attacker[_POK_AB_ID] == _ABILITYNAMES_MOLD_BREAKER)


@njit
def normalized_type(attacker, move):
    """
    The type the attacker's move hits with: Normalize makes every move but Struggle Normal,
    Hidden Power and Natural Gift included (pokeplatinum BattleSystem_ApplyTypeChart, Showdown gen4)
    """
    if attacker[_POK_AB_ID] == _ABILITYNAMES_NORMALIZE and move[_MOVE_ID] != _MOVENAME_STRUGGLE:
        return _TYPES_NORMAL
    return move[_MOVE_TYPE]


@njit
def levitates(pok, attacker, gravity=False):
    """
    Levitate keeps Ground moves off unless the attacker has Mold Breaker. Gravity and Ingrain
    switch it off (pokeplatinum Battler_Ability)
    """
    return (
        pok[_POK_AB_ID] == _ABILITYNAMES_LEVITATE
        and not gravity
        and not pok[_POK_VOL_STATUS] & _VOLSTATUS_INGRAIN
        and ignorable_ability(pok, attacker)
    )


@njit
def effective_weather(battle_array):
    """
    The weather its effects see: none while a living active has Cloud Nine or Air Lock. The
    weather itself stays up and keeps counting down (pokeplatinum NO_CLOUD_NINE)
    """
    for base in (battle_array[_FIELD_MY_POK] * POK_LEN, (battle_array[_FIELD_OPP_POK] + 6) * POK_LEN):
        if (
            battle_array[base + _POK_CURRENT_HP] > 0
            and battle_array[base + _POK_AB_ID] in WEATHER_SUPPRESSORS
        ):
            return 0
    return battle_array[_FIELD_WEATHER]


@njit
def reveal_ability(pok):
    """
    A battle message named pok's ability, so the foe's AI knows it until pok switches out
    (pokeplatinum BattleMessage_AbilityTag on script messages; messages built in C teach nothing)
    """
    pok[_POK_AB_KNOWN] = 1
