"""Effective speed, shared by turn order (engine_helper) and speed-based power (damage_calc)"""
from Utils.jit import njit
from Utils.helper import stage_to_multiplier
from Models.constants import (
    _POK_SPEED, _POK_STATUS, _STATUS_PARALYSIS, _POK_SPEED_STAT_STAGE, _POK_AB_WHEN,
    _ABILITYACTIVATION_ON_MODIFY_SPEED, _WEATHER_SUN, _ABILITYNAMES_CHLOROPHYLL, _WEATHER_RAIN,
    _ABILITYNAMES_SWIFT_SWIM, _POK_AB_ID
)


@njit
def check_speed(p1, p2, weather):
    """Gives speed after modifications of stages, abilities, and paralysis (Showdown/Smogon-DP
    confirmed order: stat stage -> ability modifier -> item modifier (not yet implemented) ->
    paralysis -> tailwind (not yet implemented). Paralysis is applied last, to the already-
    truncated result of the earlier steps, not multiplied in alongside them.)"""
    p1_speed = p1[_POK_SPEED]
    p2_speed = p2[_POK_SPEED]
    # Apply Stat stages if necessary
    if p1[_POK_SPEED_STAT_STAGE] != 0:
        p1_speed = stage_to_multiplier(p1[_POK_SPEED_STAT_STAGE], p1_speed)
    if p2[_POK_SPEED_STAT_STAGE] != 0:
        p2_speed = stage_to_multiplier(p2[_POK_SPEED_STAT_STAGE], p2_speed)
    ab_w1 = p1[_POK_AB_WHEN]
    ab_w2 = p2[_POK_AB_WHEN]
    if ab_w1 & _ABILITYACTIVATION_ON_MODIFY_SPEED:
        ab = p1[_POK_AB_ID]
        if weather == _WEATHER_SUN and ab == _ABILITYNAMES_CHLOROPHYLL:
            p1_speed *= 2
        elif weather == _WEATHER_RAIN and ab == _ABILITYNAMES_SWIFT_SWIM:
            p1_speed *= 2
    if ab_w2 & _ABILITYACTIVATION_ON_MODIFY_SPEED:
        ab = p2[_POK_AB_ID]
        if weather == _WEATHER_SUN and ab == _ABILITYNAMES_CHLOROPHYLL:
            p2_speed *= 2
        elif weather == _WEATHER_RAIN and ab == _ABILITYNAMES_SWIFT_SWIM:
            p2_speed *= 2
    # TODO: item modifiers (Choice Scarf ×1.5, Iron Ball/Macho Brace/Power items ×0.5,
    # Quick Powder ×2) go here once items are wired into the speed calc — before paralysis.
    if p1[_POK_STATUS] == _STATUS_PARALYSIS:
        p1_speed //= 4
    if p2[_POK_STATUS] == _STATUS_PARALYSIS:
        p2_speed //= 4
    # TODO: Tailwind ×2 goes here, last.
    return p1_speed, p2_speed
