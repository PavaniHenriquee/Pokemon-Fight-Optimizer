"""Pokemon stat formulas and the conversion to its array block"""
from Models.idx_const import Pok, Move, Item, MOVE_STRIDE, POK_LEN
from Models.helper import Types, Gender
from DataBase.PkDB import PokemonName
from DataBase.MoveDB import MoveName
from DataBase.ItemDB import ItemNames
from DataBase.AbilitiesDB import AbilityNames
from DataBase.loader import moveDB


def test_level5_charmander_stats(make_pokemon):
    """Charmander base 39/52/43/60/50/65, 31 IVs, 0 EVs, Hardy, L5"""
    p = make_pokemon("Charmander", 5, "Blaze", ["Scratch"])
    assert p.max_hp == 20          # (2*39+31)*5//100 + 5 + 10
    assert p.attack == 11          # (2*52+31)*5//100 + 5
    assert p.defense == 10
    assert p.special_attack == 12
    assert p.special_defense == 11
    assert p.speed == 13
    assert p.current_hp == p.max_hp


def test_nature_multipliers(make_pokemon):
    """Adamant: +10% Atk, -10% SpA, floored after the multiplier"""
    hardy = make_pokemon("Charmander", 50, "Blaze", ["Scratch"])
    adamant = make_pokemon("Charmander", 50, "Blaze", ["Scratch"], nature="Adamant")
    assert hardy.attack == 72 and adamant.attack == 79      # floor(72 * 1.1)
    assert hardy.special_attack == 80 and adamant.special_attack == 72
    assert hardy.speed == adamant.speed
    assert hardy.max_hp == adamant.max_hp


def test_evs_and_ivs(make_pokemon):
    """252 HP EVs add 63 stat points before the level scaling"""
    from Models.pokemon import Pokemon
    evs = {"HP": 252, "Attack": 0, "Defense": 0, "Special Attack": 0,
           "Special Defense": 0, "Speed": 0}
    ivs = {k: 0 for k in evs}
    p = Pokemon("Charmander", "Male", 100, "Blaze", "Hardy", ["Scratch"], ivs=ivs, evs=evs)
    assert p.max_hp == 2 * 39 + 63 + 100 + 10
    assert make_pokemon("Charmander", 100, "Blaze", ["Scratch"]).max_hp == 2 * 39 + 31 + 110


def test_to_np_base_fields(make_pokemon):
    """Identity, types, HP and start-of-battle defaults"""
    arr = make_pokemon("Geodude", 12, "Sturdy", ["Tackle"], gender="Female").to_np()
    assert arr.shape == (POK_LEN,)
    assert arr[Pok.ID] == PokemonName.GEODUDE
    assert arr[Pok.LEVEL] == 12
    assert (arr[Pok.TYPE1], arr[Pok.TYPE2]) == (Types.ROCK, Types.GROUND)
    assert arr[Pok.CURRENT_HP] == arr[Pok.MAX_HP] > 0
    assert arr[Pok.GENDER] == Gender.FEMALE
    assert arr[Pok.LOCKED_MOVE] == -1
    assert not arr[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE + 1].any()
    assert arr[Pok.STATUS] == 0 and arr[Pok.VOL_STATUS] == 0
    assert arr[Pok.AB_ID] == AbilityNames.STURDY


def test_single_type_has_zero_type2(make_pokemon):
    """Pure types leave TYPE2 empty, which the damage calc relies on"""
    arr = make_pokemon("Pikachu", 10, "Static", ["Thunder Shock"]).to_np()
    assert arr[Pok.TYPE1] == Types.ELECTRIC
    assert arr[Pok.TYPE2] == 0


def test_moves_are_encoded_in_order(make_pokemon):
    """Move slots follow the list order; unused slots stay zero"""
    arr = make_pokemon("Charmander", 5, "Blaze", ["Scratch", "Ember"]).to_np()
    m1 = arr[Pok.MOVE1_ID:Pok.MOVE1_ID + MOVE_STRIDE]
    m2 = arr[Pok.MOVE2_ID:Pok.MOVE2_ID + MOVE_STRIDE]
    assert m1[Move.ID] == MoveName.SCRATCH
    assert m1[Move.TYPE] == Types.NORMAL
    assert m1[Move.POWER] == moveDB["Scratch"]["power"]
    assert m1[Move.PP] == moveDB["Scratch"]["pp"]
    assert m2[Move.ID] == MoveName.EMBER
    assert m2[Move.TYPE] == Types.FIRE
    assert not arr[Pok.MOVE3_ID:Pok.ITEM_ID].any()


def test_always_hit_accuracy_is_minus_one(make_pokemon):
    """`accuracy: true` in MoveDB is stored as -1 (never misses)"""
    swift = next(n for n, m in moveDB.items() if m.get("accuracy") is True)
    arr = make_pokemon("Pikachu", 10, "Static", [swift]).to_np()
    assert arr[Pok.MOVE1_ID + Move.ACCURACY] == -1


def test_item_encoded(make_pokemon):
    """Held item lands in the item block, no item means zeros"""
    with_item = make_pokemon("Charmander", 5, "Blaze", ["Scratch"], item="Oran Berry").to_np()
    without = make_pokemon("Charmander", 5, "Blaze", ["Scratch"]).to_np()
    assert with_item[Item.ID] == ItemNames.ORAN_BERRY
    assert with_item[Item.ITEM_TYPE] != 0 and with_item[Item.WHEN] != 0
    assert not without[Item.ID:].any()
