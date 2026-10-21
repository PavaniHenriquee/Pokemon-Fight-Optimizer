"""Project-wide njit wrapper, so caching is toggled with an environment variable"""
import inspect
import os
from numba import njit as _njit

CACHE = os.environ.get("NUMBA_CACHE_ON", "0") == "1"


def njit(*args, **kwargs):
    """Drop-in replacement for numba.njit, cache follows NUMBA_CACHE_ON unless set explicitly"""
    kwargs.setdefault("cache", CACHE)
    # Bare usage: @njit
    if len(args) == 1 and inspect.isfunction(args[0]):
        return _njit(**kwargs)(args[0])
    # Usage with arguments: @njit(inline='always'), @njit("int64(int64)"), ...
    return _njit(*args, **kwargs)
