import json
import random
import math
#import numpy

class Pokemon:
    def __init__(self, name, base_data, level, ability, item, moves):
        self.name = name
        self.base_data = base_data
        self.level = level
        self.ability = ability
        self.item = item
        self.moves = moves
        self.types = base_data.get("type", [])   # added: list of types
        self.current_hp = self.calculate_hp()
        self.status = None # Burn, Freeze, Paralyze, Sleep

    def calculate_hp(self):
        base = self.base_data['base stats']['HP']
        iv = 31  # max: 31 for now
        ev = 0  # min: 0 for now
        lvl = self.level
        hp = ((2 * base + iv + (ev // 4)) * lvl) // 100 + lvl + 10
        return hp

with open("Database\PkDB.json","r") as f:
    pkDB = json.load(f)
with open("Database\AbilitiesDB.json","r") as f:
    abDB = json.load(f)
with open("Database\ItemDB.json","r") as f:
    itemDB = json.load(f)
with open("Database\MoveDB.json","r") as f:
    moveDB = json.load(f)
with open("Database\\TypeChart.json","r") as f:
    type_chart = json.load(f)
round = 1
charmander = Pokemon("Charmander", pkDB["Charmander"], 5, abDB["Blaze"], None, {
    1: moveDB["Scratch"],
    2: moveDB["Growl"]
})
squirtle = Pokemon("Squirtle", pkDB["Squirtle"], 5, abDB["Torrent"], None, {
    1: moveDB["Tackle"],
    2: moveDB["Tail Whip"]
})
myPartyPk = [charmander]
oppPartyPk = [squirtle]

def round_half_down(value: float) -> int:
    """Round to nearest integer with .5 rounded down."""
    flo = math.floor(value)
    frac = value - flo
    if frac > 0.5:
        return math.ceil(value)
    else:
        return flo

def get_type_effectiveness(atk_type, defender_types):
    mult = 1.0
    if atk_type not in type_chart:
        return 1.0
    for d in defender_types:
        # defender type key assumed to match chart keys
        mult *= float(type_chart[atk_type].get(d, 1.0))
    return mult

def calculate_damage(attacker, defender, move):
    if move['category'] == "Status":
        # Status moves don't deal damage
        return 0
    if move['category'] == 'Physical':
        attack = attacker.base_data['base stats']['Attack']
        defense = defender.base_data['base stats']['Defense']
    else:
        attack = attacker.base_data['base stats']['Special Attack']
        defense = defender.base_data['base stats']['Special Defense']

    damage = (((2 * attacker.level / 5 + 2) * attack * move['power'] / defense) / 50 + 2) * (random.randint(85, 100) / 100)

    # STAB
    if move['type'] in getattr(attacker, 'types', []):
        damage *= 1.5

    # type effectiveness
    effectiveness = get_type_effectiveness(move['type'], getattr(defender, 'types', []))
    damage *= effectiveness
    final_damage = round_half_down(damage)
    return final_damage, effectiveness

def battle_turn(p1, move1, p2, move2):
    if p1.base_data['base stats']['Speed'] > p2.base_data['base stats']['Speed']:
        order = [(p1, move1,p2), (p2, move2,p1)]
    else:
        order = [(p2, move2,p1), (p1, move1,p2)]
    for attacker, move, defender in order:
        if attacker.current_hp <= 0 or defender.current_hp <= 0:
            continue # Skip if either Pokémon is fainted

        damage, effectiveness = calculate_damage(attacker, defender, move)
        defender.current_hp -= damage
        print(f"{attacker.name} used {move['name']} on {defender.name}!")
        print(f"It dealt {damage} damage.")
        print(f"Effectiveness: {effectiveness}x")
        if defender.current_hp <= 0:
            print(f"{defender.name} has fainted!")
        else:
            print(f"{defender.name} has {defender.current_hp} HP left.")

battle_turn(charmander, moveDB["Scratch"], squirtle, moveDB["Tackle"])
