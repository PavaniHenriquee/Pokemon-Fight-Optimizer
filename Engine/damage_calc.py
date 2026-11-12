"""Damage calculations"""
import random
import numpy as np
from Utils.jit import njit
from Utils.helper import get_type_effectiveness
from Engine.speed import check_speed, slow_start_active, has_tailwind
from DataBase.PkDB import PokemonName, POKEMON_BASE_ATK, POKEMON_BASE_DEF
from Models.constants import (
    _MOVE_TYPE,
    _ABILITYNAMES_BLAZE, _ABILITYNAMES_TORRENT, _ABILITYNAMES_OVERGROW,
    _POK_AB_ID, _ABILITYNAMES_GUTS, _POK_STATUS, _ABILITYNAMES_HUGE_POWER,
    _ABILITYNAMES_HUSTLE, _MOVE_OH_KO, _MOVE_CATEGORY, _MOVECATEGORY_PHYSICAL,
    _POK_ATTACK, _POK_DEFENSE, _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE,
    _POK_SPECIAL_ATTACK, _POK_SPECIAL_DEFENSE, _POK_SPECIAL_ATTACK_STAT_STAGE,
    _POK_SPECIAL_DEFENSE_STAT_STAGE, _WEATHER_SANDSTORM, _POK_TYPE1, _TYPES_ROCK,
    _POK_TYPE2, _POK_AB_WHEN, _ABILITYACTIVATION_ON_MODIFY_STAT, _POK_CURRENT_HP,
    _POK_MAX_HP, _TYPES_FIRE, _TYPES_WATER, _TYPES_GRASS, _ABILITYNAMES_IRON_FIST,
    _FLAGS_PUNCH, _STATUS_BURN, _WEATHER_SUN, _WEATHER_RAIN, _MOVE_POWER,
    _POK_LEVEL, _ABILITYNAMES_RECKLESS, _MOVE_RECOIL,
    _MOVE_HAS_CRASH_DAMAGE, _ABILITYNAMES_SIMPLE, _ABILITYNAMES_SOLAR_POWER,
    _ABILITYNAMES_THICK_FAT, _TYPES_ICE, _ABILITYNAMES_TINTED_LENS, _MOVE_ID, _MOVENAME_FLAIL,
    _MOVENAME_LOW_KICK, _MOVENAME_MAGNITUDE, _MOVENAME_FURY_CUTTER, _MOVENAME_ROLLOUT,
    _MOVENAME_ICE_BALL, _MOVENAME_ASSURANCE, _MOVENAME_GUST, _POK_WEIGHT, _POK_CONSEC_COUNT,
    _POK_VOL_STATUS, _VOLSTATUS_DEFENSE_CURL, _VOLSTATUS_HURT_THIS_TURN,
    _VOLSTATUS_FORESIGHT, _VOLSTATUS_INGRAIN, _VOLSTATUS_CHARGE,
    _VOLSTATUS_MUD_SPORT, _VOLSTATUS_WATER_SPORT, _TYPES_NORMAL, _TYPES_FIGHTING, _TYPES_GHOST,
    _TYPES_GROUND, _TYPES_FLYING, _TYPES_ELECTRIC, _MOVECATEGORY_SPECIAL, _MOVENAME_BRICK_BREAK,
    _SIDECONDITION_REFLECT, _SIDECONDITION_LIGHT_SCREEN, _ABILITYNAMES_ADAPTABILITY,
    _MOVENAME_GYRO_BALL, _MOVENAME_BOUNCE, _MOVENAME_DIG, _MOVENAME_EARTHQUAKE, _MOVENAME_STOMP,
    _POK_SEMI_INV_MOVE, _POK_VOL_STATUS2, _VOLSTATUS2_MINIMIZE, _POK_ID, _ITEM_HOLD_EFFECT,
    _ITEM_EFFECT_PARAM, _ITEM_EFFECT_TYPE, _HOLDEFFECT_TYPE_BOOST, _HOLDEFFECT_PIKA_SPATK_UP,
    _HOLDEFFECT_POWER_UP_PHYS, _HOLDEFFECT_POWER_UP_SE, _HOLDEFFECT_CUBONE_ATK_UP,
    _MOVENAME_EXPLOSION, _MOVENAME_SELFDESTRUCT, _ABILITYNAMES_SWARM, _TYPES_BUG,
    _ABILITYNAMES_TECHNICIAN, _MOVENAME_STRUGGLE, _ABILITYNAMES_RIVALRY, _POK_GENDER,
    _GENDER_GENDERLESS, _ABILITYNAMES_HEATPROOF, _ABILITYNAMES_DRY_SKIN, _ABILITYNAMES_FILTER,
    _ABILITYNAMES_SOLID_ROCK, _ABILITYNAMES_SNIPER, _ABILITYNAMES_UNAWARE, _ABILITYNAMES_PURE_POWER,
    _ABILITYNAMES_MARVEL_SCALE, _ABILITYNAMES_FLOWER_GIFT, _ABILITYNAMES_SCRAPPY,
    _VOLSTATUS2_FLASH_FIRE, _HOLDEFFECT_BOOST_REPEATED, _POK_METRONOME_COUNT,
    _HOLDEFFECT_POWER_UP_SPEC, _HOLDEFFECT_CLAMPERL_SPATK, _HOLDEFFECT_CLAMPERL_SPDEF,
    _HOLDEFFECT_LATI_SPECIAL, _HOLDEFFECT_DIALGA_BOOST, _HOLDEFFECT_PALKIA_BOOST,
    _HOLDEFFECT_CHOICE_ATK, _HOLDEFFECT_CHOICE_SPATK,
    _HOLDEFFECT_GIRATINA_BOOST, _HOLDEFFECT_DITTO_DEF_UP, _TYPES_DRAGON, _TYPES_STEEL,
    _HOLDEFFECT_HP_DRAIN_ON_ATK, _WEATHER_HAIL, _MOVENAME_SOLAR_BEAM,
    _MOVENAME_FLY, _MOVENAME_DIVE, _MOVENAME_SHADOW_FORCE, _MOVENAME_HURRICANE,
    _MOVENAME_SKY_UPPERCUT, _MOVENAME_THUNDER, _MOVENAME_SURF, _MOVENAME_WHIRLPOOL,
    _MOVENAME_REVERSAL, _MOVENAME_GRASS_KNOT, _MOVENAME_ERUPTION, _MOVENAME_WATER_SPOUT,
    _MOVENAME_WRING_OUT, _MOVENAME_CRUSH_GRIP, _MOVENAME_PUNISHMENT, _MOVENAME_TRUMP_CARD,
    _MOVENAME_FACADE, _MOVENAME_SMELLING_SALTS, _MOVENAME_WAKE_UP_SLAP, _STATUS_POISON,
    _STATUS_TOXIC, _STATUS_PARALYSIS, _STATUS_SLEEP, _MOVE_PP, _POK_EVASION_STAT_STAGE,
    _MOVENAME_RETURN, _MOVENAME_FRUSTRATION, _POK_FRIENDSHIP, _VOLSTATUS2_ROOST,
    _VOLSTATUS2_MIRACLE_EYE, _TYPES_PSYCHIC, _TYPES_DARK,
)
from Models.move import friendship_power
from Engine.ability_helper import ignorable_ability, normalized_type, grounded_by_item

