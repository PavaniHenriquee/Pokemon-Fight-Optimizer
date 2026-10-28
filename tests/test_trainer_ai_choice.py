"""Trainer AI move choice end to end: in clear-cut situations the moves the AI can pick, plus the
Strong AI (Evaluate Attacks) rules from Pokemow behind them"""
from collections import Counter
import numpy as np
import pytest
from Models import trainer_ai_helper as ai
from Models.trainer_ai import return_idx, choose_move
from Models.idx_const import Pok, Move
from Models.helper import Status, VolStatus, Types
from Engine.damage_calc import calculate_ai_logic_damage
from battle_driver import move_slice, pok_slice, opp_active

N = 300


def _picks(arr):
    """How often each move slot is picked over N decisions"""
    return Counter(int(return_idx(arr)) for _ in range(N))


def _battle(make_pokemon, make_battle, me, opp):
    return make_battle([make_pokemon(*me)], [make_pokemon(*opp)])


def test_weaker_moves_never_picked(make_pokemon, make_battle):
    """Mudkip vs Charmeleon: Mud-Slap and Tackle do less than Water Gun, Growl ties at 0"""
    arr = _battle(make_pokemon, make_battle,
                  ("Charmeleon", 15, "Blaze", ["Scratch", "Growl", "Ember"]),
                  ("Mudkip", 10, "Torrent", ["Mud-Slap", "Water Gun", "Growl", "Tackle"]))
    assert set(_picks(arr)) == {1, 2}


def test_strongest_move_always_picked(make_pokemon, make_battle):
    """Only damaging moves and none KOs: always the strongest"""
    arr = _battle(make_pokemon, make_battle,
                  ("Charmeleon", 15, "Blaze", ["Scratch"]),
                  ("Mudkip", 10, "Torrent", ["Tackle", "Water Gun", "Mud-Slap"]))
    assert set(_picks(arr)) == {1}


def test_weaker_move_that_kos_not_penalized(make_pokemon, make_battle):
    """Both moves KO: both get +4 and the weaker one keeps it"""
    arr = _battle(make_pokemon, make_battle,
                  ("Charmeleon", 15, "Blaze", ["Scratch"]),
                  ("Mudkip", 10, "Torrent", ["Tackle", "Water Gun"]))
    pok_slice(arr, 0)[Pok.CURRENT_HP] = 1
    assert set(_picks(arr)) == {0, 1}


def test_priority_ko_beats_normal_ko(make_pokemon, make_battle):
    """Quick Attack KO is +6, Tackle KO is +4"""
    arr = _battle(make_pokemon, make_battle,
                  ("Geodude", 10, "Sturdy", ["Tackle"]),
                  ("Rattata", 10, "Guts", ["Tackle", "Quick Attack"]))
    pok_slice(arr, 0)[Pok.CURRENT_HP] = 1
    assert set(_picks(arr)) == {1}


def test_type_immune_move_never_picked(make_pokemon, make_battle):
    """Tackle into Gastly does nothing, Ember is the only pick"""
    arr = _battle(make_pokemon, make_battle,
                  ("Gastly", 10, "Levitate", ["Lick"]),
                  ("Charmander", 10, "Blaze", ["Tackle", "Ember"]))
    assert set(_picks(arr)) == {1}


def test_levitate_ground_move_never_picked(make_pokemon, make_battle):
    """Koffing can only have Levitate, so the super effective Mud-Slap is never picked"""
    arr = _battle(make_pokemon, make_battle,
                  ("Koffing", 10, "Levitate", ["Tackle"]),
                  ("Mudkip", 10, "Torrent", ["Mud-Slap", "Tackle"]))
    assert set(_picks(arr)) == {1}


def test_fixed_damage_compared_by_its_damage(make_pokemon, make_battle):
    """Seismic Toss does the AI's level: strongest into a bulky Geodude, weaker into a frail
    target that Water Gun hits hard"""
    tank = _battle(make_pokemon, make_battle,
                   ("Geodude", 30, "Sturdy", ["Tackle"]),
                   ("Rattata", 30, "Guts", ["Tackle", "Seismic Toss"]))
    assert set(_picks(tank)) == {1}
    frail = _battle(make_pokemon, make_battle,
                    ("Charmander", 5, "Blaze", ["Scratch"]),
                    ("Mudkip", 5, "Torrent", ["Seismic Toss", "Water Gun"]))
    assert set(_picks(frail)) == {1}


