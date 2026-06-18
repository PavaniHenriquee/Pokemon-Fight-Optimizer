"""
Extract neural-network-ready inputs from a battle_array.

Returns a dict, not a single flat array, because ability identity goes
through an embedding lookup rather than being squeezed into a float:
  {
    "continuous":  float32 array, shape (CONTINUOUS_SIZE,)
    "ability_ids": int64 array,   shape (N_ABILITY_SLOTS,)
  }

continuous layout:
  my_active     (_FULL_POKEMON_FEATURES)
  opp_active    (_FULL_POKEMON_FEATURES)
  my_bench x 5  (_FULL_POKEMON_FEATURES each)
  opp_bench x 5 (_COARSE_POKEMON_FEATURES each)
  type matchup  (_MATCHUP_FEATURES)
  field         (_FIELD_FEATURES)

ability_ids order: [my_active, my_benchx5, opp_active, opp_benchx5]

Two templates only, differing purely in move detail:
  "full"   — active (mine + opponent's) and my whole bench. Every one of
             my Pokémon is a candidate active via a switch I control, and
             the opponent's active is what trainer_ai is actually reading
             right now, so both need full per-move detail.
  "coarse" — opponent's bench only, never something I act on directly.
             Movesets collapse into a single type-coverage set instead of
             4 fully detailed moves.

vol_status and stat stages are included in BOTH templates uniformly, even
though Engine.engine_helper.reset_switch_out guarantees they're always
zero for anyone not currently active. They're deliberately not stripped
for bench slots: a linear layer's gradient contribution from an input is
proportional to that input's value, so a column that is exactly 0 in
every sample never receives a gradient signal and is invisible to
training — no accuracy cost to leaving it in. The only cost is a few
extra multiply-adds in the first layer. A third template that stripped
these two fields specifically for bench would trade that negligible
saving for another near-duplicate function to keep in sync as the engine
keeps changing — not worth it while still under active development.

All block sizes are derived by calling each feature function once at
import time, never hand-counted. The empty-slot / fainted-Pokémon early
returns reference these same size constants, so they're measured using
dummy input deliberately built to skip that branch (nonzero move ID,
nonzero current HP) and walk the real computation path instead —
measuring with an all-zero dummy hits the early return and crashes
trying to read its own not-yet-defined size.
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
_MAX_PP         = 64.0  # highest PP considering PP ups
_MAX_TURN       = 100.0
_N_TYPES        = 19

_VOL_BITS = (1, 2, 4, 8, 16, 32, 64, 128, 256)
_AI_KNOWS_BITS = (
    _ENEMY_AI_KNOWS_ABILITY, _ENEMY_AI_KNOWS_MOVE1, _ENEMY_AI_KNOWS_MOVE2,
    _ENEMY_AI_KNOWS_MOVE3, _ENEMY_AI_KNOWS_MOVE4,
)
_N_ITEM_CATS = 9  # 0 = empty slot, 1-8 = Potions enum values

N_ABILITY_SLOTS = 12  # fixed by game rules (6v6 parties), not a feature-engineering choice — safe to hardcode


# ── Small categorical helpers ──────────────────────────────────────────────────
@njit
def _status_onehot(status: int) -> np.ndarray:
    v = np.zeros(7, dtype=np.float32)
    if 0 <= status < 7:
        v[status] = 1.0
    return v


@njit
def _vol_bits(vol: int) -> np.ndarray:
    return np.array([1.0 if (vol & b) else 0.0 for b in _VOL_BITS], dtype=np.float32)


@njit
def _ai_knows_bits(knows: int) -> np.ndarray:
    return np.array([1.0 if (knows & b) else 0.0 for b in _AI_KNOWS_BITS], dtype=np.float32)


@njit
def _item_onehot(item_id: int) -> np.ndarray:
    v = np.zeros(_N_ITEM_CATS, dtype=np.float32)
    if 0 <= item_id < _N_ITEM_CATS:
        v[item_id] = 1.0
    return v


@njit
def _type_multihot(type1: int, type2: int) -> np.ndarray:
    """19-dim set membership for a Pokémon's typing (1 or 2 bits set)."""
    v = np.zeros(_N_TYPES, dtype=np.float32)
    if 1 <= type1 <= _N_TYPES:
        v[type1 - 1] = 1.0
    if 1 <= type2 <= _N_TYPES:
        v[type2 - 1] = 1.0
    return v


