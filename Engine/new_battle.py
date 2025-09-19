"""Battle class where it follows battle flow, doing the sequence selection, start of turn, actions,
end of turn and repeat"""
import random
from Engine.engine_helper import (
    check_speed,
    move_order,
    calculate_hit_miss,
    calculate_crit,
    get_non_fainted_pokemon,
    reset_switch_out,
    MoveOutcome,
    flinch_checker,
    vol_early_returns,
    thaw,
    to_battle_array
)
from Engine.status_calc import paralysis, sec_effects, calculate_effects, after_turn_status, freeze
from Engine.damage_calc import calculate_damage
from Models.trainer_ai import TrainerAI
from Models.idx_nparray import PokArray
from DataBase.PkDB import PokemonName


def switch_menu(current_pokemon, alive_pokemon, my_pty):
    """Makes what the switch menu looks like, it should loop where its used"""
    switch_pok = -1
    ret_menu = False
    opt = []
    print("Choose the Pokemon you want to switch to:")
    for i, pok in enumerate(my_pty):
        if pok in alive_pokemon and pok != current_pokemon:
            opt.append(i + 1)
            print(f"{i+1}. {pok.name}")
    if not current_pokemon.fainted:
        print("r. Return to previous menu")
    switch_choice = input("Choose: ")
    if switch_choice == 'r' and not current_pokemon.fainted:
        ret_menu = True
        return switch_pok, ret_menu
    if int(switch_choice) in opt:
        switch_pok = int(switch_choice) - 1  # Because of idx 0
        return switch_pok, ret_menu
    print("Please select a valid answer.")
    return switch_pok, ret_menu


