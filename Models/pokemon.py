"""Pokemon class, so i can check each pokemon and its conditions and stats"""
import math
import numpy as np
from Utils.loader import natures
from DataBase.loader import pkDB, abDB, itemDB, moveDB
from DataBase.PkDB import PokemonName
from Models.helper import type_to_number, status_to_number, gender_to_number, vol_status
from Models.move import Move
from Models.ability import ability_to_np
from Models.item import item_to_np


class Pokemon:
    """Pokemon class, so i can follow everything related to each pokemon"""
    def __init__(self, name: str, gender, level, ability, nature, moves, ivs=None, evs=None, status=0, item=None):
        self.name = name
        self.base_data = pkDB[name]
        self.gender = gender  # Male, Female, None
        self.weight = self.base_data.get("weight", 1)
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
        status_val = status_to_number(self.status)

        gender = gender_to_number(self.gender)

        type1, type2 = type_to_number(self.types)

        stats = np.array([
            PokemonName[self.name.upper()],
            self.level,
            type1,
            type2,
            self.current_hp,
            self.max_hp,
            self.attack,
            self.defense,
            self.special_attack,
            self.special_defense,
            self.speed,
            self.stat_stages['Attack'],
            self.stat_stages['Defense'],
            self.stat_stages['Special Attack'],
            self.stat_stages['Special Defense'],
            self.stat_stages['Speed'],
            self.stat_stages['Accuracy'],
            self.stat_stages['Evasion'],
            status_val,
            vol_status(),
            self.sleep_counter,
            self.badly_poison,
            self.turns,
            gender,
            self.weight
        ], dtype=np.float32)
        ability = ability_to_np(self.ability)

        move_helper = Move(self.move1)
        move1 = move_helper.to_array()
        move_helper = Move(self.move2)
        move2 = move_helper.to_array()
        move_helper = Move(self.move3)
        move3 = move_helper.to_array()
        move_helper = Move(self.move4)
        move4 = move_helper.to_array()

        item = item_to_np(self.item)

        pok_array = np.concatenate([stats, ability, move1, move2, move3, move4, item], dtype=np.float32)  # pylint:disable=E1123

        return pok_array
