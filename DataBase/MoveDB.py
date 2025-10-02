"""Database for moves in python, where it gives everything a move does"""  # pylint:disable=C0103
from types import SimpleNamespace


MoveName = SimpleNamespace(

    TACKLE = 1,
    GROWL = 2,
    SCRATCH = 3,
    TAIL_WHIP = 4,
    POUND = 5,
    LEER = 6,
    EMBER = 7,
    BUBBLE = 8,
    RAZOR_LEAF = 9,
    EXPLOSION = 10,
    SELFDESTRUCT = 11,
    FOCUS_PUNCH = 12,
    SUCKER_PUNCH = 13,
    FUTURE_SIGHT = 14,
    FAKE_OUT = 15,
    DREAM_EATER = 16,
    NIGHTMARE = 17,
    SWAGGER = 18,
    PSYCH_UP = 19,
    FLATTER = 20,
    DRAGON_DANCE = 21

)

MoveIdToName = {v: k for k, v in MoveName.__dict__.items() if not k.startswith("__")}