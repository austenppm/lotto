"""Ticket generation strategies.

Every combination is equally likely to be drawn, so no strategy here changes
the odds of winning. They differ only in *which* numbers they favour:

  hot        numbers drawn often recently
  cold       numbers drawn rarely recently
  overdue    numbers with the longest gap since last drawn
  balanced   blend of hot and overdue
  unpopular  avoids numbers people over-pick (birthdays 1-31, patterns), which
             doesn't improve odds but raises the expected payout when you win,
             because prizes are shared among fewer winners
  random     uniform, unfiltered -- the honest baseline
"""

from __future__ import annotations

import random

from .data import Draw
from .games import Game
from .stats import Shape, number_stats, shape

STRATEGIES = ("balanced", "hot", "cold", "overdue", "unpopular", "random")


def _normalize(w: list[float]) -> list[float]:
    mean = sum(w) / len(w)
    return [x / mean for x in w]


def weights(game: Game, draws: list[Draw], strategy: str, window: int = 100) -> list[float]:
    """Relative weight for each number 1..max_num (index 0 = number 1)."""
    if strategy == "random" or not draws:
        return [1.0] * game.max_num
    st = number_stats(game, draws, window)
    hot = _normalize([s.recent + 1 for s in st])
    overdue = _normalize([min(4.0, max(0.25, (s.gap + 1) / s.expected_gap)) for s in st])
    if strategy == "hot":
        return hot
    if strategy == "cold":
        return _normalize([1 / h for h in hot])
    if strategy == "overdue":
        return overdue
    if strategy == "balanced":
        return [(h + o) / 2 for h, o in zip(hot, overdue)]
    if strategy == "unpopular":
        # Birthday numbers (1-31) and lucky 7s are over-picked by players.
        w = [1.0] * game.max_num
        for n in range(1, game.max_num + 1):
            if n <= 31 and game.max_num > 31:
                w[n - 1] *= 0.6
            if n % 10 == 7:
                w[n - 1] *= 0.8
        return w
    raise ValueError(f"unknown strategy: {strategy}")


def _sample(game: Game, w: list[float], rng: random.Random) -> tuple[int, ...]:
    pool = list(range(1, game.max_num + 1))
    wts = list(w)
    picked = []
    for _ in range(game.pick):
        i = rng.choices(range(len(pool)), weights=wts)[0]
        picked.append(pool.pop(i))
        wts.pop(i)
    return tuple(sorted(picked))


def _unpopular_ok(combo: tuple[int, ...]) -> bool:
    """Reject shapes people love to pick: arithmetic progressions, same last digit clumps."""
    diffs = {b - a for a, b in zip(combo, combo[1:])}
    last_digits = [n % 10 for n in combo]
    return len(diffs) > 1 and max(last_digits.count(d) for d in set(last_digits)) <= 2


