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
        self.stat_stages = {
            'atk': 0,
            'def': 0,
            'spatk': 0,
            'spdef': 0,
            'spe': 0,
            'hp': 0
        }

    def calculate_hp(self):
        base = self.base_data['base stats']['HP']
        iv = 31  # max: 31 for now
        ev = 0  # min: 0 for now
        lvl = self.level
        hp = ((2 * base + iv + (ev // 4)) * lvl) // 100 + lvl + 10
        return hp