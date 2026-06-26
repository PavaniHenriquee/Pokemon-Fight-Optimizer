"""Transform item in Numpy array"""
import numpy as np
from Models.helper import ItemActivation, ItemType, Types
from Models.idx_const import Item as ItemIdx, ITEM_LEN
from DataBase.ItemDB import ItemNames
from DataBase.PkDB import PokemonName


def item_to_np(item):
    """Basic array for Item"""
    array = np.zeros(ITEM_LEN, dtype=np.int16)
    off = ItemIdx.ID
    if not item:
        return array

    array[ItemIdx.ID-off] = getattr(ItemNames, item['name'].upper())
    array[ItemIdx.WHEN-off] = getattr(ItemActivation, item['when'].upper())
    array[ItemIdx.ITEM_TYPE-off] = getattr(ItemType, item['type'].upper())
    array[ItemIdx.ITEM_USER-off] = getattr(PokemonName, item['item_user'].upper()) if 'item_user' in item else 0
    array[ItemIdx.FLING_POWER-off] = item.get('fling_power', 0)
    array[ItemIdx.FLING_STATUS-off] = item.get('fling_status', 0)
    array[ItemIdx.FLING_VOLATILE-off] = item.get('fling_volatile', 0)
    array[ItemIdx.NATURAL_GIFT_POWER-off] = item.get('natural_gift_power', 0)
    if item.get('natural_gift_type', 0):
        natgif_type = getattr(Types, item['natural_gift_type'].upper())
    else:
        natgif_type = 0
    array[ItemIdx.NATURAL_GIFT_TYPE-off] = natgif_type
    return array