def test_redundant_status_never_picked(make_pokemon, make_battle):
    """Thunder Wave into an already paralyzed target"""
    arr = _battle(make_pokemon, make_battle,
                  ("Rattata", 10, "Guts", ["Tackle"]),
                  ("Pikachu", 10, "Static", ["Thunder Wave", "Thunder Shock"]))
    pok_slice(arr, 0)[Pok.STATUS] = Status.PARALYSIS
    assert set(_picks(arr)) == {1}


def test_no_pp_move_never_picked(make_pokemon, make_battle):
    """The stronger move is out of PP: never picked, but its damage still makes the weaker one
    take the -1 (pokeplatinum TrainerAI_CalcAllDamage loops every known move)"""
    arr = _battle(make_pokemon, make_battle,
                  ("Charmeleon", 15, "Blaze", ["Scratch"]),
                  ("Mudkip", 10, "Torrent", ["Water Gun", "Tackle"]))
    move_slice(opp_active(arr), 0)[Move.PP] = 0
    assert set(_picks(arr)) == {1}
    assert choose_move(arr)[1, 1] == -1


def test_hyper_beam_not_compared(make_pokemon, make_battle):
    """Hyper Beam isn't subject to the damage calc, so it doesn't make Tackle 'not the strongest'"""
    arr = _battle(make_pokemon, make_battle,
                  ("Geodude", 30, "Sturdy", ["Tackle"]),
                  ("Rattata", 10, "Guts", ["Hyper Beam", "Tackle"]))
    rows = choose_move(arr)
    assert rows[1, 1] == 0 and rows[1, 3] == 1
    assert rows[0, 3] == 0


def test_weaker_4x_move_gets_no_bonus(make_pokemon, make_battle):
    """Check_CannotKO terminates: the weaker 4x move only takes the -1, the strongest 4x move
    rolls 68.8% of +2"""
    arr = _battle(make_pokemon, make_battle,
                  ("Geodude", 25, "Sturdy", ["Tackle"]),
                  ("Mudkip", 10, "Torrent", ["Water Gun", "Bubble Beam"]))
    weak, strong = set(), set()
    for _ in range(N):
        rows = choose_move(arr)
        weak.add(int(rows[0, 1]))
        strong.add(int(rows[1, 1]))
    assert weak == {-1}
    assert strong == {0, 2}


def test_wonder_guard_withdraw_fallthrough(make_pokemon, make_battle):
    """Shedinja: when no Wonder Guard withdraw is rolled, the withdraw 3 check reuses its
    candidates without crashing"""
    arr = make_battle(
        [make_pokemon("Shedinja", 20, "Wonder Guard", ["Scratch"])],
        [make_pokemon("Mudkip", 10, "Torrent", ["Tackle", "Water Gun"]),
         make_pokemon("Charmander", 10, "Blaze", ["Ember"]),
         make_pokemon("Ponyta", 10, "Flash Fire", ["Ember"])],
    )
    for _ in range(N):
        assert return_idx(arr) in (-5, -4, 0, 1)


def _eval(poke, move, damage_calc, effectiveness=1.0, ko=True):
    """evaluate_attack_flag of the AI's first move against a 10 HP target"""
    ai_pok = poke("Machop", 30, "Guts", [move])
    user = poke("Rattata", 30, "Guts", ["Tackle"])
    user[Pok.CURRENT_HP] = 10
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.evaluate_attack_flag(
        50 if ko else 5, effectiveness, user, move_slice(ai_pok, 0), 0, rand, damage_calc
    )
    return score, [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]


@pytest.mark.parametrize("move", ["Explosion", "Selfdestruct", "Focus Punch", "Sucker Punch"])
def test_risky_moves_no_ko_bonus(poke, move):
    """Pokemow Check_MoveCheck: 80.1% of -2 even when they would KO, no +4"""
    assert _eval(poke, move, False) == (0, [(-2, 205)])


def test_future_sight_risky_ko(poke):
    """Check_RiskyCanKO: 33.6% of +4"""
    assert _eval(poke, "Future Sight", True) == (0, [(4, 85)])


@pytest.mark.parametrize("move, expected", [("Tackle", 4), ("Quick Attack", 6), ("Bug Bite", 4)])
def test_ko_bonus(poke, move, expected):
    """Check_GeneralCanKO +4, Check_PriorityCanKO +6"""
    assert _eval(poke, move, True) == (expected, [])


