"""Mechanics that are known to be wrong or missing right now. Each test asserts the CORRECT
mechanic and is a strict xfail, so the suite stays green today. When you implement/fix one,
its test XPASSes and fails with "XPASS(strict)": move it to the matching test file without
the marker so it becomes a normal regression test. If something here is intentional, delete
the test instead.
"""
import pytest


def bug(reason):
    """Strict xfail with the evidence as the reason"""
    return pytest.mark.xfail(strict=True, reason=reason)
