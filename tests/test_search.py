"""SearchEngine: structural checks only (no golden data, no tuning values asserted),
so the search can keep changing without rewriting these"""
import numpy as np
import pytest
from SearchEngine.models import (
    valid_action_mask, valid_actions_array, is_terminal_arr, step_arr, node_key, _hp_bracket,
    cvar_from_hist, best_slot, GameState, Node, NodeSnapshot, reconstruct_battle_array,
    ACTION_ORDER, ACTION_SLOT, N_SLOTS, N_BINS,
)
from SearchEngine.mcts_eval import (
    evaluate_terminal, rollout_arr, rollout_pref, field_move_fails
)
from SearchEngine.my_mcts import (
    _select_expand, _backprop, mcts_loop, recursive_backup, print_best_path, wilson_lower_bound,
)
from SearchEngine.helper import find_best_terminal_node, prune_dominated
from Models.idx_const import Pok, Move, Field
from Models.helper import ActionType, BattlePhase, VolStatus, SideCondition
from Models.trainer_ai import return_idx
from battle_driver import (
    SCENARIOS, build_scenario, play_battle, legal_actions, is_over, my_active, opp_active,
    pok_slice, move_slice,
)

MOVE, SWITCH = ActionType.MOVE, ActionType.SWITCH


def mask_actions(arr):
    """valid_action_mask decoded to the same list format as battle_driver.legal_actions"""
    mask = valid_action_mask(arr)
    return [ACTION_ORDER[s] for s in range(N_SLOTS) if mask >> s & 1]


# ── Valid actions / terminal ─────────────────────────────────────────────────

def test_action_slots_round_trip():
    """ACTION_SLOT is the inverse of ACTION_ORDER"""
    assert all(ACTION_SLOT[a] == s for s, a in enumerate(ACTION_ORDER))


def test_valid_actions_single_pokemon(one_v_one):
    """Only my 3 moves, no switches when alone"""
    assert mask_actions(one_v_one()) == [(MOVE, 0), (MOVE, 1), (MOVE, 2)]


def test_struggle_only_when_no_pp(one_v_one):
    """All PP gone → Struggle is the only move"""
    arr = one_v_one()
    for i in range(3):
        move_slice(my_active(arr), i)[Move.PP] = 0
    assert mask_actions(arr) == [(MOVE, 10)]


def test_no_switch_to_fainted_or_active(make_pokemon, make_battle):
    """Switches only to alive, non-active party members"""
    team = [make_pokemon(n, 10, "Run Away", ["Tackle"]) for n in ("Rattata", "Pidgey", "Sentret")]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    pok_slice(arr, 1)[Pok.CURRENT_HP] = 0
    assert mask_actions(arr) == [(MOVE, 0), (SWITCH, 2)]


def test_death_phase_only_switches(make_pokemon, make_battle):
    """After my active faints only replacements are offered"""
    team = [make_pokemon(n, 10, "Run Away", ["Tackle"]) for n in ("Rattata", "Pidgey")]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    my_active(arr)[Pok.CURRENT_HP] = 0
    arr[Field.PHASE] = BattlePhase.DEATH_END_OF_TURN
    assert mask_actions(arr) == [(SWITCH, 1)]


def test_ingrain_blocks_switching_but_not_replacing(make_pokemon, make_battle):
    """An Ingrained active can't switch out, its replacement after fainting is still picked"""
    team = [make_pokemon(n, 10, "Run Away", ["Tackle"]) for n in ("Rattata", "Pidgey")]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    my_active(arr)[Pok.VOL_STATUS] = VolStatus.INGRAIN
    assert mask_actions(arr) == [(MOVE, 0)] == legal_actions(arr)
    my_active(arr)[Pok.CURRENT_HP] = 0
    arr[Field.PHASE] = BattlePhase.DEATH_END_OF_TURN
    assert mask_actions(arr) == [(SWITCH, 1)] == legal_actions(arr)


def test_valid_actions_array_matches_mask(one_v_one):
    """The (n, 2) array form has the same content as the mask"""
    arr = one_v_one()
    assert [tuple(r) for r in valid_actions_array(arr)] == mask_actions(arr)


@pytest.mark.parametrize("name", SCENARIOS)
def test_search_and_engine_agree_during_battles(name):
    """Through whole battles, the search's legal actions / terminal check match an
    independent implementation"""
    def check(arr, _action):
        if not is_over(arr):
            assert mask_actions(arr) == legal_actions(arr)
        assert is_terminal_arr(arr) == is_over(arr)
    for seed in range(10):
        play_battle(build_scenario(name), seed, on_turn=check)


