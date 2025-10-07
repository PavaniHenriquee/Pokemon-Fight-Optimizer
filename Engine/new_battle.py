"""Battle class where it follows battle flow, doing the sequence selection, start of turn, actions,
end of turn and repeat"""
import random
import numpy as np
from Engine.engine_helper import (
    check_speed,
    move_order,
    calculate_hit_miss,
    calculate_crit,
    reset_switch_out,
    MoveOutcome,
    flinch_checker,
    thaw,
    to_battle_array
)
from Engine.status_calc import paralysis, sec_effects, calculate_effects, after_turn_status, freeze
from Engine.damage_calc import calculate_damage
from Models.trainer_ai import TrainerAI
from Models.idx_const import (
    Pok, Field, Move, Sec, POK_LEN, MOVE_STRIDE, OFFSET_MOVE, OFFSET_SEC
)
from Models.helper import count_party, Status, VolStatus, MoveCategory
from DataBase.PkDB import PokIdToName
from DataBase.MoveDB import MoveIdToName


def switch_menu(current_pokemon, my_pty):
    """Makes what the switch menu looks like, it should loop outside"""
    switch_pok = -1
    ret_menu = False
    opt = []
    print("Choose the Pokemon you want to switch to:")
    for i in range(6):
        off = POK_LEN*i
        if (
            my_pty[Pok.CURRENT_HP + off] != 0
            and my_pty[Pok.ID + off] != current_pokemon[Pok.ID]
        ):
            opt.append(i + 1)
            print(f"{i+1}. {PokIdToName[my_pty[Pok.ID + off]].capitalize()}")
    if current_pokemon[Pok.CURRENT_HP] > 0:
        print("r. Return to previous menu")
    switch_choice = input("Choose1: ")
    if switch_choice == 'r' and current_pokemon[Pok.CURRENT_HP] >= 0:
        ret_menu = True
        return switch_pok, ret_menu
    if int(switch_choice) in opt:
        switch_pok = int(switch_choice) - 1  # Because of idx 0
        return switch_pok, ret_menu
    print("Please select a valid answer.")
    return switch_pok, ret_menu


def battle_menu(current_pokemon, my_pty):
    """Prompt the player for a move or switch.

    Returns:
        (current_move_idx, switch_pok_idx) \n
        current_move_idx: 1..4 or -1 if switch chosen \n
        switch_pok_idx: 0..5 of my party list (or -1)
    """
    current_move_idx = -1
    switch_pok_idx = -1
    pok_moves_len = 0
    for m in (
        current_pokemon[Pok.MOVE1_ID],
        current_pokemon[Pok.MOVE2_ID],
        current_pokemon[Pok.MOVE3_ID],
        current_pokemon[Pok.MOVE4_ID]
    ):
        if m != 0:
            pok_moves_len += 1

    while current_move_idx < 0 or current_move_idx >= pok_moves_len:
        print(f"Your current Pokemon is {PokIdToName[current_pokemon[Pok.ID]].capitalize()}")
        if count_party(my_pty) > 1:
            print("Choose one of the moves or if you want to switch:")
        else:
            print("Choose one of the moves:")

        for i, move in enumerate(
        (current_pokemon[Pok.MOVE1_ID],
        current_pokemon[Pok.MOVE2_ID],
        current_pokemon[Pok.MOVE3_ID],
        current_pokemon[Pok.MOVE4_ID]),
        start=1
        ):
            if move!= 0:
                print(f"{i}. {MoveIdToName[move].capitalize()}")

        if count_party(my_pty) > 1:
            print('s. Switch')

        choice = input("Choose2: ")
        if choice.isdigit():
            current_move_idx = int(choice) - 1
            if current_move_idx < 0 or current_move_idx > pok_moves_len:
                print("Please select a valid move.")
                current_move_idx = -1
            continue
        if choice == 's' and count_party(my_pty) > 1:
            alive = np.where(my_pty[Pok.CURRENT_HP:: POK_LEN] > 0)[0].tolist()
            while switch_pok_idx not in alive:
                switch_pok_idx, ret_menu = switch_menu(current_pokemon, my_pty)
                if ret_menu:
                    break
            if switch_pok_idx >= 0:
                break
            continue
        print("Please select a valid answer.")
        current_move_idx = -1

    return current_move_idx, switch_pok_idx


