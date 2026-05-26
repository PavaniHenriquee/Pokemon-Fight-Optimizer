"""Battle class where it follows battle flow, doing the sequence selection, start of turn, actions,
end of turn and repeat"""
import random
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
    trainer_ai_items
)
from Engine.status_calc import sec_effects, calculate_effects
from Engine.damage_calc import calculate_damage, struggle
from Models.trainer_ai import sub_after_death
from Models.idx_const import (
    Pok, Field, Move, Flags, Sec, POK_LEN, MOVE_STRIDE, OFFSET_MOVE
)
from Models.helper import (
    count_party, Status, AbilityActivation,
    ActionType, BattlePhase, PHYSICAL_SPECIAL, MoveOutcome
)
from Models.move import STRUGGLE
from DataBase.AbilitiesDB import AbilityNames
from DataBase.MoveDB import MoveName


def start_of_turn(opp_move, switch_idx, battle_array):
    """What happens before everything in the turn order, so switches and trainer items"""
    # TODO: Opponent Items
    opp_switch = None
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    opp_active = battle_array[Field.OPP_POK]
    my_active = battle_array[Field.MY_POK]
    current_pokemon = battle_array[
        (my_active * POK_LEN):((my_active+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((opp_active+6) * POK_LEN):((opp_active+7) * POK_LEN)
    ]
    battle_array[Field.AI_TOOK_DMG_LAST_TURN] = 0
    if opp_move < 0:
        if opp_move <= -10:  #Item
            item_list = battle_array[Field.AI_ITEM1:(Field.AI_ITEM1+4)]
            slot = -(opp_move // 10) - 1  #Items are -10, -20, -30, -40
            trainer_ai_items(current_opp, item_list[slot])
        else:
            i = opp_move + 6  #Before i subtracted -6 from idx that's why add 6 so it's 0..5
            opp_switch = opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]

    if switch_idx >= 0 > opp_move >-10:
        my_s, opp_s = check_speed(
            current_pokemon, current_opp, battle_array[Field.WEATHER]
        )
        speed_tie = False
        if my_s == opp_s:
            if random.getrandbits(1):
                speed_tie = True
        if my_s > opp_s or speed_tie:
            # My Pokemon
            reset_switch_out(current_pokemon)
            battle_array[Field.MY_POK] = switch_idx
            battle_array[Field.AI_KNOWS] = 0
            battle_array[Field.MY_LAST_MOVE] = 0
            battle_array[Field.MY_ENTER_FIELD] = 1
            current_pokemon = battle_array[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]
            switch_in(current_pokemon, current_opp)
            # Opponent Pokemon
            reset_switch_out(current_opp)
            battle_array[Field.OPP_POK] = opp_switch
            battle_array[Field.OPP_ENTER_FIELD] = 1
            current_opp = battle_array[
                ((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)
            ]
            switch_in(current_opp, current_pokemon)
        elif my_s < opp_s:
            # Opponent Pokemon
            reset_switch_out(current_opp)
            battle_array[Field.OPP_POK] = opp_switch
            battle_array[Field.OPP_ENTER_FIELD] = 1
            current_opp = battle_array[
                ((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)
            ]
            switch_in(current_opp, current_pokemon)
            # My Pokemon
            reset_switch_out(current_pokemon)
            battle_array[Field.MY_POK] = switch_idx
            battle_array[Field.AI_KNOWS] = 0
            battle_array[Field.MY_LAST_MOVE] = 0
            battle_array[Field.MY_ENTER_FIELD] = 1
            current_pokemon = battle_array[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]
            switch_in(current_pokemon, current_opp)
        return

    if opp_switch:
        reset_switch_out(current_opp)
        battle_array[Field.OPP_POK] = opp_switch
        battle_array[Field.OPP_ENTER_FIELD] = 1
        current_opp = battle_array[
            ((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)
        ]
        switch_in(current_opp, current_pokemon)

    if switch_idx >= 0:
        reset_switch_out(current_pokemon)
        battle_array[Field.MY_POK] = switch_idx
        battle_array[Field.AI_KNOWS] = 0
        battle_array[Field.MY_LAST_MOVE] = 0
        battle_array[Field.MY_ENTER_FIELD] = 1
        current_pokemon = battle_array[
            (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
        ]
        switch_in(current_pokemon, current_opp)


def ps_moves(attacker, defender, move, weather):
    """Physical or Special moves, where I need to calculate damage and secondary effects"""
    ab_when = defender[Pok.AB_WHEN]
    if ab_when & AbilityActivation.ON_CRITICAL:
        crit = False
    else:
        crit = calculate_crit()
    damage = calculate_damage(attacker, defender, move, weather, crit)
    if damage <= defender[Pok.CURRENT_HP]:
        defender[Pok.CURRENT_HP] -= damage
        if (
            move[Flags.CONTACT]
            and (
                attacker[Pok.AB_ID] & AbilityActivation.ON_CONTACT
                or defender[Pok.AB_ID] & AbilityActivation.ON_CONTACT
            )
        ):
            contact_ability(attacker, defender)
    else:
        defender[Pok.CURRENT_HP] = 0
        # Aftermath damage after kill
        if (
            defender[Pok.AB_ID] == AbilityNames.AFTERMATH
            and move[Flags.CONTACT]
            and move[Move.POWER] != 0  # Becuase of moves like counter
            and attacker[Pok.AB_ID] != AbilityNames.DAMP
        ):
            dmg = attacker[Pok.MAX_HP] // 4
            if dmg <= attacker[Pok.CURRENT_HP:]:
                attacker[Pok.CURRENT_HP] -= damage
            else:
                attacker[Pok.CURRENT_HP] = 0
                return  # Both are dead so early return

    # TODO: recoil

    # Check for secondary effects and apply them
    if move[Sec.CHANCE] and defender[Pok.CURRENT_HP] > 0:
        sec_effects(move, attacker, defender, weather)


def action(current_move, opp_move, battle_array):
    """Where the moves are calculated"""
    current_pokemon = battle_array[
        (battle_array[Field.MY_POK] * POK_LEN):
        ((battle_array[Field.MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[Field.OPP_POK]+6) * POK_LEN):
        ((battle_array[Field.OPP_POK]+7) * POK_LEN)
    ]
    weather = battle_array[Field.WEATHER]
    p1_switch = False
    p2_switch = False
    flinch = False
    if current_move < 0 and opp_move < 0:
        return  # Check if neither used an action, if so early return
    if current_move < 0:
        p1_switch = True
    if opp_move < 0:  # Switches mid battle are (-6..-1)
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
        if atk1[Pok.CURRENT_HP] > 0 and not early_returns(atk1, def1, 1, flinch, mv1):
            if mv1[Move.ID] != MoveName.STRUGGLE:
                mv1[Move.PP] -= 1
                if first_is_mine:
                    battle_array[Field.MY_LAST_MOVE] = mv1[Move.ID]
            elif first_is_mine:
                battle_array[Field.MY_LAST_MOVE] = -1

            move_hit = calculate_hit_miss(mv1, atk1, def1, weather)
            if move_hit == MoveOutcome.HIT:
                if mv1[Move.ID] == MoveName.STRUGGLE:
                    struggle(atk1, def1)
                elif mv1[Move.CATEGORY] in PHYSICAL_SPECIAL:
                    ps_moves(atk1, def1, mv1, weather)
                    if first_is_mine:   # def1 is current_opp only when my pokemon goes first
                        battle_array[Field.AI_TOOK_DMG_LAST_TURN] = mv1[Move.TYPE]
                    flinch = flinch_checker(mv1, def1)
                    if def1[Pok.STATUS] == Status.FREEZE:
                        thaw(mv1, def1)
                else:
                    calculate_effects(atk1, def1, mv1, weather)

    # ---- Second move ----
    if count >= 2:
        if atk2[Pok.CURRENT_HP] > 0 and not early_returns(atk2, def2, 2, flinch, mv2):
            if mv2[Move.ID] != MoveName.STRUGGLE:
                mv2[Move.PP] -= 1
                if not first_is_mine:   # second attacker is mine when opp went first
                    battle_array[Field.MY_LAST_MOVE] = mv2[Move.ID]
            elif not first_is_mine:
                battle_array[Field.MY_LAST_MOVE] = -1

            move_hit = calculate_hit_miss(mv2, atk2, def2, weather)
            if move_hit == MoveOutcome.HIT:
                if mv2[Move.ID] == MoveName.STRUGGLE:
                    struggle(atk2, def2)
                elif mv2[Move.CATEGORY] in PHYSICAL_SPECIAL:
                    ps_moves(atk2, def2, mv2, weather)
                    if not first_is_mine:   # def2 is current_opp only when opp went first
                        battle_array[Field.AI_TOOK_DMG_LAST_TURN] = mv2[Move.TYPE]
                    if def2[Pok.STATUS] == Status.FREEZE:
                        thaw(mv2, def2)
                else:
                    calculate_effects(atk2, def2, mv2, weather)


def end_of_turn(battle_array):
    """Does end of turn calculations like switch if dead, burn, poison, leech seed, ...,\n
    items like leftovers\n
    Weather damage like hail, sandstorm"""
    current_pokemon = battle_array[
        (battle_array[Field.MY_POK] * POK_LEN):
        ((battle_array[Field.MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[Field.OPP_POK]+6) * POK_LEN):
        ((battle_array[Field.OPP_POK]+7) * POK_LEN)
    ]
    weather = battle_array[Field.WEATHER]
    m_hp = current_pokemon[Pok.CURRENT_HP]
    opp_hp = current_opp[Pok.CURRENT_HP]
    my_enter_field = battle_array[Field.MY_ENTER_FIELD]
    opp_enter_field = battle_array[Field.OPP_ENTER_FIELD]
    m_abi = current_pokemon[Pok.AB_ID]
    o_abi = current_opp[Pok.AB_ID]

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
                if m_abi & AbilityActivation.ON_RESIDUAL:
                    on_residual(current_pokemon, my_enter_field)
                if my_enter_field:
                    battle_array[Field.MY_ENTER_FIELD] = 0
            current_pokemon[Pok.CURRENT_HP] = m_hp
        else:
            if m_abi & AbilityActivation.ON_RESIDUAL:
                on_residual(current_pokemon, my_enter_field)
            if my_enter_field:
                battle_array[Field.MY_ENTER_FIELD] = 0
    if opp_hp > 0:
        heal_end_turn(current_opp, weather)
        dmg = after_turn_damage(current_opp, weather)
        if dmg != 0:
            if dmg > opp_hp:
                opp_hp = 0
            else:
                opp_hp -= dmg
                if o_abi & AbilityActivation.ON_RESIDUAL:
                    on_residual(current_opp, opp_enter_field)
                if opp_enter_field:
                    battle_array[Field.OPP_ENTER_FIELD] = 0
            current_opp[Pok.CURRENT_HP] = opp_hp
        else:
            if m_abi & AbilityActivation.ON_RESIDUAL:
                on_residual(current_pokemon, my_enter_field)
            if opp_enter_field:
                battle_array[Field.OPP_ENTER_FIELD] = 0

    # If Opponent is dead
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    if opp_hp == 0 and m_hp != 0:
        if count_party(opp_pty) == 0:
            return None
        i = sub_after_death(
            opp_pty, current_pokemon, current_opp
        )
        battle_array[Field.OPP_POK] = i
        current_opp = opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
        switch_in(current_pokemon, current_opp)
        return i
    return None


def turn_sim(opp_move, current_action, battle_array):
    """One turn"""
    if current_action[0] == ActionType.MOVE:
        switch_idx = -1
        current_move = current_action[1]
    else:
        current_move = -1
        switch_idx = current_action[1]
    start_of_turn(opp_move, switch_idx, battle_array)
    action(current_move, opp_move, battle_array)
    opp_idx = end_of_turn(battle_array)
    current_pokemon = battle_array[
        (battle_array[Field.MY_POK] * POK_LEN):
        ((battle_array[Field.MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[Field.OPP_POK]+6) * POK_LEN):
        ((battle_array[Field.OPP_POK]+7) * POK_LEN)
    ]

    if not opp_idx:
        opp_idx = battle_array[Field.OPP_POK]
    if current_pokemon[Pok.CURRENT_HP] <= 0:
        return BattlePhase.DEATH_END_OF_TURN, opp_idx

    battle_array[Field.TURN] += 1
    current_opp[Pok.TURNS] += 1
    current_pokemon[Pok.TURNS] += 1
    return BattlePhase.TURN_START, opp_idx


def switch_in_action(battle_array, switch_idx: int):
    """Grab the switch idx from MCTS and progress it"""
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    my_pty = battle_array[0:(6 * POK_LEN)]
    current_pokemon = battle_array[
        (battle_array[Field.MY_POK] * POK_LEN):
        ((battle_array[Field.MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[Field.OPP_POK]+6) * POK_LEN):
        ((battle_array[Field.OPP_POK]+7) * POK_LEN)
    ]
    if current_opp[Pok.CURRENT_HP] <= 0:
        i = sub_after_death(
            opp_pty, current_pokemon, current_opp
        )
        opp_switch = opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
        my_switch = my_pty[
            (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
        ]

        my_s, opp_s = check_speed(
            my_switch, opp_switch, battle_array[Field.WEATHER]
        )
        speed_tie= False
        if my_s == opp_s:
            if random.getrandbits(1):
                speed_tie = True

        if my_s > opp_s or speed_tie:
            # My Pokemon
            battle_array[Field.MY_POK] = switch_idx
            battle_array[Field.AI_KNOWS] = 0
            battle_array[Field.MY_LAST_MOVE] = 0
            current_pokemon = my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]

            # Opponent Pokemon
            current_opp = opp_switch
            battle_array[Field.OPP_POK] = i

            # Switch in effects after they are already switched
            switch_in(current_pokemon, current_opp)
            switch_in(current_opp, current_pokemon)
        elif my_s < opp_s:
            # Opponent Pokemon
            battle_array[Field.OPP_POK] = i
            current_opp = opp_switch

            # My Pokemon
            battle_array[Field.MY_POK] = switch_idx
            battle_array[Field.AI_KNOWS] = 0
            battle_array[Field.MY_LAST_MOVE] = 0
            current_pokemon = my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]

            # Switch in effects after they are already switched
            switch_in(current_opp, current_pokemon)
            switch_in(current_pokemon, current_opp)

        battle_array[Field.TURN] += 1
        current_opp[Pok.TURNS] += 1
        current_pokemon[Pok.TURNS] += 1
        return
    battle_array[Field.MY_POK] = switch_idx
    current_pokemon = my_pty[
        (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
    ]
    battle_array[Field.TURN] += 1
    current_opp[Pok.TURNS] += 1
    current_pokemon[Pok.TURNS] += 1
    battle_array[Field.AI_KNOWS] = 0
    battle_array[Field.MY_LAST_MOVE] = 0
