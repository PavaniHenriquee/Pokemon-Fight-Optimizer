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
    thaw,
    after_turn_damage,
    early_returns,
    switch_in
)
from Engine.status_calc import sec_effects, calculate_effects
from Engine.damage_calc import calculate_damage, struggle
from Models.trainer_ai import sub_after_death
from Models.idx_const import (
    Pok, Field, Move, Flags, Sec, POK_LEN
)
from Models.helper import (
    count_party, Status, AbilityActivation,
    ActionType, BattlePhase, PHYSICAL_SPECIAL
)
from DataBase.AbilitiesDB import AbilityNames


class Battle():
    """Battle class, where i calculate all the battle, following the flow of battle"""
    def __init__(self, battle_array):
        # Make the normalized battle array
        self.battle_array = battle_array
        self.my_pty = battle_array[0:(6 * POK_LEN)]
        self.opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]

        # current active Pokémon
        opp_active = battle_array[Field.OPP_POK]
        my_active = battle_array[Field.MY_POK]
        self.current_pokemon = battle_array[
            (my_active * POK_LEN):((my_active+1) * POK_LEN)
        ]
        self.current_opp = battle_array[
            ((opp_active+6) * POK_LEN):((opp_active+7) * POK_LEN)
        ]

    def start_of_turn(self, opp_move, switch_idx):
        """What happens before everything in the turn order, so switches and trainer items"""
        # TODO: Opponent Items
        opp_switch = None
        if opp_move == 's':
            i = sub_after_death(
                self.opp_pty, self.current_pokemon, self.current_opp
            )
            opp_switch = self.opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]

        if switch_idx >= 0 and opp_move == 's':
            my_switch = self.my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]
            my_s, opp_s = check_speed(
                self.current_pokemon, self.current_opp, self.battle_array[Field.WEATHER]
            )
            speed_tie = False
            if my_s == opp_s:
                if random.getrandbits(1):
                    speed_tie = True
            if my_s > opp_s or speed_tie:
                # My Pokemon
                reset_switch_out(self.current_pokemon)
                self.battle_array[Field.MY_POK] = switch_idx
                self.battle_array[Field.AI_KNOWS] = 0
                self.battle_array[Field.MY_LAST_MOVE] = 0
                self.current_pokemon = my_switch
                switch_in(self.current_pokemon, self.current_opp)
                # Opponent Pokemon
                reset_switch_out(self.current_opp)
                self.current_opp = opp_switch
                self.battle_array[Field.OPP_POK] = opp_switch
                switch_in(self.current_opp, self.current_pokemon)
            elif my_s < opp_s:
                # Opponent Pokemon
                reset_switch_out(self.current_opp)
                self.battle_array[Field.OPP_POK] = opp_switch
                self.current_opp = opp_switch
                switch_in(self.current_opp, self.current_pokemon)
                # My Pokemon
                reset_switch_out(self.current_pokemon)
                self.battle_array[Field.MY_POK] = switch_idx
                self.battle_array[Field.AI_KNOWS] = 0
                self.battle_array[Field.MY_LAST_MOVE] = 0
                self.current_pokemon = my_switch
                switch_in(self.current_pokemon, self.current_opp)
            return

        if opp_switch:
            reset_switch_out(self.current_opp)
            self.current_opp = opp_switch
            self.battle_array[Field.OPP_POK] = opp_switch
            switch_in(self.current_opp, self.current_pokemon)

        if switch_idx >= 0:
            reset_switch_out(self.current_pokemon)
            self.battle_array[Field.MY_POK] = switch_idx
            self.battle_array[Field.AI_KNOWS] = 0
            self.battle_array[Field.MY_LAST_MOVE] = 0
            self.current_pokemon = self.my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]
            switch_in(self.current_pokemon, self.current_opp)

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
            # TODO: Check everything if opponent switches, specially if they die on entering
            p2_switch = True

        order = move_order(
            self.current_pokemon,
            current_move,
            self.current_opp,
            opp_move,
            p1_switch,
            p2_switch,
            self.battle_array[Field.WEATHER]
        )

        for idx, (attacker, move, defender) in enumerate(order, start=1):
            # If attacker slower and died before could attack
            if attacker[Pok.CURRENT_HP] <= 0 or early_returns(attacker, defender, idx, flinch, move):
                continue

            if not isinstance(move, int):  # This is to check for Struggle since it's not a np.array
                move[Move.PP] -= 1
                if attacker is self.current_pokemon:
                    self.battle_array[Field.MY_LAST_MOVE] = move[Move.ID]
            else:
                self.battle_array[Field.MY_LAST_MOVE] = -1  # -1 to be Struggle

            move_hit = calculate_hit_miss(move, attacker, defender)

            if move_hit is MoveOutcome.HIT:
                if isinstance(move, int):
                    struggle(attacker, defender)
                elif move[Move.CATEGORY] in PHYSICAL_SPECIAL:
                    self.ps_moves(attacker, defender, move)
                    flinch = flinch_checker(move, defender)
                    if defender[Pok.STATUS] == Status.FREEZE:
                        thaw(move, defender)
                else:
                    calculate_effects(attacker, defender, move, self.battle_array[Field.WEATHER])

    def ps_moves(self, attacker, defender, move):
        """Physical or Special moves, where I need to calculate damage and secondary effects"""
        ab_when = defender[Pok.AB_WHEN]
        weather = self.battle_array[Field.WEATHER]
        if ab_when & AbilityActivation.ON_CRITICAL:
            crit = False
        else:
            crit = calculate_crit()
        damage = calculate_damage(attacker, defender, move, weather, crit)
        if damage <= defender[Pok.CURRENT_HP]:
            defender[Pok.CURRENT_HP] -= damage
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
            sec_effects(move, attacker, defender, damage, weather)

    def end_of_turn(self):
        """Does end of turn calculations like switch if dead, burn, poison, leech seed, ...,\n
        items like leftovers\n
        Weather damage like hail, sandstorm"""
        # TODO: Abilities
        # TODO: Items
        m_hp = self.current_pokemon[Pok.CURRENT_HP]
        opp_hp = self.current_opp[Pok.CURRENT_HP]
        weather = self.battle_array[Field.WEATHER]

        # Calculate after turn status like burn, leech seed, curse
        if m_hp > 0:
            dmg = after_turn_damage(self.current_pokemon, weather)
            if dmg != 0:
                if dmg > m_hp:
                    m_hp = 0
                else:
                    m_hp -= dmg
                self.current_opp[Pok.CURRENT_HP] = m_hp
        if opp_hp > 0:
            dmg = after_turn_damage(self.current_opp, weather)
            if dmg != 0:
                if dmg > opp_hp:
                    opp_hp = 0
                else:
                    opp_hp -= dmg
                self.current_opp[Pok.CURRENT_HP] = opp_hp

        # If Opponent is dead
        if opp_hp == 0 and m_hp != 0:
            if count_party(self.opp_pty) == 0:
                return None
            i = sub_after_death(
                self.opp_pty, self.current_pokemon, self.current_opp
            )
            self.battle_array[Field.OPP_POK] = i
            self.current_opp = self.opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
            switch_in(self.current_pokemon, self.current_opp)
            return i
        return None

    def switch_in_action(self, switch_idx: int):
        """Grab the switch idx from MCTS and progress it"""
        if self.current_opp[Pok.CURRENT_HP] <= 0:
            i = sub_after_death(
                self.opp_pty, self.current_pokemon, self.current_opp
            )
            opp_switch = self.opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
            my_switch = self.my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]

            my_s, opp_s = check_speed(
                my_switch, opp_switch, self.battle_array[Field.WEATHER]
            )
            speed_tie= False
            if my_s == opp_s:
                if random.getrandbits(1):
                    speed_tie = True

            if my_s > opp_s or speed_tie:
                # My Pokemon
                self.battle_array[Field.MY_POK] = switch_idx
                self.battle_array[Field.AI_KNOWS] = 0
                self.battle_array[Field.MY_LAST_MOVE] = 0
                self.current_pokemon = self.my_pty[
                    (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
                ]

                # Opponent Pokemon
                self.current_opp = opp_switch
                self.battle_array[Field.OPP_POK] = opp_switch

                # Switch in effects after they are already switched
                switch_in(self.current_pokemon, self.current_opp)
                switch_in(self.current_opp, self.current_pokemon)
                self.battle_array[Field.TURN] += 1
                self.current_opp[Pok.TURNS] += 1
                self.current_pokemon[Pok.TURNS] += 1
            elif my_s < opp_s:
                # Opponent Pokemon
                self.battle_array[Field.OPP_POK] = opp_switch
                self.current_opp = opp_switch

                # My Pokemon
                self.battle_array[Field.MY_POK] = switch_idx
                self.battle_array[Field.AI_KNOWS] = 0
                self.battle_array[Field.MY_LAST_MOVE] = 0
                self.current_pokemon = self.my_pty[
                    (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
                ]

                # Switch in effects after they are already switched
                switch_in(self.current_opp, self.current_pokemon)
                switch_in(self.current_pokemon, self.current_opp)
                self.battle_array[Field.TURN] += 1
                self.current_opp[Pok.TURNS] += 1
                self.current_pokemon[Pok.TURNS] += 1
            return
        self.battle_array[Field.MY_POK] = switch_idx
        self.current_pokemon = self.my_pty[
            (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
        ]
        self.battle_array[Field.TURN] += 1
        self.current_opp[Pok.TURNS] += 1
        self.current_pokemon[Pok.TURNS] += 1
        self.battle_array[Field.AI_KNOWS] = 0
        self.battle_array[Field.MY_LAST_MOVE] = 0


    def turn_sim(self, opp_move, current_action):
        """One turn"""
        if current_action[0] == ActionType.MOVE:
            switch_idx = -1
            current_move = current_action[1]
        else:
            current_move = -1
            switch_idx = current_action[1]
        self.start_of_turn(opp_move, switch_idx)
        self.action(current_move, opp_move)
        opp_idx = self.end_of_turn()

        if not opp_idx:
            opp_idx = self.battle_array[Field.OPP_POK]
        if self.current_pokemon[Pok.CURRENT_HP] <= 0:
            return BattlePhase.DEATH_END_OF_TURN, opp_idx

        self.battle_array[Field.TURN] += 1
        self.current_opp[Pok.TURNS] += 1
        self.current_pokemon[Pok.TURNS] += 1
        return BattlePhase.TURN_START, opp_idx
