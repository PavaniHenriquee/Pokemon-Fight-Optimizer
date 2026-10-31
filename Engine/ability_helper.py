"""Ability checks shared by damage_calc and engine_helper"""
from Utils.jit import njit
from Models.constants import (
    _POK_AB_BREAKABLE, _POK_AB_ID, _ABILITYNAMES_MOLD_BREAKER, _ABILITYNAMES_LEVITATE,
    _POK_VOL_STATUS, _VOLSTATUS_INGRAIN, _POK_AB_KNOWN,
)


@njit
def ignorable_ability(defender, attacker):
    """
    Whether the defender's ability takes effect against this attacker. Mold Breaker ignores
    every breakable one (pokeplatinum Battler_IgnorableAbility)
    """
    return not (defender[_POK_AB_BREAKABLE] and attacker[_POK_AB_ID] == _ABILITYNAMES_MOLD_BREAKER)


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
def reveal_ability(pok):
    """
    A battle message named pok's ability, so the foe's AI knows it until pok switches out
    (pokeplatinum BattleMessage_AbilityTag on script messages; messages built in C teach nothing)
    """
    pok[_POK_AB_KNOWN] = 1
