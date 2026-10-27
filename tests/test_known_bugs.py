"""Mechanics that are known to be wrong or missing right now. Each test asserts the CORRECT
mechanic and is a strict xfail, so the suite stays green today. When you implement/fix one,
its test XPASSes and fails with "XPASS(strict)": move it to the matching test file without
the marker so it becomes a normal regression test. If something here is intentional, delete
the test instead.
"""
import pytest
from Engine.battle import ps_moves
from Models.idx_const import Pok
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

