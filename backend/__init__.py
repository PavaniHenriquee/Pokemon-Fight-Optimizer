"""Backend package. Turns on the Numba compile cache before anything imports Utils.jit"""
from Utils.jit_cache import use_cache

use_cache("backend")
