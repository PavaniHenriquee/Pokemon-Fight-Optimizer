"""Database for abilities in python, where it gives everything a move does""" 


class AbilityNames:
    """Abilty indexes for check"""
    ADAPTABILITY = 1
    AFTERMATH    = ADAPTABILITY + 1
    BATTLE_ARMOR = AFTERMATH + 1
    BLAZE        = BATTLE_ARMOR + 1
    CHLOROPHYLL  = BLAZE + 1
    DAMP         = CHLOROPHYLL + 1
    GUTS         = DAMP + 1
    HUGE_POWER   = GUTS + 1
    HUSTLE       = HUGE_POWER + 1
    ILLUMINATE   = HUSTLE + 1
    INNER_FOCUS  = ILLUMINATE + 1
    INTIMIDATE   = INNER_FOCUS + 1
    IRON_FIST    = INTIMIDATE + 1
    KEEN_EYE     = IRON_FIST + 1
    MAGIC_GUARD  = KEEN_EYE + 1
    MOLD_BREAKER = MAGIC_GUARD + 1
    NO_GUARD     = MOLD_BREAKER + 1
    OVERGROW     = NO_GUARD + 1
    PICKUP       = OVERGROW + 1
    POISON_POINT = PICKUP + 1
    RAIN_DISH    = POISON_POINT + 1
    RECKLESS     = RAIN_DISH + 1
    ROCK_HEAD    = RECKLESS + 1
    RUN_AWAY     = ROCK_HEAD + 1
    SAND_VEIL    = RUN_AWAY + 1
    SIMPLE       = SAND_VEIL + 1
    SOLAR_POWER  = SIMPLE + 1
    SOUNDPROOF   = SOLAR_POWER + 1
    SPEED_BOOST  = SOUNDPROOF + 1
    STEADFAST    = SPEED_BOOST + 1
    STURDY       = STEADFAST + 1
    SUCTION_CUPS = STURDY + 1
    SWIFT_SWIM   = SUCTION_CUPS + 1
    SYNCHRONIZE  = SWIFT_SWIM + 1
    THICK_FAT    = SYNCHRONIZE + 1
    TINTED_LENS  = THICK_FAT + 1
    TORRENT      = TINTED_LENS + 1
    UNBURDEN     = TORRENT + 1
    WATER_ABSORB = UNBURDEN + 1
