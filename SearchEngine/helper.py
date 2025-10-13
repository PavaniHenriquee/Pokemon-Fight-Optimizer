"""helper functions"""
import random
import copy
# import numpy as np
from DataBase.pok_sets import charmander, squirtle, bulbasaur
from Engine.engine_helper import to_battle_array
from Models.idx_const import Pok


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


def multiple_nodes(child, new_state):
    """Check to see if the current state needs to create a new node"""
    for c in child:
        c_my_active = c.state.get_my_active()
        c_opp_active = c.state.get_opp_active()
        new_my = new_state.get_my_active()
        new_opp = new_state.get_opp_active()
        has_phase = False
        has_same_opp = False
        my_status = False
        opp_status = False
        my_vol = False
        opp_vol = False
        # my_stat = False
        # opp_stat = False
        # Check to see if already considered that my pok died
        if c.state.phase == new_state.phase:
            # c.state = new_state
            # node = c
            has_phase = True
        # Check to see if already considered opp died
        if c.state.opp_active == new_state.opp_active:
            has_same_opp = True
        # Check to see if i got a different status
        if c_my_active[Pok.STATUS] == new_my[Pok.STATUS]:
            my_status = True
        # Check to see if the opp got a different status
        if c_opp_active[Pok.STATUS] == new_opp[Pok.STATUS]:
            opp_status = True
        # Check to see if i got a different vol_status
        if c_my_active[Pok.VOL_STATUS] == new_my[Pok.VOL_STATUS]:
            my_vol = True
        # Check to see if the opp got a different vol_status
        if c_opp_active[Pok.VOL_STATUS] == new_opp[Pok.VOL_STATUS]:
            opp_vol = True
        '''# Check to see if i got a different vol_status
        if np.array_equal(
            c_my_active[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE+1],
            new_my[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE+1]
        ):
            my_stat = True
        # Check to see if the opp got a different vol_status
        if np.array_equal(
            c_opp_active[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE+1],
            new_opp[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE+1]
        ):
            opp_stat = True'''

        # Found Node that fits
        if all((has_phase, has_same_opp, my_status, opp_status, opp_vol, my_vol)):
            c.state = new_state
            node = c
            return node

    return None
    