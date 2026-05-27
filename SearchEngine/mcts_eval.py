"""Evaluation of terminal and current state"""
import random
from Models.idx_const import(
    Pok, Sec, POK_LEN, OFFSET_MOVE, MOVE_STRIDE, Move, Field
)
from Models.helper import count_party, count_Id, MoveCategory
from Engine.damage_calc import calculate_damage, struggle
from Utils.helper import get_type_effectiveness
from SearchEngine.models import ActionType


def party_hp_fraction(battle_array, offset, maxp):
    """Compute sum(current_hp / max_hp) across a party (0..6)"""
    total_frac = 0.0
    for i in range(maxp):
        start = offset + i * POK_LEN
        curr = battle_array[start + Pok.CURRENT_HP]
        mx = battle_array[start + Pok.MAX_HP]
        if mx <= 0:
            frac = 0.0
        else:
            frac = max(0.0, curr) / mx
        total_frac += frac
    return total_frac / maxp  # normalized 0..1

def count_fainted(battle_array, offset, maxp):
    """ Opposite of count party"""
    fallen = 0
    for i in range(maxp):
        start = offset + i * POK_LEN
        if battle_array[start + Pok.CURRENT_HP] <= 0:
            fallen += 1
    return fallen

def evaluate_terminal(sim_state) -> tuple[float, int, int]:
    """
    Terminal evaluation for MCTS backprop with strictly segregated reward tiers.
    Guaranteed Win (0-death) > Guaranteed Win (Casualties) > Incomplete Rollout > Loss
    """
    my_pty_count = count_Id(sim_state.battle_array[0:(6 * POK_LEN)])
    my_alive = count_party(sim_state.battle_array[0:(6 * POK_LEN)])
    opp_alive = count_party(sim_state.battle_array[(6 * POK_LEN):(12 * POK_LEN)])
    dead = my_pty_count - my_alive

    # 1. ACTUAL VICTORY
    if opp_alive == 0 and my_alive > 0:
        # Base value starts at 0.50 for winning, and scales up to 1.0 based on survival
        # 6/6 alive = 1.0 | 5/6 alive = 0.916 | 1/6 alive = 0.583
        win_value = 0.36 + (0.64 * (my_alive / my_pty_count)**2)

        # Turn penalty is tightly constrained (max 0.05) so it can NEVER
        # cross the gap between survival counts (which is 0.50 / 6 = 0.0833)
        turn = sim_state.battle_array[Field.TURN]
        turn_penalty = min(0.05, turn * 0.0005)

        return win_value - turn_penalty, 1, dead

    # 2. ACTUAL LOSS / DRAW
    if my_alive == 0:
        return 0.0, 0, dead

    # 3. INCOMPLETE ROLLOUT (Max Depth Reached)
    # Scaled to exist strictly between 0.01 and 0.35
    opp_pty_count = count_Id(sim_state.battle_array[(6 * POK_LEN):(12 * POK_LEN)])
    my_hp = party_hp_fraction(sim_state.battle_array, 0, my_pty_count)
    opp_hp = party_hp_fraction(sim_state.battle_array, 6 * POK_LEN, opp_pty_count)

    heuristic = my_hp / (my_hp + opp_hp + 1e-9)
    incomplete_value = 0.01 + (heuristic * 0.34)  # Range: 0.01 to 0.35

    return incomplete_value, 0, dead


def _weighted_choice(ev):
    """
    Fast path: single dominant action (very common case)
    Avoids full scan most of the time
    """
    best_action, best_weight = ev[0]
    total = best_weight
    for action, weight in ev[1:]:
        total += weight
        if weight > best_weight:
            best_weight = weight
            best_action = action

    # If one action is overwhelmingly dominant, pick it directly
    # 100 vs rest-at-1: e.g. 4 actions → total ~103, dominant has 97% chance anyway
    if best_weight >= total * 0.90:
        return best_action

    # Otherwise do the proper weighted draw
    r = random.randrange(total)
    cumulative = 0
    for action, weight in ev:
        cumulative += weight
        if r < cumulative:
            return action


def rollout_pref(c_pok, o_pok, o_idx, weather, actions) -> tuple:
    """
    Prefer certain moves to reduce noise
    """
    if o_idx != 10 or o_idx < 0:
        o_move = o_pok[OFFSET_MOVE + o_idx * MOVE_STRIDE: OFFSET_MOVE + (o_idx + 1) * MOVE_STRIDE]
        o_dmg = calculate_damage(o_pok, c_pok, o_move, weather)  # still worth it for 1 calc
    else:
        o_dmg = struggle(o_pok, c_pok, rec=False)
    opp_hp_ratio = o_pok[Pok.CURRENT_HP] * 4 // o_pok[Pok.MAX_HP]
    faster = c_pok[Pok.SPEED] > o_pok[Pok.SPEED]
    can_survive = o_dmg < c_pok[Pok.CURRENT_HP]
    ev = []

    for a in actions:
        weight = 1

        if a[0] == ActionType.MOVE:
            if a[1] == 10:
                continue
            move = c_pok[OFFSET_MOVE + a[1] * MOVE_STRIDE: OFFSET_MOVE + (a[1] + 1) * MOVE_STRIDE]
            cat = move[Move.CATEGORY]

            if cat == MoveCategory.STATUS:
                # Status moves: give a small base weight so they're not excluded
                weight = 1

            else:
                # Cheap type effectiveness first — no damage calc
                eff, den = get_type_effectiveness(move[Move.TYPE], o_pok[Pok.TYPE1], o_pok[Pok.TYPE2])
                eff_ratio = eff // den  # 0, 1, 2, or 4

                if eff_ratio == 0:
                    weight = 0  # immune — never pick this
                else:
                    # STAB bonus
                    stab = move[Move.TYPE] in (c_pok[Pok.TYPE1], c_pok[Pok.TYPE2])

                    # Only do full damage calc if it looks like a KO candidate
                    likely_strong = (
                        eff_ratio >= 2                          # super effective
                        or (stab and move[Move.POWER] >= 60)   # strong STAB
                        or (opp_hp_ratio == 0 and eff_ratio >= 1)   # <25% HP, any non-resisted
                        or (opp_hp_ratio == 1 and eff_ratio >= 1 and stab)  # <50% HP, STAB neutral
                    )

                    if likely_strong:
                        dmg = calculate_damage(c_pok, o_pok, move, weather)
                        if dmg >= o_pok[Pok.CURRENT_HP] and (faster or can_survive):
                            weight = 100  # KO when safe to do so
                        elif eff_ratio == 4:
                            weight = 20
                        elif eff_ratio == 2:
                            weight = 8
                        elif stab:
                            weight = 4
                    else:
                        # Resisted or neutral, no calc — rough signal only
                        if eff_ratio == 1:
                            weight = 2 if stab else 1
                        else:  # 0.5x
                            weight = 1

                    # Secondary effect scaled by chance
                    if move[Sec.CHANCE]:
                        weight += move[Sec.CHANCE] // 10

        else:  # switch
            if o_dmg >= c_pok[Pok.CURRENT_HP] and not faster:
                weight = 50

        if weight > 0:
            ev.append((a, weight))

    if not ev:  # fallback if everything was immune or list empty
        return random.choice(actions)

    return _weighted_choice(ev)
