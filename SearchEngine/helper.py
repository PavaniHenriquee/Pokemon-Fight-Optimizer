"""helper functions"""
import random
import copy
from DataBase.pok_sets import charmander, squirtle, bulbasaur
from Engine.engine_helper import to_battle_array


def create_random_initial_state():
    """random team selector"""
    team_pool = [charmander, squirtle, bulbasaur]

    def random_team(pool, max_size=3):
        size = random.randint(1, max_size)  # random team size 1–3
        chosen = random.sample(pool, size)  # pick without replacement
        team = [copy.deepcopy(p) for p in chosen]  # make independent copies
        random.shuffle(team)  # randomize order
        return team

    my_team = random_team(team_pool)
    opp_team = random_team(team_pool)
    battle_array = to_battle_array(my_team, opp_team)
    return battle_array
