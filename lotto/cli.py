"""Command-line interface: python -m lotto <command> <game> ..."""

from __future__ import annotations

import argparse
import random
from math import comb

from . import backtest, data
from .games import GAMES, Game
from .predict import STRATEGIES, generate, spread
from .stats import number_stats, shape


def _fmt(nums) -> str:
    return " ".join(f"{n:2d}" for n in nums)


def _games(key: str) -> list[Game]:
    return list(GAMES.values()) if key == "all" else [GAMES[key]]


def cmd_update(args) -> None:
    for g in _games(args.game):
        draws = data.load(g, refresh=True)
        last = draws[-1]
        print(f"{g.name:9s} {len(draws):5d} draws, latest #{last.no} {last.date}  {_fmt(last.numbers)}")


def cmd_stats(args) -> None:
    for g in _games(args.game):
        draws = data.load(g)
        st = number_stats(g, draws, args.window)
        sh = shape(draws)
        print(f"\n=== {g.name}: {g.pick} of 1-{g.max_num}, {len(draws)} draws "
              f"(#{draws[0].no} {draws[0].date} .. #{draws[-1].no} {draws[-1].date}) ===")
        print(f"Last draw: {_fmt(draws[-1].numbers)}  bonus {_fmt(draws[-1].bonus)}")
        print(f"Typical shape: sum {sh.sum_lo}-{sh.sum_hi}, odd count {sorted(sh.odd_ok)}, "
              f"longest consecutive run <= {sh.run_max}")
        exp_recent = min(args.window, len(draws)) * g.pick / g.max_num
        by_recent = sorted(st, key=lambda s: -s.recent)
        by_gap = sorted(st, key=lambda s: -s.gap)
        print(f"Hot  (last {args.window}, expected ~{exp_recent:.1f}): "
              + ", ".join(f"{s.number}({s.recent})" for s in by_recent[:8]))
        print(f"Cold (last {args.window}): " + ", ".join(f"{s.number}({s.recent})" for s in by_recent[-8:][::-1]))
        print(f"Overdue (draws since seen, expected ~{st[0].expected_gap:.1f}): "
              + ", ".join(f"{s.number}({s.gap})" for s in by_gap[:8]))
        if args.table:
            print("\n num  total  recent  gap")
            for s in st:
                print(f" {s.number:3d}  {s.total:5d}  {s.recent:6d}  {s.gap:3d}")
        print("Odds per ticket: " + ", ".join(
            f"{i + 1}等 1 in {1 / p:,.0f}" for i, p in enumerate(g.tier_odds())))


def cmd_predict(args) -> None:
    g = GAMES[args.game]
    draws = data.load(g)
    rng = random.Random(args.seed)
    strategies = list(STRATEGIES) if args.strategy == "all" else [args.strategy]
    print(f"{g.name} picks based on {len(draws)} draws (next draw after #{draws[-1].no} {draws[-1].date})")
    for s in strategies:
        print(f"\n[{s}]")
        for t in generate(g, draws, s, args.n, rng, window=args.window):
            print(f"  {_fmt(t)}   sum={sum(t)}")
    print(f"\nEach ticket: 1 in {g.combinations:,} for the jackpot, whichever strategy you use.")


DRAW_DAYS = {"mini": "Tue", "loto6": "Mon & Thu", "loto7": "Fri"}


