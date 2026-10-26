"""Mechanics that are known to be wrong or missing right now. Each test asserts the CORRECT
mechanic and is a strict xfail, so the suite stays green today. When you implement/fix one,
its test XPASSes and fails with "XPASS(strict)": move it to the matching test file without
the marker so it becomes a normal regression test. If something here is intentional, delete
the test instead.
"""
import pytest
from Engine.battle import ps_moves
from Models.idx_const import Pok
from Models.trainer_ai import return_idx
from battle_driver import move_slice


def bug(reason):
    """Strict xfail with the evidence as the reason"""
    return pytest.mark.xfail(strict=True, reason=reason)


@bug("Not implemented yet (TODO.txt): DamageSources.LEVEL (-4) isn't handled in "
     "_resolve_move_damage, so it returns -4 and the move HEALS the target by 4")
@pytest.mark.parametrize("move", ["Seismic Toss", "Night Shade"])
def test_level_damage_moves_deal_user_level(poke, move):
    """Bulbapedia: Seismic Toss / Night Shade deal damage equal to the user's level"""
    a = poke("Machop", 14, "Guts", [move])
    d = poke("Rattata", 30, "Run Away", ["Tackle"])
    d[Pok.CURRENT_HP] -= 20
    hp = d[Pok.CURRENT_HP]
    ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.CURRENT_HP] == hp - 14


@bug("Not implemented yet (TODO.txt: Focus Energy (B)): expert_vol_status raises "
     "'Need implementation' for volatiles other than confusion")
def test_ai_with_focus_energy(make_pokemon, make_battle):
    """The AI can score Focus Energy without crashing"""
    arr = make_battle(
        [make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])],
        [make_pokemon("Rattata", 10, "Run Away", ["Tackle", "Focus Energy"])],
    )
    assert 0 <= return_idx(arr) <= 1
