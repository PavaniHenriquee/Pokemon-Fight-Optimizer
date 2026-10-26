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
    AERIAL_ACE      = ACID + 1
    AGILITY         = AERIAL_ACE + 1
    AIR_CUTTER      = AGILITY + 1
    AMNESIA         = AIR_CUTTER + 1
    AQUA_JET        = AMNESIA + 1
    AQUA_RING       = AQUA_JET + 1
    ARM_THRUST      = AQUA_RING + 1
    ASSURANCE       = ARM_THRUST + 1
    ASTONISH        = ASSURANCE + 1
    ATTRACT         = ASTONISH + 1
    AURORA_BEAM     = ATTRACT + 1
    BARRIER         = AURORA_BEAM + 1
    BATON_PASS      = BARRIER + 1
    BIDE            = BATON_PASS + 1
    BIND            = BIDE + 1
    BITE            = BIND + 1
    BONE_CLUB       = BITE + 1
    BOUNCE          = BONE_CLUB + 1
    BRICK_BREAK     = BOUNCE + 1
    BUBBLE          = BRICK_BREAK + 1
    BUBBLE_BEAM     = BUBBLE + 1
    BUG_BITE        = BUBBLE_BEAM + 1
    BULK_UP         = BUG_BITE + 1
    BULLDOZE        = BULK_UP + 1
    BULLET_SEED     = BULLDOZE + 1
    CHARGE          = BULLET_SEED + 1
    CHARM           = CHARGE + 1
    CLAMP           = CHARM + 1
    COMET_PUNCH     = CLAMP + 1
    CONFUSE_RAY     = COMET_PUNCH + 1
    CONFUSION       = CONFUSE_RAY + 1
    COPYCAT         = CONFUSION + 1
    COUNTER         = COPYCAT + 1
    COVET           = COUNTER + 1
    CURSE           = COVET + 1
    DEFENSE_CURL    = CURSE + 1
    DESTINY_BOND    = DEFENSE_CURL + 1
    DIG             = DESTINY_BOND + 1
    DISARMING_VOICE = DIG + 1
    DOUBLE_KICK     = DISARMING_VOICE + 1
    DOUBLE_SLAP     = DOUBLE_KICK + 1
    DOUBLE_TEAM     = DOUBLE_SLAP + 1
    DRAGON_BREATH   = DOUBLE_TEAM + 1
    DRAGON_DANCE    = DRAGON_BREATH + 1
    DRAGON_RAGE     = DRAGON_DANCE + 1
    DRAINING_KISS   = DRAGON_RAGE + 1
    DREAM_EATER     = DRAINING_KISS + 1
    EMBER           = DREAM_EATER + 1
    ENCORE          = EMBER + 1
    ENDURE          = ENCORE + 1
    EXPLOSION       = ENDURE + 1
    EXTRASENSORY    = EXPLOSION + 1
    EXTREME_SPEED   = EXTRASENSORY + 1
    FAKE_OUT        = EXTREME_SPEED + 1
    FAKE_TEARS      = FAKE_OUT + 1
    FEINT           = FAKE_TEARS + 1
    FEINT_ATTACK    = FEINT + 1
    FIRE_FANG       = FEINT_ATTACK + 1
    FIRE_PUNCH      = FIRE_FANG + 1
    FIRE_SPIN       = FIRE_PUNCH + 1
    FLAIL           = FIRE_SPIN + 1
    FLAME_WHEEL     = FLAIL + 1
    FLASH           = FLAME_WHEEL + 1
    FLATTER         = FLASH + 1
    FOCUS_ENERGY    = FLATTER + 1
    FOCUS_PUNCH     = FOCUS_ENERGY + 1
    FOLLOW_ME       = FOCUS_PUNCH + 1
    FORCE_PALM      = FOLLOW_ME + 1
    FORESIGHT       = FORCE_PALM + 1
    FURY_ATTACK     = FORESIGHT + 1
    FURY_CUTTER     = FURY_ATTACK + 1
    FURY_SWIPES     = FURY_CUTTER + 1
    FUTURE_SIGHT    = FURY_SWIPES + 1
    GRASS_WHISTLE   = FUTURE_SIGHT + 1
    GROWL           = GRASS_WHISTLE + 1
    GROWTH          = GROWL + 1
    GUST            = GROWTH + 1
    GYRO_BALL       = GUST + 1
    HARDEN          = GYRO_BALL + 1
    HEADBUTT        = HARDEN + 1
    HELPING_HAND    = HEADBUTT + 1
    HIDDEN_POWER    = HELPING_HAND + 1
    HORN_ATTACK     = HIDDEN_POWER + 1
    HOWL            = HORN_ATTACK + 1
    HYPER_BEAM      = HOWL + 1
    HYPER_FANG      = HYPER_BEAM + 1
    HYPNOSIS        = HYPER_FANG + 1
    ICE_BALL        = HYPNOSIS + 1
    ICY_WIND        = ICE_BALL + 1
    INGRAIN         = ICY_WIND + 1
    IRON_DEFENSE    = INGRAIN + 1
    IRON_HEAD       = IRON_DEFENSE + 1
    KARATE_CHOP     = IRON_HEAD + 1
    KINESIS         = KARATE_CHOP + 1
    KNOCK_OFF       = KINESIS + 1
    LEECH_SEED      = KNOCK_OFF + 1
    LEER            = LEECH_SEED + 1
    LICK            = LEER + 1
    LIGHT_SCREEN    = LICK + 1
    LOW_KICK        = LIGHT_SCREEN + 1
    LUCKY_CHANT     = LOW_KICK + 1
    MACH_PUNCH      = LUCKY_CHANT + 1
    MAGICAL_LEAF    = MACH_PUNCH + 1
    MAGNITUDE       = MAGICAL_LEAF + 1
    MEDITATE        = MAGNITUDE + 1
    MEGA_DRAIN      = MEDITATE + 1
    METAL_CLAW      = MEGA_DRAIN + 1
    METRONOME       = METAL_CLAW + 1
    MIRROR_COAT     = METRONOME + 1
    MIRROR_MOVE     = MIRROR_COAT + 1
    MIST            = MIRROR_MOVE + 1
    MUD_BOMB        = MIST + 1
    MUD_SHOT        = MUD_BOMB + 1
    MUD_SPORT       = MUD_SHOT + 1
    MUD_SLAP        = MUD_SPORT + 1
    NASTY_PLOT      = MUD_SLAP + 1
    NATURAL_GIFT    = NASTY_PLOT + 1
    NATURE_POWER    = NATURAL_GIFT + 1
    NIGHT_SHADE     = NATURE_POWER + 1
    NIGHTMARE       = NIGHT_SHADE + 1
    ODOR_SLEUTH     = NIGHTMARE + 1
    PECK            = ODOR_SLEUTH + 1
    PERISH_SONG     = PECK + 1
    PIN_MISSILE     = PERISH_SONG + 1
    POISON_FANG     = PIN_MISSILE + 1
    POISON_POWDER   = POISON_FANG + 1
    POISON_STING    = POISON_POWDER + 1
    POUND           = POISON_STING + 1
    POWDER_SNOW     = POUND + 1
    PROTECT         = POWDER_SNOW + 1
    PSYBEAM         = PROTECT + 1
    PSYCH_UP        = PSYBEAM + 1
    PSYWAVE         = PSYCH_UP + 1
    PURSUIT         = PSYWAVE + 1
    QUICK_ATTACK    = PURSUIT + 1
    RAGE            = QUICK_ATTACK + 1
    RAIN_DANCE      = RAGE + 1
    RAPID_SPIN      = RAIN_DANCE + 1
    RAZOR_LEAF      = RAPID_SPIN + 1
    RECOVER         = RAZOR_LEAF + 1
    RECYCLE         = RECOVER + 1
    REFLECT         = RECYCLE + 1
    REFRESH         = REFLECT + 1
    ROAR            = REFRESH + 1
    ROCK_BLAST      = ROAR + 1
    ROCK_POLISH     = ROCK_BLAST + 1
    ROCK_SLIDE      = ROCK_POLISH + 1
    ROCK_THROW      = ROCK_SLIDE + 1
    ROCK_TOMB       = ROCK_THROW + 1
    ROLLOUT         = ROCK_TOMB + 1
    SAFEGUARD       = ROLLOUT + 1
    SAND_ATTACK     = SAFEGUARD + 1
    SANDSTORM       = SAND_ATTACK + 1
    SCARY_FACE      = SANDSTORM + 1
    SCREECH         = SCARY_FACE + 1
    SEISMIC_TOSS    = SCREECH + 1
    SELFDESTRUCT    = SEISMIC_TOSS + 1
    SHOCK_WAVE      = SELFDESTRUCT + 1
    SCRATCH         = SHOCK_WAVE + 1
    SILVER_WIND     = SCRATCH + 1
    SING            = SILVER_WIND + 1
    SLAM            = SING + 1
    SLEEP_POWDER    = SLAM + 1
    SLEEP_TALK      = SLEEP_POWDER + 1
    SMOG            = SLEEP_TALK + 1
    SMOKESCREEN     = SMOG + 1
    SPARK           = SMOKESCREEN + 1
    SPLASH          = SPARK + 1
    STEALTH_ROCK    = SPLASH + 1
    STOMP           = STEALTH_ROCK + 1
    STRING_SHOT     = STOMP + 1
    STRUGGLE        = STRING_SHOT + 1
    STUN_SPORE      = STRUGGLE + 1
    SUCKER_PUNCH    = STUN_SPORE + 1
    SUPERSONIC      = SUCKER_PUNCH + 1
    SWAGGER         = SUPERSONIC + 1
    SWEET_KISS      = SWAGGER + 1
    SWEET_SCENT     = SWEET_KISS + 1
    SWIFT           = SWEET_SCENT + 1
    SYNTHESIS       = SWIFT + 1
    TACKLE          = SYNTHESIS + 1
    TAIL_WHIP       = TACKLE + 1
    TAKE_DOWN       = TAIL_WHIP + 1
    TAUNT           = TAKE_DOWN + 1
    TELEPORT        = TAUNT + 1
    THUNDER_PUNCH   = TELEPORT + 1
    THUNDER_SHOCK   = THUNDER_PUNCH + 1
    THUNDER_WAVE    = THUNDER_SHOCK + 1
    TICKLE          = THUNDER_WAVE + 1
    TOXIC_SPIKES    = TICKLE + 1
    TRICK_ROOM      = TOXIC_SPIKES + 1
    TWINEEDLE       = TRICK_ROOM + 1
    UPROAR          = TWINEEDLE + 1
    VICE_GRIP       = UPROAR + 1
    VINE_WHIP       = VICE_GRIP + 1
    WATER_GUN       = VINE_WHIP + 1
    WATER_PULSE     = WATER_GUN + 1
    WATER_SPORT     = WATER_PULSE + 1
    WHIRLPOOL       = WATER_SPORT + 1
    WHIRLWIND       = WHIRLPOOL + 1
    WILL_O_WISP     = WHIRLWIND + 1
    WING_ATTACK     = WILL_O_WISP + 1
    WITHDRAW        = WING_ATTACK + 1
    WORRY_SEED      = WITHDRAW + 1
    WRAP            = WORRY_SEED + 1
    YAWN            = WRAP + 1
    ZEN_HEADBUTT    = YAWN + 1


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
