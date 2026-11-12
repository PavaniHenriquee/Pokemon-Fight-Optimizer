"""What the engine can't run yet, for a trainer's team (the Setup picker, /start, the coverage report)"""
from DataBase.loader import moveDB, abDB, itemDB
from Models.constants import (
    _POTIONS_POTION, _POTIONS_SUPER_POTION, _POTIONS_HYPER_POTION,
    _POTIONS_FULL_RESTORE, _POTIONS_FULL_HEAL,
    _POTIONS_X_SPECIAL, _POTIONS_X_DEFEND, _POTIONS_X_SPEED,
)

# In MoveDB / AbilitiesDB but with no mechanics yet (ENGINE_PLAN.md's "in MoveDB" moves). It only shrinks:
# drop an entry in the batch that implements it
NOT_IMPLEMENTED = frozenset({
    # abilities
    "Color Change",
})


def team_lacks(team: list) -> list:
    """Sorted names a team uses that the engine can't run: moves not in MoveDB, held items not in ItemDB,
    and NOT_IMPLEMENTED moves and abilities"""
    lacks = set()
    for p in team:
        lacks |= {m for m in p.get("moves", []) if m and (m not in moveDB or m in NOT_IMPLEMENTED)}
        if p.get("item") and p["item"] not in itemDB:
            lacks.add(p["item"])
        if p.get("ability") in NOT_IMPLEMENTED or (p.get("ability") and p["ability"] not in abDB):
            lacks.add(p["ability"])
    return sorted(lacks)


# The trainer items the AI can use: TrainerDB's name -> the value a Field.AI_ITEM slot holds
TRAINER_ITEMS: dict[str, int] = {
    "Potion":       _POTIONS_POTION,
    "Super Potion": _POTIONS_SUPER_POTION,
    "Hyper Potion": _POTIONS_HYPER_POTION,
    "Full Restore": _POTIONS_FULL_RESTORE,
    "Full Heal":    _POTIONS_FULL_HEAL,
    "X Special":    _POTIONS_X_SPECIAL,
    "X Defend":     _POTIONS_X_DEFEND,
    "X Speed":      _POTIONS_X_SPEED,
}


def trainer_lacks(team: list, trainer_items: list) -> list:
    """team_lacks, then the trainer items TRAINER_ITEMS doesn't have"""
    return team_lacks(team) + sorted({i for i in trainer_items if i and i not in TRAINER_ITEMS})
