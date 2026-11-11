"""SearchEngine: structural checks only (no golden data, no tuning values asserted),
so the search can keep changing without rewriting these"""
import random
import numpy as np
import pytest
from SearchEngine.models import (
    valid_action_mask, valid_actions_array, is_terminal_arr, step_arr, node_key, _hp_bracket,
    best_slot, GameState, Node, NodeSnapshot, reconstruct_battle_array, random_untried_slot,
    opp_turns, foe_pp_along_path, real_position, ACTION_ORDER, ACTION_SLOT, N_SLOTS, ROOT_C,
    STATS_COLS, VOL2_KEY_BITS, AB_KEY_BITS, AB_KEY_SHIFT, TURN_AB_KEY_BIT, OPP_DIDNT_MOVE,
    OPP_STRUGGLED, OPP_SWITCHED, OPP_USED_ITEM, OPP_TURN_BITS, SIDE_KEY_SHIFT, CHOICE_KEY_SHIFT,
    STOCKPILE_KEY_SHIFT, LAST_RESORT_KEY_BIT, ENCORE_KEY_SHIFT, DISABLE_KEY_SHIFT, SIDE_COND_K1_BITS,
    SIDE_COND_HI_BITS, SPIKES_KEY_SHIFT, ITEM_KEY_SHIFT, ITEM_KEY_BITS, TYPE_KEY_SHIFT, TYPE_KEY_BITS,
    LOCK_KEY_SHIFT, LOCK_KEY_MASK, CHARGING_KEY_BIT, RECHARGING_KEY_BIT, GRAVITY_KEY_BIT,
    TRICK_ROOM_KEY_BIT,
)
from SearchEngine import models as search_models
from SearchEngine.mcts_eval import (
    evaluate_terminal, rollout_arr, rollout_pref, field_move_fails, status_move_blocked,
    sleep_move_fails
)
from SearchEngine.my_mcts import (
    _select_expand, _backprop, mcts_loop, recursive_backup, print_best_path, wilson_lower_bound,
)
from SearchEngine.helper import find_best_terminal_node, prune_dominated
from Models.idx_const import Pok, Move, Field, Item, ITEM_LEN
from Models.item import ITEM_TABLE
from Models.helper import (
    ActionType, BattlePhase, Status, VolStatus, VolStatus2, SideCondition, Types, Weather
)
from Models.constants import _POTIONS_POTION
from Models.trainer_ai import return_idx
from DataBase.ItemDB import ItemNames
from DataBase.AbilitiesDB import AbilityNames
from DataBase.MoveDB import MoveName
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


@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_perish_song(one_v_one, mine):
    """The Perish Song bit splits nodes on either side, like the other volatiles"""
    arr = one_v_one()
    key = node_key(arr)
    (my_active(arr) if mine else opp_active(arr))[Pok.VOL_STATUS] |= VolStatus.PERISH_SONG
    assert node_key(arr) != key


def test_node_key_sees_field_but_not_timers(one_v_one):
    """Weather, Gravity, side conditions and Toxic Spikes layers split nodes, the turns left don't"""
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
    gravity = arr.copy()
    gravity[Field.GRAVITY_TURNS] = 5
    key_gravity = node_key(gravity)
    assert key_gravity != key
    gravity[Field.GRAVITY_TURNS] = 2
    assert node_key(gravity) == key_gravity


@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_vol_status2(one_v_one, mine):
    """Minimize (VolStatus2) splits nodes on either side, and the two sides don't collide"""
    arr = one_v_one()
    key = node_key(arr)
    (my_active(arr) if mine else opp_active(arr))[Pok.VOL_STATUS2] |= VolStatus2.MINIMIZE
    assert node_key(arr) != key
    other = one_v_one()
    (opp_active(other) if mine else my_active(other))[Pok.VOL_STATUS2] |= VolStatus2.MINIMIZE
    assert node_key(other) != node_key(arr)


def test_node_key_sees_power_trick(one_v_one):
    """Power Trick's VolStatus2 bit is under VOL2_KEY_BITS"""
    arr = one_v_one()
    key = node_key(arr)
    my_active(arr)[Pok.VOL_STATUS2] |= VolStatus2.POWER_TRICK
    assert node_key(arr) != key


@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_changed_ability(one_v_one, mine):
    """An ability Trace or Worry Seed changed splits nodes by which ability it is, the sides
    don't collide, and an unchanged ability adds nothing"""
    def build(ab_mine, ability):
        arr = one_v_one()
        pok = my_active(arr) if ab_mine else opp_active(arr)
        pok[Pok.BASE_AB_ID] = AbilityNames.TRACE
        pok[Pok.AB_ID] = ability
        return arr
    base = one_v_one()
    sturdy = build(mine, AbilityNames.STURDY)
    assert node_key(sturdy) != node_key(base)
    assert node_key(build(mine, AbilityNames.ROCK_HEAD)) != node_key(sturdy)
    assert node_key(build(not mine, AbilityNames.STURDY)) != node_key(sturdy)


def test_ability_ids_fit_the_key_bits():
    """node_key packs a changed ability id in AB_KEY_BITS bits per side, up to k1 bit 25"""
    ids = [v for k, v in vars(AbilityNames).items() if k.isupper() and isinstance(v, int)]
    assert max(ids) < 2 ** AB_KEY_BITS
    assert AB_KEY_SHIFT + 2 * AB_KEY_BITS <= 26


@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_held_item(one_v_one, mine):
    """Holding an item or not (an eaten berry, Knock Off) splits nodes, and the sides don't
    collide"""
    def build(item_mine):
        arr = one_v_one()
        my_active(arr)[Item.ID] = 0
        (my_active(arr) if item_mine else opp_active(arr))[Item.ID] = ItemNames.ORAN_BERRY
        return arr
    empty = one_v_one()
    my_active(empty)[Item.ID] = 0
    assert node_key(build(mine)) != node_key(empty)
    assert node_key(build(mine)) != node_key(build(not mine))


@pytest.mark.parametrize("mine", [True, False])
@pytest.mark.parametrize("ability, on_turns, off_turns", [
    (AbilityNames.TRUANT, 2, 3),       # loafs this turn or acts
    (AbilityNames.SLOW_START, 5, 6),   # still slowed or done
])
def test_node_key_sees_turn_count_abilities(one_v_one, mine, ability, on_turns, off_turns):
    """Truant's loaf turn and an active Slow Start split nodes, and the sides don't collide"""
    def build(ab_mine, turns):
        arr = one_v_one()
        pok = my_active(arr) if ab_mine else opp_active(arr)
        pok[Pok.AB_ID] = ability
        pok[Pok.TURNS_ACTIVE] = turns
        return arr
    assert node_key(build(mine, on_turns)) != node_key(build(mine, off_turns))
    assert node_key(build(mine, off_turns)) == node_key(build(mine, off_turns + 2))
    assert node_key(build(mine, on_turns)) != node_key(build(not mine, on_turns))


def test_vol_status_leaves_the_turn_ability_bit_free():
    """The turn-count ability bit sits right above each side's VolStatus in k3"""
    assert sum(_int_attrs(VolStatus)) < 2 ** TURN_AB_KEY_BIT
    assert TURN_AB_KEY_BIT < 32


