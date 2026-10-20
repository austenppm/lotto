"""Game definitions and prize-tier rules."""

from __future__ import annotations

from dataclasses import dataclass
from math import comb


@dataclass(frozen=True)
class Game:
    key: str
    name: str
    pick: int       # main numbers drawn
    max_num: int    # numbers range 1..max_num
    bonus: int      # bonus numbers drawn
    price: int      # yen per ticket
    tiers: int      # number of prize tiers
    url: str

    @property
    def combinations(self) -> int:
        return comb(self.max_num, self.pick)

    def tier(self, main_hits: int, bonus_hits: int) -> int | None:
        """Prize tier (1 = jackpot) for a ticket, or None if it wins nothing."""
        p, b = self.pick, bonus_hits > 0
        if main_hits == p:
            return 1
        if main_hits == p - 1:
            return 2 if b else 3
        if self.key == "mini":
            return 4 if main_hits == 3 else None
        if self.key == "loto6":
            return {4: 4, 3: 5}.get(main_hits)
        # loto7
        if main_hits == 5:
            return 4
        if main_hits == 4:
            return 5
        if main_hits == 3 and b:
            return 6
        return None

    def tier_odds(self) -> list[float]:
        """Exact probability of each prize tier for a single ticket."""
        n, k, nb = self.max_num, self.pick, self.bonus
        total = comb(n, k)
        losers = n - k - nb
        probs = [0.0] * self.tiers
        for m in range(k + 1):
            for b in range(min(nb, k - m) + 1):
                ways = comb(k, m) * comb(nb, b) * comb(losers, k - m - b)
                t = self.tier(m, b)
                if t:
                    probs[t - 1] += ways / total
        return probs


GAMES: dict[str, Game] = {
    "mini": Game("mini", "Mini Loto", 5, 31, 1, 200, 4, "https://miniloto.thekyo.jp/data/miniloto.csv"),
    "loto6": Game("loto6", "Loto 6", 6, 43, 1, 200, 5, "https://loto6.thekyo.jp/data/loto6.csv"),
    "loto7": Game("loto7", "Loto 7", 7, 37, 2, 300, 6, "https://loto7.thekyo.jp/data/loto7.csv"),
}