# ==========================================
# 1. CONSTANTS & LOOKUPS
# ==========================================
MULTIPLIERS = (85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100)
STARTER_AB = (_ABILITYNAMES_BLAZE, _ABILITYNAMES_TORRENT, _ABILITYNAMES_OVERGROW, _ABILITYNAMES_SWARM)
THICK_F_TYPES = (_TYPES_FIRE, _TYPES_ICE)
DOUBLE_ATK_AB = (_ABILITYNAMES_HUGE_POWER, _ABILITYNAMES_PURE_POWER)
FILTER_AB = (_ABILITYNAMES_FILTER, _ABILITYNAMES_SOLID_ROCK)
STAGES_TABLE = (
    (2, 8), (2, 7), (2, 6), (2, 5), (2, 4), (2, 3), # -6 to -1
    (2, 2),                                         # 0
    (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2)  # +1 to +6
)
# (upper limit inclusive in hectograms, power), heavier than the last one is 120
WEIGHT_TO_POWER = ((100, 20), (250, 40), (500, 60), (1000, 80), (2000, 100))
# (roll 0..99 below this, power), the rest is 150
MAGNITUDE_TABLE = ((5, 10), (15, 30), (35, 50), (65, 70), (85, 90), (95, 110))
ROLLOUT_MOVES = (_MOVENAME_ROLLOUT, _MOVENAME_ICE_BALL)
SOLAR_DOWN_WEATHER = (_WEATHER_RAIN, _WEATHER_SANDSTORM, _WEATHER_HAIL)
# Pok.METRONOME_COUNT packs the Metronome item's move id above its count
METRONOME_MOVE_SHIFT = 4
METRONOME_COUNT_MASK = (1 << METRONOME_MOVE_SHIFT) - 1
FORESIGHT_TYPES = (_TYPES_NORMAL, _TYPES_FIGHTING)
# Semi-invulnerable moves by where the user is, and the moves that still reach it there
AIRBORNE_MOVES = (_MOVENAME_BOUNCE, _MOVENAME_FLY)
UNDERGROUND_MOVES = (_MOVENAME_DIG,)
UNDERWATER_MOVES = (_MOVENAME_DIVE,)
# Shadow Force vanishes: no move in the engine reaches it
VANISH_MOVES = (_MOVENAME_SHADOW_FORCE,)
SEMI_INVULNERABLE_MOVES = AIRBORNE_MOVES + UNDERGROUND_MOVES + UNDERWATER_MOVES + VANISH_MOVES
# pokeplatinum MOVE_EFFECT_NO_WEATHER_DAMAGE: no sandstorm or hail damage, no Ice Body heal
NO_WEATHER_MOVES = UNDERGROUND_MOVES + UNDERWATER_MOVES
# RP's Hurricane takes Twister's place, so it reaches Fly and Bounce and doubles there like it
HITS_AIRBORNE = (_MOVENAME_GUST, _MOVENAME_HURRICANE, _MOVENAME_SKY_UPPERCUT, _MOVENAME_THUNDER)
HITS_UNDERGROUND = (_MOVENAME_EARTHQUAKE, _MOVENAME_MAGNITUDE)
HITS_UNDERWATER = (_MOVENAME_SURF, _MOVENAME_WHIRLPOOL)
DOUBLES_AIRBORNE = (_MOVENAME_GUST, _MOVENAME_HURRICANE)
# Power drops with the user's HP / grows with the target's HP
HP_FALLOFF_MOVES = (_MOVENAME_ERUPTION, _MOVENAME_WATER_SPOUT)
WRING_OUT_MOVES = (_MOVENAME_WRING_OUT, _MOVENAME_CRUSH_GRIP)
# pokeplatinum BtlCmd_BeatUp reads the move's power, 10
BEAT_UP_POWER = 10
# Triple Kick's kicks are 10, 20 and 30 (pokeplatinum effect 0104 adds 10 per kick)
TRIPLE_KICK_STEP = 10
# pokeplatinum MON_CONDITION_FACADE_BOOST
FACADE_STATUSES = (_STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC, _STATUS_PARALYSIS)
# Gen IV: only Stomp doubles against a minimized target
MINIMIZE_DOUBLES = (_MOVENAME_STOMP,)
# They faint the user and, in Gen IV, halve the target's Defense
EXPLODE_MOVES = (_MOVENAME_EXPLOSION, _MOVENAME_SELFDESTRUCT)
PIKACHU = PokemonName.PIKACHU
# Thick Club works for both, Item.ITEM_USER only holds one
THICK_CLUB_USERS = (PokemonName.CUBONE, PokemonName.MAROWAK)
SOUL_DEW_USERS = (PokemonName.LATIAS, PokemonName.LATIOS)
CLAMPERL = PokemonName.CLAMPERL
DITTO = PokemonName.DITTO
DIALGA = PokemonName.DIALGA
PALKIA = PokemonName.PALKIA
# pokeplatinum checks the species, so both forms get the Griseous Orb boost
GIRATINA_FORMS = (PokemonName.GIRATINA, PokemonName.GIRATINA_ORIGIN)


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


