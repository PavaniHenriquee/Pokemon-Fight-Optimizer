"""Ability checks shared by damage_calc and engine_helper"""
from Utils.jit import njit
from Models.constants import _POK_AB_BREAKABLE, _POK_AB_ID, _ABILITYNAMES_MOLD_BREAKER


@njit
def ignorable_ability(defender, attacker):
    """
    Whether the defender's ability takes effect against this attacker. Mold Breaker ignores
    every breakable one (pokeplatinum Battler_IgnorableAbility)
    """
    return not (defender[_POK_AB_BREAKABLE] and attacker[_POK_AB_ID] == _ABILITYNAMES_MOLD_BREAKER)
