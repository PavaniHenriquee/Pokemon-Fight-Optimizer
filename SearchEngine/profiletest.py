"""test"""
from cProfile import Profile
from pstats import SortKey, Stats

def fib(n):
    """test"""
    return n if n < 2 else fib(n - 2) + fib(n - 1)

with Profile() as profile:
    fib(30)
    (
        Stats(profile)
        .strip_dirs()
        .sort_stats(SortKey.TIME)
        .print_stats()
    )