def cmd_plan(args) -> None:
    rng = random.Random(args.seed)
    weekly = 0
    for key, n in (("mini", args.mini), ("loto6", args.loto6), ("loto7", args.loto7)):
        if not n:
            continue
        g = GAMES[key]
        draws = data.load(g)
        tickets = spread(g, draws, n, rng)
        rand_sets = [generate(g, draws, "random", n, rng) for _ in range(20)]
        p = backtest.prize_chance(g, tickets, args.trials)
        p_rand = sum(backtest.prize_chance(g, t, args.trials // 20) for t in rand_sets) / len(rand_sets)
        cost = n * g.price
        weekly += cost * (2 if key == "loto6" and args.both else 1)
        print(f"\n=== {g.name} — next draw after #{draws[-1].no} {draws[-1].date} ({DRAW_DAYS[key]}) ===")
        for t in tickets:
            print(f"  {_fmt(t)}")
        print(f"  ¥{cost:,} | any prize: {p:.1%} (vs {p_rand:.1%} for {n} random tickets)"
              f" | jackpot: 1 in {g.combinations // n:,}")
    if weekly:
        yearly = weekly * 52
        print(f"\nSpend ¥{weekly:,}/week = ¥{yearly:,}/year; expect ~¥{yearly // 2:,} back on average "
              f"(~50% payout rate).")


def cmd_backtest(args) -> None:
    g = GAMES[args.game]
    draws = data.load(g)
    strategies = list(STRATEGIES) if args.strategy == "all" else [args.strategy, "random"]
    results = backtest.run(g, draws, strategies, args.last, args.per_draw, args.seed)
    n_draws = min(args.last, len(draws) - 50)
    print(f"{g.name}: {n_draws} draws x {args.per_draw} tickets/strategy, "
          f"¥{g.price}/ticket, real payouts from each draw")
    print(f"Expected avg matches by pure chance: {g.pick * g.pick / g.max_num:.3f}\n")
    tiers = "  ".join(f"{i + 1}等" for i in range(g.tiers))
    print(f"{'strategy':10s} {'avg hit':>7s}  {tiers}  {'spent':>10s} {'won':>10s} {'ROI':>7s}")
    for r in results:
        counts = "  ".join(f"{c:3d}" for c in r.tier_counts)
        print(f"{r.strategy:10s} {r.avg_hits:7.3f}  {counts}  ¥{r.spent:>9,} ¥{r.won:>9,} {r.roi:+7.1%}")
    print("\nDifferences between strategies are noise; all lose ~50% long-run (the payout rate).")


def cmd_check(args) -> None:
    g = GAMES[args.game]
    ticket = tuple(sorted(set(args.numbers)))
    if len(ticket) != g.pick or not all(1 <= n <= g.max_num for n in ticket):
        raise SystemExit(f"{g.name} needs {g.pick} distinct numbers between 1 and {g.max_num}")
    draws = data.load(g)
    wins: list[tuple] = []
    best = 0
    for d in draws:
        main, tier = backtest.score(g, ticket, d)
        best = max(best, main)
        if tier:
            wins.append((d, main, tier))
    print(f"{_fmt(ticket)} against {len(draws)} {g.name} draws: best match {best}, {len(wins)} prize(s)")
    for d, main, tier in wins[-args.show:]:
        print(f"  #{d.no} {d.date}  {_fmt(d.numbers)}  -> {main} hit, {tier}等 ¥{d.prizes[tier - 1]:,}")
    won = sum(d.prizes[t - 1] for d, _, t in wins)
    print(f"Would have spent ¥{len(draws) * g.price:,} and won ¥{won:,}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="lotto", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    game_choices = list(GAMES)

    s = sub.add_parser("update", help="download latest draw history")
    s.add_argument("game", nargs="?", default="all", choices=game_choices + ["all"])
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("stats", help="hot / cold / overdue numbers and odds")
    s.add_argument("game", nargs="?", default="all", choices=game_choices + ["all"])
    s.add_argument("--window", type=int, default=100, help="recent draws counted as 'hot' (default 100)")
    s.add_argument("--table", action="store_true", help="print per-number table")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("predict", help="generate tickets")
    s.add_argument("game", choices=game_choices)
    s.add_argument("-s", "--strategy", default="balanced", choices=list(STRATEGIES) + ["all"])
    s.add_argument("-n", type=int, default=5, help="tickets per strategy (default 5)")
    s.add_argument("--window", type=int, default=100)
    s.add_argument("--seed", type=int, help="for reproducible picks")
    s.set_defaults(func=cmd_predict)

    s = sub.add_parser("plan", help="this week's tickets: unpopular numbers, spread across tickets")
    s.add_argument("--loto6", type=int, default=5, help="Loto 6 tickets per draw (default 5)")
    s.add_argument("--loto7", type=int, default=5, help="Loto 7 tickets per draw (default 5)")
    s.add_argument("--mini", type=int, default=0, help="Mini Loto tickets per draw (default 0)")
    s.add_argument("--both", action="store_true", help="play both Loto 6 draws each week (Mon & Thu)")
    s.add_argument("--trials", type=int, default=100_000, help="simulated draws for prize odds")
    s.add_argument("--seed", type=int)
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("backtest", help="test strategies against past draws")
    s.add_argument("game", choices=game_choices)
    s.add_argument("-s", "--strategy", default="all", choices=list(STRATEGIES) + ["all"])
    s.add_argument("--last", type=int, default=200, help="number of past draws to test (default 200)")
    s.add_argument("--per-draw", type=int, default=5)
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(func=cmd_backtest)

    s = sub.add_parser("check", help="how a ticket would have done historically")
    s.add_argument("game", choices=game_choices)
    s.add_argument("numbers", type=int, nargs="+")
    s.add_argument("--show", type=int, default=10, help="recent prizes to list")
    s.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    args.func(args)
    return 0
