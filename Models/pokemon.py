from Utils.loader import natures
from DataBase.loader import pkDB, abDB, itemDB, moveDB
import math

class Pokemon:
    def __init__(self, name, gender, level, ability, nature, moves, ivs=None, evs=None, status = None, item = None):
        self.name = name
        self.base_data = pkDB[name]
        self.gender = gender # Male, Female, None
        self.level = level
        self.ability = abDB[ability]
        self.item = itemDB[item] if item else None
        self.move1 = moveDB[moves[0]] if len(moves) > 0 else None
        self.move2 = moveDB[moves[1]] if len(moves) > 1 else None
        self.move3 = moveDB[moves[2]] if len(moves) > 2 else None
        self.move4 = moveDB[moves[3]] if len(moves) > 3 else None
        self.moves = [m for m in [self.move1, self.move2, self.move3, self.move4] if m]
        self.types = self.base_data.get("type", [])
        self.status = status # burn, freeze, paralyze, sleep
        self.badly_poison = False
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
        self.current_hp = self.max_hp #I use this to alter hp
        self.substitute = False
        self.leech_seed = False
        self.curse = False
        self.fainted = False

    def calculate_hp(self):
        base = self.base_data['base stats']['HP']
        iv = self.ivs['HP']
        ev = self.evs['HP']
        lvl = self.level
        hp = ((2 * base + iv + (ev // 4)) * lvl) // 100 + lvl + 10
        return hp
    
    def calculate_stat(self, stat_name):
        base = self.base_data['base stats'][stat_name]
        iv = self.ivs[stat_name]
        ev = self.evs[stat_name]
        nat = self.nature[stat_name] if stat_name in self.nature else 1.0
        lvl = self.level
        stat = math.floor(((((2*base + iv + (ev // 4))*lvl)//100) + 5)*nat)
        return stat