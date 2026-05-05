"""Battle class where it follows battle flow, doing the sequence selection, start of turn, actions,
end of turn and repeat"""
import random
from Engine.engine_helper import (
    check_speed,
    move_order,
    calculate_hit_miss,
    calculate_crit,
    reset_switch_out,
    MoveOutcome,
    flinch_checker,
    thaw
)
from Engine.status_calc import paralysis, sec_effects, calculate_effects, after_turn_status, freeze
from Engine.damage_calc import calculate_damage
from Models.trainer_ai import TrainerAI
from Models.idx_const import (
    Pok, Field, Move, Sec, POK_LEN, MOVE_STRIDE, OFFSET_MOVE
)
from Models.helper import count_party, Status, VolStatus, MoveCategory


class Battle():
    """Battle class, where i calculate all the battle, following the flow of battle"""
    def __init__(self, battle_array=None):
        # Make the normalized battle array
        self.battle_array = battle_array
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
                if random.getrandbits(1):
                    speed_tie_1 = True
                else:
                    speed_tie_2 = True
            if my_s > opp_s or speed_tie_1:
                # TODO: Switch in abilities and terrain hazards
                # My Pokemon
                reset_switch_out(self.current_pokemon)
                self.battle_array[Field.MY_POK] = switch_idx
                self.current_pokemon = self.my_pty[(switch_idx * self.pok_features):((switch_idx+1) * self.pok_features)]
                # Opponent Pokemon
                reset_switch_out(self.current_opp)
                self.current_opp = opp_switch
                self.battle_array[Field.OPP_POK] = opp_switch
            elif my_s < opp_s or speed_tie_2:
                # TODO: Switch in abilities and terrain hazards
                # Opponent Pokemon
                reset_switch_out(self.current_opp)
                self.battle_array[Field.OPP_POK] = opp_switch
                self.current_opp = opp_switch
                # My Pokemon
                reset_switch_out(self.current_pokemon)
                self.battle_array[Field.MY_POK] = switch_idx
                self.current_pokemon = self.my_pty[(switch_idx * self.pok_features):((switch_idx+1) * self.pok_features)]
            return

        if opp_switch:
            # TODO: Switch in abilities and terrain hazards
            reset_switch_out(self.current_opp)
            self.current_opp = opp_switch
            self.battle_array[Field.OPP_POK] = opp_switch

        if switch_idx >= 0:
            # TODO: Switch in abilities and terrain hazards
            reset_switch_out(self.current_pokemon)
            self.battle_array[Field.MY_POK] = switch_idx
            self.current_pokemon = self.my_pty[(switch_idx * self.pok_features):((switch_idx+1) * self.pok_features)]

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
            # TODO: Check everything if opponent switches, especially if they die on entering
            p2_switch = True
            opp_move = 0  # Just so i don't break the move_order def call being ->
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
                if freeze():
                    continue
                attacker[Pok.STATUS] = 0
            # Flinch
            if idx >= 2 and flinch is True:
                continue
            # Volatile Status early returns, only not fully implemented confusion for now
            if attacker[Pok.VOL_STATUS] != 0 and attacker[Pok.VOL_STATUS] & VolStatus.CONFUSION:
                if random.getrandbits(1):
                    continue
            # In cases like after recoil damage, selfdestruct, etc.
            if defender[Pok.CURRENT_HP] <= 0:
                #TODO: Some moves still go through, like self buff, dig, future sight
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

    def ps_moves(self, attacker, defender, move):
        """Physical or Special moves, where I need to calculate damage and secondary effects"""
        crit = calculate_crit()
        damage = calculate_damage(attacker, defender, move, crit)
        if damage <= defender[Pok.CURRENT_HP]:
            defender[Pok.CURRENT_HP] -= damage
        else:
            defender[Pok.CURRENT_HP] = 0

        # TODO: recoil

        # Check for secondary effects and apply them
        if move[Sec.CHANCE]:
            sec_effects(move, attacker, defender, damage)

    def end_of_turn(self, switch_idx=None):
        """Does end of turn calculations like switch if dead, burn, poison, leech seed, ...,\n
        items like leftovers\n
        Weather damage like hail, sandstorm"""
        # TODO: weather
        # TODO: Abilities
        # TODO: Items

        # If my Pokemon is dead and my switch
        if isinstance(switch_idx, int):
            self.battle_array[Field.MY_POK] = switch_idx
            self.current_pokemon = self.my_pty[(switch_idx * self.pok_features):((switch_idx+1) * self.pok_features)]
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

        # If Opponent is dead
        if self.current_opp[Pok.CURRENT_HP] <= 0:
            if count_party(self.opp_pty) == 0:
                return
            i = self.opp_ai.sub_after_death(
                self.opp_pty, self.current_pokemon, self.current_opp
            )
            self.battle_array[Field.OPP_POK] = i
            self.current_opp = self.opp_pty[(i * self.pok_features):((i+1) * self.pok_features)]
            return i


    def turn_sim(self, opp_move, current_action):
        """One turn"""
        from SearchEngine.my_mcts import BattlePhase
        if current_action[0] == 'move':
            switch_idx = -1
            current_move = current_action[1]
        else:
            current_move = -1
            switch_idx = current_action[1]
        if self.current_opp[0] == 0 or self.current_pokemon[0] == 0:
            pass
        self.start_of_turn(opp_move, switch_idx)
        self.action(current_move, opp_move)
        opp_idx = self.end_of_turn()
        self.battle_array[Field.TURN] += 1
        self.turn += 1
        self.current_opp[Pok.TURNS] += 1
        self.current_pokemon[Pok.TURNS] += 1
        if not opp_idx:
            opp_idx = self.battle_array[Field.OPP_POK]
        if self.current_pokemon[Pok.CURRENT_HP] <= 0:
            return BattlePhase.DEATH_END_OF_TURN, opp_idx

        return BattlePhase.TURN_START, opp_idx