@njit
def matchup_types(move_type, defender, gravity=False, scrappy=False):
    """
    Defender types the type chart reads. Foresight or the attacker's Scrappy drop the Ghost type
    against Normal and Fighting, Ingrain, Gravity and Iron Ball drop the Flying type against Ground, a
    dropped type is 0 (neutral). Roost drops it against every type for the turn (pokeplatinum
    BasicTypeMulApplies, TURN_FLAG_ROOSTING). Miracle Eye drops the Dark type against Psychic
    """
    t1 = defender[_POK_TYPE1]
    t2 = defender[_POK_TYPE2]
    if defender[_POK_VOL_STATUS2] & _VOLSTATUS2_ROOST:
        if t1 == _TYPES_FLYING:
            t1 = 0
        if t2 == _TYPES_FLYING:
            t2 = 0
    vol = defender[_POK_VOL_STATUS]
    if (vol & _VOLSTATUS_FORESIGHT or scrappy) and move_type in FORESIGHT_TYPES:
        if t1 == _TYPES_GHOST:
            t1 = 0
        if t2 == _TYPES_GHOST:
            t2 = 0
    if defender[_POK_VOL_STATUS2] & _VOLSTATUS2_MIRACLE_EYE and move_type == _TYPES_PSYCHIC:
        if t1 == _TYPES_DARK:
            t1 = 0
        if t2 == _TYPES_DARK:
            t2 = 0
    if (vol & _VOLSTATUS_INGRAIN or gravity or grounded_by_item(defender)) and move_type == _TYPES_GROUND:
        if t1 == _TYPES_FLYING:
            t1 = 0
        if t2 == _TYPES_FLYING:
            t2 = 0
    return t1, t2


@njit
def is_scrappy(attacker):
    """Scrappy's Normal and Fighting moves hit Ghost types (pokeplatinum ApplyTypeChart)"""
    return attacker[_POK_AB_ID] == _ABILITYNAMES_SCRAPPY


@njit
def flash_fire_damage(attacker, m_type, damage):
    """
    A Flash Fire holder that took a Fire move powers up its own Fire moves x15/10, after the
    weather (pokeplatinum CalcMoveDamage)
    """
    if m_type == _TYPES_FIRE and attacker[_POK_VOL_STATUS2] & _VOLSTATUS2_FLASH_FIRE:
        return damage * 15 // 10
    return damage


@njit
def gravity_types(move_type, t1, t2, gravity):
    """Gravity drops the Flying type against Ground, matchup_types for a bare type pair"""
    if gravity and move_type == _TYPES_GROUND:
        if t1 == _TYPES_FLYING:
            t1 = 0
        if t2 == _TYPES_FLYING:
            t2 = 0
    return t1, t2


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
        elif atk_ab in DOUBLE_ATK_AB:
            atk *= 2
        elif slow_start_active(attacker):
            atk //= 2
        elif atk_ab == _ABILITYNAMES_HUSTLE and not move[_MOVE_OH_KO]:
            atk = (atk * 3) // 2
        elif atk_ab == _ABILITYNAMES_FLOWER_GIFT and weather == _WEATHER_SUN:
            atk = (atk * 3) // 2
    else:
        if atk_ab == _ABILITYNAMES_SOLAR_POWER and weather == _WEATHER_SUN:
            atk = (atk * 3) // 2

    return atk


@njit
def ab_modify_def(attacker, defender, defense, physical, weather):
    """
    Defender abilities on its raw Defense / Sp. Def: Marvel Scale while statused, Flower Gift in sun
    (pokeplatinum BattleSystem_CalcMoveDamage). Mold Breaker ignores both
    """
    def_ab = defender[_POK_AB_ID]
    if not ignorable_ability(defender, attacker):
        return defense
    if physical:
        if def_ab == _ABILITYNAMES_MARVEL_SCALE and defender[_POK_STATUS] != 0:
            return defense * 15 // 10
    elif def_ab == _ABILITYNAMES_FLOWER_GIFT and weather == _WEATHER_SUN:
        return defense * 15 // 10
    return defense


@njit
def unaware_stages(attacker, defender, atk_stage, def_stage):
    """
    Unaware ignores the foe's stages: the defender's Def / Sp. Def when attacking, the attacker's
    Atk / Sp. Atk when defending (Mold Breaker ignores that side)
    """
    if attacker[_POK_AB_ID] == _ABILITYNAMES_UNAWARE:
        def_stage = 0
    if defender[_POK_AB_ID] == _ABILITYNAMES_UNAWARE and ignorable_ability(defender, attacker):
        atk_stage = 0
    return atk_stage, def_stage