def battle_menu(current_pokemon, my_pty_alive, my_pty):
    """Prompt the player for a move or switch.

    Returns:
        (current_move_idx, switch_pok_idx, current_pokemon)
        current_move_idx: index of move chosen or -1 if switch chosen
        switch_pok_idx: index selected from the alive list (or -1)
    """
    current_move_idx = -1
    switch_pok_idx = -1
    while current_move_idx < 0 or current_move_idx >= len(current_pokemon.moves):
        print(f"Your current Pokemon is {current_pokemon.name}")
        if len(my_pty_alive) > 1:
            print("Choose one of the moves or if you want to switch:")
        else:
            print("Choose one of the moves:")

        for i, move in enumerate(current_pokemon.moves):
            print(f"{i+1}. {move['name']}")

        if len(my_pty_alive) > 1:
            print('s. Switch')

        choice = input("Choose: ")
        if choice.isdigit():
            current_move_idx = int(choice) - 1  # Because of index 0
            if current_move_idx < 0 or current_move_idx >= len(current_pokemon.moves):
                print("Please select a valid move.")
                current_move_idx = -1
            continue
        if choice == 's' and len(my_pty_alive) > 1:
            alive_pokemon = my_pty_alive.copy()
            # remove current from the choices
            del alive_pokemon[alive_pokemon.index(current_pokemon)]
            while switch_pok_idx < 0 and my_pty[switch_pok_idx].name in [p.name for p in alive_pokemon]:
                switch_pok_idx, ret_menu = switch_menu(current_pokemon, my_pty_alive, my_pty)
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
    def __init__(self, my_pty, opp_pty):
        # Make the normalized battle array
        self.battle_array = to_battle_array(my_pty, opp_pty)
        pok_features = len(PokArray)
        self.pok1 = self.battle_array[0:pok_features]
        self.pok2 = self.battle_array[pok_features:(2 * pok_features)]
        self.pok3 = self.battle_array[(2 * pok_features):(3 * pok_features)]
        self.pok4 = self.battle_array[(3 * pok_features):(4 * pok_features)]
        self.pok5 = self.battle_array[(4 * pok_features):(5 * pok_features)]
        self.pok6 = self.battle_array[(5 * pok_features):(6 * pok_features)]
        self.opp_pok1 = self.battle_array[(6 * pok_features):(7 * pok_features)]
        self.opp_pok2 = self.battle_array[(7 * pok_features):(8 * pok_features)]
        self.opp_pok3 = self.battle_array[(8 * pok_features):(9 * pok_features)]
        self.opp_pok4 = self.battle_array[(9 * pok_features):(10 * pok_features)]
        self.opp_pok5 = self.battle_array[(10 * pok_features):(11 * pok_features)]
        self.opp_pok6 = self.battle_array[(11 * pok_features):(12 * pok_features)]
        self.my_pty = self.battle_array[0:(6 * pok_features)]
        self.opp_pty = self.battle_array[(6 * pok_features):(12 * pok_features)]
        self.opp_ai = TrainerAI()
        self.turn = 1

        # current active Pokémon
        self.current_pokemon = self.pok1
        self.current_opp = self.opp_pok1
        self.move1 = self.current_pokemon[PokArray.MOVE1_ID:PokArray.MOVE2_ID]
        self.move2 = self.current_pokemon[PokArray.MOVE2_ID:PokArray.MOVE3_ID]
        self.move3 = self.current_pokemon[PokArray.MOVE3_ID:PokArray.MOVE4_ID]
        self.move4 = self.current_pokemon[PokArray.MOVE4_ID:PokArray.ITEM_ID]
        self.op_move1 = self.current_opp[PokArray.MOVE1_ID:PokArray.MOVE2_ID]
        self.op_move2 = self.current_opp[PokArray.MOVE2_ID:PokArray.MOVE3_ID]
        self.op_move3 = self.current_opp[PokArray.MOVE3_ID:PokArray.MOVE4_ID]
        self.op_move4 = self.current_opp[PokArray.MOVE4_ID:PokArray.ITEM_ID]

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
            print(f"You sent out {PokemonName(self.current_pokemon[PokArray.ID]).name.capitalize()}!")
            print(f"The opponent sent out {PokemonName(self.current_opp[PokArray.ID]).name.capitalize()}!")
        elif p2_speed > p1_speed or speed_tie_2:
            print(f"The opponent sent out {PokemonName(self.current_pokemon[PokArray.ID]).name.capitalize()}!")
            print(f"You sent out {PokemonName(self.current_opp[PokArray.ID]).name.capitalize()}!")
        self.current_pokemon[PokArray.TURNS] = 1
        self.current_opp[PokArray.TURNS] = 1

    def selection(self):
        """Does the selection part of the battle, what I choose and what the opponent chooses"""
        '''opp_move = self.opp_ai.return_idx(
            self.current_opp,
            self.current_pokemon,
            self.my_pty_alive,
            self.opp_pty_alive,
            self.turn
        )'''
        opp_move = 1
        current_move_idx, switch_move_idx = battle_menu(self.current_pokemon, self.my_pty_alive, self.my_pty)
        return opp_move, current_move_idx, switch_move_idx

    def start_of_turn(self, opp_move, switch_idx):
        """What happens before everything in the turn order, so switches and trainer items"""
        # TODO: Opponent Items
        opp_switch = None
        if opp_move == 's':
            opp_switch = self.opp_pty_alive[self.opp_ai.sub_after_death(
                self.opp_pty_alive, self.current_pokemon, self.current_opp
            )]

        if switch_idx >= 0 and opp_move == 's':
            my_p, opp_p = check_speed(self.current_pokemon, self.current_opp)
            speed_tie_1 = False
            speed_tie_2 = False
            if my_p == opp_p:
                if random.randint(1, 2) == 1:
                    speed_tie_1 = True
                else:
                    speed_tie_2 = True
            if my_p > opp_p or speed_tie_1:
                # TODO: Switch in abilities and terrain hazards
                print(f'You switched {self.current_pokemon.name} out.')
                reset_switch_out(self.current_pokemon)
                self.current_pokemon = self.my_pty[switch_idx]
                print(f'You switched {self.current_pokemon.name} in.')

                print(f'Opponent has switched {self.current_opp.name} out.')
                reset_switch_out(self.current_opp)
                self.current_opp = opp_switch
                print(f'Opponent has switched {self.current_opp.name} in.')
            elif my_p < opp_p or speed_tie_2:
                # TODO: Switch in abilities and terrain hazards
                print(f'Opponent has switched {self.current_opp.name} out.')
                reset_switch_out(self.current_opp)
                self.current_opp = opp_switch
                print(f'Opponent has switched {self.current_opp.name} in.')

                print(f'You switched {self.current_pokemon.name} out.')
                reset_switch_out(self.current_pokemon)
                self.current_pokemon = self.my_pty[switch_idx]
                print(f'You switched {self.current_pokemon.name} in.')
            return

        if opp_switch:
            # TODO: Switch in abilities and terrain hazards
            print(f'Opponent has switched {self.current_opp.name} out.')
            reset_switch_out(self.current_opp)
            self.current_opp = opp_switch
            print(f'Opponent has switched {self.current_opp.name} in.')

        if switch_idx >= 0:
            # TODO: Switch in abilities and terrain hazards
            print(f'You switched {self.current_pokemon.name} out.')
            reset_switch_out(self.current_pokemon)
            self.current_pokemon = self.my_pty[switch_idx]
            print(f'You switched {self.current_pokemon.name} in.')

    def action(self, current_move, opp_move):
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

        order = move_order(
            self.current_pokemon,
            self.current_pokemon.moves[current_move],
            self.current_opp,
            self.current_opp.moves[opp_move],
            p1_switch,
            p2_switch)

        for idx, (attacker, move, defender) in enumerate(order, start=1):
            # If attacker slower and died before could attack
            if attacker.current_hp <= 0:
                continue
            # Check for Sleep and if the attacker wakes up, TODO: Sleep Talk and Snore
            if attacker.status == 'sleep':
                if attacker.sleep_counter > 0:
                    print(f"{attacker.name} is fast asleep!")
                    attacker.sleep_counter -= 1
                    continue
                attacker.status = None
                print(f"{attacker.name} has woken up!")
            # Check for Paralysis
            if attacker.status == 'paralysis' and paralysis():
                print(f"{attacker.name} is fully paralysed!")
                continue
            # Freeze
            if attacker.status == 'freeze':
                early_return = freeze()
                if early_return:
                    print(f'{attacker.name} is frozen solid!')
                    continue
                attacker.status = None
                print(f"{attacker.name} has thawed out!")
            # Flinch
            if idx >= 2 and flinch is True:
                print(f"{attacker.name} flinched and couldn\'t move!")
                continue
            # Volatile Status early returns, only confusion for now
            if attacker.vol_status:
                early_return = vol_early_returns(attacker, self.current_pokemon)
                if early_return:
                    continue
            # In cases like after recoil damage, selfdestruct, etc.
            if defender.current_hp <= 0:
                print(f"{attacker.name} used {move['name']} on {defender.name}!")
                print("But it failed.")
                continue

            move_hit = calculate_hit_miss(move, attacker, defender)

            if move_hit is MoveOutcome.HIT:
                if move['category'] in ['Physical', 'Special']:
                    self.ps_moves(attacker, defender, move)
                    flinch = flinch_checker(move)
                    if defender.status == 'freeze':
                        thaw(move, defender)
                else:
                    if attacker == self.current_pokemon:
                        print(f"{attacker.name} used {move['name']}!")
                    else:
                        print(f"Opponent {attacker.name} used {move['name']}!")
                    calculate_effects(attacker, defender, move)

            if move_hit is MoveOutcome.MISS:
                if attacker == self.current_pokemon:
                    print(f"{attacker.name} used {move['name']}!")
                else:
                    print(f"Opponent {attacker.name} used {move['name']}!")
                print('But it missed.')

            if move_hit is MoveOutcome.INVULNERABLE:
                if attacker == self.current_pokemon:
                    print(f"{attacker.name} used {move['name']}!")
                else:
                    print(f"Opponent {attacker.name} used {move['name']}!")
                print('But it had no effect.')

    def ps_moves(self, attacker, defender, move):
        """Physical or Special moves, where I need to calculate damage and secondary effects"""
        crit = calculate_crit()
        damage, effectivness = calculate_damage(attacker, defender, move, crit)
        defender.current_hp -= damage
        dead = defender.current_hp <= 0

        # Check to see which side is attacking and represent accordingly
        if attacker == self.current_pokemon:
            print(f"{attacker.name} used {move['name']} on {defender.name}!")
        else:
            print(f"Opponent {attacker.name} used {move['name']} on {defender.name}!")

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
        if move['effects']:
            sec_effects(move, attacker, defender, damage)

        # Text of how much hp left, or if dead
        if dead:
            print(f"\033[91m{defender.name} has fainted! \033[0m")
            defender.fainted = True
        else:
            print(f"{defender.name} has {defender.current_hp} HP left.")

    def end_of_turn(self):
        """Does end of turn calculations like switch if dead, burn, poison, leech seed, ...,
        items like leftovers, hail, sandstorm"""
        # TODO: weather
        # TODO: Abilities
        # TODO: Items

        # Calculate after turn status like burn, leech seed, curse
        if self.current_pokemon.fainted is False:
            after_turn_status(self.current_pokemon)
        if self.current_opp.fainted is False:
            after_turn_status(self.current_opp)

        # Switch after everything it Pokemon is dead. TODO: order of switch
        if self.current_pokemon.fainted is True:
            switch_pok_idx = -1
            self.my_pty_alive = get_non_fainted_pokemon(self.my_pty_alive)
            if len(self.my_pty_alive) == 0:
                return
            while switch_pok_idx < 0 and self.my_pty[switch_pok_idx].name in [p.name for p in self.my_pty_alive]:
                switch_pok_idx, _ = switch_menu(self.current_pokemon, self.my_pty_alive, self.my_pty)
                self.current_pokemon = self.my_pty[switch_pok_idx]
        if self.current_opp.fainted is True:
            self.opp_pty_alive = get_non_fainted_pokemon(self.opp_pty_alive)
            if len(self.opp_pty_alive) == 0:
                return
            self.current_opp = self.opp_pty_alive[
                self.opp_ai.sub_after_death(self.opp_pty_alive, self.current_pokemon, self.current_opp)
            ]
            print(f'the opponent has sent {self.current_opp.name} out')

    def run(self):
        """Runs through the entire battle"""
        self.start_of_battle()
        while len(self.my_pty_alive) > 0 and len(self.opp_pty_alive) > 0:
            opp_move, current_move, switch_idx = self.selection()
            self.start_of_turn(opp_move, switch_idx)
            self.action(current_move, opp_move)
            self.end_of_turn()
            self.turn += 1
            self.current_opp.turns += 1
            self.current_pokemon.turns += 1

        if len(self.my_pty_alive) == 0:
            print("You Lost!")
        if len(self.opp_pty_alive) == 0:
            print("You Won!")


def battle(my_pty, opp_pty):
    """Just so it's easier to call on main"""
    b = Battle(my_pty, opp_pty)
    return b.run()
