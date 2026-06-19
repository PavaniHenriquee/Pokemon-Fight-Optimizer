"""
Extract neural-network-ready features from a battle_array as a single
flat float32 array, fully njit-compiled from the call into battle_array
straight through to the returned array.

Layout, shape (TOTAL_SIZE,):
  [0 : CONTINUOUS_SIZE]   continuous/categorical features
  [CONTINUOUS_SIZE : end] N_ABILITY_SLOTS raw ability IDs, stored as
                          float (lossless — float32 represents integers
                          exactly up to 2**24, far past any ability ID),
                          NOT normalized, since an embedding layer needs
                          the literal integer back as a lookup index.

Within the continuous block:
  my_active     (_FULL_POKEMON_FEATURES)
  opp_active    (_FULL_POKEMON_FEATURES)
  my_bench x 5  (_FULL_POKEMON_FEATURES each)
  opp_bench x 5 (_COARSE_POKEMON_FEATURES each)
  matchup       (_MATCHUP_FEATURES)
  field         (_FIELD_FEATURES)

ability slot order: [my_active, my_benchx5, opp_active, opp_benchx5]

Two templates, differing purely in move detail — "full" for active
(both sides) and my whole bench, "coarse" (type-coverage only) for the
opponent's bench, which I never act on directly. vol_status and stat
stages are included in both uniformly; they're always zero for anyone
not currently active, and a linear layer's gradient contribution from a
constant-zero column is always zero, so the network simply never
attaches meaning to it — there's no accuracy or speed cost to leaving
it in, only a cost to maintaining a third template that strips it.

Architecture: every _write_* function takes (out, offset, ...), writes
its block directly into out[offset:offset+width], and returns
offset+width. There is no construct-and-return-a-small-array anywhere
in this file, and that's deliberate, not just style — Numba compiles an
entire njit function body ahead of running any of it, including
branches a given call won't take. The previous design's early returns
(`return np.zeros(_SOME_FEATURES, ...)` for an empty/fainted slot)
referenced a size constant that didn't exist yet at first-call
compilation time, which is exactly the error this hit. Writing in place
removes the bug at the root: an empty slot just returns offset+width
without writing anything, which is correct because the output buffer
starts as np.zeros(...) and an unwritten slice is already zero.

Every width constant below is derived from already-known small facts —
game-rule constants (19 types, 7 statuses, 5 weather states) or len() of
a short tuple of field names — computed via plain arithmetic at import
time, before any njit function is ever compiled. Nothing is measured by
calling a function, so there's no circularity to trip over. The one
remaining manual bit is keeping each scalar-name tuple in sync with the
actual sequence of writes in its corresponding function; the assertion
at the bottom of this file catches drift between the two immediately
and loudly at import time, rather than producing a silently
wrong-shaped array.

Usage:
    from NeuralNetwork.models import to_nn_input, split_features
    combined = to_nn_input(battle_array)
    continuous, ability_ids = split_features(combined)
"""
import numpy as np
from numba import njit
from Utils.helper import get_type_effectiveness
from DataBase.MoveDB import PHYSICAL, SPECIAL, FIRE_WATER_ELECTRIC
from Models.idx_const import POK_LEN, MOVE_STRIDE, OFFSET_MOVE, Field
from Models.constants import (
    _FIELD_MY_POK, _FIELD_OPP_POK, _FIELD_TURN, _FIELD_WEATHER,
    _FIELD_TRICKROOM, _FIELD_PHASE,
    _FIELD_MY_ENTER_FIELD, _FIELD_OPP_ENTER_FIELD,
    _FIELD_MY_LAST_MOVE, _FIELD_AI_TOOK_DMG_LAST_TURN, _FIELD_AI_KNOWS,
    _FIELD_AI_ITEM1, _FIELD_AI_ITEM2, _FIELD_AI_ITEM3, _FIELD_AI_ITEM4,
    _POK_CURRENT_HP, _POK_MAX_HP,
    _POK_ATTACK, _POK_DEFENSE, _POK_SPECIAL_ATTACK, _POK_SPECIAL_DEFENSE, _POK_SPEED,
    _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE,
    _POK_SPECIAL_ATTACK_STAT_STAGE, _POK_SPECIAL_DEFENSE_STAT_STAGE,
    _POK_SPEED_STAT_STAGE, _POK_ACCURACY_STAT_STAGE, _POK_EVASION_STAT_STAGE,
    _POK_STATUS, _POK_VOL_STATUS, _POK_TYPE1, _POK_TYPE2,
    _POK_AB_ID, _POK_LEVEL, _POK_TURNS, _POK_SLEEP_COUNTER, _POK_BADLY_POISON,
    _MOVE_ID, _MOVE_CATEGORY, _MOVE_TYPE, _MOVE_POWER, _MOVE_ACCURACY,
    _MOVE_PP, _MOVE_PRIORITY, _MOVE_STATUS,
    _MOVE_BOOST_ATK, _MOVE_BOOST_DEF, _MOVE_BOOST_SPATK,
    _MOVE_BOOST_SPDEF, _MOVE_BOOST_SPEED, _MOVE_BOOST_ACC, _MOVE_BOOST_EV,
    _MOVE_RECOIL, _MOVE_DRAIN,
    _SEC_CHANCE, _SEC_STATUS,
    _MOVECATEGORY_PHYSICAL, _MOVECATEGORY_SPECIAL, _MOVECATEGORY_STATUS,
    _ENEMY_AI_KNOWS_ABILITY, _ENEMY_AI_KNOWS_MOVE1, _ENEMY_AI_KNOWS_MOVE2,
    _ENEMY_AI_KNOWS_MOVE3, _ENEMY_AI_KNOWS_MOVE4,
    _BATTLEPHASE_DEATH_END_OF_TURN,
)