def test_vol_status2_fits_node_key():
    """node_key packs each side's VOL_STATUS2 into VOL2_KEY_BITS bits, grow it with the bitmap"""
    assert sum(_int_attrs(VolStatus2)) < 2 ** VOL2_KEY_BITS


def test_node_key_fields_fit():
    """k5 and k6 fields follow each other without overlap and leave each half's top bit free,
    and what they hold fits their bits"""
    k5 = [(0, VOL2_KEY_BITS), (CHOICE_KEY_SHIFT, 3), (STOCKPILE_KEY_SHIFT, 2), (LAST_RESORT_KEY_BIT, 1),
          (ENCORE_KEY_SHIFT, 2), (DISABLE_KEY_SHIFT, 2)]
    k6 = [(0, SIDE_COND_HI_BITS), (SPIKES_KEY_SHIFT, 2), (ITEM_KEY_SHIFT, ITEM_KEY_BITS),
          (TYPE_KEY_SHIFT, 2 * TYPE_KEY_BITS), (LOCK_KEY_SHIFT, LOCK_KEY_MASK.bit_length()),
          (CHARGING_KEY_BIT, 1), (RECHARGING_KEY_BIT, 1)]
    for fields in (k5, k6):
        for (shift, bits), (next_shift, _) in zip(fields, fields[1:]):
            assert shift + bits == next_shift
        assert fields[-1][0] + fields[-1][1] < SIDE_KEY_SHIFT
    assert sum(_int_attrs(SideCondition)) < 2 ** (SIDE_COND_K1_BITS + SIDE_COND_HI_BITS)
    assert max(_int_attrs(ItemNames)) < 2 ** ITEM_KEY_BITS
    assert max(_int_attrs(Types)) < 2 ** TYPE_KEY_BITS
    assert TRICK_ROOM_KEY_BIT == GRAVITY_KEY_BIT + 1 < 63


def _keys_after(one_v_one, change, mine):
    """node_key before, after change(pok) on one active, and after the same change on the other"""
    base = one_v_one()
    keys = [node_key(base)]
    for on_mine in (mine, not mine):
        arr = one_v_one()
        change(my_active(arr) if on_mine else opp_active(arr))
        keys.append(node_key(arr))
    return keys


def _splits(one_v_one, change, mine):
    """The change splits nodes on that side, and the two sides don't collide"""
    base, changed, other_side = _keys_after(one_v_one, change, mine)
    return changed != base and changed != other_side


@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_item_id(one_v_one, mine):
    """A swapped item (Trick, Thief) splits nodes even though both still hold one"""
    def swap(pok):
        pok[Item.ID] = ItemNames.CHARCOAL if pok[Item.ID] != ItemNames.CHARCOAL else ItemNames.LEFTOVERS
    assert _splits(one_v_one, swap, mine)


@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_types(one_v_one, mine):
    """A changed type (Conversion, Color Change) splits nodes by which type"""
    def change(pok):
        pok[Pok.TYPE1] = Types.STEEL if pok[Pok.TYPE1] != Types.STEEL else Types.WATER
    def change2(pok):
        pok[Pok.TYPE2] = Types.GHOST if pok[Pok.TYPE2] != Types.GHOST else Types.DARK
    assert _splits(one_v_one, change, mine)
    assert _splits(one_v_one, change2, mine)


@pytest.mark.parametrize("mine", [True, False])
@pytest.mark.parametrize("vol, slot_idx", [
    (VolStatus.ENCORE, Pok.ENCORE_TURNS), (VolStatus.DISABLE, Pok.DISABLE_TURNS),
])
def test_node_key_sees_encore_and_disable_slots(one_v_one, mine, vol, slot_idx):
    """Encore and Disable split nodes by their slot while they hold, not by the turns left, and a
    leftover slot after they end adds nothing"""
    def held(slot, turns):
        def change(pok):
            pok[Pok.VOL_STATUS] |= vol
            pok[slot_idx] = turns * 4 + slot
        return change
    _, slot1, _ = _keys_after(one_v_one, held(1, 3), mine)
    _, slot1_later, _ = _keys_after(one_v_one, held(1, 5), mine)
    _, slot2, _ = _keys_after(one_v_one, held(2, 3), mine)
    assert slot1 == slot1_later
    assert slot1 != slot2
    assert _splits(one_v_one, held(1, 3), mine)
    def ended(pok):
        pok[slot_idx] = 2
    base, after, _ = _keys_after(one_v_one, ended, mine)
    assert after == base


@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_locks(one_v_one, mine):
    """A locked move (Rollout) splits nodes by its slot, and charging and recharging split too"""
    def locked(slot):
        def change(pok):
            pok[Pok.LOCKED_MOVE] = slot
        return change
    def charge_recharge(value):
        def change(pok):
            pok[Pok.CHARGE_RECHARGE] = value
        return change
    keys = {_keys_after(one_v_one, locked(s), mine)[1] for s in range(4)}
    assert len(keys) == 4
    assert _splits(one_v_one, locked(0), mine)
    assert _splits(one_v_one, charge_recharge(1), mine)
    assert _splits(one_v_one, charge_recharge(-1), mine)
    assert (_keys_after(one_v_one, charge_recharge(1), mine)[1]
            != _keys_after(one_v_one, charge_recharge(-1), mine)[1])


def test_node_key_sees_trick_room_but_not_its_turns(one_v_one):
    """Trick Room splits nodes, the turns left don't, and it doesn't collide with Gravity"""
    arr = one_v_one()
    key = node_key(arr)
    arr[Field.TRICKROOM] = 5
    key_tr = node_key(arr)
    assert key_tr != key
    arr[Field.TRICKROOM] = 2
    assert node_key(arr) == key_tr
    gravity = one_v_one()
    gravity[Field.GRAVITY_TURNS] = 5
    assert node_key(gravity) != key_tr


@pytest.mark.parametrize("side", [Field.MY_SIDE_COND, Field.OPP_SIDE_COND])
def test_node_key_sees_new_side_conditions_in_k6(one_v_one, side):
    """A side condition above k1's bits splits nodes through k6 and leaves k1 (and with it the
    Toxic Spikes layers next to it) alone"""
    arr = one_v_one()
    key = node_key(arr)
    arr[side] = 1 << SIDE_COND_K1_BITS
    new = node_key(arr)
    assert new[0] == key[0]
    assert new != key
    other = one_v_one()
    other[Field.OPP_SIDE_COND if side == Field.MY_SIDE_COND else Field.MY_SIDE_COND] = (
        1 << SIDE_COND_K1_BITS
    )
    assert node_key(other) != new


def test_node_key_death_phase_ignores_my_side(one_v_one):
    """In the death phase my fainted active's item, types and lock don't split nodes"""
    arr = one_v_one()
    arr[Field.PHASE] = BattlePhase.DEATH_END_OF_TURN
    key = node_key(arr)
    me = my_active(arr)
    me[Item.ID] = ItemNames.CHARCOAL
    me[Pok.TYPE1] = Types.STEEL
    me[Pok.LOCKED_MOVE] = 2
    assert node_key(arr) == key


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
    ("Sunny Day", {Field.WEATHER: Weather.SUN}, True),
    ("Hail", {Field.WEATHER: Weather.HAIL}, True),
    ("Hail", {Field.WEATHER: Weather.SUN}, False),
    ("Gravity", {}, False),
    ("Gravity", {Field.GRAVITY_TURNS: 3}, True),
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


