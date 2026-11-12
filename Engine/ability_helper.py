"""Ability checks shared by damage_calc and engine_helper"""
from Utils.jit import njit
from Models.idx_const import POK_LEN
from Models.constants import (
    _POK_AB_BREAKABLE, _POK_AB_ID, _ABILITYNAMES_MOLD_BREAKER, _ABILITYNAMES_LEVITATE,
    _POK_VOL_STATUS, _VOLSTATUS_INGRAIN, _POK_AB_KNOWN, _POK_CURRENT_HP, _FIELD_MY_POK,
    _FIELD_OPP_POK, _FIELD_WEATHER, _ABILITYNAMES_CLOUD_NINE, _ABILITYNAMES_AIR_LOCK,
    _ABILITYNAMES_NORMALIZE, _MOVE_ID, _MOVE_TYPE, _MOVENAME_STRUGGLE, _TYPES_NORMAL,
    _ITEM_HOLD_EFFECT, _HOLDEFFECT_SPEED_DOWN_GROUNDED, _MOVENAME_WEATHER_BALL, _MOVE_POWER,
    _WEATHER_SUN, _WEATHER_RAIN, _WEATHER_SANDSTORM, _WEATHER_HAIL, _TYPES_FIRE, _TYPES_WATER,
    _TYPES_ROCK, _TYPES_ICE, _ABILITYNAMES_FORECAST, _POK_TYPE1, _POK_TYPE2,
    _POK_MAGNET_RISE_TURNS,
)

# Abilities that switch the weather's effects off while their holder is out
WEATHER_SUPPRESSORS = (_ABILITYNAMES_CLOUD_NINE, _ABILITYNAMES_AIR_LOCK)
# Weather Ball's type per weather (pokeplatinum BtlCmd_CalcWeatherBallParams)
WEATHER_BALL_TYPES = (
    (_WEATHER_SUN, _TYPES_FIRE), (_WEATHER_RAIN, _TYPES_WATER), (_WEATHER_SANDSTORM, _TYPES_ROCK),
    (_WEATHER_HAIL, _TYPES_ICE)
)
# Castform's type per weather, sandstorm leaves it Normal (pokeplatinum FIELD_CONDITION_CASTFORM)
FORECAST_TYPES = ((_WEATHER_SUN, _TYPES_FIRE), (_WEATHER_RAIN, _TYPES_WATER), (_WEATHER_HAIL, _TYPES_ICE))


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
    Hidden Power and Natural Gift included
    """
    if attacker[_POK_AB_ID] == _ABILITYNAMES_NORMALIZE and move[_MOVE_ID] != _MOVENAME_STRUGGLE:
        return _TYPES_NORMAL
    return move[_MOVE_TYPE]


@njit
def weather_ball_type(weather):
    """The type Weather Ball takes under the weather its effects see, Normal under none"""
    for w, m_type in WEATHER_BALL_TYPES:
        if weather == w:
            return m_type
    return _TYPES_NORMAL


@njit
def slot_move_type(attacker, move, weather):
    """
    normalized_type for a move read off its slot, outside its own execution: Weather Ball takes the
    weather's type, unless Normalize makes it Normal (pokeplatinum Move_CalcVariableType)
    """
    if move[_MOVE_ID] == _MOVENAME_WEATHER_BALL and attacker[_POK_AB_ID] != _ABILITYNAMES_NORMALIZE:
        return weather_ball_type(weather)
    return normalized_type(attacker, move)


@njit
def weather_ball_move(move, weather):
    """
    Weather Ball under a weather has double power and the weather's type, under none (Cloud Nine
    included) it's Normal with its own power (Showdown onModifyType / onModifyMove). Other moves
    are returned as is
    """
    if move[_MOVE_ID] != _MOVENAME_WEATHER_BALL or weather == 0:
        return move
    mv = move.copy()
    mv[_MOVE_POWER] *= 2
    mv[_MOVE_TYPE] = weather_ball_type(weather)
    return mv


@njit
def forecast(pok, weather):
    """
    A living Forecast holder is Fire in sun, Water in rain, Ice in hail and Normal otherwise
    (pokeplatinum BattleSystem_TriggerFormChange; Showdown reads the effective weather, so Cloud
    Nine turns it back to Normal)
    """
    if pok[_POK_CURRENT_HP] <= 0 or pok[_POK_AB_ID] != _ABILITYNAMES_FORECAST:
        return
    new_type = _TYPES_NORMAL
    for w, f_type in FORECAST_TYPES:
        if weather == w:
            new_type = f_type
    pok[_POK_TYPE1] = new_type
    pok[_POK_TYPE2] = 0


@njit
def forecast_actives(battle_array):
    """Forecast for both actives, after anything that can change the weather they see"""
    weather = effective_weather(battle_array)
    for base in (battle_array[_FIELD_MY_POK] * POK_LEN, (battle_array[_FIELD_OPP_POK] + 6) * POK_LEN):
        forecast(battle_array[base:base + POK_LEN], weather)


@njit
def grounded_by_item(pok):
    """
    Iron Ball grounds its holder: Ground moves reach it through the Flying type and Levitate
    (pokeplatinum HOLD_EFFECT_SPEED_DOWN_GROUNDED)
    """
    return pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_SPEED_DOWN_GROUNDED


@njit
def magnet_risen(pok):
    """
    Magnet Rise keeps Ground moves off while its turns last, unless Ingrain or an Iron Ball
    ground the Pokemon (pokeplatinum BattleSystem_ApplyTypeChart). Gravity ends it
    """
    return (
        pok[_POK_MAGNET_RISE_TURNS] > 0
        and not pok[_POK_VOL_STATUS] & _VOLSTATUS_INGRAIN
        and not grounded_by_item(pok)
    )


@njit
def levitates(pok, attacker, gravity=False):
    """
    Levitate keeps Ground moves off unless the attacker has Mold Breaker. Gravity, Ingrain and
    Iron Ball switch it off
    """
    return (
        pok[_POK_AB_ID] == _ABILITYNAMES_LEVITATE
        and not gravity
        and not pok[_POK_VOL_STATUS] & _VOLSTATUS_INGRAIN
        and not grounded_by_item(pok)
        and ignorable_ability(pok, attacker)
    )


@njit
def effective_weather(battle_array):
    """
    The weather its effects see: none while a living active has Cloud Nine or Air Lock. The
    weather itself stays up and keeps counting down
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
