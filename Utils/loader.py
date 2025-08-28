import json
import os

def load_utils(file_name):
    base_path = os.path.dirname(__file__) # always relative to Database Folder
    with open(os.path.join(base_path, file_name), "r") as f:
        return json.load(f)

type_chart = load_utils("TypeChart.json")