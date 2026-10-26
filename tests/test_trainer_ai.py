"""Trainer AI: which expert-flag evaluation a status move is scored by, and that the AI can
pick a move with any implemented status move in its kit"""
import numpy as np
import pytest
from Models import trainer_ai_helper as ai
from Models.trainer_ai import return_idx
from battle_driver import move_slice

# Status moves that carry both a volatile and a stat boost are the tricky ones
ROUTING = [
    ("Swagger", "vol"),        # confusion on the foe + Atk +2 → confuse logic (Psych Up case)
    ("Flatter", "vol"),        # confusion on the foe + SpA +1
    ("Confuse Ray", "vol"),
    ("Defense Curl", "stat"),  # Def +1, the volatile is only a Rollout marker
    ("Harden", "stat"),
    ("Growl", "stat"),
    ("Thunder Wave", "status"),
]


@pytest.mark.parametrize("move, expected", ROUTING)
def test_expert_flag_routing(monkeypatch, poke, move, expected):
    """expert_flag sends each status move to the evaluation of what the move is for"""
    called = []
    monkeypatch.setattr(ai, "expert_status", lambda *a: called.append("status") or 0)
    monkeypatch.setattr(ai, "expert_vol_status", lambda *a: called.append("vol") or 0)
    monkeypatch.setattr(ai, "expert_stat", lambda *a: called.append("stat") or 0)
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    ai.expert_flag(ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0)
    assert called == [expected]


@pytest.mark.parametrize("move", [
    "Swagger", "Flatter", "Defense Curl", "Thunder Wave", "Poison Powder", "Sleep Powder",
    "Hypnosis", "Will-O-Wisp", "Confuse Ray", "Supersonic",
])
@pytest.mark.parametrize("ai_faster", [True, False])
def test_ai_picks_a_move_with_status_kit(make_pokemon, make_battle, move, ai_faster):
    """Full-HP AI holding a status move, moving first or second, picks a legal slot"""
    me = make_pokemon("Geodude", 30 if not ai_faster else 10, "Sturdy", ["Tackle"])
    opp = make_pokemon("Pikachu", 30 if ai_faster else 10, "Static", ["Thunder Shock", move])
    arr = make_battle([me], [opp])
    for _ in range(20):
        assert return_idx(arr) in (0, 1)
