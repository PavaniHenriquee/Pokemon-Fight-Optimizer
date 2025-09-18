"""Transform item in Numpy array"""
import numpy as np
from Models.idx_nparray import ItemIdx
from Models.helper import ItemActivation, ItemType
from DataBase.ItemDB import ItemNames
from DataBase.PkDB import PokemonName


def item_to_np(item):
    """Basic array for Item"""
    array = np.zeros(len(ItemIdx), dtype=np.int16)
    if not item:
        return array

    array[ItemIdx.ID] = ItemNames[item['name'].upper()].value
    array[ItemIdx.WHEN] = ItemActivation[item['when'].upper()].value
    array[ItemIdx.ITEM_TYPE] = ItemType[item['item_type'].upper()].value
    array[ItemIdx.ITEM_USER] = PokemonName[item['item_user'].upper()].value if 'item_user' in item else 0
    array[ItemIdx.FLING_POWER] = item.get('fling_power', 0)
    array[ItemIdx.FLING_STATUS] = item.get('fling_status', 0)
    array[ItemIdx.FLING_VOLATILE] = item.get('fling_volatile', 0)
    array[ItemIdx.NATURAL_GIFT_POWER] = item.get('natural_gift_power', 0)
    array[ItemIdx.NATURAL_GIFT_TYPE] = item.get('natural_gift_type', 0)
    return array