@njit
def _type_onehot(type_id: int) -> np.ndarray:
    """One-hot for a single type value (a move's type, or the type that
    hit me last turn) as opposed to a Pokémon's set of up to two."""
    v = np.zeros(_N_TYPES, dtype=np.float32)
    if 1 <= type_id <= _N_TYPES:
        v[type_id - 1] = 1.0
    return v


@njit
def _stab_effectiveness(atk_type1, atk_type2, def_type1, def_type2) -> np.ndarray:
    """2 floats: effectiveness of each of the attacker's own types against
    the defender's typing, computed directly from the type chart rather
    than left for the network to rediscover. 0.25=neutral, 0=immune,
    1.0=4x."""
    eff1, den1 = get_type_effectiveness(atk_type1, def_type1, def_type2)
    out2 = 0.0
    if atk_type2:
        eff2, den2 = get_type_effectiveness(atk_type2, def_type1, def_type2)
        out2 = (eff2 / den2) / 4.0
    return np.array([(eff1 / den1) / 4.0, out2], dtype=np.float32)


@njit
def _last_move_features(move_id: int) -> np.ndarray:
    """
    5 features derived from my_last_move (0 = none yet, -1 = Struggle,
    >0 = a real move ID). Only the properties trainer_ai actually
    branches on are encoded — full move identity is redundant with the
    active Pokémon's own moveset block elsewhere in the vector.
    """
    if move_id == 0:
        return np.zeros(5, dtype=np.float32)
    is_phys = move_id in PHYSICAL
    is_spec = move_id in SPECIAL
    return np.array([
        1.0,
        is_phys*1.0,
        is_spec*1.0,
        int(not is_phys and not is_spec)*1.0,
        int(move_id in FIRE_WATER_ELECTRIC)*1.0,
    ], dtype=np.float32)


def _move_features(mv: np.ndarray) -> np.ndarray:
    """
    One move slice, all zeros for an empty slot. Type, category, primary
    status, and secondary status are all one-hot — none of these are
    ordinal. Boosts stay per-stat since which stat changes is exactly
    the strategically relevant part. Accuracy splits into 'ignores
    accuracy/evasion stage checks entirely' vs 'has this base accuracy
    but is still stage-modified', matching the literal branch in
    trainer_ai_helper.expert_flag.
    """
    if mv[_MOVE_ID] == 0:
        return np.zeros(_MOVE_FEATURES, dtype=np.float32)

    acc = mv[_MOVE_ACCURACY]
    ignores_accuracy = acc == -1
    base_accuracy = 0.0 if ignores_accuracy else float(acc) / 100.0
    category = int(mv[_MOVE_CATEGORY])

    base = np.array([
        float(mv[_MOVE_PP]) > 0,
        float(mv[_MOVE_POWER]) / _MAX_MOVE_POWER,
        float(ignores_accuracy),
        base_accuracy,
        float(mv[_MOVE_PP])       / _MAX_PP,
        float(mv[_MOVE_PRIORITY]) / _MAX_PRIORITY,
        float(mv[_MOVE_BOOST_ATK])   / 2.0,
        float(mv[_MOVE_BOOST_DEF])   / 2.0,
        float(mv[_MOVE_BOOST_SPATK]) / 2.0,
        float(mv[_MOVE_BOOST_SPDEF]) / 2.0,
        float(mv[_MOVE_BOOST_SPEED]) / 2.0,
        float(mv[_MOVE_BOOST_ACC])   / 2.0,
        float(mv[_MOVE_BOOST_EV])    / 2.0,
        float(mv[_MOVE_RECOIL])   / 100.0,
        float(mv[_MOVE_DRAIN])    / 100.0,
        float(mv[_SEC_CHANCE])    / 100.0,
    ], dtype=np.float32)

    category_onehot = np.array([
        float(category == _MOVECATEGORY_PHYSICAL),
        float(category == _MOVECATEGORY_SPECIAL),
        float(category == _MOVECATEGORY_STATUS),
    ], dtype=np.float32)

    return np.concatenate([
        base,
        category_onehot,
        _type_onehot(int(mv[_MOVE_TYPE])),
        _status_onehot(int(mv[_MOVE_STATUS])),
        _status_onehot(int(mv[_SEC_STATUS])),
    ])