# ── Normalization ceilings for genuinely continuous fields ────────────────────
_MAX_STAT       = 500.0
_MAX_MOVE_POWER = 250.0
_MAX_PRIORITY   = 7.0
_MAX_PP         = 40.0
_MAX_TURN       = 100.0

# ── Stable game-rule constants (not feature-engineering choices) ──────────────
_N_TYPES   = 19
_N_STATUS  = 7
_N_WEATHER = 5   # none, sun, rain, hail, sandstorm

_VOL_BITS = (1, 2, 4, 8, 16, 32, 64, 128, 256)
_N_VOL = len(_VOL_BITS)

_AI_KNOWS_BITS = (
    _ENEMY_AI_KNOWS_ABILITY, _ENEMY_AI_KNOWS_MOVE1, _ENEMY_AI_KNOWS_MOVE2,
    _ENEMY_AI_KNOWS_MOVE3, _ENEMY_AI_KNOWS_MOVE4,
)
_N_AI_KNOWS = len(_AI_KNOWS_BITS)

_N_ITEM_CATS = 9  # 0 = empty slot, 1-8 = Potions enum values

N_ABILITY_SLOTS = 12  # fixed by game rules (6v6 parties) — safe to hardcode

# ── Block widths, derived from name-tuples and known constants, not measured ──
_POKEMON_BASE_NAMES = (
    'is_alive', 'hp_ratio', 'max_hp', 'attack', 'defense', 'spatk', 'spdef', 'speed',
    'atk_stage', 'def_stage', 'spatk_stage', 'spdef_stage', 'spe_stage', 'acc_stage', 'eva_stage',
    'level', 'turns', 'sleep_counter', 'badly_poison',
)
_POKEMON_BASE_LEN = len(_POKEMON_BASE_NAMES)

_MOVE_SCALAR_NAMES = (
    'usable', 'power', 'ignores_acc', 'base_acc', 'pp_ratio', 'priority',
    'boost_atk', 'boost_def', 'boost_spatk', 'boost_spdef', 'boost_speed',
    'boost_acc', 'boost_ev', 'recoil', 'drain', 'sec_chance',
)
_MOVE_SCALAR_LEN = len(_MOVE_SCALAR_NAMES)
_MOVE_FEAT_LEN = _MOVE_SCALAR_LEN + 3 + _N_TYPES + _N_STATUS + _N_STATUS

_FULL_POKEMON_FEATURES = (
    _POKEMON_BASE_LEN + _N_TYPES + _N_STATUS + _N_VOL + 4 * _MOVE_FEAT_LEN
)
_COARSE_POKEMON_FEATURES = (
    _POKEMON_BASE_LEN + _N_TYPES + _N_STATUS + _N_VOL + _N_TYPES + 4 + 1
)

