"""Transform item in Numpy array"""
import numpy as np
from Utils.jit import njit
from Models.helper import ItemActivation, ItemType, Types, HoldEffect, Status, VolStatus, VolStatus2
from Models.idx_const import Item as ItemIdx, ITEM_LEN, Pok
from DataBase.ItemDB import ItemNames
from DataBase.PkDB import PokemonName
from DataBase.loader import itemDB


def item_to_np(item):
    """Basic array for Item"""
    array = np.zeros(ITEM_LEN, dtype=np.int16)
    off = ItemIdx.ID
    if not item:
        return array

    array[ItemIdx.ID-off] = getattr(ItemNames, item['name'].upper())
    array[ItemIdx.WHEN-off] = getattr(ItemActivation, item['when'].upper()) if 'when' in item else 0
    array[ItemIdx.ITEM_TYPE-off] = getattr(ItemType, item['type'].upper())
    array[ItemIdx.ITEM_USER-off] = getattr(PokemonName, item['item_user'].upper()) if 'item_user' in item else 0
    array[ItemIdx.FLING_POWER-off] = item.get('fling_power', 0)
    fling_status = item.get('fling_status')
    array[ItemIdx.FLING_STATUS-off] = getattr(Status, fling_status.upper()) if fling_status else 0
    fling_volatile = item.get('fling_volatile')
    array[ItemIdx.FLING_VOLATILE-off] = getattr(VolStatus, fling_volatile.upper()) if fling_volatile else 0
    array[ItemIdx.NATURAL_GIFT_POWER-off] = item.get('natural_gift_power', 0)
    if item.get('natural_gift_type', 0):
        natgif_type = getattr(Types, item['natural_gift_type'].upper())
    else:
        natgif_type = 0
    array[ItemIdx.NATURAL_GIFT_TYPE-off] = natgif_type
    array[ItemIdx.HOLD_EFFECT-off] = getattr(HoldEffect, item['hold_effect'].upper())
    array[ItemIdx.EFFECT_PARAM-off] = item.get('effect_param', 0)
    effect_type = getattr(Types, item['effect_type'].upper()) if 'effect_type' in item else 0
    array[ItemIdx.EFFECT_TYPE-off] = effect_type
    return array


def _item_table():
    """Item block of every item by id, so Recycle can rebuild a consumed item"""
    ids = [v for k, v in vars(ItemNames).items() if k.isupper() and isinstance(v, int)]
    table = np.zeros((max(ids) + 1, ITEM_LEN), dtype=np.int32)
    for item in itemDB.values():
        table[getattr(ItemNames, item['name'].upper())] = item_to_np(item)
    return table


ITEM_TABLE = _item_table()


# Plain ints for the njit helpers below (Numba can't read class attributes)
_ID = ItemIdx.ID
_END = ItemIdx.ID + ITEM_LEN
_VOL_STATUS2 = Pok.VOL_STATUS2
_EMBARGO = VolStatus2.EMBARGO
# Columns of an ITEM_TABLE row
_HOLD_EFFECT_COL = ItemIdx.HOLD_EFFECT - ItemIdx.ID
_ITEM_TYPE_COL = ItemIdx.ITEM_TYPE - ItemIdx.ID


@njit
def embargoed(pok):
    """Embargo: the held item does nothing until it ends"""
    return pok[_VOL_STATUS2] & _EMBARGO != 0


@njit
def refresh_item(pok):
    """
    Rebuild the item block from the item id, and under Embargo keep only the id: every effect read
    sees no item, while checks for holding one still see it (pokeplatinum Battler_HeldItem returns
    ITEM_NONE, the raw heldItem stays)
    """
    pok[_ID:_END] = ITEM_TABLE[pok[_ID]]
    if embargoed(pok):
        pok[_ID + 1:_END] = 0


@njit
def raw_hold_effect(pok):
    """The held item's hold effect, Embargo or not: the speed-halving items and the AI's
    LoadHeldItemEffect read it (pokeplatinum battleMons[].heldItem)"""
    return ITEM_TABLE[pok[_ID], _HOLD_EFFECT_COL]


@njit
def raw_item_type(pok):
    """The held item's type, Embargo or not"""
    return ITEM_TABLE[pok[_ID], _ITEM_TYPE_COL]