# ── Per-Pokemon base block shared by both templates ───────────────────────────
@njit
def _pokemon_base(pok: np.ndarray) -> np.ndarray:
    """HP, raw stats, stat stages, level/turns, sleep/toxic counters.
    Shared verbatim by both templates and by active and bench slots
    alike — see module docstring for why stat stages (always zero on
    bench) aren't worth special-casing out."""
    max_hp = max(float(pok[_POK_MAX_HP]), 1.0)
    return np.array([
        1.0,  # is_alive — caller only reaches this after the HP check
        float(pok[_POK_CURRENT_HP]) / max_hp,
        max_hp / _MAX_STAT,

        float(pok[_POK_ATTACK])          / _MAX_STAT,
        float(pok[_POK_DEFENSE])         / _MAX_STAT,
        float(pok[_POK_SPECIAL_ATTACK])  / _MAX_STAT,
        float(pok[_POK_SPECIAL_DEFENSE]) / _MAX_STAT,
        float(pok[_POK_SPEED])           / _MAX_STAT,

        float(pok[_POK_ATTACK_STAT_STAGE])          / 6.0,
        float(pok[_POK_DEFENSE_STAT_STAGE])         / 6.0,
        float(pok[_POK_SPECIAL_ATTACK_STAT_STAGE])  / 6.0,
        float(pok[_POK_SPECIAL_DEFENSE_STAT_STAGE]) / 6.0,
        float(pok[_POK_SPEED_STAT_STAGE])           / 6.0,
        float(pok[_POK_ACCURACY_STAT_STAGE])        / 6.0,
        float(pok[_POK_EVASION_STAT_STAGE])         / 6.0,

        float(pok[_POK_LEVEL]) / 100.0,
        float(pok[_POK_TURNS]) / 50.0,
        float(pok[_POK_SLEEP_COUNTER]) / 5.0,
        float(pok[_POK_BADLY_POISON])  / 16.0,
    ], dtype=np.float32)


def _full_pokemon_features(pok: np.ndarray) -> np.ndarray:
    """
    Full move detail: my active, my whole bench, opponent's active.
    Ability is excluded — it goes through ability_ids instead of a
    float. All zeros if fainted.
    """
    if pok[_POK_CURRENT_HP] <= 0:
        return np.zeros(_FULL_POKEMON_FEATURES, dtype=np.float32)

    moves = np.concatenate([
        _move_features(pok[OFFSET_MOVE + i * MOVE_STRIDE : OFFSET_MOVE + (i + 1) * MOVE_STRIDE])
        for i in range(4)
    ])

    return np.concatenate([
        _pokemon_base(pok),
        _type_multihot(int(pok[_POK_TYPE1]), int(pok[_POK_TYPE2])),
        _status_onehot(int(pok[_POK_STATUS])),
        _vol_bits(int(pok[_POK_VOL_STATUS])),
        moves,
    ])


def _coarse_pokemon_features(pok: np.ndarray) -> np.ndarray:
    """
    Compressed move detail: opponent's bench only — never something I
    act on directly. Movesets collapse into one type-coverage set rather
    than 4 fully detailed moves. All zeros if fainted.
    """
    if pok[_POK_CURRENT_HP] <= 0:
        return np.zeros(_COARSE_POKEMON_FEATURES, dtype=np.float32)

    coverage = np.zeros(_N_TYPES, dtype=np.float32)
    usable   = np.zeros(4, dtype=np.float32)
    has_status_move = 0.0
    for i in range(4):
        mv = pok[OFFSET_MOVE + i * MOVE_STRIDE : OFFSET_MOVE + (i + 1) * MOVE_STRIDE]
        if mv[_MOVE_ID] == 0:
            continue
        mv_type = int(mv[_MOVE_TYPE])
        if 1 <= mv_type <= _N_TYPES:
            coverage[mv_type - 1] = 1.0
        if mv[_MOVE_PP] > 0:
            usable[i] = 1.0
        if mv[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
            has_status_move = 1.0

    return np.concatenate([
        _pokemon_base(pok),
        _type_multihot(int(pok[_POK_TYPE1]), int(pok[_POK_TYPE2])),
        _status_onehot(int(pok[_POK_STATUS])),
        _vol_bits(int(pok[_POK_VOL_STATUS])),
        coverage,
        usable,
        np.array([has_status_move], dtype=np.float32),
    ])


@njit
def _matchup_features(my_active, opp_active) -> np.ndarray:
    return np.concatenate((
        _stab_effectiveness(
            int(my_active[_POK_TYPE1]), int(my_active[_POK_TYPE2]),
            int(opp_active[_POK_TYPE1]), int(opp_active[_POK_TYPE2]),
        ),
        _stab_effectiveness(
            int(opp_active[_POK_TYPE1]), int(opp_active[_POK_TYPE2]),
            int(my_active[_POK_TYPE1]), int(my_active[_POK_TYPE2]),
        ),
    ))


@njit
def _field_features(battle_array: np.ndarray) -> np.ndarray:
    weather = int(battle_array[_FIELD_WEATHER])
    weather_enc = np.zeros(5, dtype=np.float32)
    if 0 <= weather < 5:
        weather_enc[weather] = 1.0

    return np.concatenate((
        weather_enc,
        np.array([
            float(battle_array[_FIELD_TURN]) / _MAX_TURN,
            float(battle_array[_FIELD_TRICKROOM]) > 0,
            int(battle_array[_FIELD_PHASE]) == _BATTLEPHASE_DEATH_END_OF_TURN*1.0,
            float(battle_array[_FIELD_MY_ENTER_FIELD])  > 0,
            float(battle_array[_FIELD_OPP_ENTER_FIELD]) > 0,
        ], dtype=np.float32),
        _last_move_features(int(battle_array[_FIELD_MY_LAST_MOVE])),
        _type_onehot(int(battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN])),
        _ai_knows_bits(int(battle_array[_FIELD_AI_KNOWS])),
        _item_onehot(int(battle_array[_FIELD_AI_ITEM1])),
        _item_onehot(int(battle_array[_FIELD_AI_ITEM2])),
        _item_onehot(int(battle_array[_FIELD_AI_ITEM3])),
        _item_onehot(int(battle_array[_FIELD_AI_ITEM4])),
    ))


