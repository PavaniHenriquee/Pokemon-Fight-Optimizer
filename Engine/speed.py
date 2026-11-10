"""Effective speed, shared by turn order (engine_helper) and speed-based power (damage_calc)"""
import random
from Utils.jit import njit
from Utils.helper import stage_to_multiplier
from Models.constants import (
    _POK_SPEED, _POK_STATUS, _STATUS_PARALYSIS, _POK_SPEED_STAT_STAGE, _POK_AB_WHEN,
    _ABILITYACTIVATION_ON_MODIFY_SPEED, _WEATHER_SUN, _ABILITYNAMES_CHLOROPHYLL, _WEATHER_RAIN,
    _ABILITYNAMES_SWIFT_SWIM, _POK_AB_ID, _ABILITYNAMES_SIMPLE, _ABILITYNAMES_QUICK_FEET,
    _ABILITYNAMES_SLOW_START, _POK_TURNS_ACTIVE, _ABILITYNAMES_UNBURDEN, _POK_VOL_STATUS2,
    _VOLSTATUS2_CAN_UNBURDEN, _ITEM_ID, _ITEM_HOLD_EFFECT, _ITEM_EFFECT_PARAM,
    _HOLDEFFECT_SOMETIMES_PRIORITY, _HOLDEFFECT_DITTO_SPEED_UP, _POK_ID,
    _HOLDEFFECT_EVS_UP_SPEED_DOWN, _HOLDEFFECT_LVLUP_EV_UP, _HOLDEFFECT_SPEED_DOWN_GROUNDED,
    _POK_CURRENT_HP, _POK_MAX_HP, _ABILITYNAMES_GLUTTONY, _HOLDEFFECT_PINCH_PRIORITY,
    _HOLDEFFECT_CHOICE_SPEED,
)
from Models.item import raw_hold_effect
from DataBase.PkDB import PokemonName

DITTO = PokemonName.DITTO
# Macho Brace, the Power items and Iron Ball (pokeplatinum sSpeedHalvingItemEffects)
SPEED_HALVING = (_HOLDEFFECT_EVS_UP_SPEED_DOWN, _HOLDEFFECT_LVLUP_EV_UP, _HOLDEFFECT_SPEED_DOWN_GROUNDED)


@njit
def quick_claw(pok):
    """Quick Claw's 20% to move first in its bracket, one roll per holder per turn (Showdown gen4
    onBeforeTurn; the chance is the item's effect param)"""
    return (
        pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_SOMETIMES_PRIORITY
        and random.randint(0, 99) < pok[_ITEM_EFFECT_PARAM]
    )


@njit
def pinch_hp(pok):
    """
    The pinch berries' HP check: at most max HP / its effect param (4), Gluttony halves the param
    (pokeplatinum BattleSystem_TriggerHeldItem, CompareBattlerSpeed)
    """
    divisor = pok[_ITEM_EFFECT_PARAM]
    if pok[_POK_AB_ID] == _ABILITYNAMES_GLUTTONY:
        divisor //= 2
    return pok[_POK_CURRENT_HP] <= pok[_POK_MAX_HP] // divisor


@njit
def custap_ready(pok):
    """A live Custap Berry holder in a pinch moves first in its bracket, like an activated Quick
    Claw (pokeplatinum CompareBattlerSpeed)"""
    return (
        pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_PINCH_PRIORITY
        and pok[_POK_CURRENT_HP] > 0
        and pinch_hp(pok)
    )


@njit
def slow_start_active(pok):
    """
    Slow Start lasts the rest of the turn it came in plus 5 full turns (pokeplatinum
    slowStartTurnNumber = totalTurns + 1, active while totalTurns - it < 5)
    """
    return pok[_POK_AB_ID] == _ABILITYNAMES_SLOW_START and pok[_POK_TURNS_ACTIVE] <= 5


@njit
def _speed(pok, weather):
    """
    One Pokemon's speed in pokeplatinum BattleSystem_CompareBattlerSpeed order: stages (Simple
    doubles them) -> Swift Swim / Chlorophyll -> items -> Quick Feet or paralysis -> Slow Start ->
    Unburden -> Tailwind
    """
    speed = pok[_POK_SPEED]
    ab = pok[_POK_AB_ID]
    stage = pok[_POK_SPEED_STAT_STAGE]
    if ab == _ABILITYNAMES_SIMPLE:
        stage = max(-6, min(6, stage * 2))
    # Apply Stat stages if necessary
    if stage != 0:
        speed = stage_to_multiplier(stage, speed)
    speed_ab = pok[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_MODIFY_SPEED
    if speed_ab:
        if weather == _WEATHER_SUN and ab == _ABILITYNAMES_CHLOROPHYLL:
            speed *= 2
        elif weather == _WEATHER_RAIN and ab == _ABILITYNAMES_SWIFT_SWIM:
            speed *= 2
    # Embargo doesn't stop the speed-halving items (pokeplatinum reads the raw heldItem there)
    if raw_hold_effect(pok) in SPEED_HALVING:
        speed //= 2
    elif pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_CHOICE_SPEED:
        speed = speed * 15 // 10
    elif pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_DITTO_SPEED_UP and pok[_POK_ID] == DITTO:
        speed *= 2
    if speed_ab and ab == _ABILITYNAMES_QUICK_FEET and pok[_POK_STATUS] != 0:
        speed = speed * 15 // 10
    elif pok[_POK_STATUS] == _STATUS_PARALYSIS:
        speed //= 4
    if speed_ab:
        if slow_start_active(pok):
            speed //= 2
        elif (
            ab == _ABILITYNAMES_UNBURDEN
            and pok[_POK_VOL_STATUS2] & _VOLSTATUS2_CAN_UNBURDEN
            and not pok[_ITEM_ID]
        ):
            speed *= 2
    # TODO: Tailwind ×2 goes here, last.
    return speed


@njit
def check_speed(p1, p2, weather):
    """Gives speed after modifications of stages, abilities, and paralysis (Showdown/Smogon-DP
    confirmed order: stat stage -> ability modifier -> item modifiers ->
    paralysis -> tailwind (not yet implemented). Paralysis is applied last, to the already-
    truncated result of the earlier steps, not multiplied in alongside them.)"""
    return _speed(p1, weather), _speed(p2, weather)
