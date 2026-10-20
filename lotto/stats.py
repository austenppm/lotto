"""Descriptive statistics over draw history."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .data import Draw
from .games import Game


@dataclass
class NumberStat:
    number: int
    total: int        # appearances over all history
    recent: int       # appearances in the recent window
    gap: int          # draws since last appearance
    expected_gap: float


def number_stats(game: Game, draws: list[Draw], window: int = 100) -> list[NumberStat]:
    total = Counter(n for d in draws for n in d.numbers)
    recent = Counter(n for d in draws[-window:] for n in d.numbers)
    last_seen: dict[int, int] = {}
    for idx, d in enumerate(draws):
        for n in d.numbers:
            last_seen[n] = idx
    end = len(draws)
    return [
        NumberStat(n, total[n], recent[n], end - last_seen.get(n, -1) - 1, game.max_num / game.pick)
        for n in range(1, game.max_num + 1)
    ]


def max_run(nums: tuple[int, ...]) -> int:
    """Longest run of consecutive numbers in a sorted combination."""
    best = run = 1
    for a, b in zip(nums, nums[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    return best


def odd_count(nums: tuple[int, ...]) -> int:
    return sum(n % 2 for n in nums)


def percentile(values: list[int], q: float) -> int:
    s = sorted(values)
    return s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))]


@dataclass
class Shape:
    """What a 'typical' winning combination looks like, learned from history."""
    sum_lo: int
    sum_hi: int
    odd_ok: frozenset[int]
    run_max: int
    past: frozenset[tuple[int, ...]]

    def fits(self, combo: tuple[int, ...]) -> bool:
        return (
            self.sum_lo <= sum(combo) <= self.sum_hi
            and odd_count(combo) in self.odd_ok
            and max_run(combo) <= self.run_max
            and combo not in self.past
        )


def shape(draws: list[Draw]) -> Shape:
    sums = [sum(d.numbers) for d in draws]
    odds = Counter(odd_count(d.numbers) for d in draws)
    runs = [max_run(d.numbers) for d in draws]
    return Shape(
        sum_lo=percentile(sums, 0.10),
        sum_hi=percentile(sums, 0.90),
        odd_ok=frozenset(k for k, v in odds.items() if v / len(draws) >= 0.05),
        run_max=percentile(runs, 0.95),
        past=frozenset(d.numbers for d in draws),
    )
