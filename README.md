# lotto

A dependency-free Python CLI for Japan's Mini Loto, Loto 6 and Loto 7. It downloads the full draw history, then reports hot, cold and overdue numbers. It can also generate tickets with several strategies, backtest those strategies against past draws, and check how a given ticket would have done.

```bash
pip install -e .
lotto update                      # download draw history
lotto stats loto6 --table
lotto predict loto7 -s unpopular -n 5
lotto backtest loto6 --last 200
lotto check loto6 3 11 19 24 31 40
```

Strategies: `balanced`, `hot`, `cold`, `overdue`, `unpopular` (avoids popular combos to reduce prize sharing) and `random`. Draws are random; this is a statistics exercise, not a way to win.