# ── UCB / backprop ───────────────────────────────────────────────────────────

def _stats(rows):
    stats = np.zeros((N_SLOTS, STATS_COLS))
    for slot, visits, total in rows:
        stats[slot, 0] = visits
        stats[slot, 1] = total
    return stats


def test_best_slot_skips_unvisited_and_prefers_better_mean():
    """No exploration: the higher mean wins; unvisited rows are ignored"""
    stats = _stats([(0, 10, 2.0), (3, 10, 8.0)])
    assert best_slot(stats, 20, 0.0) == 3
    assert best_slot(np.zeros((N_SLOTS, STATS_COLS)), 0, 0.42) == -1


def test_best_slot_explores_rarely_visited():
    """With exploration a barely-tried action beats a well-known slightly better one"""
    stats = _stats([(0, 1000, 600.0), (1, 2, 1.0)])
    assert best_slot(stats, 1002, 2.0) == 1


def test_only_the_root_uses_root_c(monkeypatch):
    """Selection passes ROOT_C at the root, every node below it keeps best_action's default"""
    root_state = GameState(build_scenario("starters"))
    root = Node(root_state)
    calls = {True: set(), False: set()}
    real = Node.best_action

    def spy(node, *args):
        calls[node is root].add(args)
        return real(node, *args)

    monkeypatch.setattr(Node, "best_action", spy)
    mcts_loop(root, root_state, max_iterations=300, terminal_iterations=10**9)
    assert calls[True] == {(ROOT_C,)}
    assert calls[False] == {()}


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
    assert row[0] == 2 and row[1] == 1.0


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


def test_snapshot_restores_bench_items():
    """A bench Pokemon's item block, recyclable item and knocked off mark come back from the
    snapshot, not from the initial array (an eaten berry stays eaten)"""
    initial = build_scenario("starters")
    arr = initial.copy()
    bench, other = pok_slice(arr, 1, False), pok_slice(arr, 2, False)
    bench[Item.ID:Item.ID + ITEM_LEN] = ITEM_TABLE[ItemNames.SITRUS_BERRY]
    other[Pok.CONSUMED_ITEM] = ItemNames.ORAN_BERRY
    other[Pok.ITEM_KNOCKED_OFF] = 1
    out = reconstruct_battle_array(NodeSnapshot.from_state(GameState(arr)), initial)
    for i in (1, 2):
        assert (pok_slice(out, i, False) == pok_slice(arr, i, False)).all()


# ── What the foe really did ──────────────────────────────────────────────────

SCRATCH, GROWL = (MOVE, 0), (MOVE, 1)


def _foe_battle(make_pokemon, make_battle, foe_moves, my_ability="Guts", my_moves=("Scratch", "Growl")):
    """My level 50 Machop is faster: its Scratch knocks the foe out, its Growl leaves it alive"""
    mine = [make_pokemon("Machop", 50, my_ability, list(my_moves))]
    foes = [make_pokemon("Rattata", 5, "Run Away", foe_moves),
            make_pokemon("Geodude", 30, "Sturdy", ["Tackle"])]
    return make_battle(mine, foes)


def _pack(*turns):
    """step_arr's answer for these (foe's party slot, what it did, PP paid), oldest first"""
    did = 0
    for foe, what, paid in turns:
        did = did << OPP_TURN_BITS | ((foe << 5 | what << 2 | paid) + 1)
    return did


def test_foe_that_fainted_first_didnt_move(make_pokemon, make_battle):
    """Knocked out before its turn: no PP paid, the Pokemon in now is the replacement"""
    arr = _foe_battle(make_pokemon, make_battle, ["Scratch"])
    pp = move_slice(pok_slice(arr, 0, True), 0)[Move.PP]
    assert opp_turns(step_arr(arr, *SCRATCH, 0)) == [(0, OPP_DIDNT_MOVE, 0)]
    assert move_slice(pok_slice(arr, 0, True), 0)[Move.PP] == pp
    assert arr[Field.OPP_POK] == 1


def test_foe_that_moved_and_then_fainted_did_move(make_pokemon, make_battle):
    """Quick Attack goes first, the same knockout comes after it"""
    arr = _foe_battle(make_pokemon, make_battle, ["Quick Attack"])
    assert opp_turns(step_arr(arr, *SCRATCH, 0)) == [(0, 1, 1)]
    assert arr[Field.OPP_POK] == 1


def test_foe_blocked_by_sleep_didnt_move(make_pokemon, make_battle):
    """A flinch, full paralysis and the rest stop at the same early return"""
    arr = _foe_battle(make_pokemon, make_battle, ["Scratch"])
    opp_active(arr)[Pok.STATUS] = Status.SLEEP
    opp_active(arr)[Pok.SLEEP_COUNTER] = 5
    assert opp_turns(step_arr(arr, *GROWL, 0)) == [(0, OPP_DIDNT_MOVE, 0)]


def test_locked_move_ran_without_paying_pp(make_pokemon, make_battle):
    """Uproar pays PP on its first turn only, the locked turns still ran unless the foe faints first"""
    arr = _foe_battle(make_pokemon, make_battle, ["Uproar"])
    assert opp_turns(step_arr(arr, *GROWL, 0)) == [(0, 1, 1)]
    assert opp_active(arr)[Pok.LOCKED_MOVE] == 0
    assert opp_turns(step_arr(arr, *GROWL, 0)) == [(0, 1, 0)]
    assert opp_turns(step_arr(arr, *SCRATCH, 0)) == [(0, OPP_DIDNT_MOVE, 0)]