@njit
def raw_atk_def(move, attacker, defender, weather=0, crit=False):
    """
    Getting the right attack and defense and applying the right modifiers
    """
    physical = move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL
    atk_is_simple = attacker[_POK_AB_ID] == _ABILITYNAMES_SIMPLE
    def_is_simple = (
        defender[_POK_AB_ID] == _ABILITYNAMES_SIMPLE and ignorable_ability(defender, attacker)
    )
    if physical:
        raw_attack = item_attack(attacker, attacker[_POK_ATTACK])
        raw_defense = item_defense(defender, defender[_POK_DEFENSE])
        atk_stage = attacker[_POK_ATTACK_STAT_STAGE]
        def_stage = defender[_POK_DEFENSE_STAT_STAGE]
    else:
        raw_attack = item_sp_attack(attacker, attacker[_POK_SPECIAL_ATTACK])
        raw_defense = item_sp_defense(defender, defender[_POK_SPECIAL_DEFENSE])
        atk_stage = attacker[_POK_SPECIAL_ATTACK_STAT_STAGE]
        def_stage = defender[_POK_SPECIAL_DEFENSE_STAT_STAGE]
        # Sandstorm Sp.Def boost for Rock types
        if (
            weather == _WEATHER_SANDSTORM
            and (
                defender[_POK_TYPE1] == _TYPES_ROCK
                or defender[_POK_TYPE2] == _TYPES_ROCK
            )
        ):
            raw_defense = (raw_defense * 3) // 2
    atk_stage, def_stage = unaware_stages(attacker, defender, atk_stage, def_stage)
    if crit:
        def_stage = min(def_stage, 0)
        atk_stage = max(atk_stage, 0)

    if attacker[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_MODIFY_STAT:
        raw_attack = ab_modify_stat(attacker, raw_attack, physical, move, weather)
    if defender[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_MODIFY_STAT:
        raw_defense = ab_modify_def(attacker, defender, raw_defense, physical, weather)

    attack = apply_stat_stage(raw_attack, atk_stage, atk_is_simple)
    defense = apply_stat_stage(raw_defense, def_stage, def_is_simple)
    # Gen IV Explosion and Selfdestruct halve the Defense after the stages (Showdown gen4 getDamage)
    if physical and move[_MOVE_ID] in EXPLODE_MOVES:
        defense = max(1, defense // 2)

    return attack, defense


@njit
def technician_power(attacker, move, power):
    """Technician: power 60 or less x15/10, after Charge and before items, never Struggle"""
    if (
        attacker[_POK_AB_ID] == _ABILITYNAMES_TECHNICIAN
        and move[_MOVE_ID] != _MOVENAME_STRUGGLE
        and power <= 60
    ):
        return power * 15 // 10
    return power


@njit
def rivalry_power(attacker, defender, power):
    """Rivalry: same gender x125/100, opposite x75/100, nothing if either is genderless"""
    if attacker[_POK_AB_ID] != _ABILITYNAMES_RIVALRY:
        return power
    atk_gender = attacker[_POK_GENDER]
    def_gender = defender[_POK_GENDER]
    if atk_gender == _GENDER_GENDERLESS or def_gender == _GENDER_GENDERLESS:
        return power
    if atk_gender == def_gender:
        return power * 125 // 100
    return power * 75 // 100


@njit
def base_power_ability(attacker, defender, move, power):
    """
    Ability and Sport power modifiers after the held item, in pokeplatinum BattleSystem_CalcMoveDamage
    order: Thick Fat, Sport, pinch abilities, Heatproof, Dry Skin, Rivalry, Iron Fist. Reckless
    stays last. Defender abilities are ignored by Mold Breaker
    """
    att_ab = attacker[_POK_AB_ID]
    m_type = normalized_type(attacker, move)
    def_ab = defender[_POK_AB_ID] if ignorable_ability(defender, attacker) else 0

    if def_ab == _ABILITYNAMES_THICK_FAT and m_type in THICK_F_TYPES:
        power //= 2

    power = sport_power(attacker, defender, move, power)

    # Pinch abilities
    if (
        att_ab in STARTER_AB
        and attacker[_POK_CURRENT_HP] / attacker[_POK_MAX_HP] <= 1 / 3
        and (
            (att_ab == _ABILITYNAMES_BLAZE and m_type == _TYPES_FIRE)
            or (att_ab == _ABILITYNAMES_TORRENT and m_type == _TYPES_WATER)
            or (att_ab == _ABILITYNAMES_OVERGROW and m_type == _TYPES_GRASS)
            or (att_ab == _ABILITYNAMES_SWARM and m_type == _TYPES_BUG)
        )
    ):
        power = power * 15 // 10

    if m_type == _TYPES_FIRE:
        if def_ab == _ABILITYNAMES_HEATPROOF:
            power //= 2
        elif def_ab == _ABILITYNAMES_DRY_SKIN:
            power = power * 125 // 100

    power = rivalry_power(attacker, defender, power)

    # Iron Fist
    if att_ab == _ABILITYNAMES_IRON_FIST and move[_FLAGS_PUNCH]:
        power = power * 12 // 10

    # Reckless
    if (
        att_ab == _ABILITYNAMES_RECKLESS
        and (
            move[_MOVE_RECOIL]
            or move[_MOVE_HAS_CRASH_DAMAGE]
        )
    ):
        power = power * 12 // 10

    return power


@njit
def orb_boosts(effect, species, move_type):
    """Adamant / Lustrous / Griseous Orb: their species' Dragon moves and its other type"""
    if effect == _HOLDEFFECT_DIALGA_BOOST:
        return species == DIALGA and move_type in (_TYPES_DRAGON, _TYPES_STEEL)
    if effect == _HOLDEFFECT_PALKIA_BOOST:
        return species == PALKIA and move_type in (_TYPES_DRAGON, _TYPES_WATER)
    if effect == _HOLDEFFECT_GIRATINA_BOOST:
        return species in GIRATINA_FORMS and move_type in (_TYPES_DRAGON, _TYPES_GHOST)
    return False


@njit
def item_power(attacker, move_type, category, power):
    """
    Held item power boosts in pokeplatinum BattleSystem_CalcMoveDamage order: type item, Light Ball,
    the Dialga / Palkia / Giratina orbs, Muscle Band, Wise Glasses. The boost is effect_param percent
    """
    effect = attacker[_ITEM_HOLD_EFFECT]
    if effect == _HOLDEFFECT_TYPE_BOOST and move_type == attacker[_ITEM_EFFECT_TYPE]:
        return power * (100 + attacker[_ITEM_EFFECT_PARAM]) // 100
    if effect == _HOLDEFFECT_PIKA_SPATK_UP and attacker[_POK_ID] == PIKACHU:
        return power * 2
    if orb_boosts(effect, attacker[_POK_ID], move_type):
        return power * (100 + attacker[_ITEM_EFFECT_PARAM]) // 100
    if effect == _HOLDEFFECT_POWER_UP_PHYS and category == _MOVECATEGORY_PHYSICAL:
        return power * (100 + attacker[_ITEM_EFFECT_PARAM]) // 100
    if effect == _HOLDEFFECT_POWER_UP_SPEC and category == _MOVECATEGORY_SPECIAL:
        return power * (100 + attacker[_ITEM_EFFECT_PARAM]) // 100
    return power


@njit
def item_attack(attacker, attack):
    """Choice Band x150/100, Thick Club doubles Cubone's and Marowak's Attack, before every ability"""
    if attacker[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_CHOICE_ATK:
        return attack * 150 // 100
    if (
        attacker[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_CUBONE_ATK_UP
        and attacker[_POK_ID] in THICK_CLUB_USERS
    ):
        return attack * 2
    return attack


@njit
def item_defense(defender, defense):
    """Metal Powder doubles Ditto's Defense (pokeplatinum BattleSystem_CalcMoveDamage)"""
    if defender[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_DITTO_DEF_UP and defender[_POK_ID] == DITTO:
        return defense * 2
    return defense


@njit
def item_sp_attack(attacker, sp_attack):
    """Choice Specs x150/100, Soul Dew x150/100 for Latias and Latios, DeepSeaTooth x2 for Clamperl"""
    effect = attacker[_ITEM_HOLD_EFFECT]
    if effect == _HOLDEFFECT_CHOICE_SPATK:
        return sp_attack * 150 // 100
    if effect == _HOLDEFFECT_LATI_SPECIAL and attacker[_POK_ID] in SOUL_DEW_USERS:
        return sp_attack * 150 // 100
    if effect == _HOLDEFFECT_CLAMPERL_SPATK and attacker[_POK_ID] == CLAMPERL:
        return sp_attack * 2
    return sp_attack


@njit
def item_sp_defense(defender, sp_defense):
    """Soul Dew x150/100 for Latias and Latios, DeepSeaScale x2 for Clamperl"""
    effect = defender[_ITEM_HOLD_EFFECT]
    if effect == _HOLDEFFECT_LATI_SPECIAL and defender[_POK_ID] in SOUL_DEW_USERS:
        return sp_defense * 150 // 100
    if effect == _HOLDEFFECT_CLAMPERL_SPDEF and defender[_POK_ID] == CLAMPERL:
        return sp_defense * 2
    return sp_defense


@njit
def crit_multiplier(attacker):
    """A crit doubles the damage, Sniper triples it (pokeplatinum BattleSystem_CalcCriticalMulti)"""
    return 3 if attacker[_POK_AB_ID] == _ABILITYNAMES_SNIPER else 2


@njit
def beat_up_damage(attacker, member, defender, crit):
    """One Beat Up hit from a party member: its base Attack and level against the target's base
    Defense, power 10, then the crit and the roll. Typeless, no stage, item, ability, weather or
    screen (pokeplatinum BtlCmd_BeatUp)"""
    damage = (
        POKEMON_BASE_ATK[member[_POK_ID]] * BEAT_UP_POWER * (member[_POK_LEVEL] * 2 // 5 + 2)
        // POKEMON_BASE_DEF[defender[_POK_ID]] // 50 + 2
    )
    if crit:
        damage *= crit_multiplier(attacker)
    return damage * MULTIPLIERS[random.getrandbits(4)] // 100


@njit
def life_orb_damage(attacker, damage):
    """Life Orb x(100+30)/100 after the crit, before the Metronome item (pokeplatinum
    BtlCmd_CalcDamage). Not in the AI's estimate, TrainerAI_CalcDamage skips it."""
    if attacker[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_HP_DRAIN_ON_ATK:
        return damage * (100 + attacker[_ITEM_EFFECT_PARAM]) // 100
    return damage


@njit
def filter_damage(attacker, defender, effectiveness, effectiveness2, damage):
    """
    Filter and Solid Rock cut a super effective hit to 3/4, at least 1, before Expert Belt
    (pokeplatinum BattleSystem_ApplyTypeChart). Mold Breaker ignores them
    """
    if (
        effectiveness * effectiveness2 > 4
        and defender[_POK_AB_ID] in FILTER_AB
        and ignorable_ability(defender, attacker)
    ):
        return max(1, damage * 3 // 4)
    return damage


@njit
def expert_belt(attacker, effectiveness, effectiveness2, damage):
    """Expert Belt boosts a super effective hit by effect_param percent"""
    if attacker[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_POWER_UP_SE and effectiveness * effectiveness2 > 4:
        return damage * (100 + attacker[_ITEM_EFFECT_PARAM]) // 100
    return damage


@njit
def screen_damage(category, move_id, def_side, crit, damage):
    """
    Reflect halves physical and Light Screen special damage in singles. A crit and Brick Break
    go through them (pokeplatinum BattleSystem_CalcDamage)
    """
    if crit or move_id == _MOVENAME_BRICK_BREAK:
        return damage
    if (
        (category == _MOVECATEGORY_PHYSICAL and def_side & _SIDECONDITION_REFLECT)
        or (category == _MOVECATEGORY_SPECIAL and def_side & _SIDECONDITION_LIGHT_SCREEN)
    ):
        return damage // 2
    return damage


@njit
def multipliers(
        move: np.ndarray, attacker: np.ndarray, defender: np.ndarray,
        weather:int, crit: bool, roll_mult: int, damage: int, def_side: int=0, gravity: bool=False
) -> int:
    """Calc multipliers for base formula damage, def_side is the defender's Field.SIDE_COND"""
    m_type = normalized_type(attacker, move)
    atk_type1 = attacker[_POK_TYPE1]
    atk_type2 = attacker[_POK_TYPE2]
    def_type1, def_type2 = matchup_types(m_type, defender, gravity, is_scrappy(attacker))

    # Burn
    if attacker[_POK_STATUS] == _STATUS_BURN:
        if (
            move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL
            and attacker[_POK_AB_ID] != _ABILITYNAMES_GUTS
        ):
            damage //= 2

    damage = screen_damage(move[_MOVE_CATEGORY], move[_MOVE_ID], def_side, crit, damage)

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
        # Solar Beam is halved in rain, sandstorm and hail (pokeplatinum FIELD_CONDITION_SOLAR_DOWN)
        if move[_MOVE_ID] == _MOVENAME_SOLAR_BEAM and w in SOLAR_DOWN_WEATHER:
            damage //= 2

    damage = flash_fire_damage(attacker, normalized_type(attacker, move), damage)

    # Adding 2 after the above
    damage += 2

    # Crit
    if crit:
        damage *= crit_multiplier(attacker)

    damage = life_orb_damage(attacker, damage)

    # Metronome item x(10+n)/10 (pokeplatinum BattleScript_CalcMoveDamage)
    if attacker[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_BOOST_REPEATED:
        damage = damage * (10 + (attacker[_POK_METRONOME_COUNT] & METRONOME_COUNT_MASK)) // 10

    # TODO: Me First

    # Roll Multiplier
    if roll_mult is None:
        roll_mult = MULTIPLIERS[random.getrandbits(4)]
    damage = (damage * roll_mult) // 100

    # STAB
    if m_type == atk_type1 or m_type == atk_type2:  # pylint: disable=R1714
        if attacker[_POK_AB_ID] == _ABILITYNAMES_ADAPTABILITY:
            damage *= 2
        else:
            damage = (damage*3) // 2

    # Effectiveness type 1
    effectiveness, _ = get_type_effectiveness(m_type, def_type1, 0)
    if effectiveness != 2:
        damage = (effectiveness * damage)//2

    # Effectiveness type 2
    effectiveness2 = 2  # Base is 2 since later //2
    if def_type2:
        effectiveness2, _ = get_type_effectiveness(m_type, def_type2, 0)
        if effectiveness2 != 2:
            damage = (effectiveness2 * damage)//2

    damage = filter_damage(attacker, defender, effectiveness, effectiveness2, damage)

    damage = expert_belt(attacker, effectiveness, effectiveness2, damage)

    # Tinted Lens
    if (
        attacker[_POK_AB_ID] == _ABILITYNAMES_TINTED_LENS
        and (effectiveness * effectiveness2 // 4) == 0
    ):
        damage *= 2

    # TODO: Berry

    return damage


@njit
def flail(attacker):
    """
    Flail and Reversal power from the user's HP bar in 64 pixels, at least 1 while it has HP
    (pokeplatinum BtlCmd_CalcFlailPower, App_PixelCount; Showdown gen4)
    """
    pixels = attacker[_POK_CURRENT_HP] * 64 // attacker[_POK_MAX_HP]
    if pixels == 0 and attacker[_POK_CURRENT_HP] > 0:
        pixels = 1
    if pixels <= 1:
        return 200
    if pixels <= 5:
        return 150
    if pixels <= 12:
        return 100
    if pixels <= 21:
        return 80
    if pixels <= 42:
        return 40
    return 20


@njit
def punishment_power(defender):
    """60 plus 20 per positive stage of the target, at most 200 (pokeplatinum
    BtlCmd_CalcPunishmentPower)"""
    boosts = 0
    for stat in range(_POK_ATTACK_STAT_STAGE, _POK_EVASION_STAT_STAGE + 1):
        if defender[stat] > 0:
            boosts += defender[stat]
    return min(60 + 20 * boosts, 200)


@njit
def trump_card_power(pp_left):
    """Trump Card power from the PP left after paying for it (pokeplatinum
    BtlCmd_CalcTrumpCardPower)"""
    if pp_left <= 0:
        return 200
    if pp_left == 1:
        return 80
    if pp_left == 2:
        return 60
    if pp_left == 3:
        return 50
    return 40


@njit
def weight_power(defender):
    """Low Kick power from the target's weight in hectograms"""
    weight = defender[_POK_WEIGHT]
    for limit, power in WEIGHT_TO_POWER:
        if weight <= limit:
            return power
    return 120


@njit
def magnitude_power():
    """Rolls Magnitude's power"""
    roll = random.randint(0, 99)
    for limit, power in MAGNITUDE_TABLE:
        if roll < limit:
            return power
    return 150


@njit
def gyro_ball_power(attacker, defender, weather, atk_side=0, def_side=0):
    """1 + 25 * target speed / user speed, up to 150, with both effective speeds, Tailwind
    included, Trick Room not (pokeplatinum monSpeedValues). atk_side / def_side are the user's and
    the target's Field.SIDE_COND"""
    user_speed, target_speed = check_speed(
        attacker, defender, weather, has_tailwind(atk_side), has_tailwind(def_side)
    )
    if user_speed < 1:
        return 1
    return min(150, 1 + 25 * target_speed // user_speed)


@njit
def semi_inv_power(defender, move_id, power):
    """
    Double power against a target hiding where the move reaches: Gust and Hurricane in the air,
    Earthquake and Magnitude underground, Surf and Whirlpool underwater (pokeplatinum POWER_MULTI 20)
    """
    hidden = defender[_POK_SEMI_INV_MOVE]
    if (
        (hidden in AIRBORNE_MOVES and move_id in DOUBLES_AIRBORNE)
        or (hidden in UNDERGROUND_MOVES and move_id in HITS_UNDERGROUND)
        or (hidden in UNDERWATER_MOVES and move_id in HITS_UNDERWATER)
    ):
        return power * 2
    return power


@njit
def variable_power(attacker, defender, move, weather=0, atk_side=0, def_side=0):
    """
    Base power for moves whose power depends on the battle state. Counters are only read here,
    the battle flow updates them
    """
    move_id = move[_MOVE_ID]
    power = move[_MOVE_POWER]
    if move_id == _MOVENAME_GYRO_BALL:
        return gyro_ball_power(attacker, defender, weather, atk_side, def_side)
    if move_id == _MOVENAME_FLAIL or move_id == _MOVENAME_REVERSAL:
        return flail(attacker)
    if move_id == _MOVENAME_LOW_KICK or move_id == _MOVENAME_GRASS_KNOT:
        return weight_power(defender)
    if move_id in HP_FALLOFF_MOVES:
        return max(power * attacker[_POK_CURRENT_HP] // attacker[_POK_MAX_HP], 1)
    if move_id in WRING_OUT_MOVES:
        return 1 + 120 * defender[_POK_CURRENT_HP] // defender[_POK_MAX_HP]
    if move_id == _MOVENAME_PUNISHMENT:
        return punishment_power(defender)
    if move_id == _MOVENAME_TRUMP_CARD:
        return trump_card_power(move[_MOVE_PP])
    # The user's friendship, so a called Return or Frustration has its own power too
    if move_id == _MOVENAME_RETURN or move_id == _MOVENAME_FRUSTRATION:
        return friendship_power(move_id, attacker[_POK_FRIENDSHIP])
    if move_id == _MOVENAME_FACADE and attacker[_POK_STATUS] in FACADE_STATUSES:
        return power * 2
    if move_id == _MOVENAME_SMELLING_SALTS and defender[_POK_STATUS] == _STATUS_PARALYSIS:
        return power * 2
    if move_id == _MOVENAME_WAKE_UP_SLAP and defender[_POK_STATUS] == _STATUS_SLEEP:
        return power * 2
    if move_id == _MOVENAME_MAGNITUDE:
        return semi_inv_power(defender, move_id, magnitude_power())
    if move_id in DOUBLES_AIRBORNE or move_id in HITS_UNDERGROUND or move_id in HITS_UNDERWATER:
        return semi_inv_power(defender, move_id, power)
    if move_id in MINIMIZE_DOUBLES and defender[_POK_VOL_STATUS2] & _VOLSTATUS2_MINIMIZE:
        return power * 2
    if move_id == _MOVENAME_FURY_CUTTER:
        return power << (max(attacker[_POK_CONSEC_COUNT], 1) - 1)
    if move_id in ROLLOUT_MOVES:
        power <<= max(attacker[_POK_CONSEC_COUNT], 1) - 1
        if attacker[_POK_VOL_STATUS] & _VOLSTATUS_DEFENSE_CURL:
            power *= 2
        return power
    if move_id == _MOVENAME_ASSURANCE and defender[_POK_VOL_STATUS] & _VOLSTATUS_HURT_THIS_TURN:
        return power * 2
    return power


@njit
def charge_power(attacker, move, power):
    """Charge doubles the power of the user's Electric move"""
    if attacker[_POK_VOL_STATUS] & _VOLSTATUS_CHARGE and normalized_type(attacker, move) == _TYPES_ELECTRIC:
        return power * 2
    return power


@njit
def sport_power(attacker, defender, move, power):
    """Mud Sport halves Electric power and Water Sport halves Fire power while either active has it"""
    vol = attacker[_POK_VOL_STATUS] | defender[_POK_VOL_STATUS]
    m_type = normalized_type(attacker, move)
    if m_type == _TYPES_ELECTRIC and vol & _VOLSTATUS_MUD_SPORT:
        return power // 2
    if m_type == _TYPES_FIRE and vol & _VOLSTATUS_WATER_SPORT:
        return power // 2
    return power



# ==========================================
# 4. CORE DAMAGE FUNCTIONS
# ==========================================
@njit
def calculate_damage(
        attacker: np.ndarray, defender: np.ndarray, move: np.ndarray,
        weather: int=0, crit: bool=False, roll_multiplier: int=None, def_side: int=0,
        gravity: bool=False, atk_side: int=0,
) -> int:
    """Standard damage calculation. def_side / atk_side are the defender's and the attacker's
    Field.SIDE_COND"""

    attack, defense = raw_atk_def(move, attacker, defender, weather, crit)

    power = charge_power(attacker, move, variable_power(attacker, defender, move, weather, atk_side, def_side))
    power = technician_power(attacker, move, power)
    power = item_power(attacker, normalized_type(attacker, move), move[_MOVE_CATEGORY], power)
    power = base_power_ability(attacker, defender, move, power)

    level = attacker[_POK_LEVEL]

    # Base damage formula
    damage = attack * power * (level * 2 // 5 + 2) // defense // 50

    return multipliers(
        move, attacker, defender, weather, crit, roll_multiplier, damage, def_side, gravity
    )


@njit
def future_damage(attacker, defender, move, weather=0, def_side=0):
    """
    Future Sight and Doom Desire's damage, fixed when the move is used: the base formula with the
    power chain, the target's screens, the weather, +2 and the roll. No crit, STAB, type chart,
    Life Orb, Metronome item, Filter, Expert Belt, Tinted Lens or resist berry (pokeplatinum
    BtlCmd_TryFutureSight: CalcMoveDamage with the data type, then CalcDamageVariance)
    """
    attack, defense = raw_atk_def(move, attacker, defender, weather, False)
    power = charge_power(attacker, move, variable_power(attacker, defender, move, weather, 0, def_side))
    power = technician_power(attacker, move, power)
    power = item_power(attacker, move[_MOVE_TYPE], move[_MOVE_CATEGORY], power)
    power = base_power_ability(attacker, defender, move, power)
    damage = attack * power * (attacker[_POK_LEVEL] * 2 // 5 + 2) // defense // 50
    damage = screen_damage(move[_MOVE_CATEGORY], move[_MOVE_ID], def_side, False, damage)
    if weather == _WEATHER_SUN:
        if move[_MOVE_TYPE] == _TYPES_FIRE:
            damage = damage * 3 // 2
        elif move[_MOVE_TYPE] == _TYPES_WATER:
            damage //= 2
    elif weather == _WEATHER_RAIN:
        if move[_MOVE_TYPE] == _TYPES_WATER:
            damage = damage * 3 // 2
        elif move[_MOVE_TYPE] == _TYPES_FIRE:
            damage //= 2
    damage += 2
    return damage * MULTIPLIERS[random.getrandbits(4)] // 100


@njit
def calculate_damage_confusion(pok):
    """Calculate the damage for Confusion self hit"""
    is_simple = pok[_POK_AB_ID] == _ABILITYNAMES_SIMPLE

    attack = item_attack(pok, pok[_POK_ATTACK])

    # Abilities affecting stat(equal logic to ab_mod_stat but without move), on the raw stat
    # before the stage like ab_modify_stat
    pok_ab = pok[_POK_AB_ID]
    if pok_ab == _ABILITYNAMES_GUTS and pok[_POK_STATUS] != 0:
        attack = (attack*3)//2
    elif pok_ab in DOUBLE_ATK_AB:
        attack *= 2
    elif slow_start_active(pok):
        attack //= 2
    elif pok_ab == _ABILITYNAMES_HUSTLE:
        attack = (attack*3)//2

    attack = apply_stat_stage(attack, pok[_POK_ATTACK_STAT_STAGE], is_simple)
    defense = apply_stat_stage(
        item_defense(pok, pok[_POK_DEFENSE]), pok[_POK_DEFENSE_STAT_STAGE], is_simple
    )

    # Confusion counts as a 40 power Normal move: Silk Scarf and Light Ball boost it, Muscle Band doesn't
    power = 40
    effect = pok[_ITEM_HOLD_EFFECT]
    if effect == _HOLDEFFECT_TYPE_BOOST and pok[_ITEM_EFFECT_TYPE] == _TYPES_NORMAL:
        power = power * (100 + pok[_ITEM_EFFECT_PARAM]) // 100
    elif effect == _HOLDEFFECT_PIKA_SPATK_UP and pok[_POK_ID] == PIKACHU:
        power *= 2
    # It hits itself, so a gendered Rivalry user always gets the same-gender boost
    power = rivalry_power(pok, pok, power)

    # Base damage formula
    damage = attack * power * (pok[_POK_LEVEL] * 2 // 5 + 2) // defense // 50
    if pok[_POK_STATUS] == _STATUS_BURN and pok_ab != _ABILITYNAMES_GUTS:
        damage //= 2
    # Adding 2 after the above
    damage += 2
    # Random Multiplier
    damage = (damage * MULTIPLIERS[random.getrandbits(4)]) // 100
    #TODO: Helping Hand
    #TODO: Power Split, Guard Split

    return damage




@njit
def calculate_ai_logic_damage(
        effectivenes, attacker, defender, move, weather, def_side=0, gravity=False
):
    """
    AI calculates damages from its damage a little different, so here i do it
    like it is in the games
    """
    attack, defense = raw_atk_def(move, attacker, defender, weather)

    # Ability
    # Pokemow: Gust / Hurricane, Earthquake and Surf / Whirlpool double against a hidden target
    power = charge_power(attacker, move, semi_inv_power(defender, move[_MOVE_ID], move[_MOVE_POWER]))
    power = technician_power(attacker, move, power)
    power = item_power(attacker, normalized_type(attacker, move), move[_MOVE_CATEGORY], power)
    power = base_power_ability(attacker, defender, move, power)

    level = attacker[_POK_LEVEL]

    # Base damage formula
    damage = attack * power * (level * 2 // 5 + 2) // defense // 50

    # Burn
    if attacker[_POK_STATUS] == _STATUS_BURN:
        if (
            move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL
            and attacker[_POK_AB_ID] != _ABILITYNAMES_GUTS
        ):
            damage //= 2

    damage = screen_damage(move[_MOVE_CATEGORY], move[_MOVE_ID], def_side, False, damage)

    # TODO: Targets

    # Weather
    if weather:
        w = weather
        m_type = normalized_type(attacker, move)
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
        # Solar Beam is halved in rain, sandstorm and hail (pokeplatinum FIELD_CONDITION_SOLAR_DOWN)
        if move[_MOVE_ID] == _MOVENAME_SOLAR_BEAM and w in SOLAR_DOWN_WEATHER:
            damage //= 2

    damage = flash_fire_damage(attacker, normalized_type(attacker, move), damage)

    # Adding 2 after the above
    damage += 2

    # pokeplatinum TrainerAI_CalcDamage runs the battle's type chart (BattleSystem_ApplyTypeChart):
    # STAB and each type, the AI's effectiveness only decides the immunities
    if effectivenes == 0:
        return 0
    m_type = normalized_type(attacker, move)
    if m_type == attacker[_POK_TYPE1] or m_type == attacker[_POK_TYPE2]:  # pylint: disable=R1714
        if attacker[_POK_AB_ID] == _ABILITYNAMES_ADAPTABILITY:
            damage *= 2
        else:
            damage = (damage*3) // 2
    def_type1, def_type2 = matchup_types(m_type, defender, gravity, is_scrappy(attacker))
    effectiveness1, _ = get_type_effectiveness(m_type, def_type1, 0)
    damage = (effectiveness1 * damage) // 2
    effectiveness2 = 2
    if def_type2:
        effectiveness2, _ = get_type_effectiveness(m_type, def_type2, 0)
        damage = (effectiveness2 * damage) // 2

    damage = filter_damage(attacker, defender, effectiveness1, effectiveness2, damage)
    damage = expert_belt(attacker, effectiveness1, effectiveness2, damage)

    if (
        attacker[_POK_AB_ID] == _ABILITYNAMES_TINTED_LENS
        and 0 < effectiveness1 * effectiveness2 < 4
    ):
        damage *= 2

    return int(damage)
