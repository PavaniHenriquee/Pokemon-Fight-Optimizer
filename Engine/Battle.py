"""Refactored Battle module: encapsulates battle state into a Battle class.

This preserves the original behaviour while removing module-level globals.
Keep helper functions imported from your project (calculate_damage, calculate_status, etc.).
"""

from Engine.damage_calc import calculate_damage
from Engine.status_calc import calculate_status, sec_stat_change, after_turn_status
from Utils.helper import (
    calculate_hit_miss,
    calculate_crit,
    get_non_fainted_pokemon,
    switch_menu,
    speed_tie,
)
from Models.trainer_ai import TrainerAI


class Battle:
    """Encapsulates a single battle between two trainer parties.

    Usage:
        b = Battle(my_party, opp_party)
        b.run()

    The class was designed to keep behaviour identical to your original
    script while removing module-level globals and making state explicit.
    """

    def __init__(self, my_pty, opp_pty, interactive=True):
        # copy the lists so external callers don't get mutated lists unexpectedly
        self.my_pty_alive = list(my_pty)
        self.opp_pty_alive = list(opp_pty)

        self.opp_ai = TrainerAI()
        self.turn = 1
        self.interactive = interactive

        # current active Pokémon
        self.current_pokemon = self.my_pty_alive[0]
        self.current_opp = self.opp_pty_alive[0]

        print(f"You sent out {self.current_pokemon.name}!")
        print(f"The opponent sent out {self.current_opp.name}!")

    def battle_menu(self):
        """Prompt the player for a move or switch.

        Returns:
            (current_move, switch_pok, current_pokemon)
            current_move: index of move chosen or -1 if switch chosen
            switch_pok: index selected from the alive list (or -1)
            current_pokemon: the (possibly updated) current pokemon object
        """
        current_move = -1
        switch_pok = -1
        while current_move < 0 or current_move >= len(self.current_pokemon.moves):
            print(f"Your current Pokemon is {self.current_pokemon.name}")
            if len(self.my_pty_alive) > 1:
                print("Choose one of the moves or if you want to switch:")
            else:
                print("Choose one of the moves:")

            for i, move in enumerate(self.current_pokemon.moves):
                print(f"{i+1}. {move['name']}")

            if len(self.my_pty_alive) > 1:
                print('s. Switch')

            choice = input("Choose: ")
            if choice.isdigit():
                current_move = int(choice) - 1  # Because of index 0
                if current_move < 0 or current_move >= len(self.current_pokemon.moves):
                    print("Please select a valid move.")
                    current_move = -1
                continue
            if choice == 's' and len(self.my_pty_alive) > 1:
                alive_pokemon = self.my_pty_alive.copy()
                # remove current from the choices
                del alive_pokemon[alive_pokemon.index(self.current_pokemon)]
                while switch_pok < 0 or switch_pok >= len(alive_pokemon):
                    switch_pok, ret_menu, self.current_pokemon = switch_menu(alive_pokemon, self.current_pokemon)
                    if ret_menu:
                        break
                if switch_pok >= 0:
                    break
                continue
            print("Please select a valid answer.")
            current_move = -1

        return current_move, switch_pok, self.current_pokemon

    def battle_turn(self, p1, move1, p2, move2, p1_switch=False):
        """Perform a single turn of the battle.

        p1 and p2 are the attacker/defender Pokémon objects as in the original
        functions. move1 and move2 follow the original conventions (dictionaries
        for real moves; the original code sometimes passes 0 when a switch
        is performed but p1_switch=True so we handle that case by not accessing
        move1 when p1_switch is True).
        """
        dead = False
        # Determine order
        if p1_switch:
            order = [(p2, move2, p1)]
        elif (move1['priority'] != 0 or move2['priority'] != 0) and move1['priority'] != move2['priority']:
            if move1['priority'] > move2['priority']:
                order = [(p1, move1, p2), (p2, move2, p1)]
            else:
                order = [(p2, move2, p1), (p1, move1, p2)]
        else:
            if p1.speed > p2.speed:
                order = [(p1, move1, p2), (p2, move2, p1)]
            elif p2.speed > p1.speed:
                order = [(p2, move2, p1), (p1, move1, p2)]
            else:
                order = speed_tie(p1, move1, p2, move2)

        for attacker, move, defender in order:
            if defender.current_hp <= 0:
                print(f"{attacker.name} used {move['name']} on {defender.name}!")
                print("But it failed.")
                continue  # In cases like self-destruct
            if attacker.current_hp <= 0:
                continue  # Failsafe

            # Check Move accuracy
            move_hit = calculate_hit_miss(move, attacker, defender)

            # Calculate move damage or effects
            if move_hit is True:
                if move['category'] == "Physical" or move['category'] == "Special":
                    # Calculate if it's a critical hit (Only gen 3 to 5 behaviour preserved)
                    crit = calculate_crit()
                    damage, effectiveness = calculate_damage(attacker, defender, move, crit)
                    defender.current_hp -= damage
                    dead = defender.current_hp <= 0
                    # print statements kept intentionally to mirror original behaviour
                    if attacker == p1:
                        print(f"{attacker.name} used {move['name']} on {defender.name}!")
                    else:
                        print(f"Opponent {attacker.name} used {move['name']} on {defender.name}!")

                    if crit is True:
                        print("\033[91mIt's a critical hit! \033[0m")

                    print(f"It dealt {damage} damage.")
                    if effectiveness != 1:
                        print(f"Effectiveness: {effectiveness}x")

                    # Check for move effects
                    if move['effects']:
                        sec_stat_change(move, attacker, defender)

                    if dead:
                        print(f"\033[91m{defender.name} has fainted! \033[0m")
                        defender.fainted = True
                    else:
                        print(f"{defender.name} has {defender.current_hp} HP left.")
                else:
                    print(f"{attacker.name} used {move['name']}!")
                    calculate_status(attacker, defender, move)
            else:
                print(f"{attacker.name} used {move['name']} on {defender.name}!")
                print('But it missed!')

        if not dead:
            after_turn_status(p1)
            after_turn_status(p2)
        dead_u = p1.current_hp <= 0
        dead_ai = p2.current_hp <= 0
        if dead_u:
            print(f"\033[91m{p1.name} has fainted! \033[0m")
        if dead_ai:
            print(f"\033[91m{p2.name} has fainted! \033[0m")

        # end of turn, increment instance turn counter
        self.turn += 1

    def run(self):
        """Main loop for the whole battle. Returns the result string ('win'|'lose')."""
        while len(self.my_pty_alive) > 0 and len(self.opp_pty_alive) > 0:
            opp_move_idx = self.opp_ai.return_idx(
                self.current_opp, self.current_pokemon, self.my_pty_alive, self.opp_pty_alive, self.turn
            )
            opp_move = self.current_opp.moves[opp_move_idx]

            current_move, switch_pok, self.current_pokemon = self.battle_menu()

            if current_move >= 0:  # if switched current_move is -1
                self.battle_turn(self.current_pokemon, self.current_pokemon.moves[current_move], self.current_opp, opp_move)
            elif switch_pok >= 0:
                # when switching we call battle_turn with p1_switch=True
                self.battle_turn(self.current_pokemon, 0, self.current_opp, opp_move, p1_switch=True)

            # prune fainted
            self.my_pty_alive = get_non_fainted_pokemon(self.my_pty_alive)
            self.opp_pty_alive = get_non_fainted_pokemon(self.opp_pty_alive)

            if len(self.my_pty_alive) == 0:
                print("You Lost!")
                return 'lose'
            if len(self.opp_pty_alive) == 0:
                print("You Won!")
                return 'win'

            # handle opponent faint replacement
            if self.current_opp.fainted:
                self.current_opp = self.opp_pty_alive[self.opp_ai.sub_after_death(self.opp_pty_alive, self.current_pokemon, self.current_opp)]
                print(f'the opponent has sent {self.current_opp.name} out')

            # handle player faint replacement
            if self.current_pokemon.fainted:
                switch_pok = -1
                while switch_pok < 0 or switch_pok >= len(self.my_pty_alive):
                    switch_pok, ret_menu, self.current_pokemon = switch_menu(self.my_pty_alive, self.current_pokemon)
                    if ret_menu:
                        break

        # loop end (defensive)
        if len(self.opp_pty_alive) == 0:
            print("You Won!")
            return 'win'
        print("You Lost!")
        return 'lose'


# Optional helper for backwards compatibility with your previous API
def battle(my_pty, opp_pty):
    """Compatibility wrapper that mirrors the original function signature."""
    b = Battle(my_pty, opp_pty)
    return b.run()
