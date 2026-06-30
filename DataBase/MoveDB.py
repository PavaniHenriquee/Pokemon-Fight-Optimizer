"""Database for moves in python, where it gives everything a move does"""
from dataclasses import dataclass
from DataBase.loader import moveDB


@dataclass(slots=True)
class MoveName:
    """
    Move names to number
    """
    ABSORB          = 1
    ACID            = ABSORB + 1
    AMNESIA         = ACID + 1
    AQUA_JET        = AMNESIA + 1
    ARM_THRUST      = AQUA_JET + 1
    ASTONISH        = ARM_THRUST + 1
    BIDE            = ASTONISH + 1
    BITE            = BIDE + 1
    BONE_CLUB       = BITE + 1
    BRICK_BREAK     = BONE_CLUB + 1
    BUBBLE          = BRICK_BREAK + 1
    BUG_BITE        = BUBBLE + 1
    BULLDOZE        = BUG_BITE + 1
    BULLET_SEED     = BULLDOZE + 1
    CHARM           = BULLET_SEED + 1
    CONFUSE_RAY     = CHARM + 1
    CONFUSION       = CONFUSE_RAY + 1
    COUNTER         = CONFUSION + 1
    COVET           = COUNTER + 1
    CURSE           = COVET + 1
    DEFENSE_CURL    = CURSE + 1
    DIG             = DEFENSE_CURL + 1
    DISARMING_VOICE = DIG + 1
    DRAGON_DANCE    = DISARMING_VOICE + 1
    DRAGON_RAGE     = DRAGON_DANCE + 1
    DREAM_EATER     = DRAGON_RAGE + 1
    EMBER           = DREAM_EATER + 1
    EXPLOSION       = EMBER + 1
    FAKE_OUT        = EXPLOSION + 1
    FIRE_PUNCH      = FAKE_OUT + 1
    FLAIL           = FIRE_PUNCH + 1
    FLATTER         = FLAIL + 1
    FOCUS_ENERGY    = FLATTER + 1
    FOCUS_PUNCH     = FOCUS_ENERGY + 1
    FORCE_PALM      = FOCUS_PUNCH + 1
    FORESIGHT       = FORCE_PALM + 1
    FURY_CUTTER     = FORESIGHT + 1
    FURY_SWIPES     = FURY_CUTTER + 1
    FUTURE_SIGHT    = FURY_SWIPES + 1
    GRASS_WHISTLE   = FUTURE_SIGHT + 1
    GROWL           = GRASS_WHISTLE + 1
    GROWTH          = GROWL + 1
    GUST            = GROWTH + 1
    HARDEN          = GUST + 1
    HEADBUTT        = HARDEN + 1
    HIDDEN_POWER    = HEADBUTT + 1
    HOWL            = HIDDEN_POWER + 1
    HYPER_BEAM      = HOWL + 1
    HYPNOSIS        = HYPER_BEAM + 1
    INGRAIN         = HYPNOSIS + 1
    KARATE_CHOP     = INGRAIN + 1
    LEER            = KARATE_CHOP + 1
    LOW_KICK        = LEER + 1
    MEGA_DRAIN      = LOW_KICK + 1
    METAL_CLAW      = MEGA_DRAIN + 1
    METRONOME       = METAL_CLAW + 1
    MUD_SHOT        = METRONOME + 1
    MUD_SPORT       = MUD_SHOT + 1
    MUD_SLAP        = MUD_SPORT + 1
    NATURE_POWER    = MUD_SLAP + 1
    NIGHTMARE       = NATURE_POWER + 1
    PECK            = NATURE_POWER + 1
    POISON_STING    = PECK + 1
    POUND           = POISON_STING + 1
    PROTECT         = POUND + 1
    PSYCH_UP        = PROTECT + 1
    PURSUIT         = PSYCH_UP + 1
    QUICK_ATTACK    = PURSUIT + 1
    RAZOR_LEAF      = QUICK_ATTACK + 1
    ROAR            = RAZOR_LEAF + 1
    ROCK_POLISH     = ROAR + 1
    ROCK_THROW      = ROCK_POLISH + 1
    ROCK_TOMB       = ROCK_THROW + 1
    ROLLOUT         = ROCK_TOMB + 1
    SAND_ATTACK     = ROLLOUT + 1
    SANDSTORM       = SAND_ATTACK + 1
    SCARY_FACE      = SANDSTORM + 1
    SELFDESTRUCT    = SCARY_FACE + 1
    SHOCK_WAVE      = SELFDESTRUCT + 1
    SCRATCH         = SHOCK_WAVE + 1
    SING            = SCRATCH + 1
    SLAM            = SING + 1
    SLEEP_TALK      = SLAM + 1
    SPARK           = SLEEP_TALK + 1
    SPLASH          = SPARK + 1
    STEALTH_ROCK    = SPLASH + 1
    STOMP           = STEALTH_ROCK + 1
    STRING_SHOT     = STOMP + 1
    STRUGGLE        = STRING_SHOT + 1
    SUCKER_PUNCH    = STRUGGLE + 1
    SUPERSONIC      = SUCKER_PUNCH + 1
    SWAGGER         = SUPERSONIC + 1
    SWEET_SCENT     = SWAGGER + 1
    TACKLE          = SWEET_SCENT + 1
    TAIL_WHIP       = TACKLE + 1
    TAUNT           = TAIL_WHIP + 1
    THUNDER_PUNCH   = TAUNT + 1
    THUNDER_WAVE    = THUNDER_PUNCH + 1
    UPROAR          = THUNDER_WAVE + 1
    VINE_WHIP       = UPROAR + 1
    WATER_PULSE     = VINE_WHIP + 1
    WATER_SPORT     = WATER_PULSE + 1
    WING_ATTACK     = WATER_SPORT + 1
    WITHDRAW        = WING_ATTACK + 1
    WRAP            = WITHDRAW + 1
    ZEN_HEADBUTT    = WRAP + 1


MoveIdToName = {v: k for k, v in MoveName.__dict__.items() if not k.startswith("__")}


def _build_category_tuples():
    physical = {-1}  # Struggle is physical
    special = set()
    for move_data in moveDB.values():
        name_key = move_data["name"].upper()
        move_id = getattr(MoveName, name_key, None)
        if move_id is None:
            continue  # move in JSON but not yet in MoveName — skip silently
        category = move_data.get("category")
        if category == "Physical":
            physical.add(move_id)
        elif category == "Special":
            special.add(move_id)
    return tuple(physical), tuple(special)

def _build_type_tuples(typ):
    _type = set()
    for move_data in moveDB.values():
        name_key = move_data["name"].upper()
        move_id = getattr(MoveName, name_key, None)
        if move_id is None:
            continue  # move in JSON but not yet in MoveName — skip silently
        category = move_data.get("category")
        if category in ("Physical","Special"):
            ty = move_data.get("type")
            if ty == typ:
                _type.add(move_id)
    return tuple(_type)

PHYSICAL, SPECIAL = _build_category_tuples()
FIRE_MOVES = _build_type_tuples("Fire")
WATER_MOVES = _build_type_tuples("Water")
ELECTRIC_MOVES = _build_type_tuples("Electric")
FIRE_WATER_ELECTRIC = FIRE_MOVES + WATER_MOVES + ELECTRIC_MOVES