def test_damage_calc_move_4x_deferred(poke):
    """A damaging move that can't KO leaves the 4x check to choose_move, after the -1"""
    assert _eval(poke, "Tackle", True, 4.0, ko=False) == (0, [])


def test_exempt_move_4x_and_no_ko(poke):
    """Hyper Beam can't get the KO bonus, only the 4x check"""
    assert _eval(poke, "Hyper Beam", False, 4.0) == (0, [(2, 176)])


@pytest.mark.parametrize("attacker, ability, move, target, expected", [
    ("Mudkip", "Torrent", "Tackle", "Bulbasaur", (1.0, False)),      # neutral on Grass/Poison
    ("Mudkip", "Torrent", "Tackle", "Geodude", (0.5, False)),        # resisted by Rock only
    ("Rattata", "Guts", "Tackle", "Geodude", (0.5, False)),          # STAB 0.5x: 0.75x -> 0.5x
    ("Mudkip", "Torrent", "Mud-Slap", "Magnemite", (4.0, True)),     # Ground into Electric/Steel
    ("Mudkip", "Torrent", "Mud-Slap", "Bulbasaur", (1.0, False)),    # 2x and 0.5x cancel
    ("Charmander", "Blaze", "Ember", "Bulbasaur", (2.0, True)),      # STAB 2x: 3x -> 2x
    ("Mudkip", "Torrent", "Water Gun", "Geodude", (4.0, True)),      # STAB 4x: 6x -> 4x
    ("Charmander", "Blaze", "Ember", "Rattata", (1.5, False)),       # neutral STAB is kept
])
def test_ai_effectiveness_dual_type(poke, attacker, ability, move, target, expected):
    """Pokemow: the move's type is checked against both of the target's types, then 0.375x,
    0.75x, 3x and 6x are taken as STAB boosted and adjusted to 0.25x, 0.5x, 2x and 4x"""
    ai_pok = poke(attacker, 10, ability, [move])
    user = poke(target, 10, "Sturdy", ["Tackle"])
    assert ai.trainer_ai_effectiveness(move_slice(ai_pok, 0), ai_pok, user) == expected


def test_ai_damage_keeps_stab_on_super_effective(poke):
    """pokeplatinum TrainerAI_CalcDamage uses the battle's type chart: STAB Water Gun into a
    Fire type is 1.5x then 2x, the AI's 3x -> 2x effectiveness adjustment doesn't reach it"""
    stab_ai = poke("Mudkip", 10, "Torrent", ["Water Gun"])
    plain_ai = stab_ai.copy()
    plain_ai[Pok.TYPE1] = Types.NORMAL
    user = poke("Charmeleon", 15, "Blaze", ["Scratch"])
    mv = move_slice(stab_ai, 0)
    stab = calculate_ai_logic_damage(2.0, stab_ai, user, mv, 0)
    plain = calculate_ai_logic_damage(2.0, plain_ai, user, mv, 0)
    assert plain % 2 == 0 and stab == 2 * ((plain // 2) * 3 // 2)


def test_ai_damage_rollout_boosts_ignored(make_pokemon, make_battle):
    """Rollout's consecutive and Defense Curl boosts are set outside BattleSystem_CalcMoveDamage,
    the AI sees base power"""
    me = ("Charmeleon", 15, "Blaze", ["Scratch"])
    opp = ("Geodude", 10, "Sturdy", ["Rollout"])
    arr = _battle(make_pokemon, make_battle, me, opp)
    base = int(choose_move(arr)[0, 2])
    ai_pok = opp_active(arr)
    ai_pok[Pok.CONSEC_COUNT] = 3
    ai_pok[Pok.VOL_STATUS] |= VolStatus.DEFENSE_CURL
    assert int(choose_move(arr)[0, 2]) == base


@pytest.mark.parametrize("move", ["Counter", "Bide", "Mirror Coat", "Flail", "Magnitude"])
def test_power_1_moves_not_compared(make_pokemon, make_battle, move):
    """Power 1 and not an alt power move: no kill check and no 'not the strongest' -1"""
    arr = _battle(make_pokemon, make_battle,
                  ("Charmeleon", 15, "Blaze", ["Scratch"]),
                  ("Mudkip", 10, "Torrent", ["Water Gun", move]))
    rows = choose_move(arr)
    assert rows[1, 3] == 0 and rows[0, 1] == 0
