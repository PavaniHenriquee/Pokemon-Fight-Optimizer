"""Database for Items in python, where it gives the idx for Items name"""
from dataclasses import dataclass

@dataclass(slots=True)
class ItemNames:
    """Item names to number"""
    ORAN_BERRY   = 1
    SITRUS_BERRY = 2