# ── Derived sizes ──────────────────────────────────────────────────────────────
# Dummy inputs are deliberately non-empty / non-fainted so each function
# walks its real body instead of its early return. Order matters:
# _MOVE_FEATURES must be set before the pokemon-level functions are
# measured, since their dummy calls have all-zero move slices and depend
# on _MOVE_FEATURES already existing to resolve their own early returns.

_dummy_move = np.zeros(MOVE_STRIDE, dtype=np.int32)
_dummy_move[_MOVE_ID] = 1
_MOVE_FEATURES = len(_move_features(_dummy_move))

_dummy_pok = np.zeros(POK_LEN, dtype=np.int32)
_dummy_pok[_POK_CURRENT_HP] = 1
_dummy_pok[_POK_MAX_HP] = 1
_FULL_POKEMON_FEATURES   = len(_full_pokemon_features(_dummy_pok))
_COARSE_POKEMON_FEATURES = len(_coarse_pokemon_features(_dummy_pok))
_MATCHUP_FEATURES        = len(_matchup_features(_dummy_pok, _dummy_pok))

_dummy_field = np.zeros(Field.AI_KNOWS + 1, dtype=np.int32)
_FIELD_FEATURES = len(_field_features(_dummy_field))

CONTINUOUS_SIZE = (
    _FULL_POKEMON_FEATURES * 7      # my_active + opp_active + my_bench×5
    + _COARSE_POKEMON_FEATURES * 5  # opp_bench×5
    + _MATCHUP_FEATURES
    + _FIELD_FEATURES
)


# ── Public API ────────────────────────────────────────────────────────────────

def to_nn_input(battle_array: np.ndarray) -> dict:
    """
    Convert a battle_array into {'continuous': float32[CONTINUOUS_SIZE],
    'ability_ids': int64[N_ABILITY_SLOTS]}.
    """
    my_idx  = int(battle_array[_FIELD_MY_POK])
    opp_idx = int(battle_array[_FIELD_OPP_POK])

    my_active  = battle_array[my_idx  * POK_LEN       : (my_idx  + 1) * POK_LEN]
    opp_active = battle_array[(opp_idx + 6) * POK_LEN : (opp_idx + 7) * POK_LEN]
    my_bench  = [battle_array[i * POK_LEN : (i + 1) * POK_LEN] for i in range(6) if i != my_idx]
    opp_bench = [battle_array[(i + 6) * POK_LEN : (i + 7) * POK_LEN] for i in range(6) if i != opp_idx]

    ability_ids = np.array([
        int(my_active[_POK_AB_ID]),
        *[int(p[_POK_AB_ID]) for p in my_bench],
        int(opp_active[_POK_AB_ID]),
        *[int(p[_POK_AB_ID]) for p in opp_bench],
    ], dtype=np.int64)

    continuous = np.concatenate([
        _full_pokemon_features(my_active),
        _full_pokemon_features(opp_active),
        *[_full_pokemon_features(p) for p in my_bench],
        *[_coarse_pokemon_features(p) for p in opp_bench],
        _matchup_features(my_active, opp_active),
        _field_features(battle_array),
    ])

    return {"continuous": continuous, "ability_ids": ability_ids}