def test_step_arr_advances_a_turn(one_v_one):
    """step_arr plays a whole turn in place"""
    arr = one_v_one()
    step_arr(arr, MOVE, 0, int(return_idx(arr)))
    assert arr[Field.TURN] == 2
    assert arr[Field.PHASE] in (BattlePhase.TURN_START, BattlePhase.DEATH_END_OF_TURN)


def test_gamestate_clone_is_independent(one_v_one):
    """clone() copies the array, stepping the clone leaves the original alone"""
    state = GameState(one_v_one())
    before = state.battle_array.copy()
    clone = state.clone()
    clone.step((MOVE, 0))
    assert (state.battle_array == before).all()
    assert not (clone.battle_array == before).all()
    assert state.get_valid_actions() == mask_actions(before)


# ── Node keys / buckets ──────────────────────────────────────────────────────

@pytest.mark.parametrize("hp, bracket", [(0, 0), (1, 1), (25, 2), (50, 3), (75, 4), (99, 4),
                                         (100, 5)])
def test_hp_bracket(hp, bracket):
    """Fainted 0, then <25/25/50/75%, full 5"""
    assert _hp_bracket(hp, 100) == bracket


def test_node_key_buckets(one_v_one):
    """Same bracket → same key; crossing a bracket or a stage change → different key"""
    arr = one_v_one()
    key = node_key(arr)
    assert node_key(arr.copy()) == key
    opp = opp_active(arr)
    opp[Pok.CURRENT_HP] = opp[Pok.MAX_HP] - 1           # still "75%+"
    k_hurt = node_key(arr)
    opp[Pok.CURRENT_HP] = opp[Pok.MAX_HP] * 3 // 4 + 1
    assert node_key(arr) == k_hurt
    opp[Pok.CURRENT_HP] = 1
    assert node_key(arr) != k_hurt
    my_active(arr)[Pok.ATTACK_STAT_STAGE] = -1
    assert node_key(arr) != key


def test_node_key_sees_field_but_not_timers(one_v_one):
    """Weather, side conditions and Toxic Spikes layers split nodes, the turns left don't"""
    arr = one_v_one()
    key = node_key(arr)
    for slot, value in (
        (Field.WEATHER, 2), (Field.MY_SIDE_COND, SideCondition.REFLECT),
        (Field.OPP_SIDE_COND, SideCondition.STEALTH_ROCK), (Field.MY_TOXIC_SPIKES, 1),
        (Field.OPP_TOXIC_SPIKES, 2),
    ):
        other = arr.copy()
        other[slot] = value
        assert node_key(other) != key
    other = arr.copy()
    other[Field.MY_REFLECT_TURNS] = 3
    other[Field.WEATHER_DURATION] = 4
    assert node_key(other) == key


@pytest.mark.parametrize("move, field, fails", [
    ("Reflect", {}, False),
    ("Reflect", {Field.MY_SIDE_COND: SideCondition.REFLECT}, True),
    ("Reflect", {Field.OPP_SIDE_COND: SideCondition.REFLECT}, False),
    ("Stealth Rock", {Field.OPP_SIDE_COND: SideCondition.STEALTH_ROCK}, True),
    ("Stealth Rock", {Field.MY_SIDE_COND: SideCondition.STEALTH_ROCK}, False),
    ("Toxic Spikes", {Field.OPP_TOXIC_SPIKES: 1}, False),
    ("Toxic Spikes", {Field.OPP_TOXIC_SPIKES: 2}, True),
    ("Rain Dance", {Field.WEATHER: 2}, True),
    ("Rain Dance", {Field.WEATHER: 4}, False),
    ("Growl", {}, False),
])
def test_rollout_skips_field_moves_that_would_fail(
        make_pokemon, make_battle, move, field, fails
):
    """field_move_fails reads the side the move lands on"""
    pok = make_pokemon("Geodude", 20, "Sturdy", [move])
    arr = make_battle([pok], [make_pokemon("Rattata", 20, "Run Away", ["Tackle"])])
    for slot, value in field.items():
        arr[slot] = value
    assert field_move_fails(move_slice(my_active(arr), 0), arr) == fails


# ── CVaR / UCB / backprop ────────────────────────────────────────────────────

def test_cvar_takes_the_worst_tail():
    """15% tail of a half-zero/half-one histogram is all from the bottom bin"""
    hist = np.zeros(N_BINS)
    hist[0], hist[-1] = 10, 10
    assert cvar_from_hist(hist, 20, 0.15) == pytest.approx(0.5 / N_BINS)
    assert cvar_from_hist(np.zeros(N_BINS), 0, 0.15) == 0.0


