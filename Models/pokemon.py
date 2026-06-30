"""Pokemon class, so i can check each pokemon and its conditions and stats"""
import math
import numpy as np
from Utils.loader import natures
from DataBase.loader import pkDB, abDB, itemDB, moveDB
from DataBase.PkDB import PokemonName
from Models.helper import type_to_number, Status, gender_to_number
from Models.move import Moves
from Models.ability import ability_to_np
from Models.item import item_to_np


class Pokemon:
    """Pokemon class, so i can follow everything related to each pokemon"""
    def __init__(
            self,
            name: str,
            gender: str,
            level: int,
            ability: str,
            nature: str,
            moves: list[str],
            ivs: dict=None,
            evs: dict=None,
            status: str=0,
            item: str=None
    ):
        self.name = name
        self.base_data = pkDB[name]
        self.gender = gender  # Male, Female, None
        self.weight = int(self.base_data.get("weight"))
        self.level = level
        self.ability = abDB[ability]
        self.item = itemDB[item] if item else None
        self.move1 = moveDB[moves[0]] if len(moves) > 0 else None
        self.move2 = moveDB[moves[1]] if len(moves) > 1 else None
        self.move3 = moveDB[moves[2]] if len(moves) > 2 else None
        self.move4 = moveDB[moves[3]] if len(moves) > 3 else None
        self.moves = [m for m in [self.move1, self.move2, self.move3, self.move4] if m]
        self.types = self.base_data.get("type", [])
        self.status = status  # burn, freeze, paralysis, sleep
        self.badly_poison = 0  # if badly_poison it's how many turns
        self.sleep_counter = 0
        self.vol_status = []
        self.confusion = False
        self.attract = False
        self.nature = natures[nature]
        self.stat_stages = {
            'Attack': 0,
            'Defense': 0,
            'Special Attack': 0,
            'Special Defense': 0,
            'Speed': 0,
            'Accuracy': 0,
            'Evasion': 0
        }
        self.ivs = ivs if ivs else {
            'HP': 31,
            'Attack': 31,
            'Defense': 31,
            'Special Attack': 31,
            'Special Defense': 31,
            'Speed': 31
        }
        self.evs = evs if evs else {
            'HP': 0,
            'Attack': 0,
            'Defense': 0,
            'Special Attack': 0,
            'Special Defense': 0,
            'Speed': 0
        }
        self.max_hp = self.calculate_hp()
        self.attack = self.calculate_stat('Attack')
        self.defense = self.calculate_stat('Defense')
        self.special_attack = self.calculate_stat('Special Attack')
        self.special_defense = self.calculate_stat('Special Defense')
        self.speed = self.calculate_stat('Speed')
        self.current_hp = self.max_hp  # I use this to alter hp
        self.substitute = False
        self.leech_seed = False
        self.curse = False
        self.turns = 0
        self.fainted = False

    def calculate_hp(self):
        """Calculate HP"""
        base = self.base_data['base stats']['HP']
        iv = self.ivs['HP']
        ev = self.evs['HP']
        lvl = self.level
        hp = ((2 * base + iv + (ev // 4)) * lvl) // 100 + lvl + 10
        return hp

    def calculate_stat(self, stat_name):
        """Calculate every stat that's not HP"""
        base = self.base_data['base stats'][stat_name]
        iv = self.ivs[stat_name]
        ev = self.evs[stat_name]
        nat = self.nature[stat_name] if stat_name in self.nature else 1.0
        lvl = self.level
        stat = math.floor(((((2 * base + iv + (ev // 4)) * lvl) // 100) + 5) * nat)
        return stat

    def to_np(self):
        """Transforming everything in np array"""
        status_val = getattr(Status, self, self.status.upper()) if self.status else 0

        gender = gender_to_number(self.gender)

        type1, type2 = type_to_number(self.types)

        pok_enum = self.name.upper().replace("-", "_").replace(" ", "_")
        stats = np.array([
            getattr(PokemonName, pok_enum),  # ID
            self.level,  #Level
            type1,       #Type1
            type2,       #Type2
            self.current_hp,  #Current_hp
            self.max_hp,      #Max_HP
            self.attack,      #Attack
            self.defense,     #Defense
            self.special_attack,   #Special_attack
            self.special_defense,  #Special_defense
            self.speed,  #Speed
            self.stat_stages['Attack'],
            self.stat_stages['Defense'],
            self.stat_stages['Special Attack'],
            self.stat_stages['Special Defense'],
            self.stat_stages['Speed'],
            self.stat_stages['Accuracy'],
            self.stat_stages['Evasion'],
            status_val,
            0,  # this is for vol_status, which can't start a battle with any
            self.sleep_counter,
            self.badly_poison,
            0,   # This is dmg taken
            0,   # This is Charge Recharge
            -1,  # This is for Locked move -1 because move idx is 0-3
            self.turns,
            gender,
            self.weight
        ], dtype=np.int32)
        ability = ability_to_np(self.ability)

        move_helper = Moves(self.move1)
        move1 = move_helper.to_array()
        move_helper = Moves(self.move2)
        move2 = move_helper.to_array()
        move_helper = Moves(self.move3)
        move3 = move_helper.to_array()
        move_helper = Moves(self.move4)
        move4 = move_helper.to_array()

        item = item_to_np(self.item)

        pok_array = np.concatenate([stats, ability, move1, move2, move3, move4, item], dtype=np.int32)

        return pok_array
