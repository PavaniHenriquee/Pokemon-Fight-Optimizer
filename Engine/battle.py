"""Battle class where it follows battle flow, doing the sequence selection, start of turn, actions,
end of turn and repeat"""
import random
from numba import njit
from Engine.engine_helper import (
    check_speed,
    move_order,
    calculate_hit_miss,
    calculate_crit,
    reset_switch_out,
    flinch_checker,
    thaw,
    after_turn_damage,
    early_returns,
    switch_in,
    contact_ability,
    heal_end_turn,
    on_residual,
    trainer_ai_items,
    drain
)
from Engine.status_calc import sec_effects, calculate_effects
from Engine.damage_calc import calculate_damage, struggle
from Models.trainer_ai import sub_after_death
from Models.idx_const import (
    POK_LEN, MOVE_STRIDE, OFFSET_MOVE
)
from Models.helper import (
    count_party, PHYSICAL_SPECIAL
)
from Models.constants import (
    _FIELD_OPP_POK, _FIELD_MY_POK, _FIELD_AI_TOOK_DMG_LAST_TURN, _FIELD_AI_ITEM1, _FIELD_WEATHER,
    _FIELD_AI_KNOWS, _FIELD_MY_LAST_MOVE, _FIELD_MY_ENTER_FIELD, _FIELD_OPP_ENTER_FIELD, _FIELD_TURN,
    _POK_AB_WHEN, _POK_CURRENT_HP, _POK_AB_ID, _POK_MAX_HP, _POK_STATUS, _POK_TURNS,
    _ABILITYACTIVATION_ON_CONTACT, _ABILITYACTIVATION_ON_RESIDUAL,
    _ABILITYNAMES_AFTERMATH, _ABILITYNAMES_DAMP, _FLAGS_CONTACT, _MOVE_POWER, _MOVE_ID, _MOVE_PP,
    _MOVE_CATEGORY, _MOVE_TYPE, _SEC_CHANCE, _SEC_VOL_STATUS, _MOVENAME_STRUGGLE, _MOVEOUTCOME_HIT,
    _VOLSTATUS_FLINCH, _STATUS_FREEZE, _ACTIONTYPE_MOVE, _BATTLEPHASE_TURN_START,
    _BATTLEPHASE_DEATH_END_OF_TURN, _FIELD_PHASE, _MOVE_DRAIN, _MOVE_MULTI_HIT_MIN, _MOVE_MULTI_HIT_MAX,
    _POK_VOL_STATUS, _VOLSTATUS_BIDE, _POK_DMG_TAKEN, _MOVE_CHARGE_RECHARGE, _POK_CHARGE_RECHARGE,
    _POK_LOCKED_MOVE
)
from Models.move import STRUGGLE