def test_locked_move_that_ran_before_the_foe_fainted_counts(make_pokemon, make_battle):
    """Its last move can't tell this from fainting first, the engine's note can"""
    mine = [make_pokemon("Slowpoke", 50, "Oblivious", ["Scratch", "Growl"])]
    foes = [make_pokemon("Rattata", 30, "Run Away", ["Uproar"]),
            make_pokemon("Geodude", 30, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, foes)
    assert opp_turns(step_arr(arr, *GROWL, 0)) == [(0, 1, 1)]
    opp_active(arr)[Pok.CURRENT_HP] = 1
    assert opp_turns(step_arr(arr, *SCRATCH, 0)) == [(0, 1, 0)]
    assert arr[Field.OPP_POK] == 1


def test_struggle_counts_unless_the_foe_fainted_first(make_pokemon, make_battle):
    """Struggle pays no PP, its slot is 10"""
    arr = _foe_battle(make_pokemon, make_battle, ["Scratch"])
    move_slice(opp_active(arr), 0)[Move.PP] = 0
    assert opp_turns(step_arr(arr, *GROWL, 10)) == [(0, OPP_STRUGGLED, 0)]
    assert opp_turns(step_arr(arr, *SCRATCH, 10)) == [(0, OPP_DIDNT_MOVE, 0)]


def test_encore_landing_first_is_the_move_that_ran(make_pokemon, make_battle):
    """The foe picked Scratch, my faster Encore makes it use its last move Tackle instead"""
    arr = _foe_battle(make_pokemon, make_battle, ["Scratch", "Tackle"], my_moves=("Encore", "Growl"))
    assert opp_turns(step_arr(arr, *GROWL, 1)) == [(0, 2, 1)]
    assert opp_turns(step_arr(arr, MOVE, 0, 0)) == [(0, 2, 1)]


def test_foe_move_after_my_baton_pass_pick(make_pokemon, make_battle):
    """A slower foe's move runs with my pick, the paused turn itself has no foe turn yet"""
    mine = [make_pokemon("Rattata", 30, "Run Away", ["Baton Pass", "Tackle"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, [make_pokemon("Machop", 10, "Guts", ["Tackle"])])
    state = GameState(arr)
    state.opp_move_cache = 0
    state.step((MOVE, 0))
    assert state.phase == BattlePhase.BATON_PASS and state.opp_move_last is None
    state.step((SWITCH, 1))
    assert opp_turns(state.opp_move_last) == [(0, 1, 1)]


def test_faster_foe_before_my_baton_pass_pick(make_pokemon, make_battle):
    """It already moved in the paused turn, my pick has no foe turn"""
    mine = [make_pokemon("Rattata", 5, "Run Away", ["Baton Pass", "Tackle"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, [make_pokemon("Machop", 50, "Guts", ["Growl"])])
    state = GameState(arr)
    state.opp_move_cache = 0
    state.step((MOVE, 0))
    assert state.phase == BattlePhase.BATON_PASS
    assert opp_turns(state.opp_move_last) == [(0, 1, 1)]
    state.step((SWITCH, 1))
    assert state.opp_move_last is None


@pytest.mark.parametrize("ability, move, paid", [
    ("Guts", "Scratch", 1),
    ("Pressure", "Scratch", 2),
    ("Pressure", "Harden", 1),
])
def test_foe_move_notes_the_pp_it_paid(make_pokemon, make_battle, ability, move, paid):
    """One more into my Pressure, not for a move on itself"""
    arr = _foe_battle(make_pokemon, make_battle, [move], my_ability=ability)
    assert opp_turns(step_arr(arr, *GROWL, 0)) == [(0, 1, paid)]


def test_foe_pursuit_counts(make_pokemon, make_battle):
    """It runs before my switch, in start_of_turn"""
    mine = [make_pokemon("Machop", 50, "Guts", ["Scratch"]),
            make_pokemon("Geodude", 50, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, [make_pokemon("Rattata", 5, "Run Away", ["Pursuit"])])
    assert opp_turns(step_arr(arr, SWITCH, 1, 0)) == [(0, 1, 1)]


def test_foe_switch_and_item_always_happen(make_pokemon, make_battle):
    """Those run at the start of the turn, before anything can stop them"""
    arr = _foe_battle(make_pokemon, make_battle, ["Scratch"])
    arr[Field.AI_ITEM1] = _POTIONS_POTION
    assert opp_turns(step_arr(arr, *GROWL, -10)) == [(0, OPP_USED_ITEM, 0)]
    assert opp_turns(step_arr(arr, *GROWL, -5)) == [(0, OPP_SWITCHED, 0)]
    assert arr[Field.OPP_POK] == 1


def test_forced_turns_keep_every_turn_and_its_foe(make_pokemon, make_battle):
    """My Uproar locks me in for the whole step: its first turn knocks Rattata out before it moves,
    Geodude comes in and moves in the next one"""
    arr = _foe_battle(make_pokemon, make_battle, ["Scratch"], my_moves=("Uproar",))
    turns = opp_turns(step_arr(arr, MOVE, 0, 0))
    assert turns[0] == (0, OPP_DIDNT_MOVE, 0)
    assert turns[1] == (1, 1, 1)


def test_game_state_has_no_foe_turn_when_i_only_pick_a_replacement(make_pokemon, make_battle):
    """opp_move_last and the node snapshot follow step_arr, also when the foe didn't get to move"""
    state = GameState(_foe_battle(make_pokemon, make_battle, ["Scratch"]))
    state.step(SCRATCH)
    assert state.opp_move_last == _pack((0, OPP_DIDNT_MOVE, 0))
    assert NodeSnapshot.from_state(state).opp_move_idx == state.opp_move_last

    team = [make_pokemon("Rattata", 10, "Run Away", ["Tackle"]) for _ in range(2)]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    my_active(arr)[Pok.CURRENT_HP] = 0
    arr[Field.PHASE] = BattlePhase.DEATH_END_OF_TURN
    state = GameState(arr)
    state.step((SWITCH, 1))
    assert state.opp_move_last is None
    assert NodeSnapshot.from_state(state).opp_move_idx == -1


def test_node_counts_every_move_merged_into_it(make_pokemon, make_battle):
    """Pound and Quick Attack leave the same state, so they share a node: its count has both, and
    every visit is counted"""
    mine = [make_pokemon("Machop", 50, "Guts", ["Leer"])]
    foes = [make_pokemon("Rattata", 5, "Run Away", ["Pound", "Quick Attack"])]
    root_state = GameState(make_battle(mine, foes))
    root = Node(root_state)
    mcts_loop(root, root_state, max_iterations=120, terminal_iterations=10**9)
    outcomes = root.children[(MOVE, 0)]
    both = {_pack((0, 1, 1)), _pack((0, 2, 1))}
    assert any(set(node.opp_moves) == both for node in outcomes)
    for node in outcomes:
        assert sum(node.opp_moves.values()) == node.visits
    assert root.opp_moves == {}


def test_random_untried_slot_only_picks_set_bits():
    """All of them, nothing else"""
    mask = 1 << 0 | 1 << 3 | 1 << 7
    assert {random_untried_slot(mask) for _ in range(200)} == {0, 3, 7}
    assert random_untried_slot(1 << 10) == 10


# ── Continue from here ───────────────────────────────────────────────────────

def _pp_battle(make_pokemon, make_battle):
    """Foe moves: an attack, a status move at me, and one on itself"""
    mine = [make_pokemon("Machop", 50, "Guts", ["Scratch", "Growl"])]
    foes = [make_pokemon("Rattata", 5, "Run Away", ["Scratch", "Leer", "Harden"]),
            make_pokemon("Geodude", 5, "Sturdy", ["Tackle", "Harden"])]
    return make_battle(mine, foes)


def _foe_pp(arr, slot=0):
    pok = pok_slice(arr, slot, True)
    return [int(move_slice(pok, m)[Move.PP]) for m in range(3)]


def test_foe_pp_is_the_roots_minus_what_the_path_paid(make_pokemon, make_battle):
    """Whatever the node's own PP says, a step with no foe turn and one that didn't move pay nothing"""
    initial = _pp_battle(make_pokemon, make_battle)
    start = _foe_pp(initial)
    out = initial.copy()
    move_slice(pok_slice(out, 0, True), 0)[Move.PP] = 3
    foe_pp_along_path(out, initial, [
        _pack((0, 1, 1)), None, _pack((0, OPP_DIDNT_MOVE, 0)), _pack((0, 2, 2)), _pack((0, 1, 1), (0, 1, 0)),
    ])
    assert _foe_pp(out) == [start[0] - 2, start[1] - 2, start[2]]


def test_foe_pp_goes_to_the_foe_that_moved(make_pokemon, make_battle):
    """It may be on the bench by now, and it stops at 0"""
    initial = _pp_battle(make_pokemon, make_battle)
    move_slice(pok_slice(initial, 1, True), 1)[Move.PP] = 1
    active, bench = _foe_pp(initial, 0), _foe_pp(initial, 1)
    out = initial.copy()
    foe_pp_along_path(out, initial, [_pack((1, 1, 1)), _pack((1, 2, 2))])
    assert _foe_pp(out, 0) == active
    assert _foe_pp(out, 1) == [bench[0] - 1, 0, bench[2]]


def _clicked(arr, picks, action=GROWL):
    """A step of a path for each pick: (parent, action, node, what the foe did). The node keeps the
    snapshot of the visit where the foe did that"""
    path = []
    state = GameState(arr)
    for pick in picks:
        parent = Node(state)
        state = state.clone()
        state.opp_move_cache = pick
        state.step(action)
        path.append((parent, action, Node(state), state.opp_move_last))
    return path


def test_real_position_is_the_snapshot_when_the_foe_did_what_its_visit_did(
        monkeypatch, make_pokemon, make_battle):
    """A rare node with its one visit is this case: nothing runs again, it's instant"""
    def must_not_run(*_args):
        raise AssertionError("the snapshot already has this move")
    monkeypatch.setattr(search_models, "_retry_step", must_not_run)
    initial = _pp_battle(make_pokemon, make_battle)
    path = _clicked(initial, [1])
    out = real_position(initial, path)
    assert (out == reconstruct_battle_array(path[-1][2].snapshot, initial)).all()


def test_real_position_runs_the_last_step_for_another_move(make_pokemon, make_battle):
    """The snapshot's visit used Scratch, the foe really used Pound, which leaves the same state: PP,
    its last move and what my Mirror Move copies all follow, the HP stays the snapshot's"""
    mine = [make_pokemon("Machop", 50, "Guts", ["Scratch", "Growl"])]
    foes = [make_pokemon("Rattata", 5, "Run Away", ["Scratch", "Pound"]),
            make_pokemon("Geodude", 5, "Sturdy", ["Tackle"])]
    initial = make_battle(mine, foes)
    start = _foe_pp(initial)
    parent, action, node, _ = _clicked(initial, [0])[0]
    out = real_position(initial, [(parent, action, node, _pack((0, 2, 1)))])
    foe = pok_slice(out, 0, True)
    pound = move_slice(foe, 1)[Move.ID]
    assert _foe_pp(out) == [start[0], start[1] - 1, start[2]]
    assert foe[Pok.LAST_MOVE_ID] == pound
    assert out[Field.LAST_MOVE] == pound
    assert my_active(out)[Pok.MIRROR_MOVE] == pound
    snap = reconstruct_battle_array(node.snapshot, initial)
    for i in range(12):
        side = i >= 6
        slot = i - 6 if side else i
        assert pok_slice(out, slot, side)[Pok.CURRENT_HP] == pok_slice(snap, slot, side)[Pok.CURRENT_HP]


def _rollout_battle(make_pokemon, make_battle, ability):
    mine = [make_pokemon("Machop", 50, "Guts", ["Scratch", "Growl"])]
    foes = [make_pokemon("Geodude", 20, ability, ["Tackle", "Rollout"])]
    return make_battle(mine, foes)


def test_rollout_lock_doesnt_merge_with_tackle(make_pokemon, make_battle):
    """node_key sees the foe's Rollout lock (No Guard, it can't miss), so it and Tackle land in
    different nodes"""
    initial = _rollout_battle(make_pokemon, make_battle, "No Guard")
    rollout = _clicked(initial, [1])[0][2]
    tackle = _clicked(initial, [0])[0][2]
    assert pok_slice(reconstruct_battle_array(rollout.snapshot, initial), 0, True)[Pok.LOCKED_MOVE] == 1
    assert rollout.key != tackle.key


def test_real_position_follows_tackle_on_a_missed_rollout(make_pokemon, make_battle):
    """A missed Rollout leaves no lock, so outside the HP brackets it has Tackle's key. When the foe
    really used Tackle the last step runs again with it"""
    initial = _rollout_battle(make_pokemon, make_battle, "Sturdy")
    parent, action, rollout, _ = _clicked(initial, [1])[0]
    snap = reconstruct_battle_array(rollout.snapshot, initial)
    assert pok_slice(snap, 0, True)[Pok.LOCKED_MOVE] == -1
    tackle = _clicked(initial, [0])[0][2].key
    assert rollout.key[0] & ~search_models.KEY_HP_BITS == tackle[0] & ~search_models.KEY_HP_BITS
    assert rollout.key[1:] == tackle[1:]
    out = real_position(initial, [(parent, action, rollout, _pack((0, 1, 1)))])
    foe = pok_slice(out, 0, True)
    assert foe[Pok.LOCKED_MOVE] == -1
    assert foe[Pok.LAST_MOVE_ID] == MoveName.TACKLE


def test_real_position_keeps_the_snapshot_when_the_last_step_cant_be_found(
        monkeypatch, make_pokemon, make_battle):
    """Asleep the foe can't really use that move, it gives up in time. PP still follows the path"""
    monkeypatch.setattr(search_models, "LAST_STEP_BUDGET", 0.01)
    initial = _pp_battle(make_pokemon, make_battle)
    start = _foe_pp(initial)
    opp_active(initial)[Pok.STATUS] = Status.SLEEP
    opp_active(initial)[Pok.SLEEP_COUNTER] = 5
    parent, action, node, did = _clicked(initial, [0])[0]
    assert did == _pack((0, OPP_DIDNT_MOVE, 0))
    out = real_position(initial, [(parent, action, node, _pack((0, 2, 1)))])
    snap = reconstruct_battle_array(node.snapshot, initial)
    move_slice(pok_slice(snap, 0, True), 1)[Move.PP] = start[1] - 1
    assert (out == snap).all()


def test_real_position_pays_for_the_whole_path(make_pokemon, make_battle):
    """Each step's move counts, not only the last one, and not the moves of the snapshot's history"""
    initial = _pp_battle(make_pokemon, make_battle)
    start = _foe_pp(initial)
    path = _clicked(initial, [0, 0, 1])
    first = (path[0][0], path[0][1], path[0][2], _pack((0, 3, 1)))
    out = real_position(initial, [first, path[1], path[2]])
    assert _foe_pp(out) == [start[0] - 1, start[1] - 1, start[2] - 1]


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


@pytest.mark.parametrize("item, pp, moves", [
    ("Choice Band", 10, [(MOVE, 1)]), ("Choice Band", 0, [(MOVE, 10)]),
    ("Oran Berry", 10, [(MOVE, 0), (MOVE, 1)]),
])
def test_choice_lock_filters_moves(make_pokemon, make_battle, item, pp, moves):
    """Only the locked move while a choice item holds it, Struggle once it's out of PP"""
    team = [make_pokemon("Rattata", 10, "Run Away", ["Tackle", "Growl"], item=item),
            make_pokemon("Pidgey", 10, "Run Away", ["Tackle"])]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    my_active(arr)[Pok.CHOICE_LOCK] = 2
    move_slice(my_active(arr), 1)[Move.PP] = pp
    assert mask_actions(arr) == moves + [(SWITCH, 1)] == legal_actions(arr)


def test_bind_blocks_switching(make_pokemon, make_battle):
    """A partially trapped active can't switch out"""
    team = [make_pokemon(n, 10, "Run Away", ["Tackle"]) for n in ("Rattata", "Pidgey")]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Wrap"])])
    my_active(arr)[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED
    assert mask_actions(arr) == [(MOVE, 0)] == legal_actions(arr)


@pytest.mark.parametrize("mine, my_ability, foe_ability, gravity, trapped", [
    ("Rattata", "Run Away", "Shadow Tag", False, True),
    ("Wobbuffet", "Shadow Tag", "Shadow Tag", False, False),
    ("Geodude", "Rock Head", "Magnet Pull", False, False),
    ("Magnemite", "Sturdy", "Magnet Pull", False, True),
    ("Rattata", "Run Away", "Arena Trap", False, True),
    ("Pidgey", "Keen Eye", "Arena Trap", False, False),
    ("Gastly", "Levitate", "Arena Trap", False, False),
    ("Pidgey", "Keen Eye", "Arena Trap", True, True),
    ("Gastly", "Levitate", "Arena Trap", True, True),
    ("Rattata", "Run Away", "Static", False, False),
])
def test_trapping_abilities_block_switching(make_pokemon, make_battle, mine, my_ability,
                                            foe_ability, gravity, trapped):
    """pokeplatinum Battler_IsTrapped: Shadow Tag unless I have it too, Magnet Pull on Steel
    types, Arena Trap on grounded Pokemon (Gravity grounds Flying and Levitate). Ghosts aren't
    exempt in Gen IV"""
    team = [make_pokemon(mine, 10, my_ability, ["Tackle"]),
            make_pokemon("Rattata", 10, "Run Away", ["Tackle"])]
    arr = make_battle(team, [make_pokemon("Diglett", 10, foe_ability, ["Scratch"])])
    arr[Field.GRAVITY_TURNS] = 5 if gravity else 0
    expected = [(MOVE, 0)] if trapped else [(MOVE, 0), (SWITCH, 1)]
    assert mask_actions(arr) == expected == legal_actions(arr)


@pytest.mark.parametrize("mine, my_ability", [("Pidgey", "Keen Eye"), ("Gastly", "Levitate")])
def test_arena_trap_traps_an_iron_ball_holder(make_pokemon, make_battle, mine, my_ability):
    """pokeplatinum BattlerIsGrounded: Iron Ball grounds a Flying or Levitate holder"""
    team = [make_pokemon(mine, 10, my_ability, ["Tackle"], item="Iron Ball"),
            make_pokemon("Rattata", 10, "Run Away", ["Tackle"])]
    arr = make_battle(team, [make_pokemon("Diglett", 10, "Arena Trap", ["Scratch"])])
    assert mask_actions(arr) == [(MOVE, 0)] == legal_actions(arr)


def test_fainted_trapper_does_not_trap(make_pokemon, make_battle):
    """The trapping abilities only count a living foe"""
    team = [make_pokemon(n, 10, "Run Away", ["Tackle"]) for n in ("Rattata", "Pidgey")]
    arr = make_battle(team, [make_pokemon("Diglett", 10, "Arena Trap", ["Scratch"])])
    opp_active(arr)[Pok.CURRENT_HP] = 0
    assert mask_actions(arr) == [(MOVE, 0), (SWITCH, 1)]


@pytest.mark.parametrize("vol, foe_ability", [
    (0, "Shadow Tag"), (0, "Arena Trap"),
    (VolStatus.PARTIALLY_TRAPPED, "Run Away"), (VolStatus.INGRAIN, "Run Away"),
])
def test_shed_shell_always_switches(make_pokemon, make_battle, vol, foe_ability):
    """pokeplatinum Battler_IsTrapped returns "not trapped" for a Shed Shell holder before any
    other check, bind and Ingrain included"""
    team = [make_pokemon("Rattata", 10, "Run Away", ["Tackle"], item="Shed Shell"),
            make_pokemon("Pidgey", 10, "Keen Eye", ["Tackle"])]
    arr = make_battle(team, [make_pokemon("Diglett", 10, foe_ability, ["Scratch"])])
    my_active(arr)[Pok.VOL_STATUS] = vol
    assert mask_actions(arr) == [(MOVE, 0), (SWITCH, 1)] == legal_actions(arr)


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


# ── Phase 6: Baton Pass phase and Roar ───────────────────────────────────────

def _baton_pass_paused(make_pokemon, make_battle):
    mine = [make_pokemon("Rattata", 30, "Run Away", ["Baton Pass", "Tackle"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"]),
            make_pokemon("Zubat", 20, "Inner Focus", ["Bite"])]
    arr = make_battle(mine, [make_pokemon("Machop", 10, "Guts", ["Tackle"])])
    step_arr(arr, MOVE, 0, 0)
    assert arr[Field.PHASE] == BattlePhase.BATON_PASS
    return arr


def test_baton_pass_phase_only_offers_switches(make_pokemon, make_battle):
    """Mid-turn pick: the bench, not the moves, not the passer"""
    arr = _baton_pass_paused(make_pokemon, make_battle)
    assert mask_actions(arr) == [(SWITCH, 1), (SWITCH, 2)] == legal_actions(arr)


def test_step_arr_finishes_the_paused_turn(make_pokemon, make_battle):
    """The pick runs the foe's pending move and the end of turn"""
    arr = _baton_pass_paused(make_pokemon, make_battle)
    turn = arr[Field.TURN]
    step_arr(arr, SWITCH, 2, -50)
    assert arr[Field.PHASE] == BattlePhase.TURN_START and arr[Field.MY_POK] == 2
    assert arr[Field.TURN] == turn + 1


def test_game_state_steps_through_the_baton_pass_phase(make_pokemon, make_battle):
    """No AI move is asked for while I pick"""
    state = GameState(_baton_pass_paused(make_pokemon, make_battle))
    assert state.opp_move is None
    state.step((SWITCH, 1))
    assert state.phase == BattlePhase.TURN_START and state.my_active == 1


def test_baton_pass_phase_after_the_foe_fainted(make_pokemon, make_battle):
    """The foe moved first and fainted (a confusion self-hit), my Baton Pass still runs: the pick,
    the key and a rollout work, and the end of the turn brings in its replacement"""
    mine = [make_pokemon("Rattata", 30, "Run Away", ["Baton Pass", "Tackle"]),
            make_pokemon("Zubat", 20, "Inner Focus", ["Bite"])]
    arr = make_battle(mine, [make_pokemon("Machop", 10, "Guts", ["Tackle"]),
                             make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])])
    step_arr(arr, MOVE, 0, 0)
    assert arr[Field.PHASE] == BattlePhase.BATON_PASS
    opp_active(arr)[Pok.CURRENT_HP] = 0
    arr[Field.PENDING_OPP_MOVE] = 0
    assert mask_actions(arr) == [(SWITCH, 1)]
    node_key(arr)
    value, _, _ = rollout_arr(arr.copy())
    assert 0.0 <= value <= 1.0
    step_arr(arr, SWITCH, 1, -50)
    assert arr[Field.MY_POK] == 1 and arr[Field.OPP_POK] == 1
    assert opp_active(arr)[Pok.CURRENT_HP] > 0


def test_node_key_sees_my_slot_and_the_baton_pass_phase(make_pokemon, make_battle):
    """Roar's random pick on my side and the paused turn are different nodes"""
    mine = [make_pokemon("Rattata", 10, "Run Away", ["Tackle"]) for _ in range(2)]
    arr = make_battle(mine, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    key = node_key(arr)
    other = arr.copy()
    other[Field.MY_POK] = 1
    assert node_key(other) != key
    other = arr.copy()
    other[Field.PHASE] = BattlePhase.BATON_PASS
    assert node_key(other) != key


def test_gravity_hides_its_moves(make_pokemon, make_battle):
    """Under Gravity Splash and Bounce aren't valid actions"""
    arr = make_battle([make_pokemon("Pidgey", 10, "Keen Eye", ["Splash", "Bounce", "Tackle"])],
                      [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    assert mask_actions(arr) == [(MOVE, 0), (MOVE, 1), (MOVE, 2)]
    arr[Field.GRAVITY_TURNS] = 3
    assert mask_actions(arr) == [(MOVE, 2)]


def _int_attrs(cls):
    return [v for k, v in vars(cls).items() if k.isupper() and isinstance(v, int)]



def test_rollout_keeps_explosion_out_of_the_damage_bonus(make_pokemon, make_battle):
    """A STAB Explosion that KOs would get the KO weight (100), but it only gets the minimum
    weight, like the trainer AI keeps it out of its damage calc. Tackle (STAB, weak) gets 2"""
    me = make_pokemon("Rattata", 50, "Run Away", ["Explosion", "Tackle"])
    foe = make_pokemon("Machop", 5, "Guts", ["Growl"])
    arr = make_battle([me], [foe])
    counts = {0: 0, 1: 0}
    random.seed(1)
    actions = np.array([[ActionType.MOVE, 0], [ActionType.MOVE, 1]], dtype=np.int16)
    for _ in range(300):
        _, idx = rollout_pref(arr, 0, actions)
        counts[int(idx)] += 1
    assert counts[0] < counts[1]



@pytest.mark.parametrize("foe_lv, foe_ab, picked", [
    (20, "Run Away", True), (21, "Run Away", False), (20, "Sturdy", False),
])
def test_rollout_ohko_weight(make_pokemon, make_battle, foe_lv, foe_ab, picked):
    """An OHKO move skips the damage calc with weight 1, and 0 when it can't work"""
    me = make_pokemon("Rattata", 20, "Run Away", ["Guillotine", "Tackle"])
    foe = make_pokemon("Rattata", foe_lv, foe_ab, ["Growl"])
    arr = make_battle([me], [foe])
    random.seed(1)
    actions = np.array([[ActionType.MOVE, 0], [ActionType.MOVE, 1]], dtype=np.int16)
    picks = {int(rollout_pref(arr, 0, actions)[1]) for _ in range(100)}
    assert (0 in picks) == picked


@pytest.mark.parametrize("foe_ab, picked", [
    ("Run Away", True), ("Volt Absorb", False), ("Wonder Guard", False),
])
def test_rollout_skips_moves_an_ability_takes(make_pokemon, make_battle, foe_ab, picked):
    """A damaging move the foe's ability takes gets weight 0, like a type immunity"""
    me = make_pokemon("Pikachu", 20, "Static", ["Thunder Shock", "Growl"])
    foe = make_pokemon("Rattata", 20, foe_ab, ["Growl"])
    arr = make_battle([me], [foe])
    random.seed(1)
    actions = np.array([[ActionType.MOVE, 0], [ActionType.MOVE, 1]], dtype=np.int16)
    picks = {int(rollout_pref(arr, 0, actions)[1]) for _ in range(100)}
    assert (0 in picks) == picked


@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_the_metronome_item_count(one_v_one, mine):
    """The count changes damage and the stored move changes the next count, both split nodes"""
    arr = one_v_one()
    pok = my_active(arr) if mine else opp_active(arr)
    key = node_key(arr)
    pok[Pok.METRONOME_COUNT] = (MoveName.TACKLE << 4) + 1
    one = node_key(arr)
    pok[Pok.METRONOME_COUNT] += 1
    two = node_key(arr)
    pok[Pok.METRONOME_COUNT] = (MoveName.GROWL << 4) + 2
    assert len({key, one, two, node_key(arr)}) == 4


@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_the_choice_lock(make_pokemon, make_battle, mine):
    """The locked slot splits nodes while a choice item holds it, a leftover lock without one adds
    nothing"""
    my = [make_pokemon("Rattata", 10, "Run Away", ["Tackle", "Growl"], item="Choice Band")]
    opp = [make_pokemon("Rattata", 10, "Run Away", ["Tackle", "Growl"], item="Choice Scarf")]
    arr = make_battle(my, opp)
    pok = my_active(arr) if mine else opp_active(arr)
    free = node_key(arr)
    pok[Pok.CHOICE_LOCK] = 1
    one = node_key(arr)
    pok[Pok.CHOICE_LOCK] = 2
    assert len({free, one, node_key(arr)}) == 3
    shift = CHOICE_KEY_SHIFT + (SIDE_KEY_SHIFT if mine else 0)
    assert node_key(arr)[4] >> shift & 7 == 2
    pok[Item.ID:Item.ID + ITEM_LEN] = 0
    without = node_key(arr)
    pok[Pok.CHOICE_LOCK] = 0
    assert without == node_key(arr)


@pytest.mark.parametrize("ability, picked", [("Cute Charm", True), ("Normalize", False)])
def test_rollout_sees_normalize(make_pokemon, make_battle, ability, picked):
    """A normalized Lick can't touch a Ghost, so the rollout gives it weight 0"""
    me = make_pokemon("Skitty", 20, ability, ["Lick", "Growl"])
    foe = make_pokemon("Gastly", 20, "Levitate", ["Lick"])
    arr = make_battle([me], [foe])
    random.seed(1)
    actions = np.array([[ActionType.MOVE, 0], [ActionType.MOVE, 1]], dtype=np.int16)
    picks = {int(rollout_pref(arr, 0, actions)[1]) for _ in range(100)}
    assert (0 in picks) == picked


def test_rollout_keeps_resisted_moves(make_pokemon, make_battle):
    """A resisted move gets the minimum weight, not the immune weight 0 (the ratio is in quarters,
    so 0.5x no longer floors to 0)"""
    me = make_pokemon("Charmander", 20, "Blaze", ["Ember", "Growl"])
    foe = make_pokemon("Squirtle", 20, "Torrent", ["Tackle"])
    arr = make_battle([me], [foe])
    random.seed(1)
    actions = np.array([[ActionType.MOVE, 0], [ActionType.MOVE, 1]], dtype=np.int16)
    picks = {int(rollout_pref(arr, 0, actions)[1]) for _ in range(100)}
    assert picks == {0, 1}


@pytest.mark.parametrize("move, foe_ab, attacker_ab, picked", [
    ("Thunder Wave", "Run Away", "Static", True),
    ("Thunder Wave", "Limber", "Static", False),
    ("Thunder Wave", "Limber", "Mold Breaker", True),
    ("Growl", "Clear Body", "Static", False),
    ("Growl", "Hyper Cutter", "Static", False),
    ("Tail Whip", "Hyper Cutter", "Static", True),
])
def test_rollout_skips_status_moves_an_ability_stops(make_pokemon, make_battle, move, foe_ab,
                                                     attacker_ab, picked):
    """A status move the foe's ability makes useless gets weight 0: the status is one it keeps off,
    or every stat drop is one it stops"""
    me = make_pokemon("Pikachu", 20, attacker_ab, [move, "Thunder Shock"])
    foe = make_pokemon("Rattata", 20, foe_ab, ["Growl"])
    arr = make_battle([me], [foe])
    random.seed(1)
    actions = np.array([[ActionType.MOVE, 0], [ActionType.MOVE, 1]], dtype=np.int16)
    picks = {int(rollout_pref(arr, 0, actions)[1]) for _ in range(100)}
    assert (0 in picks) == picked


def test_rollout_counts_a_working_ohko_as_a_ko(make_pokemon, make_battle):
    """The opponent's OHKO move that can work counts as a KO, so a slower active switches out"""
    me = make_pokemon("Geodude", 20, "Rock Head", ["Tackle"])
    bench = make_pokemon("Rattata", 20, "Run Away", ["Tackle"])
    foe = make_pokemon("Krabby", 20, "Hyper Cutter", ["Guillotine"])
    arr = make_battle([me, bench], [foe])
    my_active(arr)[Pok.CURRENT_HP] = 10
    random.seed(1)
    actions = np.array([[ActionType.MOVE, 0], [ActionType.SWITCH, 1]], dtype=np.int16)
    picks = {(int(t), int(i)) for t, i in (rollout_pref(arr, 0, actions) for _ in range(100))}
    assert picks == {(ActionType.SWITCH, 1)}


# ── Substitute ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mine", [True, False])
def test_node_key_sees_a_substitute_not_its_hp(one_v_one, mine):
    """Whether a Substitute is up splits nodes, its HP doesn't"""
    arr = one_v_one()
    key = node_key(arr)
    pok = my_active(arr) if mine else opp_active(arr)
    pok[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    pok[Pok.SUB_HP] = 4
    with_sub = node_key(arr)
    assert with_sub != key
    pok[Pok.SUB_HP] = 1
    assert node_key(arr) == with_sub


@pytest.mark.parametrize("move, foe_sub, my_sub, picked", [
    ("Thunder Wave", False, False, True),
    ("Thunder Wave", True, False, False),     # the foe's Substitute stops it
    ("Taunt", True, False, True),             # bypasses it
    ("Substitute", False, False, True),
    ("Substitute", False, True, False),       # already up
])
def test_rollout_sees_substitute(make_pokemon, make_battle, move, foe_sub, my_sub, picked):
    """A status move into the foe's Substitute, or my Substitute that would fail, gets weight 0"""
    me = make_pokemon("Pikachu", 20, "Static", ["Tackle", move])
    foe = make_pokemon("Rattata", 20, "Run Away", ["Tackle"])
    arr = make_battle([me], [foe])
    for pok, up in ((opp_active(arr), foe_sub), (my_active(arr), my_sub)):
        if up:
            pok[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
            pok[Pok.SUB_HP] = 5
    random.seed(1)
    actions = np.array([[ActionType.MOVE, 0], [ActionType.MOVE, 1]], dtype=np.int16)
    picks = {int(rollout_pref(arr, 0, actions)[1]) for _ in range(200)}
    assert (1 in picks) == picked


def test_rollout_sees_embargo_and_trick_fail(poke):
    """status_move_blocked: Embargo on a foe already under it, Trick with no item on either side"""
    me = poke("Murkrow", 20, "Insomnia", ["Embargo", "Trick"])
    foe = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert not status_move_blocked(move_slice(me, 0), me, foe, 0)
    foe[Pok.VOL_STATUS2] |= VolStatus2.EMBARGO
    assert status_move_blocked(move_slice(me, 0), me, foe, 0)
    assert status_move_blocked(move_slice(me, 1), me, foe, 0)
    foe[Item.ID] = ItemNames.LEFTOVERS
    assert not status_move_blocked(move_slice(me, 1), me, foe, 0)


def test_rollout_sees_the_sleep_move_fails(poke):
    """sleep_move_fails: Snore and Sleep Talk awake, Dream Eater and Nightmare on an awake foe, Rest
    at full HP, Psycho Shift without a status; none of them once they'd work. No ability revealed"""
    me = poke("Hypno", 30, "Insomnia", ["Snore", "Sleep Talk", "Dream Eater", "Nightmare"])
    rester = poke("Snorlax", 30, "Insomnia", ["Rest", "Psycho Shift"])
    foe = poke("Geodude", 30, "Sturdy", ["Tackle"])
    assert all(sleep_move_fails(move_slice(me, i), me, foe) for i in range(4))
    assert all(sleep_move_fails(move_slice(rester, i), rester, foe) for i in range(2))
    me[Pok.STATUS] = foe[Pok.STATUS] = Status.SLEEP
    assert not any(sleep_move_fails(move_slice(me, i), me, foe) for i in range(4))
    foe[Pok.VOL_STATUS] |= VolStatus.NIGHTMARE
    assert sleep_move_fails(move_slice(me, 3), me, foe)
    rester[Pok.CURRENT_HP] -= 1
    assert sleep_move_fails(move_slice(rester, 0), rester, foe)    # Insomnia
    assert not rester[Pok.AB_KNOWN]
    rester[Pok.AB_ID] = AbilityNames.THICK_FAT
    rester[Pok.STATUS] = Status.BURN
    foe[Pok.STATUS] = 0
    assert not sleep_move_fails(move_slice(rester, 0), rester, foe)
    assert not sleep_move_fails(move_slice(rester, 1), rester, foe)


def test_node_key_sees_last_resort_working(make_pokemon, make_battle):
    """One bit, set while the active knows Last Resort and it would work; the other slots used
    don't split nodes for a Pokemon without it"""
    arr = make_battle([make_pokemon("Eevee", 30, "Run Away", ["Tackle", "Last Resort", "Growl"])],
                      [make_pokemon("Snorlax", 50, "Thick Fat", ["Tackle", "Harden"])])
    key = node_key(arr)
    my_active(arr)[Pok.LAST_RESORT] = 0b001
    assert node_key(arr) == key
    my_active(arr)[Pok.LAST_RESORT] = 0b101
    assert node_key(arr) != key
    key = node_key(arr)
    opp_active(arr)[Pok.LAST_RESORT] = 0b11
    assert node_key(arr) == key


def test_rollout_sees_heal_block_fail(poke):
    """status_move_blocked: Heal Block on a foe already under it"""
    me = poke("Abra", 20, "Synchronize", ["Heal Block"])
    foe = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert not status_move_blocked(move_slice(me, 0), me, foe, 0)
    foe[Pok.VOL_STATUS] |= VolStatus.HEAL_BLOCK
    assert status_move_blocked(move_slice(me, 0), me, foe, 0)