_LAST_MOVE_LEN = 5  # has_last_move, is_physical, is_special, is_status, is_fire_water_electric

_FIELD_SCALAR_NAMES = (
    'turn_ratio', 'trickroom_active', 'is_death_phase', 'my_enter_field', 'opp_enter_field'
)
_FIELD_SCALAR_LEN = len(_FIELD_SCALAR_NAMES)
_FIELD_FEATURES = (
    _N_WEATHER
    + _FIELD_SCALAR_LEN
    + _LAST_MOVE_LEN
    + _N_TYPES          # took-damage-last-turn type onehot
    + _N_AI_KNOWS
    + 4 * _N_ITEM_CATS
)

_MATCHUP_FEATURES = 4  # two stab-effectiveness pairs: mine→theirs, theirs→mine

CONTINUOUS_SIZE = (
    _FULL_POKEMON_FEATURES * 7      # my_active + opp_active + my_bench×5
    + _COARSE_POKEMON_FEATURES * 5  # opp_bench×5
    + _MATCHUP_FEATURES
    + _FIELD_FEATURES
)
TOTAL_SIZE = CONTINUOUS_SIZE + N_ABILITY_SLOTS


# ── Small in-place write helpers — all (out, offset, ...) -> new_offset ───────

@njit
def _write_status_onehot(out, offset, status):
    if 0 <= status < _N_STATUS:
        out[offset + status] = 1.0
    return offset + _N_STATUS


@njit
def _write_vol_bits(out, offset, vol):
    for i in range(_N_VOL):
        out[offset + i] = 1.0 if (vol & _VOL_BITS[i]) else 0.0
    return offset + _N_VOL


@njit
def _write_ai_knows(out, offset, knows):
    for i in range(_N_AI_KNOWS):
        out[offset + i] = 1.0 if (knows & _AI_KNOWS_BITS[i]) else 0.0
    return offset + _N_AI_KNOWS


@njit
def _write_item_onehot(out, offset, item_id):
    if 0 <= item_id < _N_ITEM_CATS:
        out[offset + item_id] = 1.0
    return offset + _N_ITEM_CATS


@njit
def _write_type_onehot(out, offset, type_id):
    """One-hot for a single type value (a move's type, or the type that
    hit me last turn) as opposed to a Pokémon's set of up to two."""
    if 1 <= type_id <= _N_TYPES:
        out[offset + type_id - 1] = 1.0
    return offset + _N_TYPES


@njit
def _write_type_multihot(out, offset, type1, type2):
    """Set membership for a Pokémon's typing (1 or 2 bits set)."""
    if 1 <= type1 <= _N_TYPES:
        out[offset + type1 - 1] = 1.0
    if 1 <= type2 <= _N_TYPES:
        out[offset + type2 - 1] = 1.0
    return offset + _N_TYPES


@njit
def _write_stab_effectiveness(out, offset, atk_type1, atk_type2, def_type1, def_type2):
    """2 values: effectiveness of each of the attacker's own types
    against the defender's typing, computed directly from the type
    chart. 0.25=neutral, 0=immune, 1.0=4x."""
    eff1, den1 = get_type_effectiveness(atk_type1, def_type1, def_type2)
    out[offset] = (eff1 / den1) / 4.0
    if atk_type2:
        eff2, den2 = get_type_effectiveness(atk_type2, def_type1, def_type2)
        out[offset + 1] = (eff2 / den2) / 4.0
    return offset + 2


@njit
def _write_matchup(out, offset, my_t1, my_t2, opp_t1, opp_t2):
    offset = _write_stab_effectiveness(out, offset, my_t1, my_t2, opp_t1, opp_t2)
    offset = _write_stab_effectiveness(out, offset, opp_t1, opp_t2, my_t1, my_t2)
    return offset


