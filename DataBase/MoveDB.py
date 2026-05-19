"""Database for moves in python, where it gives everything a move does"""
from dataclasses import dataclass
from DataBase.loader import moveDB


@dataclass(slots=True)
class MoveName:
    """
    Move names to number
    """
    TACKLE = 1
    GROWL = 2
    SCRATCH = 3
    TAIL_WHIP = 4
    POUND = 5
    LEER = 6
    EMBER = 7
    BUBBLE = 8
    RAZOR_LEAF = 9
    EXPLOSION = 10
    SELFDESTRUCT = 11
    FOCUS_PUNCH = 12
    SUCKER_PUNCH = 13
    FUTURE_SIGHT = 14
    FAKE_OUT = 15
    DREAM_EATER = 16
    NIGHTMARE = 17
    SWAGGER = 18
    PSYCH_UP = 19
    FLATTER = 20
    DRAGON_DANCE = 21


MoveIdToName = {v: k for k, v in MoveName.__dict__.items() if not k.startswith("__")}


def _build_category_sets():
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
    return frozenset(physical), frozenset(special)

PHYSICAL, SPECIAL = _build_category_sets()
