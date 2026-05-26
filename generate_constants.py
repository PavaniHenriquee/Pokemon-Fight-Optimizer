"""
Automatically build constants for use with Numba
"""
from Models.idx_const import Pok, Move, Flags, Sec, Field, Item
from Models.helper import (
    MoveCategory, Types, Weather, AbilityActivation, Status, VolStatus, Gender,
    Enemy_AI_Knows, Potions, MoveOutcome
)
from DataBase.AbilitiesDB import AbilityNames
from DataBase.MoveDB import MoveName

def build_constants_file():
    """
    Easy def to write it out
    """

    with open("Models/constants.py", "w") as f:
        f.write("# AUTO-GENERATED CONSTANTS FILE\n")
        f.write("# Do not edit manually. Run generate_constants.py to update.\n\n")

        # Your exact loop logic, but writing to a file instead of setattr
        for _cls in (
            Pok, Move, Flags, Sec, Field, Item, MoveCategory, AbilityNames,
            Types, Weather, AbilityActivation, Status, MoveName, VolStatus,
            Gender, Enemy_AI_Knows, Potions, MoveOutcome
        ):
            f.write(f"# --- {_cls.__name__.upper()} CONSTANTS ---\n")
            for _attr, _val in vars(_cls).items():
                if _attr.isupper() and isinstance(_val, int):
                    # Writes exactly what VSCode wants to see: _POK_ID = 0
                    f.write(f"_{_cls.__name__.upper()}_{_attr} = {_val}\n")

            f.write("\n") # Add a blank line between classes

    print("Successfully generated constants.py")

if __name__ == "__main__":
    build_constants_file()
