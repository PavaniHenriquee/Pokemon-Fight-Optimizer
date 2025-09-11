"""Natures and type chart"""
import json
import os


def load_utils(file_name):
    """get the data from the JSON file"""
    base_path = os.path.dirname(__file__)  # always relative to Utils Folder
    with open(os.path.join(base_path, file_name), "r") as f:
        return json.load(f)


type_chart = load_utils("TypeChart.json")
natures = load_utils("Nature.json")
