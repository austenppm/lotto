"""Walk-forward backtest: for each past draw, pick tickets using only earlier data."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .data import Draw
from .games import Game
from .predict import generate
from .stats import shape


@dataclass
class Result:
    strategy: str
    tickets: int = 0
    main_hits: int = 0
    tier_counts: list[int] = field(default_factory=list)
    spent: int = 0
    won: int = 0

    @property
    def avg_hits(self) -> float:
        return self.main_hits / self.tickets if self.tickets else 0.0

    @property
    def roi(self) -> float:
        return (self.won - self.spent) / self.spent if self.spent else 0.0


def score(game: Game, ticket: tuple[int, ...], draw: Draw) -> tuple[int, int | None]:
    nums = set(ticket)
    main = len(nums & set(draw.numbers))
    bonus = len(nums & set(draw.bonus))
    return main, game.tier(main, bonus)


def run(
    game: Game,
    draws: list[Draw],
    strategies: list[str],
    last: int = 200,
    per_draw: int = 5,
    seed: int = 0,
    min_history: int = 50,
) -> list[Result]:
    results = {s: Result(s, tier_counts=[0] * game.tiers) for s in strategies}
    start = max(min_history, len(draws) - last)
    for i in range(start, len(draws)):
        history, target = draws[:i], draws[i]
        hist_shape = shape(history)
        for s in strategies:
            rng = random.Random(f"{seed}-{s}-{i}")
            r = results[s]
            for t in generate(game, history, s, per_draw, rng, hist_shape=hist_shape):
                main, tier = score(game, t, target)
                r.tickets += 1
                r.main_hits += main
                r.spent += game.price
                if tier:
                    r.tier_counts[tier - 1] += 1
                    r.won += target.prizes[tier - 1]
    return list(results.values())


def prize_chance(game: Game, tickets: list[tuple[int, ...]], trials: int = 100_000,
                 rng: random.Random | None = None) -> float:
    """Monte Carlo estimate of P(at least one ticket wins any prize) in one draw."""
    rng = rng or random.Random(0)
    sets = [set(t) for t in tickets]
    pool = range(1, game.max_num + 1)
    hits = 0
    for _ in range(trials):
        drawn = rng.sample(pool, game.pick + game.bonus)
        main, bonus = set(drawn[:game.pick]), set(drawn[game.pick:])
        if any(game.tier(len(s & main), len(s & bonus)) for s in sets):
            hits += 1
    return hits / trials