def test_cvar_never_exceeds_mean():
    """Tail mean <= overall mean for any histogram"""
    rng = np.random.default_rng(0)
    for _ in range(50):
        hist = rng.integers(0, 20, N_BINS).astype(float)
        visits = hist.sum()
        if visits == 0:
            continue
        mean = sum(hist[i] * (i + 0.5) / N_BINS for i in range(N_BINS)) / visits
        assert cvar_from_hist(hist, visits, 0.15) <= mean + 1e-9


def _stats(rows):
    stats = np.zeros((N_SLOTS, 2 + N_BINS))
    for slot, visits, total in rows:
        stats[slot, 0] = visits
        stats[slot, 1] = total
        stats[slot, 2 + min(int(total / visits * N_BINS), N_BINS - 1)] = visits
    return stats


def test_best_slot_skips_unvisited_and_prefers_better_mean():
    """No exploration, no risk: the higher mean wins; unvisited rows are ignored"""
    stats = _stats([(0, 10, 2.0), (3, 10, 8.0)])
    assert best_slot(stats, 20, 0.0, 0.0, 0.15) == 3
    assert best_slot(np.zeros((N_SLOTS, 2 + N_BINS)), 0, 0.42, 0.3, 0.15) == -1


def test_best_slot_explores_rarely_visited():
    """With exploration a barely-tried action beats a well-known slightly better one"""
    stats = _stats([(0, 1000, 600.0), (1, 2, 1.0)])
    assert best_slot(stats, 1002, 2.0, 0.0, 0.15) == 1


def test_backprop_counts(one_v_one):
    """Every node on the path gets the visit, every (parent, action) row gets the value"""
    state = GameState(one_v_one())
    root = Node(state)
    child = Node(state.clone())
    action = (MOVE, 0)
    _backprop([root, child], [action], 1.0, 1, 0)
    _backprop([root, child], [action], 0.0, 0, 0)
    assert root.visits == child.visits == 2
    assert root.wins == 1 and root.win_chance == 0.5
    row = root.stats[ACTION_SLOT[action]]
    assert row[0] == 2 and row[1] == 1.0 and row[2:].sum() == 2


def test_wilson_lower_bound():
    """Lower bound sits below the raw rate and grows with sample size"""
    assert wilson_lower_bound(0, 0) == 0
    assert wilson_lower_bound(9, 10) < 0.9
    assert wilson_lower_bound(90, 100) > wilson_lower_bound(9, 10)


# ── Evaluation / rollout ─────────────────────────────────────────────────────

def test_evaluate_terminal_outcomes(make_pokemon, make_battle):
    """Loss is 0; a clean win beats a win with a death; unfinished stays below wins"""
    team = [make_pokemon(n, 10, "Run Away", ["Tackle"]) for n in ("Rattata", "Pidgey")]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    unfinished, win_flag, _ = evaluate_terminal(arr)
    assert win_flag == 0 and 0 < unfinished < 1
    opp_active(arr)[Pok.CURRENT_HP] = 0
    clean, win_flag, dead = evaluate_terminal(arr)
    assert win_flag == 1 and dead == 0 and unfinished < clean <= 1
    pok_slice(arr, 1)[Pok.CURRENT_HP] = 0
    costly, win_flag, dead = evaluate_terminal(arr)
    assert win_flag == 1 and dead == 1 and costly < clean
    my_active(arr)[Pok.CURRENT_HP] = 0
    assert evaluate_terminal(arr)[:2] == (0.0, 0)


@pytest.mark.parametrize("name", SCENARIOS)
def test_rollout_returns_valid_value(name):
    """Rollouts from the start state finish with a value in [0, 1]"""
    for _ in range(10):
        arr = build_scenario(name)
        value, win, dead = rollout_arr(arr)
        assert 0.0 <= value <= 1.0
        assert win in (0, 1) and dead >= 0


def test_rollout_pref_picks_a_legal_action(one_v_one):
    """Heuristic choice is always one of the offered actions"""
    arr = one_v_one()
    actions = valid_actions_array(arr)
    legal = {tuple(r) for r in actions}
    for _ in range(50):
        a_type, a_idx = rollout_pref(arr, int(return_idx(arr)), actions)
        assert (int(a_type), int(a_idx)) in legal


# ── Snapshots ────────────────────────────────────────────────────────────────