def spread(
    game: Game,
    draws: list[Draw],
    n: int,
    rng: random.Random | None = None,
    restarts: int | None = None,
) -> list[tuple[int, ...]]:
    """A set of n 'unpopular' tickets that spread numbers as evenly as possible.

    No shared numbers while they fit (Loto 6: 7 tickets, Loto 7: 5); beyond
    that every number is used about equally often. Spreading doesn't change
    the expected number of wins, but it makes the tickets less correlated,
    which raises the chance that at least one ticket wins something.
    """
    rng = rng or random.Random()
    base = weights(game, draws, "unpopular")
    filt = shape(draws) if draws else None
    restarts = restarts if restarts is not None else max(3, min(200, round(2000 / max(1, n))))
    best: list[tuple[int, ...]] = []
    best_score = None
    for _ in range(restarts):
        tickets: list[tuple[int, ...]] = []
        seen: set[tuple[int, ...]] = set()
        uses = [0] * (game.max_num + 1)
        for _ in range(n):
            # Penalize each number by how much more it's been used than the least-used one.
            least = min(uses[1:])
            w = [x * 0.02 ** (uses[i + 1] - least) for i, x in enumerate(base)]
            for _ in range(500):
                combo = _sample(game, w, rng)
                if combo in seen or (filt and not filt.fits(combo)) or not _unpopular_ok(combo):
                    continue
                break
            else:
                break
            tickets.append(combo)
            seen.add(combo)
            for x in combo:
                uses[x] += 1
        if len(tickets) < n:
            continue
        # Total shared numbers over all ticket pairs = sum over numbers of C(uses, 2).
        score = sum(u * (u - 1) // 2 for u in uses)
        if best_score is None or score < best_score:
            best, best_score = tickets, score
            if score == 0:
                break
    # Fully disjoint sets are already as good as it gets; past that, even
    # spreading is only a proxy, so optimize the prize chance directly.
    if len(best) > game.max_num // game.pick and filt:
        best = _maximize_coverage(game, best, filt, base, rng)
    return best


def _maximize_coverage(
    game: Game,
    start: list[tuple[int, ...]],
    filt: Shape,
    w: list[float],
    rng: random.Random,
    samples: int = 20_000,
    iters: int | None = None,
) -> list[tuple[int, ...]]:
    """Local search: on a fixed sample of simulated draws, swap single numbers in
    tickets whenever that makes more of the draws win at least one prize.

    Each sample is one bit of a big int, so a ticket's wins across all samples
    are computed with a handful of bitwise ops (bit-sliced match counters).
    """
    iters = iters or min(10_000, max(3000, 30 * len(start)))
    nums = list(range(1, game.max_num + 1))
    in_main = [0] * (game.max_num + 1)
    in_bonus = [0] * (game.max_num + 1)
    for s in range(samples):
        drawn = rng.sample(nums, game.pick + game.bonus)
        for x in drawn[:game.pick]:
            in_main[x] |= 1 << s
        for x in drawn[game.pick:]:
            in_bonus[x] |= 1 << s
    full = (1 << samples) - 1
    # Fewest main matches that win without / with a bonus match.
    need = min(m for m in range(game.pick + 1) if game.tier(m, 0))
    need_bonus = min(m for m in range(game.pick + 1) if game.tier(m, 1))

    def wins(t: tuple[int, ...]) -> int:
        c = [0, 0, 0]  # 3-bit per-sample match counter (pick <= 7)
        bonus = 0
        for x in t:
            carry = in_main[x]
            for i in range(3):
                c[i], carry = c[i] ^ carry, c[i] & carry
            bonus |= in_bonus[x]

        def at_least(k: int) -> int:
            out = 0
            for v in range(k, 8):
                m = full
                for i in range(3):
                    m &= c[i] if v >> i & 1 else ~c[i]
                out |= m
            return out

        return at_least(need) | (at_least(need_bonus) & bonus)

    tickets = list(start)
    seen = set(tickets)
    rows = [wins(t) for t in tickets]
    for _ in range(iters):
        i = rng.randrange(len(tickets))
        old = tickets[i]
        incoming = rng.choices(nums, weights=w)[0]
        if incoming in old:
            continue
        pos = rng.randrange(game.pick)
        cand = tuple(sorted(old[:pos] + (incoming,) + old[pos + 1:]))
        if cand in seen or not filt.fits(cand) or not _unpopular_ok(cand):
            continue
        new_row = wins(cand)
        others = 0
        for j, r in enumerate(rows):
            if j != i:
                others |= r
        # Accept ties so the search can drift across plateaus.
        if (others | new_row).bit_count() >= (others | rows[i]).bit_count():
            seen.discard(old)
            seen.add(cand)
            tickets[i], rows[i] = cand, new_row
    return tickets


def generate(
    game: Game,
    draws: list[Draw],
    strategy: str,
    n: int,
    rng: random.Random | None = None,
    window: int = 100,
    hist_shape: Shape | None = None,
) -> list[tuple[int, ...]]:
    rng = rng or random.Random()
    w = weights(game, draws, strategy, window)
    filt = None
    if strategy != "random" and draws:
        filt = hist_shape or shape(draws)
    tickets: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()
    attempts = 0
    while len(tickets) < n and attempts < n * 2000:
        attempts += 1
        combo = _sample(game, w, rng)
        if combo in seen:
            continue
        if filt and not filt.fits(combo):
            continue
        if strategy == "unpopular" and not _unpopular_ok(combo):
            continue
        seen.add(combo)
        tickets.append(combo)
    return tickets
