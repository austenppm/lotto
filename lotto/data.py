"""Downloading and parsing historical draw results."""

from __future__ import annotations

import csv
import io
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .games import Game

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Draw:
    no: int
    date: date
    numbers: tuple[int, ...]
    bonus: tuple[int, ...]
    winners: tuple[int, ...]   # winning tickets per tier
    prizes: tuple[int, ...]    # yen paid per winning ticket per tier (0 if no winner)
    carryover: int


def csv_path(game: Game) -> Path:
    return DATA_DIR / f"{game.key}.csv"


def download(game: Game) -> Path:
    req = urllib.request.Request(game.url, headers={"User-Agent": "Mozilla/5.0 lotto-cli"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = csv_path(game)
    path.write_text(raw.decode("shift_jis", errors="replace"), encoding="utf-8")
    return path


def _int(s: str) -> int:
    s = s.strip().replace(",", "")
    return int(s) if s else 0


def parse(game: Game, text: str) -> list[Draw]:
    draws = []
    rows = csv.reader(io.StringIO(text))
    next(rows, None)  # header
    for row in rows:
        try:
            i = 2
            nums = tuple(sorted(_int(x) for x in row[i:i + game.pick])); i += game.pick
            bonus = tuple(_int(x) for x in row[i:i + game.bonus]); i += game.bonus
            winners = tuple(_int(x) for x in row[i:i + game.tiers]); i += game.tiers
            prizes = tuple(_int(x) for x in row[i:i + game.tiers]); i += game.tiers
            carry = _int(row[i]) if len(row) > i else 0
            d = datetime.strptime(row[1].strip(), "%Y/%m/%d").date()
            draws.append(Draw(_int(row[0]), d, nums, bonus, winners, prizes, carry))
        except (ValueError, IndexError):
            continue  # skip malformed rows
    draws.sort(key=lambda d: d.no)
    return draws


def load(game: Game, refresh: bool = False) -> list[Draw]:
    path = csv_path(game)
    if refresh or not path.exists():
        download(game)
    return parse(game, path.read_text(encoding="utf-8"))
