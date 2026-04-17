"""Natures and type chart"""
import numpy as np
import json
import os
from Models.helper import Types


def load_utils(file_name):
    """get the data from the JSON file"""
    base_path = os.path.dirname(__file__)  # always relative to Utils Folder
    with open(os.path.join(base_path, file_name), "r") as f:
        return json.load(f)


type_chart = load_utils("TypeChart.json")
natures = load_utils("Nature.json")

# Pre Calc type chart
TYPE_CHART_ARRAY = np.ones((19, 19), dtype=np.float32)

for atk_name, defenders in type_chart.items():
    atk_id = getattr(Types, atk_name.upper())
    for def_name, multi in defenders.items():
        def_id = getattr(Types, def_name.upper())
        TYPE_CHART_ARRAY[atk_id][def_id] = multi