class Battle():
    """Battle class, where i calculate all the battle, following the flow of battle"""
    def __init__(self, my_pty=None, opp_pty=None, battle_array=None):
        # Make the normalized battle array
        self.battle_array = to_battle_array(my_pty, opp_pty) if battle_array is None else battle_array
        self.pok_features = POK_LEN
        self.my_pty = self.battle_array[0:(6 * self.pok_features)]
        self.opp_pty = self.battle_array[(6 * self.pok_features):(12 * self.pok_features)]
        self.opp_ai = TrainerAI()
        self.turn = self.battle_array[Field.TURN]

        # current active Pokémon
        opp_active = int(self.battle_array[Field.OPP_POK])
        my_active = int(self.battle_array[Field.MY_POK])
        self.current_pokemon = self.battle_array[
            (my_active * self.pok_features):((my_active+1) * self.pok_features)
        ]
        self.current_opp = self.battle_array[
            ((opp_active+6) * self.pok_features):((opp_active+7) * self.pok_features)
        ]
        self.op_move1 = self.current_opp[Pok.MOVE1_ID:Pok.MOVE2_ID]
        self.op_move2 = self.current_opp[Pok.MOVE2_ID:Pok.MOVE3_ID]
        self.op_move3 = self.current_opp[Pok.MOVE3_ID:Pok.MOVE4_ID]
        self.op_move4 = self.current_opp[Pok.MOVE4_ID:Pok.ITEM_ID]

    def start_of_battle(self):
        """Select the two first pokemon of each team and does ability effects on switch in
        for each following their speed"""
        # TODO: Switch in abilities like Intimidate, Drought etc.
        p1_speed, p2_speed = check_speed(self.current_pokemon, self.current_opp)
        speed_tie_1 = False
        speed_tie_2 = False
        if p1_speed == p2_speed:
            if random.randint(1, 2) == 1:
                speed_tie_1 = True
            else:
                speed_tie_2 = True
        if p1_speed > p2_speed or speed_tie_1:
            print(f"You sent out {PokIdToName[self.current_pokemon[Pok.ID]].capitalize()}!")
            print(f"The opponent sent out {PokIdToName[self.current_opp[Pok.ID]].capitalize()}!")
        elif p2_speed > p1_speed or speed_tie_2:
            print(f"The opponent sent out {PokIdToName[self.current_pokemon[Pok.ID]].capitalize()}!")
            print(f"You sent out {PokIdToName[self.current_opp[Pok.ID]].capitalize()}!")
        self.current_pokemon[Pok.TURNS] = 1
        self.current_opp[Pok.TURNS] = 1

    def selection(self):
        """Does the selection part of the battle, what I choose and what the opponent chooses"""
        '''opp_move = self.opp_ai.return_idx(
            self.current_opp,
            self.current_pokemon,
            self.my_pty_alive,
            self.opp_pty_alive,
            self.turn
        )'''
        opp_move = self.opp_ai.return_idx(
            self.current_opp,
            self.current_pokemon,
            self.my_pty,
            self.opp_ai,
            self.turn,
            self.op_move1,
            self.op_move2,
            self.op_move3,
            self.op_move4
        )


        current_move_idx, switch_move_idx = battle_menu(self.current_pokemon, self.my_pty)
        return opp_move, current_move_idx, switch_move_idx

    def start_of_turn(self, opp_move, switch_idx):
        """What happens before everything in the turn order, so switches and trainer items"""
        # TODO: Opponent Items
        opp_switch = None
        if opp_move == 's':
            i = self.opp_ai.sub_after_death(
                self.opp_pty, self.current_pokemon, self.current_opp
            )
            opp_switch = self.opp_pty[(i * self.pok_features):((i+1) * self.pok_features)]

        if switch_idx >= 0 and opp_move == 's':
            my_s, opp_s = check_speed(self.current_pokemon, self.current_opp)
            speed_tie_1 = False
            speed_tie_2 = False
            if my_s == opp_s:
                if random.randint(1, 2) == 1:
                    speed_tie_1 = True
                else:
                    speed_tie_2 = True
            if my_s > opp_s or speed_tie_1:
                # TODO: Switch in abilities and terrain hazards
                print(f'You switched {PokIdToName[self.current_pokemon[Pok.ID]].capitalize()} out.')
                reset_switch_out(self.current_pokemon)
                self.battle_array[Field.MY_POK] = switch_idx
                self.current_pokemon = self.my_pty[(switch_idx * self.pok_features):((switch_idx+1) * self.pok_features)]
                print(f'You switched {PokIdToName[self.current_pokemon[Pok.ID]].capitalize()} in.')

                print(f'Opponent has switched {PokIdToName[self.current_opp[Pok.ID]].capitalize()} out.')
                reset_switch_out(self.current_opp)
                self.current_opp = opp_switch
                self.battle_array[Field.OPP_POK] = opp_switch
                print(f'Opponent has switched {PokIdToName[self.current_opp[Pok.ID]].capitalize()} in.')
            elif my_s < opp_s or speed_tie_2:
                # TODO: Switch in abilities and terrain hazards
                print(f'Opponent has switched {PokIdToName[self.current_opp[Pok.ID]].capitalize()} out.')
                reset_switch_out(self.current_opp)
                self.battle_array[Field.OPP_POK] = opp_switch
                self.current_opp = opp_switch
                print(f'Opponent has switched {PokIdToName[self.current_opp[Pok.ID]].capitalize()} in.')

                print(f'You switched {PokIdToName[self.current_pokemon[Pok.ID]].capitalize()} out.')
                reset_switch_out(self.current_pokemon)
                self.battle_array[Field.MY_POK] = switch_idx
                self.current_pokemon = self.my_pty[(switch_idx * self.pok_features):((switch_idx+1) * self.pok_features)]
                print(f'You switched {PokIdToName[self.current_pokemon[Pok.ID]].capitalize()} in.')
            return

        if opp_switch:
            # TODO: Switch in abilities and terrain hazards
            print(f'Opponent has switched {PokIdToName[self.current_opp[Pok.ID]].capitalize()} out.')
            reset_switch_out(self.current_opp)
            self.current_opp = opp_switch
            self.battle_array[Field.OPP_POK] = opp_switch
            print(f'Opponent has switched {PokIdToName[self.current_opp[Pok.ID]].capitalize()} in.')

        if switch_idx >= 0:
            # TODO: Switch in abilities and terrain hazards
            print(f'You switched {PokIdToName[self.current_pokemon[Pok.ID]].capitalize()} out.')
            reset_switch_out(self.current_pokemon)
            self.battle_array[Field.MY_POK] = switch_idx
            self.current_pokemon = self.my_pty[(switch_idx * self.pok_features):((switch_idx+1) * self.pok_features)]
            print(f'You switched {PokIdToName[self.current_pokemon[Pok.ID]].capitalize()} in.')

    def action(self, current_move, opp_move, search=False):
        """Where the moves are calculated"""
        p1_switch = False
        p2_switch = False
        flinch = False
        if current_move < 0 and not isinstance(opp_move, int):
            return  # Check if neither used an action, if so early return
        if current_move < 0:
            p1_switch = True
        if not isinstance(opp_move, int):
            p2_switch = True
            opp_move = 0  # Just so i don't break the move_order function call being ->
            # self.current_opp.moves[opp_move] this need to be a number

        move_offset = MOVE_STRIDE
        base_offset = OFFSET_MOVE

        order = move_order(
            self.current_pokemon,
            self.current_pokemon[
                base_offset + (move_offset * current_move):
                base_offset + (move_offset * (current_move + 1))
            ],
            self.current_opp,
            self.current_opp[
                base_offset + (move_offset * opp_move):
                base_offset + (move_offset * (opp_move + 1))
            ],
            p1_switch,
            p2_switch
        )

        if search:
            for idx, (attacker, move, defender) in enumerate(order, start=1):
                # If attacker slower and died before could attack
                if attacker[Pok.CURRENT_HP] <= 0:
                    continue
                # Check for Sleep and if the attacker wakes up, TODO: Sleep Talk and Snore
                if attacker[Pok.STATUS] == Status.SLEEP:
                    if attacker[Pok.SLEEP_COUNTER] > 0:
                        attacker[Pok.SLEEP_COUNTER] -= 1
                        continue
                    attacker[Pok.STATUS] = 0
                # Check for Paralysis
                if attacker[Pok.STATUS] == Status.PARALYSIS and paralysis():
                    continue
                # Freeze
                if attacker[Pok.STATUS] == Status.FREEZE:
                    early_return = freeze()
                    if early_return:
                        continue
                    attacker[Pok.STATUS] = 0
                # Flinch
                if idx >= 2 and flinch is True:
                    continue
                # Volatile Status early returns, only confusion for now
                if attacker[Pok.VOL_STATUS] != 0 and attacker[Pok.VOL_STATUS] & VolStatus.CONFUSION:
                    early_return = random.randint(1,2) == 1
                    if early_return:
                        continue
                # In cases like after recoil damage, selfdestruct, etc.
                if defender[Pok.CURRENT_HP] <= 0:
                    continue

                move_hit = calculate_hit_miss(move, attacker, defender)

                if move_hit is MoveOutcome.HIT:
                    if move[Move.CATEGORY] in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
                        self.ps_moves(attacker, defender, move)
                        flinch = flinch_checker(move)
                        if attacker[Pok.STATUS] == Status.FREEZE:
                            thaw(move, defender)
                    else:
                        calculate_effects(attacker, defender, move)
            return

        for idx, (attacker, move, defender) in enumerate(order, start=1):
            # If attacker slower and died before could attack
            if attacker[Pok.CURRENT_HP] <= 0:
                continue
            # Check for Sleep and if the attacker wakes up, TODO: Sleep Talk and Snore
            if attacker[Pok.STATUS] == Status.SLEEP:
                if attacker[Pok.SLEEP_COUNTER] > 0:
                    print(f"{PokIdToName[attacker[Pok.ID]].capitalize()} is fast asleep!")
                    attacker[Pok.SLEEP_COUNTER] -= 1
                    continue
                attacker[Pok.STATUS] = 0
                print(f"{PokIdToName[attacker[Pok.ID]].capitalize()} has woken up!")
            # Check for Paralysis
            if attacker[Pok.STATUS] == Status.PARALYSIS and paralysis():
                print(f"{PokIdToName[attacker[Pok.ID]].capitalize()} is fully paralysed!")
                continue
            # Freeze
            if attacker[Pok.STATUS] == Status.FREEZE:
                early_return = freeze()
                if early_return:
                    print(f'{PokIdToName[attacker[Pok.ID]].capitalize()} is frozen solid!')
                    continue
                attacker[Pok.STATUS] = 0
                print(f"{PokIdToName[attacker[Pok.ID]].capitalize()} has thawed out!")
            # Flinch
            if idx >= 2 and flinch is True:
                print(f"{PokIdToName[attacker[Pok.ID]].capitalize()} flinched and couldn\'t move!")
                continue
            # Volatile Status early returns, only confusion for now
            if attacker[Pok.VOL_STATUS] != 0 and attacker[Pok.VOL_STATUS] & VolStatus.CONFUSION:
                early_return = random.randint(1,2) == 1
                if early_return:
                    continue
            # In cases like after recoil damage, selfdestruct, etc.
            if defender[Pok.CURRENT_HP] <= 0:
                print(
                    f"{PokIdToName[attacker[Pok.ID]].capitalize()}"
                    f"used {MoveIdToName[move[Move.ID]].capitalize()} "
                    f"on {PokIdToName[defender[Pok.ID]].capitalize()}!"
                )
                print("But it failed.")
                continue

            move_hit = calculate_hit_miss(move, attacker, defender)

            if move_hit is MoveOutcome.HIT:
                if move[Move.CATEGORY] in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
                    self.ps_moves(attacker, defender, move)
                    flinch = flinch_checker(move)
                    if attacker[Pok.STATUS] == Status.FREEZE:
                        thaw(move, defender)
                else:
                    if attacker[Pok.ID] == self.current_pokemon[Pok.ID]:
                        print(
                            f"{PokIdToName[attacker[Pok.ID]].capitalize()}"
                            f"used {MoveIdToName[move[Move.ID]].capitalize()}!"
                        )
                    else:
                        print(
                            f"Opponent {PokIdToName[attacker[Pok.ID]].capitalize()}"
                            f"used {MoveIdToName[move[Move.ID]].capitalize()}!"
                        )
                    calculate_effects(attacker, defender, move)

            if move_hit is MoveOutcome.MISS:
                if attacker[Pok.ID] == self.current_pokemon[Pok.ID]:
                    print(
                        f"{PokIdToName[attacker[Pok.ID]].capitalize()}"
                        f"used {MoveIdToName[move[Move.ID]].capitalize()}!"
                    )
                else:
                    print(
                        f"Opponent {PokIdToName[attacker[Pok.ID]].capitalize()}"
                        f"used {MoveIdToName[move[Move.ID]].capitalize()}!"
                    )
                print('But it missed.')

            if move_hit is MoveOutcome.INVULNERABLE:
                if attacker[Pok.ID] == self.current_pokemon[Pok.ID]:
                    print(
                        f"{PokIdToName[attacker[Pok.ID]].capitalize()}"
                        f"used {MoveIdToName[move[Move.ID]].capitalize()}!"
                    )
                else:
                    print(
                        f"Opponent {PokIdToName[attacker[Pok.ID]].capitalize()}"
                        f"used {MoveIdToName[move[Move.ID]].capitalize()}!"
                    )
                print('But it had no effect.')

    def ps_moves(self, attacker, defender, move):
        """Physical or Special moves, where I need to calculate damage and secondary effects"""
        crit = calculate_crit()
        damage, effectivness = calculate_damage(attacker, defender, move, crit)
        if damage <= defender[Pok.CURRENT_HP]:
            defender[Pok.CURRENT_HP] -= damage
            dead = False
        else:
            defender[Pok.CURRENT_HP] = 0
            dead = True

        # Check to see which side is attacking and represent accordingly
        if attacker[Pok.ID] == self.current_pokemon[Pok.ID]:
            print(
                    f"{PokIdToName[attacker[Pok.ID]].capitalize()} "
                    f"used {MoveIdToName[move[Move.ID]].capitalize()} "
                    f"on {PokIdToName[defender[Pok.ID]].capitalize()}!"
                )
        else:
            print(
                    f"Opponent {PokIdToName[attacker[Pok.ID]].capitalize()} "
                    f"used {MoveIdToName[move[Move.ID]].capitalize()} "
                    f"on {PokIdToName[defender[Pok.ID]].capitalize()}!"
                )

        # Text to show crit
        if crit is True:
            print("\033[91mIt's a critical hit! \033[0m")

        # Since i don't have the hp bars for either side print out how much damage
        print(f"It dealt {damage} damage.")

        # If the move is supper effective or not much effective
        if effectivness >= 2:
            print("\033[92mIt's super effective! \033[0m")
        elif 0 < effectivness < 1:
            print("\033[94mIt's not very effective... \033[0m")

        # Check for secondary effects and apply them
        if move[OFFSET_SEC + Sec.CHANCE]:
            sec_effects(move, attacker, defender, damage)

        # Text of how much hp left, or if dead
        if dead:
            print(f"\033[91m{PokIdToName[defender[Pok.ID]].capitalize()} has fainted! \033[0m")
        else:
            print(
                f"{PokIdToName[defender[Pok.ID]].capitalize()} "
                f"has {int(defender[Pok.CURRENT_HP])} HP left."
            )

    def end_of_turn(self, search=False):
        """Does end of turn calculations like switch if dead, burn, poison, leech seed, ...,\n
        items like leftovers\n
        Weather damage like hail, sandstorm"""
        # TODO: weather
        # TODO: Abilities
        # TODO: Items
        if type(search) is int:  # pylint:disable=C0123
            self.battle_array[Field.MY_POK] = search
            self.current_pokemon = self.my_pty[(search * self.pok_features):((search+1) * self.pok_features)]
            self.battle_array[Field.TURN] += 1
            self.turn += 1
            self.current_opp[Pok.TURNS] += 1
            self.current_pokemon[Pok.TURNS] += 1
            return

        # Calculate after turn status like burn, leech seed, curse
        if self.current_pokemon[Pok.CURRENT_HP] >= 0:
            after_turn_status(self.current_pokemon)
        if self.current_opp[Pok.CURRENT_HP] >= 0:
            after_turn_status(self.current_opp)

        # Switch after everything and Pokemon is dead. TODO: order of switch
        if self.current_opp[Pok.CURRENT_HP] <= 0:
            if count_party(self.opp_pty) == 0:
                return
            i = self.opp_ai.sub_after_death(
                self.opp_pty, self.current_pokemon, self.current_opp
            )
            self.battle_array[Field.OPP_POK] = i
            self.current_opp = self.opp_pty[(i * self.pok_features):((i+1) * self.pok_features)]
            print(f'the opponent has sent '
                  f'{PokIdToName[self.current_opp[Pok.ID]].capitalize()} out')
            if search:
                return i
        if search is False:
            if self.current_pokemon[Pok.CURRENT_HP] <= 0:
                switch_idx = -1
                if count_party(self.my_pty) == 0:
                    return
                alive = np.where(self.my_pty[Pok.CURRENT_HP:: self.pok_features] > 0)[0].tolist()
                while switch_idx not in alive:
                    switch_idx, _ = switch_menu(self.current_pokemon, self.my_pty)
                    self.battle_array[Field.MY_POK] = switch_idx
                    self.current_pokemon = self.my_pty[
                        (switch_idx * self.pok_features):((switch_idx+1) * self.pok_features)
                    ]

    def run(self):
        """Runs through the entire battle"""
        self.start_of_battle()
        while count_party(self.my_pty) > 0 and count_party(self.opp_pty) > 0:
            opp_move, current_move, switch_idx = self.selection()
            self.start_of_turn(opp_move, switch_idx)
            self.action(current_move, opp_move)
            self.end_of_turn()
            self.battle_array[Field.TURN] += 1
            self.turn += 1
            self.current_opp[Pok.TURNS] += 1
            self.current_pokemon[Pok.TURNS] += 1

        if count_party(self.my_pty) == 0:
            print("You Lost!")
        if count_party(self.opp_pty) == 0:
            print("You Won!")

    def turn_sim(self, opp_move, current_action):
        """One turn"""
        from SearchEngine.my_mcts import BattlePhase  # pylint:disable=C0415
        if current_action[0] == 'move':
            switch_idx = -1
            current_move = current_action[1]
        else:
            current_move = -1
            switch_idx = current_action[1]
        if self.current_opp[0] == 0 or self.current_pokemon[0] == 0:
            pass
        self.start_of_turn(opp_move, switch_idx)
        self.action(current_move, opp_move, search=True)
        opp_idx = self.end_of_turn(search=True)
        self.battle_array[Field.TURN] += 1
        self.turn += 1
        self.current_opp[Pok.TURNS] += 1
        self.current_pokemon[Pok.TURNS] += 1
        if not opp_idx:
            opp_idx = self.battle_array[Field.OPP_POK]
        if self.current_pokemon[Pok.CURRENT_HP] <= 0:
            return BattlePhase.DEATH_END_OF_TURN, opp_idx

        return BattlePhase.TURN_START, opp_idx


def battle(my_pty, opp_pty):
    """Just so it's easier to call on main"""
    b = Battle(my_pty, opp_pty)
    return b.run()