@njit
def _write_last_move(out, offset, move_id):
    """5 features from my_last_move (0 = none yet, -1 = Struggle, >0 =
    a real move ID). Only what trainer_ai actually branches on."""
    if move_id == 0:
        return offset + _LAST_MOVE_LEN
    is_phys = move_id in PHYSICAL
    is_spec = move_id in SPECIAL
    out[offset]     = 1.0
    out[offset + 1] = (is_phys)*1.0
    out[offset + 2] = (is_spec)*1.0
    out[offset + 3] = (not is_phys and not is_spec)*1.0
    out[offset + 4] = (move_id in FIRE_WATER_ELECTRIC)*1.0
    return offset + _LAST_MOVE_LEN


# ── Per-Pokemon base block, shared by both templates ───────────────────────────

@njit
def _write_pokemon_base(out, offset, pok):
    max_hp = max(float(pok[_POK_MAX_HP]), 1.0)
    c = offset
    out[c] = 1.0; c += 1  # is_alive — caller only reaches this after the HP check
    out[c] = float(pok[_POK_CURRENT_HP]) / max_hp; c += 1
    out[c] = max_hp / _MAX_STAT; c += 1
    out[c] = float(pok[_POK_ATTACK])          / _MAX_STAT; c += 1
    out[c] = float(pok[_POK_DEFENSE])         / _MAX_STAT; c += 1
    out[c] = float(pok[_POK_SPECIAL_ATTACK])  / _MAX_STAT; c += 1
    out[c] = float(pok[_POK_SPECIAL_DEFENSE]) / _MAX_STAT; c += 1
    out[c] = float(pok[_POK_SPEED])           / _MAX_STAT; c += 1
    out[c] = float(pok[_POK_ATTACK_STAT_STAGE])          / 6.0; c += 1
    out[c] = float(pok[_POK_DEFENSE_STAT_STAGE])         / 6.0; c += 1
    out[c] = float(pok[_POK_SPECIAL_ATTACK_STAT_STAGE])  / 6.0; c += 1
    out[c] = float(pok[_POK_SPECIAL_DEFENSE_STAT_STAGE]) / 6.0; c += 1
    out[c] = float(pok[_POK_SPEED_STAT_STAGE])           / 6.0; c += 1
    out[c] = float(pok[_POK_ACCURACY_STAT_STAGE])        / 6.0; c += 1
    out[c] = float(pok[_POK_EVASION_STAT_STAGE])         / 6.0; c += 1
    out[c] = float(pok[_POK_LEVEL]) / 100.0; c += 1
    out[c] = float(pok[_POK_TURNS]) / 50.0; c += 1
    out[c] = float(pok[_POK_SLEEP_COUNTER]) / 5.0; c += 1
    out[c] = float(pok[_POK_BADLY_POISON])  / 16.0; c += 1
    return c


# ── One move slice ──────────────────────────────────────────────────────────────

@njit
def _write_move(out, offset, mv):
    if mv[_MOVE_ID] == 0:
        return offset + _MOVE_FEAT_LEN   # buffer already zero, nothing to write

    c = offset
    out[c] = (mv[_MOVE_PP] > 0)*1.0; c += 1
    out[c] = float(mv[_MOVE_POWER]) / _MAX_MOVE_POWER; c += 1
    acc = mv[_MOVE_ACCURACY]
    ignores_accuracy = acc == -1
    out[c] = (ignores_accuracy)*1.0; c += 1
    out[c] = 0.0 if ignores_accuracy else float(acc) / 100.0; c += 1
    out[c] = float(mv[_MOVE_PP])       / _MAX_PP; c += 1
    out[c] = float(mv[_MOVE_PRIORITY]) / _MAX_PRIORITY; c += 1
    out[c] = float(mv[_MOVE_BOOST_ATK])   / 2.0; c += 1
    out[c] = float(mv[_MOVE_BOOST_DEF])   / 2.0; c += 1
    out[c] = float(mv[_MOVE_BOOST_SPATK]) / 2.0; c += 1
    out[c] = float(mv[_MOVE_BOOST_SPDEF]) / 2.0; c += 1
    out[c] = float(mv[_MOVE_BOOST_SPEED]) / 2.0; c += 1
    out[c] = float(mv[_MOVE_BOOST_ACC])   / 2.0; c += 1
    out[c] = float(mv[_MOVE_BOOST_EV])    / 2.0; c += 1
    out[c] = float(mv[_MOVE_RECOIL]) / 100.0; c += 1
    out[c] = float(mv[_MOVE_DRAIN])  / 100.0; c += 1
    out[c] = float(mv[_SEC_CHANCE])  / 100.0; c += 1
    # c is now offset + _MOVE_SCALAR_LEN

    category = mv[_MOVE_CATEGORY]
    out[c]     = (category == _MOVECATEGORY_PHYSICAL)*1.0
    out[c + 1] = (category == _MOVECATEGORY_SPECIAL)*1.0
    out[c + 2] = (category == _MOVECATEGORY_STATUS)*1.0
    c += 3

    c = _write_type_onehot(out, c, mv[_MOVE_TYPE])
    c = _write_status_onehot(out, c, mv[_MOVE_STATUS])
    c = _write_status_onehot(out, c, mv[_SEC_STATUS])
    return c


