"""
Extract a normalized float32 feature vector from a battle_array
for neural network input.


The active Pokémon is always placed first regardless of its party slot,
so the NN sees a consistent structure across all training samples.

Usage:
    from Models.nn_features import to_nn_input, NN_INPUT_SIZE
    features = to_nn_input(battle_array)
"""
import numpy as np
from Models.idx_const import POK_LEN, MOVE_STRIDE, OFFSET_MOVE
from Models.constants import (
    # Field indices
    _FIELD_MY_POK, _FIELD_OPP_POK, _FIELD_TURN, _FIELD_WEATHER,
    _FIELD_TRICKROOM, _FIELD_PHASE,
    # Pokemon stat indices
    _POK_CURRENT_HP, _POK_MAX_HP,
    _POK_ATTACK, _POK_DEFENSE, _POK_SPECIAL_ATTACK, _POK_SPECIAL_DEFENSE, _POK_SPEED,
    # Stat stage indices
    _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE,
    _POK_SPECIAL_ATTACK_STAT_STAGE, _POK_SPECIAL_DEFENSE_STAT_STAGE,
    _POK_SPEED_STAT_STAGE, _POK_ACCURACY_STAT_STAGE, _POK_EVASION_STAT_STAGE,
    # Other Pokemon fields
    _POK_STATUS, _POK_VOL_STATUS, _POK_TYPE1, _POK_TYPE2,
    _POK_AB_ID, _POK_LEVEL, _POK_TURNS, _POK_SLEEP_COUNTER, _POK_BADLY_POISON,
    # Move fields (relative to the start of a move slice)
    _MOVE_ID, _MOVE_CATEGORY, _MOVE_TYPE, _MOVE_POWER, _MOVE_ACCURACY,
    _MOVE_PP, _MOVE_PRIORITY, _MOVE_STATUS,
    _MOVE_BOOST_ATK, _MOVE_BOOST_DEF, _MOVE_BOOST_SPATK,
    _MOVE_BOOST_SPDEF, _MOVE_BOOST_SPEED, _MOVE_BOOST_ACC, _MOVE_BOOST_EV,
    _MOVE_RECOIL, _MOVE_DRAIN,
    # Secondary effect fields (relative to the start of a move slice)
    _SEC_CHANCE, _SEC_STATUS,
    # Category / phase constants
    _MOVECATEGORY_STATUS,
    _BATTLEPHASE_DEATH_END_OF_TURN,
)

# ── Normalization ceilings ────────────────────────────────────────────────────
_MAX_STAT       = 500.0   # practical ceiling for any battle stat
_MAX_ABILITY_ID = 57.0    # highest AbilityNames value (Wonder Guard)
_MAX_MOVE_POWER = 250.0
_MAX_PRIORITY   = 7.0
_MAX_PP         = 64.0    # highest base PP of any move
_MAX_TURN       = 100.0
_N_TYPES        = 19.0    # types encoded 1-19; 0 means no secondary type

# Vol-status bitmap values in a fixed order — 9 flags
_VOL_BITS = (1, 2, 4, 8, 16, 32, 64, 128, 256)

# ── Feature-count constants (used externally when building the network) ───────
_ACTIVE_FEATURES = 89   # base(21) + status_onehot(7) + vol_bits(9) + moves(4×13=52)
_BENCH_FEATURES  = 38   # base(20) + status_onehot(7) + vol_bits(9) + move_types(4)
                        #           + move_usable(4) + has_status_move(1)
_FIELD_FEATURES  = 8    # weather_onehot(5) + turn(1) + trickroom(1) + phase(1)

NN_INPUT_SIZE = _ACTIVE_FEATURES * 2 + _BENCH_FEATURES * 10 + _FIELD_FEATURES


# ── Internal helpers ──────────────────────────────────────────────────────────

def _status_onehot(status: int) -> np.ndarray:
    """
    7-element one-hot for permanent status.
    Index 0 = no status, 1 = sleep, 2 = freeze, 3 = paralysis,
    4 = burn, 5 = poison, 6 = toxic.
    """
    v = np.zeros(7, dtype=np.float32)
    if 0 <= status < 7:
        v[status] = 1.0
    return v


def _vol_bits(vol: int) -> np.ndarray:
    """Expand the vol_status integer bitmap into 9 binary float32 flags."""
    return np.array([1.0 if (vol & b) else 0.0 for b in _VOL_BITS], dtype=np.float32)


