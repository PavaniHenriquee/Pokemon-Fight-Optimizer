"""
Helper to make the trainer ai more readable and everthing more organized
"""
from Models.idx_const import Pok, Move
from Models.helper import MoveCategory
from Utils.loader import TYPE_CHART
from DataBase.AbilitiesDB import AbilityNames


STAB_CORRECTNESS = {
    0.375: 0.25,
    0.75: 0.5,
    3.0: 2.0,
    6.0: 4.0
}
STAB_C = {0.375, 0.75, 3.0, 6.0}


def trainer_ai_effectiveness(move, ai_pok, user_pok):
    """
    How the AI consider type effectivness, which has some differences from
    how it usually goes
    """

    effectiveness = 1.0
    move_type = move[Move.TYPE]
    move_cat = move[Move.CATEGORY]
    ai_type1 = ai_pok[Pok.TYPE1]
    ai_type2 = ai_pok[Pok.TYPE2]
    ai_ability = ai_pok[Pok.AB_ID]
    user_type1 = user_pok[Pok.TYPE1]
    user_type2 = user_pok[Pok.TYPE2]

    # STAB
    if move_type == ai_type1 or move_type == ai_type2:  # pylint: disable=consider-using-in
        effectiveness *= 1.5 if ai_ability != AbilityNames.ADAPTABILITY else 2

    # Common type effectiveness
    # TODO: Scrappy, Mold Breaker, Odor Sleuth, Foresight,
    # Gastro Acid, Miracle Eye, Iron Ball
    # Gravity, Magnet Rise, Levitate, Wonder Guard, more...
    effectiveness *= TYPE_CHART[(move_type*19)+user_type1] / 2
    if user_type2:
        effectiveness *= TYPE_CHART[(move_type*19)+user_type2] / 4

    if move_cat != MoveCategory.STATUS:
        # TODO: Tinted Lens, Filter/Solid Rock, Expert Belt
        pass



    # Correct for the right effectiveness
    if effectiveness in STAB_C:
        effectiveness = STAB_CORRECTNESS[effectiveness]

    return effectiveness