# ── Full / coarse Pokémon blocks ────────────────────────────────────────────────

@njit
def _write_full_pokemon(out, offset, pok):
    """My active, my whole bench, opponent's active. Ability is excluded
    — it lives in the tail block instead. All-zero if fainted."""
    if pok[_POK_CURRENT_HP] <= 0:
        return offset + _FULL_POKEMON_FEATURES

    c = _write_pokemon_base(out, offset, pok)
    c = _write_type_multihot(out, c, pok[_POK_TYPE1], pok[_POK_TYPE2])
    c = _write_status_onehot(out, c, pok[_POK_STATUS])
    c = _write_vol_bits(out, c, pok[_POK_VOL_STATUS])
    for i in range(4):
        mv = pok[OFFSET_MOVE + i * MOVE_STRIDE : OFFSET_MOVE + (i + 1) * MOVE_STRIDE]
        c = _write_move(out, c, mv)
    return c


@njit
def _write_coarse_pokemon(out, offset, pok):
    """Opponent's bench only — never something I act on directly.
    Movesets collapse into one type-coverage set. All-zero if fainted."""
    if pok[_POK_CURRENT_HP] <= 0:
        return offset + _COARSE_POKEMON_FEATURES

    c = _write_pokemon_base(out, offset, pok)
    c = _write_type_multihot(out, c, pok[_POK_TYPE1], pok[_POK_TYPE2])
    c = _write_status_onehot(out, c, pok[_POK_STATUS])
    c = _write_vol_bits(out, c, pok[_POK_VOL_STATUS])

    coverage_start = c
    usable_start   = coverage_start + _N_TYPES
    has_status_idx = usable_start + 4

    has_status_move = 0.0
    for i in range(4):
        mv = pok[OFFSET_MOVE + i * MOVE_STRIDE : OFFSET_MOVE + (i + 1) * MOVE_STRIDE]
        if mv[_MOVE_ID] == 0:
            continue
        mv_type = mv[_MOVE_TYPE]
        if 1 <= mv_type <= _N_TYPES:
            out[coverage_start + mv_type - 1] = 1.0
        if mv[_MOVE_PP] > 0:
            out[usable_start + i] = 1.0
        if mv[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
            has_status_move = 1.0
    out[has_status_idx] = has_status_move

    return has_status_idx + 1


# ── Field block ─────────────────────────────────────────────────────────────────

@njit
def _write_field(out, offset, battle_array):
    c = offset
    weather = battle_array[_FIELD_WEATHER]
    if 0 <= weather < _N_WEATHER:
        out[c + weather] = 1.0
    c += _N_WEATHER

    out[c]     = float(battle_array[_FIELD_TURN]) / _MAX_TURN
    out[c + 1] = (battle_array[_FIELD_TRICKROOM] > 0)*1.0
    out[c + 2] = (battle_array[_FIELD_PHASE] == _BATTLEPHASE_DEATH_END_OF_TURN)*1.0
    out[c + 3] = (battle_array[_FIELD_MY_ENTER_FIELD]  > 0)*1.0
    out[c + 4] = (battle_array[_FIELD_OPP_ENTER_FIELD] > 0)*1.0
    c += _FIELD_SCALAR_LEN

    c = _write_last_move(out, c, battle_array[_FIELD_MY_LAST_MOVE])
    c = _write_type_onehot(out, c, battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN])
    c = _write_ai_knows(out, c, battle_array[_FIELD_AI_KNOWS])
    c = _write_item_onehot(out, c, battle_array[_FIELD_AI_ITEM1])
    c = _write_item_onehot(out, c, battle_array[_FIELD_AI_ITEM2])
    c = _write_item_onehot(out, c, battle_array[_FIELD_AI_ITEM3])
    c = _write_item_onehot(out, c, battle_array[_FIELD_AI_ITEM4])
    return c