def _move_features(mv: np.ndarray) -> np.ndarray:
    """
    13 features from a single MOVE_STRIDE-element move slice.
    Returns all zeros for an empty slot (move_id == 0).
    """
    if mv[_MOVE_ID] == 0:
        return np.zeros(13, dtype=np.float32)

    acc = mv[_MOVE_ACCURACY]
    acc_norm = -1.0 if acc == -1 else float(acc) / 100.0

    # Combined magnitude of all stat boosts this move applies
    total_boost = float(
        abs(mv[_MOVE_BOOST_ATK])   + abs(mv[_MOVE_BOOST_DEF])
        + abs(mv[_MOVE_BOOST_SPATK]) + abs(mv[_MOVE_BOOST_SPDEF])
        + abs(mv[_MOVE_BOOST_SPEED]) + abs(mv[_MOVE_BOOST_ACC])
        + abs(mv[_MOVE_BOOST_EV])
    ) / (3.0 * 7)   # max possible is 3 per field × 7 fields

    return np.array([
        float(mv[_MOVE_PP]) > 0,                        # 0: is usable (has PP left)
        float(mv[_MOVE_TYPE])     / _N_TYPES,           # 1: type
        float(mv[_MOVE_CATEGORY]) / 3.0,                # 2: physical/special/status
        float(mv[_MOVE_POWER])    / _MAX_MOVE_POWER,    # 3: base power
        acc_norm,                                        # 4: accuracy
        float(mv[_MOVE_PP])       / _MAX_PP,            # 5: remaining PP signal
        float(mv[_MOVE_PRIORITY]) / _MAX_PRIORITY,      # 6: priority bracket
        float(mv[_MOVE_STATUS])   > 0,                  # 7: inflicts primary status
        total_boost,                                     # 8: stat change magnitude
        float(mv[_MOVE_RECOIL])   / 100.0,              # 9: recoil fraction
        float(mv[_MOVE_DRAIN])    / 100.0,              # 10: drain fraction
        float(mv[_SEC_CHANCE])    / 100.0,              # 11: secondary effect chance
        float(mv[_SEC_STATUS])    > 0,                  # 12: secondary status flag
    ], dtype=np.float32)


def _active_features(pok: np.ndarray) -> np.ndarray:
    """
    89 features for the active Pokémon — all 4 moves fully expanded.
    'pok' must be a POK_LEN-element slice of the battle_array.

    During DEATH_END_OF_TURN phase the still-active (just-fainted) Pokémon
    is passed here; its HP ratio of 0.0 is the signal that a switch is required.
    """
    max_hp = max(float(pok[_POK_MAX_HP]), 1.0)

    base = np.array([
        float(pok[_POK_CURRENT_HP]) / max_hp,           # HP ratio
        max_hp / _MAX_STAT,                              # absolute bulk context

        float(pok[_POK_ATTACK])          / _MAX_STAT,
        float(pok[_POK_DEFENSE])         / _MAX_STAT,
        float(pok[_POK_SPECIAL_ATTACK])  / _MAX_STAT,
        float(pok[_POK_SPECIAL_DEFENSE]) / _MAX_STAT,
        float(pok[_POK_SPEED])           / _MAX_STAT,

        float(pok[_POK_ATTACK_STAT_STAGE])          / 6.0,  # stages: -6..6 → -1..1
        float(pok[_POK_DEFENSE_STAT_STAGE])         / 6.0,
        float(pok[_POK_SPECIAL_ATTACK_STAT_STAGE])  / 6.0,
        float(pok[_POK_SPECIAL_DEFENSE_STAT_STAGE]) / 6.0,
        float(pok[_POK_SPEED_STAT_STAGE])           / 6.0,
        float(pok[_POK_ACCURACY_STAT_STAGE])        / 6.0,
        float(pok[_POK_EVASION_STAT_STAGE])         / 6.0,

        float(pok[_POK_TYPE1])  / _N_TYPES,
        float(pok[_POK_TYPE2])  / _N_TYPES,          # 0.0 when single-typed
        float(pok[_POK_AB_ID])  / _MAX_ABILITY_ID,
        float(pok[_POK_LEVEL])  / 100.0,
        float(pok[_POK_SLEEP_COUNTER]) / 5.0,        # turns of sleep remaining
        float(pok[_POK_BADLY_POISON])  / 16.0,       # toxic multiplier (1-15)
        float(pok[_POK_TURNS])  / 50.0,              # turns in battle
    ], dtype=np.float32)  # 21 values

    moves = np.concatenate([
        _move_features(
            pok[OFFSET_MOVE + i * MOVE_STRIDE : OFFSET_MOVE + (i + 1) * MOVE_STRIDE]
        )
        for i in range(4)
    ])  # 4 × 13 = 52

    return np.concatenate([
        base,                                        # 21
        _status_onehot(int(pok[_POK_STATUS])),       # 7
        _vol_bits(int(pok[_POK_VOL_STATUS])),        # 9
        moves,                                       # 52
    ])  # total: 89