@njit
def start_of_turn(opp_move, switch_idx, battle_array):
    """What happens before everything in the turn order, so switches and trainer items"""
    # TODO: Opponent Items
    opp_switch = -1
    opp_active = battle_array[_FIELD_OPP_POK]
    my_active = battle_array[_FIELD_MY_POK]
    current_pokemon = battle_array[
        (my_active * POK_LEN):((my_active+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((opp_active+6) * POK_LEN):((opp_active+7) * POK_LEN)
    ]
    battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0
    if opp_move < 0:
        if opp_move <= -10:  #Item
            item_list = battle_array[_FIELD_AI_ITEM1:(_FIELD_AI_ITEM1+4)]
            slot = -(opp_move // 10) - 1  #Items are -10, -20, -30, -40
            trainer_ai_items(current_opp, item_list[slot])
        else:
            opp_switch = opp_move + 6 #Before I subtracted -6 from idx that's why +6 so it's 0..5

    if switch_idx >= 0 > opp_move >-10:
        my_s, opp_s = check_speed(
            current_pokemon, current_opp, battle_array[_FIELD_WEATHER]
        )
        speed_tie = False
        if my_s == opp_s:
            if random.getrandbits(1):
                speed_tie = True
        if my_s > opp_s or speed_tie:
            # My Pokemon
            reset_switch_out(current_pokemon)
            battle_array[_FIELD_MY_POK] = switch_idx
            battle_array[_FIELD_AI_KNOWS] = 0
            battle_array[_FIELD_MY_LAST_MOVE] = 0
            battle_array[_FIELD_MY_ENTER_FIELD] = 1
            current_pokemon = battle_array[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]
            switch_in(current_pokemon, current_opp)
            # Opponent Pokemon
            reset_switch_out(current_opp)
            battle_array[_FIELD_OPP_POK] = opp_switch
            battle_array[_FIELD_OPP_ENTER_FIELD] = 1
            current_opp = battle_array[
                ((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)
            ]
            switch_in(current_opp, current_pokemon)
        elif my_s < opp_s:
            # Opponent Pokemon
            reset_switch_out(current_opp)
            battle_array[_FIELD_OPP_POK] = opp_switch
            battle_array[_FIELD_OPP_ENTER_FIELD] = 1
            current_opp = battle_array[
                ((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)
            ]
            switch_in(current_opp, current_pokemon)
            # My Pokemon
            reset_switch_out(current_pokemon)
            battle_array[_FIELD_MY_POK] = switch_idx
            battle_array[_FIELD_AI_KNOWS] = 0
            battle_array[_FIELD_MY_LAST_MOVE] = 0
            battle_array[_FIELD_MY_ENTER_FIELD] = 1
            current_pokemon = battle_array[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]
            switch_in(current_pokemon, current_opp)
        return

    if opp_switch != -1:
        reset_switch_out(current_opp)
        battle_array[_FIELD_OPP_POK] = opp_switch
        battle_array[_FIELD_OPP_ENTER_FIELD] = 1
        current_opp = battle_array[
            ((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)
        ]
        switch_in(current_opp, current_pokemon)

    if switch_idx >= 0:
        reset_switch_out(current_pokemon)
        battle_array[_FIELD_MY_POK] = switch_idx
        battle_array[_FIELD_AI_KNOWS] = 0
        battle_array[_FIELD_MY_LAST_MOVE] = 0
        battle_array[_FIELD_MY_ENTER_FIELD] = 1
        current_pokemon = battle_array[
            (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
        ]
        switch_in(current_pokemon, current_opp)


MULTIHIT_PROB=(2,2,2,3,3,3,4,5)


@njit
def _ps_moves_core(attacker, defender, move, weather):
    """
    Finds crit, calculates and apply damage, check for contact abilities, if it applies flinch
    and if the defender dies checks for aftermath
    """
    ab_when = defender[_POK_AB_WHEN]
    crit = calculate_crit(ab_when)
    damage = calculate_damage(attacker, defender, move, weather, crit)
    flinch = False
    if damage < defender[_POK_CURRENT_HP]:
        defender[_POK_CURRENT_HP] -= damage
        if (
            move[_FLAGS_CONTACT]
            and (
                attacker[_POK_AB_ID] & _ABILITYACTIVATION_ON_CONTACT
                or defender[_POK_AB_ID] & _ABILITYACTIVATION_ON_CONTACT
            )
        ):
            contact_ability(attacker, defender)
        if move[_SEC_VOL_STATUS] & _VOLSTATUS_FLINCH:
            flinch = flinch_checker(move, defender)
    else:
        defender[_POK_CURRENT_HP] = 0
        # Aftermath damage after kill
        if (
            defender[_POK_AB_ID] == _ABILITYNAMES_AFTERMATH
            and move[_FLAGS_CONTACT]
            and move[_MOVE_POWER] != 0  # Becuase of moves like counter
            and attacker[_POK_AB_ID] != _ABILITYNAMES_DAMP
        ):
            dmg = attacker[_POK_MAX_HP] // 4
            if dmg < attacker[_POK_CURRENT_HP:]:
                attacker[_POK_CURRENT_HP] -= damage
            else:
                attacker[_POK_CURRENT_HP] = 0
                return False, damage # Both are dead so early return
    return flinch, damage


@njit
def ps_moves_multihit(attacker, defender, move, weather):
    """Physical or Special multihit moves, where I need to calculate damage and secondary effects"""
    mult_hit_min = move[_MOVE_MULTI_HIT_MIN]
    mult_hit_max = move[_MOVE_MULTI_HIT_MAX]
    dmg = 0
    flinch = False
    if mult_hit_min == 2 and mult_hit_max == 5:
        multhit = MULTIHIT_PROB[random.getrandbits(3)]
    elif mult_hit_min == mult_hit_max:
        multhit = mult_hit_min
    else:
        raise ValueError("Moves that are variable and not 2-5 shouldn't exit, check DB")
    for i in range(multhit):
        if i and early_returns(attacker, defender, 1, False, move):
            break
        flinch, damage = _ps_moves_core(attacker, defender, move, weather)
        dmg += damage

    # TODO: recoil
    if move[_MOVE_DRAIN]:
        drain(attacker, move, dmg)

    # Check for secondary effects and apply them
    if move[_SEC_CHANCE]:
        sec_effects(move, attacker, defender, weather)

    if defender[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        defender[_POK_DMG_TAKEN] += dmg

    return flinch


@njit
def ps_moves(attacker, defender, move, weather):
    """Physical or Special moves, where I need to calculate damage and secondary effects"""
    flinch, damage = _ps_moves_core(attacker, defender, move, weather)

    # TODO: recoil
    if move[_MOVE_DRAIN]:
        drain(attacker, move, damage)

    # Check for secondary effects and apply them
    if move[_SEC_CHANCE]:
        sec_effects(move, attacker, defender, weather)

    if defender[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        defender[_POK_DMG_TAKEN] += damage

    return flinch


@njit
def action(current_move, opp_move, battle_array):
    """Where the moves are calculated"""
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    weather = battle_array[_FIELD_WEATHER]
    p1_switch = False
    p2_switch = False
    flinch = False
    if current_move < 0 and opp_move < 0:
        return  # Check if neither used an action, if so early return
    if current_move < 0:
        p1_switch = True
    if opp_move < 0:  # Switches mid battle are (-6..-1) and potions are -10..-40
        # TODO: Check everything if opponent switches, specially if they die on entering
        p2_switch = True

    mv1_slot, mv2_slot, count, first_is_mine = move_order(
        current_pokemon,
        current_move,
        current_opp,
        opp_move,
        p1_switch,
        p2_switch,
        weather
    )
    if count == 0:
        return
    atk1 = current_pokemon if first_is_mine else current_opp
    def1 = current_opp     if first_is_mine else current_pokemon
    atk2 = current_opp     if first_is_mine else current_pokemon
    def2 = current_pokemon if first_is_mine else current_opp

    mv1 = (atk1[OFFSET_MOVE + mv1_slot * MOVE_STRIDE :
                OFFSET_MOVE + (mv1_slot + 1) * MOVE_STRIDE]
        if mv1_slot != 10 else STRUGGLE.copy())

    mv2 = (atk2[OFFSET_MOVE + mv2_slot * MOVE_STRIDE :
                OFFSET_MOVE + (mv2_slot + 1) * MOVE_STRIDE]
        if mv2_slot != 10 else STRUGGLE.copy())

    # ---- First move ----
    if count >= 1:
        if atk1[_POK_CURRENT_HP] > 0 and not early_returns(atk1, def1, 1, flinch, mv1):
            if mv1[_MOVE_ID] != _MOVENAME_STRUGGLE:
                mv1[_MOVE_PP] -= 1
                if first_is_mine:
                    battle_array[_FIELD_MY_LAST_MOVE] = mv1[_MOVE_ID]
            elif first_is_mine:
                battle_array[_FIELD_MY_LAST_MOVE] = -1
            # Charge moves are positive so they don't do anything first turn
            if mv1[_MOVE_CHARGE_RECHARGE] > 0 and atk1[_POK_LOCKED_MOVE] == -1:
                atk1[_POK_CHARGE_RECHARGE] = mv1[_MOVE_CHARGE_RECHARGE]
                atk1[_POK_LOCKED_MOVE] = current_move if first_is_mine else opp_move
            else:
                # Reset locked Move
                if mv1[_MOVE_CHARGE_RECHARGE] > 0:
                    atk1[_POK_LOCKED_MOVE] = -1
                move_hit = calculate_hit_miss(mv1, atk1, def1, weather)
                if move_hit == _MOVEOUTCOME_HIT:
                    if mv1[_MOVE_ID] == _MOVENAME_STRUGGLE:
                        struggle(atk1, def1)
                    elif mv1[_MOVE_CATEGORY] in PHYSICAL_SPECIAL:
                        if mv1[_MOVE_MULTI_HIT_MIN]:
                            flinch = ps_moves_multihit(atk1, def1, mv1, weather)
                        else:
                            flinch = ps_moves(atk1, def1, mv1, weather)
                        # Information for trainer ai logic
                        if first_is_mine:
                            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = mv1[_MOVE_TYPE]
                        # Check to see if the move from the attacker thawed the defender
                        if def1[_POK_STATUS] == _STATUS_FREEZE:
                            thaw(mv1, def1)
                    else:
                        calculate_effects(atk1, def1, mv1, weather)

    # ---- Second move ----
    if count >= 2:
        if atk2[_POK_CURRENT_HP] > 0 and not early_returns(atk2, def2, 2, flinch, mv2):
            if mv2[_MOVE_ID] != _MOVENAME_STRUGGLE:
                mv2[_MOVE_PP] -= 1
                if not first_is_mine:
                    battle_array[_FIELD_MY_LAST_MOVE] = mv2[_MOVE_ID]
            elif not first_is_mine:
                battle_array[_FIELD_MY_LAST_MOVE] = -1

            if mv2[_MOVE_CHARGE_RECHARGE] > 0 and atk2[_POK_LOCKED_MOVE] == -1:
                atk2[_POK_CHARGE_RECHARGE] = mv2[_MOVE_CHARGE_RECHARGE]
                atk2[_POK_LOCKED_MOVE] = opp_move if first_is_mine else current_move
            else:
                # Reset locked Move
                if mv2[_MOVE_CHARGE_RECHARGE] > 0:
                    atk2[_POK_LOCKED_MOVE] = -1
                move_hit = calculate_hit_miss(mv2, atk2, def2, weather)
                if move_hit == _MOVEOUTCOME_HIT:
                    if mv2[_MOVE_ID] == _MOVENAME_STRUGGLE:
                        struggle(atk2, def2)
                    elif mv2[_MOVE_CATEGORY] in PHYSICAL_SPECIAL:
                        if mv2[_MOVE_MULTI_HIT_MIN]:
                            _ = ps_moves_multihit(atk2, def2, mv2, weather)
                        else:
                            _ = ps_moves(atk2, def2, mv2, weather)
                        # Information for trainer ai
                        if not first_is_mine:
                            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = mv2[_MOVE_TYPE]
                        # Check to see if the move from the attacker thawed the defender
                        if def2[_POK_STATUS] == _STATUS_FREEZE:
                            thaw(mv2, def2)
                    else:
                        calculate_effects(atk2, def2, mv2, weather)


@njit
def end_of_turn(battle_array):
    """Does end of turn calculations like switch if dead, burn, poison, leech seed, ...,\n
    items like leftovers\n
    Weather damage like hail, sandstorm"""
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    weather = battle_array[_FIELD_WEATHER]
    m_hp = current_pokemon[_POK_CURRENT_HP]
    opp_hp = current_opp[_POK_CURRENT_HP]
    my_enter_field = battle_array[_FIELD_MY_ENTER_FIELD]
    opp_enter_field = battle_array[_FIELD_OPP_ENTER_FIELD]
    m_abi = current_pokemon[_POK_AB_ID]
    o_abi = current_opp[_POK_AB_ID]

    # TODO: Items
    # TODO: Weather finish before what happens to pokemon

    # Calculate after turn status like burn, leech seed, curse
    if m_hp > 0:
        heal_end_turn(current_pokemon, weather)
        dmg = after_turn_damage(current_pokemon, weather)
        if dmg != 0:
            if dmg > m_hp:
                m_hp = 0
            else:
                m_hp -= dmg
                if m_abi & _ABILITYACTIVATION_ON_RESIDUAL:
                    on_residual(current_pokemon, my_enter_field)
                if my_enter_field:
                    battle_array[_FIELD_MY_ENTER_FIELD] = 0
            current_pokemon[_POK_CURRENT_HP] = m_hp
        else:
            if m_abi & _ABILITYACTIVATION_ON_RESIDUAL:
                on_residual(current_pokemon, my_enter_field)
            if my_enter_field:
                battle_array[_FIELD_MY_ENTER_FIELD] = 0
    if opp_hp > 0:
        heal_end_turn(current_opp, weather)
        dmg = after_turn_damage(current_opp, weather)
        if dmg != 0:
            if dmg > opp_hp:
                opp_hp = 0
            else:
                opp_hp -= dmg
                if o_abi & _ABILITYACTIVATION_ON_RESIDUAL:
                    on_residual(current_opp, opp_enter_field)
                if opp_enter_field:
                    battle_array[_FIELD_OPP_ENTER_FIELD] = 0
            current_opp[_POK_CURRENT_HP] = opp_hp
        else:
            if m_abi & _ABILITYACTIVATION_ON_RESIDUAL:
                on_residual(current_pokemon, my_enter_field)
            if opp_enter_field:
                battle_array[_FIELD_OPP_ENTER_FIELD] = 0

    # If Opponent is dead
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    if opp_hp == 0 and m_hp != 0:
        if count_party(opp_pty) == 0:
            return -1
        i = sub_after_death(
            opp_pty, current_pokemon, current_opp
        )
        battle_array[_FIELD_OPP_POK] = i
        battle_array[_FIELD_MY_LAST_MOVE] = 0
        battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0
        current_opp = opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
        switch_in(current_pokemon, current_opp)
        return i
    return -1


@njit
def turn_sim(opp_move, current_action, battle_array):
    """One turn"""
    if current_action[0] == _ACTIONTYPE_MOVE:
        switch_idx = -1
        current_move = current_action[1]
    else:
        current_move = -1
        switch_idx = current_action[1]
    start_of_turn(opp_move, switch_idx, battle_array)
    action(current_move, opp_move, battle_array)
    opp_idx = end_of_turn(battle_array)
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]

    if opp_idx == -1:
        opp_idx = battle_array[_FIELD_OPP_POK]
    if current_pokemon[_POK_CURRENT_HP] <= 0:
        return _BATTLEPHASE_DEATH_END_OF_TURN, opp_idx

    battle_array[_FIELD_TURN] += 1
    current_opp[_POK_TURNS] += 1
    current_pokemon[_POK_TURNS] += 1
    return _BATTLEPHASE_TURN_START, opp_idx


def switch_in_action(battle_array, switch_idx: int):
    """Grab the switch idx from MCTS and progress it"""
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    my_pty = battle_array[0:(6 * POK_LEN)]
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    if current_opp[_POK_CURRENT_HP] <= 0:
        i = sub_after_death(
            opp_pty, current_pokemon, current_opp
        )
        opp_switch = opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
        my_switch = my_pty[
            (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
        ]

        my_s, opp_s = check_speed(
            my_switch, opp_switch, battle_array[_FIELD_WEATHER]
        )
        speed_tie= False
        if my_s == opp_s:
            if random.getrandbits(1):
                speed_tie = True

        if my_s > opp_s or speed_tie:
            # My Pokemon
            battle_array[_FIELD_MY_POK] = switch_idx
            battle_array[_FIELD_AI_KNOWS] = 0
            current_pokemon = my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]

            # Opponent Pokemon
            current_opp = opp_switch
            battle_array[_FIELD_OPP_POK] = i
            battle_array[_FIELD_MY_LAST_MOVE] = 0
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0

            # Switch in effects after they are already switched
            switch_in(current_pokemon, current_opp)
            switch_in(current_opp, current_pokemon)
        elif my_s < opp_s:
            # Opponent Pokemon
            battle_array[_FIELD_OPP_POK] = i
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0
            current_opp = opp_switch

            # My Pokemon
            battle_array[_FIELD_MY_POK] = switch_idx
            battle_array[_FIELD_AI_KNOWS] = 0
            battle_array[_FIELD_MY_LAST_MOVE] = 0
            current_pokemon = my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]

            # Switch in effects after they are already switched
            switch_in(current_opp, current_pokemon)
            switch_in(current_pokemon, current_opp)

        battle_array[_FIELD_TURN] += 1
        current_opp[_POK_TURNS] += 1
        current_pokemon[_POK_TURNS] += 1
        battle_array[_FIELD_PHASE] = _BATTLEPHASE_TURN_START
        return
    battle_array[_FIELD_MY_POK] = switch_idx
    current_pokemon = my_pty[
        (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
    ]
    battle_array[_FIELD_TURN] += 1
    current_opp[_POK_TURNS] += 1
    current_pokemon[_POK_TURNS] += 1
    battle_array[_FIELD_AI_KNOWS] = 0
    battle_array[_FIELD_MY_LAST_MOVE] = 0
    battle_array[_FIELD_PHASE] = _BATTLEPHASE_TURN_START