def test_snapshot_reconstruct_round_trip():
    """reconstruct_battle_array restores actives, field and the tracked bench fields"""
    initial = build_scenario("starters")
    arr = initial.copy()
    play_battle(arr, 3, max_turns=6)
    state = GameState(arr)
    snap = NodeSnapshot.from_state(state)
    out = reconstruct_battle_array(snap, initial)
    assert (out[Field.MY_POK:] == arr[Field.MY_POK:]).all()
    assert (opp_active(out) == opp_active(arr)).all()
    if state.phase != BattlePhase.DEATH_END_OF_TURN:
        assert (my_active(out) == my_active(arr)).all()
    for side in (False, True):
        for i in range(6):
            for idx in (Pok.CURRENT_HP, Pok.STATUS, Pok.SLEEP_COUNTER, Pok.TURNS):
                assert pok_slice(out, i, side)[idx] == pok_slice(arr, i, side)[idx]
            for m in range(4):
                assert move_slice(pok_slice(out, i, side), m)[Move.PP] == \
                    move_slice(pok_slice(arr, i, side), m)[Move.PP]


# ── Small end-to-end search ──────────────────────────────────────────────────

def test_select_expand_adds_one_child(one_v_one):
    """First iteration expands exactly one action under the root"""
    root_state = GameState(one_v_one())
    root = Node(root_state)
    _, path, actions = _select_expand(root_state.clone(), root)
    assert len(path) == 2 and len(actions) == 1
    assert list(root.children) == actions
    assert root.expanded == 1 << ACTION_SLOT[actions[0]]


def test_mcts_loop_small_search(capsys):
    """600 iterations (crosses the 500-iteration prune/convergence check) keep the tree
    consistent: root visits == iterations, per-action rows add up"""
    root_state = GameState(build_scenario("starters"))
    root = Node(root_state)
    iterations = 600
    mcts_loop(root, root_state, max_iterations=iterations, terminal_iterations=10**9)
    assert root.visits == iterations
    assert root.stats[:, 0].sum() == iterations
    assert 0.0 <= root.win_chance <= 1.0
    for action, children in root.children.items():
        assert action in ACTION_SLOT
        assert sum(c.visits for c in children) == root.stats[ACTION_SLOT[action], 0]
    node, path, actions = find_best_terminal_node(root)
    assert len(path) == len(actions) + 1 and path[-1] is node
    prune_dominated(root)
    recursive_backup(root)
    print_best_path(root, root_state.battle_array, max_depth=3)
    assert "Best at depth 0" in capsys.readouterr().out


@pytest.mark.parametrize("vol, field, packed, moves", [
    (VolStatus.DISABLE, Pok.DISABLE_TURNS, 3 * 4 + 0, [(MOVE, 1)]),
    (VolStatus.ENCORE, Pok.ENCORE_TURNS, 3 * 4 + 0, [(MOVE, 0)]),
    (VolStatus.TAUNT, Pok.TAUNT_TURNS, 3, [(MOVE, 0)]),
    (VolStatus.TAUNT | VolStatus.ENCORE, Pok.ENCORE_TURNS, 3 * 4 + 1, [(MOVE, 10)]),
])
def test_disable_encore_taunt_filter_moves(make_pokemon, make_battle, vol, field, packed, moves):
    """Blocked moves can't be picked, Struggle when nothing is left, switching stays open"""
    team = [make_pokemon("Rattata", 10, "Run Away", ["Tackle", "Growl"]),
            make_pokemon("Pidgey", 10, "Run Away", ["Tackle"])]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    my_active(arr)[Pok.VOL_STATUS] = vol
    my_active(arr)[field] = packed
    assert mask_actions(arr) == moves + [(SWITCH, 1)] == legal_actions(arr)


def test_bind_blocks_switching(make_pokemon, make_battle):
    """A partially trapped active can't switch out"""
    team = [make_pokemon(n, 10, "Run Away", ["Tackle"]) for n in ("Rattata", "Pidgey")]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Wrap"])])
    my_active(arr)[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED
    assert mask_actions(arr) == [(MOVE, 0)] == legal_actions(arr)


def test_step_stays_in_death_phase_when_the_replacement_faints(make_pokemon, make_battle):
    """A replacement that faints to Stealth Rock leaves the state in the death phase, offering
    only the Pokemon still alive"""
    team = [make_pokemon("Rattata", 10, "Run Away", ["Tackle"]) for _ in range(3)]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    arr[Field.MY_SIDE_COND] = SideCondition.STEALTH_ROCK
    my_active(arr)[Pok.CURRENT_HP] = 0
    pok_slice(arr, 1)[Pok.CURRENT_HP] = 1
    arr[Field.PHASE] = BattlePhase.DEATH_END_OF_TURN
    state = GameState(arr)
    state.step((SWITCH, 1))
    assert state.phase == BattlePhase.DEATH_END_OF_TURN and state.my_active == -1
    assert mask_actions(state.battle_array) == [(SWITCH, 2)]
    state.step((SWITCH, 2))
    assert state.phase == BattlePhase.TURN_START and state.my_active == 2