def _bench_features(pok: np.ndarray) -> np.ndarray:
    """
    45 features for a bench Pokémon — compressed move representation.
    Returns all zeros for a fainted or absent Pokémon (HP == 0).
    """
    if pok[_POK_CURRENT_HP] <= 0:
        return np.zeros(_BENCH_FEATURES, dtype=np.float32)

    max_hp = max(float(pok[_POK_MAX_HP]), 1.0)

    base = np.array([
        1.0,                                             # is_alive
        float(pok[_POK_CURRENT_HP]) / max_hp,
        max_hp / _MAX_STAT,

        float(pok[_POK_ATTACK])          / _MAX_STAT,
        float(pok[_POK_DEFENSE])         / _MAX_STAT,
        float(pok[_POK_SPECIAL_ATTACK])  / _MAX_STAT,
        float(pok[_POK_SPECIAL_DEFENSE]) / _MAX_STAT,
        float(pok[_POK_SPEED])           / _MAX_STAT,


        float(pok[_POK_TYPE1])  / _N_TYPES,
        float(pok[_POK_TYPE2])  / _N_TYPES,
        float(pok[_POK_AB_ID])  / _MAX_ABILITY_ID,
        float(pok[_POK_LEVEL])  / 100.0,
        float(pok[_POK_TURNS])  / 50.0,
    ], dtype=np.float32)  # 20 values

    # Move types let the NN reason about switch value and type coverage
    move_types = np.array([
        float(pok[OFFSET_MOVE + i * MOVE_STRIDE + _MOVE_TYPE]) / _N_TYPES
        for i in range(4)
    ], dtype=np.float32)  # 4

    # PP availability — signals Struggle risk on a potential switch-in
    move_usable = np.array([
        float(pok[OFFSET_MOVE + i * MOVE_STRIDE + _MOVE_PP]) > 0
        for i in range(4)
    ], dtype=np.float32)  # 4

    # Whether the bench Pokémon has at least one usable status move
    has_status_move = np.array([float(any(
        pok[OFFSET_MOVE + i * MOVE_STRIDE + _MOVE_CATEGORY] == _MOVECATEGORY_STATUS
        and pok[OFFSET_MOVE + i * MOVE_STRIDE + _MOVE_PP] > 0
        for i in range(4)
    ))], dtype=np.float32)  # 1

    return np.concatenate([
        base,                                        # 20
        _status_onehot(int(pok[_POK_STATUS])),       # 7
        _vol_bits(int(pok[_POK_VOL_STATUS])),        # 9
        move_types,                                  # 4
        move_usable,                                 # 4
        has_status_move,                             # 1
    ])  # total: 45


# ── Public API ────────────────────────────────────────────────────────────────

def to_nn_input(battle_array: np.ndarray) -> np.ndarray:
    """
    Convert a battle_array into a float32 feature vector.

    Layout:
      my_active | opp_active | my_benchx5 | opp_benchx5 | field

    The active Pokémon always comes first regardless of party slot index.
    This function never modifies the input array — it only reads from it.
    """
    my_idx  = int(battle_array[_FIELD_MY_POK])
    opp_idx = int(battle_array[_FIELD_OPP_POK])  # 0-5; data lives at slot opp_idx+6

    my_active  = battle_array[my_idx  * POK_LEN       : (my_idx  + 1) * POK_LEN]
    opp_active = battle_array[(opp_idx + 6) * POK_LEN : (opp_idx + 7) * POK_LEN]

    my_bench = [
        battle_array[i * POK_LEN : (i + 1) * POK_LEN]
        for i in range(6) if i != my_idx
    ]
    opp_bench = [
        battle_array[(i + 6) * POK_LEN : (i + 7) * POK_LEN]
        for i in range(6) if i != opp_idx
    ]

    # ── Field ────────────────────────────────────────────────────────────────
    weather = int(battle_array[_FIELD_WEATHER])  # 0=none 1=sun 2=rain 3=hail 4=sand
    weather_enc = np.zeros(5, dtype=np.float32)
    if 0 <= weather < 5:
        weather_enc[weather] = 1.0

    field = np.concatenate([
        weather_enc,
        np.array([
            float(battle_array[_FIELD_TURN])      / _MAX_TURN,
            float(battle_array[_FIELD_TRICKROOM]) > 0,
            float(int(battle_array[_FIELD_PHASE]) == _BATTLEPHASE_DEATH_END_OF_TURN),
        ], dtype=np.float32),
    ])  # 8

    return np.concatenate([
        _active_features(my_active),
        _active_features(opp_active),
        *[_bench_features(p) for p in my_bench],
        *[_bench_features(p) for p in opp_bench],
        field,
    ])
