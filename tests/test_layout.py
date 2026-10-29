"""Array layout (idx_const) and the generated constants file stay consistent"""
import numpy as np
import pytest
import Models.constants as C
from Models import idx_const as I
from Models import helper as H
from DataBase.AbilitiesDB import AbilityNames
from DataBase.MoveDB import MoveName
from DataBase.ItemDB import ItemNames
from Utils.helper import to_battle_array

# Same list generate_constants.py writes out
GENERATED_CLASSES = (
    I.Pok, I.Move, I.Flags, I.Sec, I.Field, I.Item, H.MoveCategory, AbilityNames,
    H.Types, H.Weather, H.AbilityActivation, H.Status, MoveName, H.VolStatus, H.VolStatus2,
    H.Gender, H.Enemy_AI_Knows, H.Potions, H.MoveOutcome, H.ActionType,
    H.BattlePhase, H.ItemActivation, H.ItemType, ItemNames, H.SideCondition, H.Terrain,
    H.DamageSources,
)


def _int_attrs(cls):
    return {k: v for k, v in vars(cls).items() if k.isupper() and isinstance(v, int)}


@pytest.mark.parametrize("cls", GENERATED_CLASSES, ids=lambda c: c.__name__)
def test_constants_file_is_up_to_date(cls):
    """Fails when an enum/index class changed but generate_constants.py wasn't run"""
    stale = {}
    for attr, val in _int_attrs(cls).items():
        name = f"_{cls.__name__.upper()}_{attr}"
        got = getattr(C, name, None)
        if got != val:
            stale[name] = (got, val)
    assert not stale, f"Run `python generate_constants.py`. (constants.py, source): {stale}"


def _contiguous(cls, start):
    values = sorted(_int_attrs(cls).values())
    return values == list(range(start, start + len(values)))


def test_move_block_is_contiguous():
    """Move base, flags and secondary indices tile the move stride with no gaps/overlaps"""
    assert _contiguous(I.Move, 0)
    assert _contiguous(I.Flags, I.BASE_MOVE_LEN)
    assert _contiguous(I.Sec, I.OFFSET_SEC)
    assert I.MOVE_STRIDE == I.BASE_MOVE_LEN + I.FLAGS_LEN + I.SEC_LEN


def test_pokemon_block_offsets():
    """Base, ability, 4 moves, item laid out back to back"""
    assert I.OFFSET_MOVE == I.Pok.AB_BREAKABLE + 1
    for i, mv in enumerate((I.Pok.MOVE1_ID, I.Pok.MOVE2_ID, I.Pok.MOVE3_ID, I.Pok.MOVE4_ID)):
        assert mv == I.OFFSET_MOVE + i * I.MOVE_STRIDE
    assert I.Pok.ITEM_ID == I.OFFSET_ITEM == I.Item.ID
    assert _contiguous(I.Item, I.Item.ID)
    assert I.POK_LEN == I.Item.ITEM_USER + 1


def test_field_block_follows_12_pokemon():
    """Field block sits right after the 12 Pokemon blocks"""
    assert I.Field.MY_POK == 12 * I.POK_LEN
    assert _contiguous(I.Field, I.Field.MY_POK)
    assert I.FIELD_LEN == len(_int_attrs(I.Field))


def test_volstatus_are_distinct_bits():
    """VolStatus is a bitmap, every value must be its own power of two"""
    values = list(_int_attrs(H.VolStatus).values())
    assert all(v > 0 and v & (v - 1) == 0 for v in values)
    assert len(set(values)) == len(values)


def test_volstatus_fits_int32():
    """The bitmap lives in an int32 slot, so no bit may reach the sign bit"""
    assert sum(_int_attrs(H.VolStatus).values()) < 2**31


def test_volstatus2_are_distinct_bits():
    """VolStatus2 is the second bitmap, same rules as VolStatus"""
    values = list(_int_attrs(H.VolStatus2).values())
    assert all(v > 0 and v & (v - 1) == 0 for v in values)
    assert len(set(values)) == len(values)
    assert sum(values) < 2**31


def test_side_condition_are_distinct_bits():
    """SideCondition is a per-side bitmap, every value must be its own power of two"""
    values = list(_int_attrs(H.SideCondition).values())
    assert all(v > 0 and v & (v - 1) == 0 for v in values)
    assert len(set(values)) == len(values)


def test_new_pokemon_counters_start_at_zero(make_pokemon):
    """Counters for volatiles and move history start empty when a Pokemon is built"""
    arr = make_pokemon("Pikachu", 10, "Static", ["Thunder Shock"]).to_np()
    assert arr.shape == (I.POK_LEN,)
    assert not arr[I.Pok.PROTECT_COUNT : I.Pok.VOL_STATUS2 + 1].any()
    assert arr[I.Pok.WEIGHT] > 0


def test_empty_battle_array_shape():
    """to_battle_array pads empty slots with zeros and returns int32"""
    arr = to_battle_array([], [])
    assert arr.dtype == np.int32
    assert arr.shape == (12 * I.POK_LEN + I.FIELD_LEN,)
    assert not arr.any()


def test_battle_array_places_parties(make_pokemon):
    """Slot 0 is mine, slot 6 is the opponent's first, the rest stay empty"""
    mine = make_pokemon("Pikachu", 10, "Static", ["Thunder Shock"])
    theirs = make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])
    arr = to_battle_array([mine], [theirs])
    np.testing.assert_array_equal(arr[:I.POK_LEN], mine.to_np())
    np.testing.assert_array_equal(arr[6 * I.POK_LEN:7 * I.POK_LEN], theirs.to_np())
    assert not arr[I.POK_LEN:6 * I.POK_LEN].any()
    assert not arr[7 * I.POK_LEN:12 * I.POK_LEN].any()