# ── Public API ────────────────────────────────────────────────────────────────

@njit
def to_nn_input(battle_array):
    """battle_array -> single float32 array of length TOTAL_SIZE.
    See module docstring for layout. Use split_features() to recover
    the continuous block and the int64 ability IDs separately."""
    out = np.zeros(TOTAL_SIZE, dtype=np.float32)

    my_idx  = battle_array[_FIELD_MY_POK]
    opp_idx = battle_array[_FIELD_OPP_POK]

    my_active  = battle_array[my_idx * POK_LEN : (my_idx + 1) * POK_LEN]
    opp_active = battle_array[(opp_idx + 6) * POK_LEN : (opp_idx + 7) * POK_LEN]

    c = 0
    c = _write_full_pokemon(out, c, my_active)
    c = _write_full_pokemon(out, c, opp_active)

    ability_offset = CONTINUOUS_SIZE
    out[ability_offset]     = float(my_active[_POK_AB_ID])
    out[ability_offset + 6] = float(opp_active[_POK_AB_ID])

    bench_slot = 1
    for i in range(6):
        if i == my_idx:
            continue
        pok = battle_array[i * POK_LEN : (i + 1) * POK_LEN]
        c = _write_full_pokemon(out, c, pok)
        out[ability_offset + bench_slot] = float(pok[_POK_AB_ID])
        bench_slot += 1

    opp_bench_slot = 7
    for i in range(6):
        if i == opp_idx:
            continue
        pok = battle_array[(i + 6) * POK_LEN : (i + 7) * POK_LEN]
        c = _write_coarse_pokemon(out, c, pok)
        out[ability_offset + opp_bench_slot] = float(pok[_POK_AB_ID])
        opp_bench_slot += 1

    c = _write_matchup(
        out, c,
        my_active[_POK_TYPE1], my_active[_POK_TYPE2],
        opp_active[_POK_TYPE1], opp_active[_POK_TYPE2],
    )
    c = _write_field(out, c, battle_array)
    assert c == CONTINUOUS_SIZE  #Check to see if i added or removed properly
    return out


def split_features(combined: np.ndarray):
    """Split the combined array into what a model actually consumes:
    the continuous float block, and the ability IDs cast back from
    their lossless float32 storage to int64 for an embedding lookup.
    Plain Python — a training/inference convenience, never on a hot path."""
    continuous  = combined[:CONTINUOUS_SIZE]
    ability_ids = combined[CONTINUOUS_SIZE:].astype(np.int64)
    return continuous, ability_ids


# ── Import-time consistency check ──────────────────────────────────────────────
# No longer needed to derive any size (those are all pre-declared above via
# plain arithmetic) — this just confirms the incremental writes inside each
# function actually add up to the width that function claims, catching drift
# immediately and loudly instead of producing a silently wrong-shaped array.
# As a side effect this also triggers compilation once at import time rather
# than on the first real call later.

_dummy_battle = np.zeros(Field.AI_KNOWS + 1, dtype=np.int32)
for _slot in range(12):
    _base = _slot * POK_LEN
    _dummy_battle[_base + _POK_CURRENT_HP] = 1
    _dummy_battle[_base + _POK_MAX_HP] = 1
    for _m in range(4):
        _mv = _base + OFFSET_MOVE + _m * MOVE_STRIDE
        _dummy_battle[_mv + _MOVE_ID] = 1
        _dummy_battle[_mv + _MOVE_PP] = 1
_dummy_battle[_FIELD_MY_LAST_MOVE] = 1
_result = to_nn_input(_dummy_battle)
assert len(_result) == TOTAL_SIZE, (
    f"to_nn_input produced {len(_result)} values, expected {TOTAL_SIZE} — "
    "an incremental offset somewhere doesn't match its declared width constant"
)
