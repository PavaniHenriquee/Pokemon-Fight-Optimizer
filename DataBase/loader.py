"""Loader for the Database"""
import json
import os


def load_database(file_name):
    """Loader of the DB"""
    base_path = os.path.dirname(__file__)  # always relative to Database Folder
    with open(os.path.join(base_path, file_name), "r", encoding=None) as f:
        return json.load(f)


pkDB = load_database("PkDB.json")
abDB = load_database("AbilitiesDB.json")
itemDB = load_database("ItemDB.json")
moveDB = load_database("MoveDB.json")
