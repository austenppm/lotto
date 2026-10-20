import random
import unittest
from datetime import date

from lotto.data import Draw, parse
from lotto.games import GAMES
from lotto.predict import STRATEGIES, generate, spread
from lotto.stats import max_run


def fake_draws(game, n=120, seed=1):
    rng = random.Random(seed)
    return [
        Draw(i + 1, date(2020, 1, 1), tuple(sorted(rng.sample(range(1, game.max_num + 1), game.pick))),
             (), (0,) * game.tiers, (0,) * game.tiers, 0)
        for i in range(n)
    ]


class TierTest(unittest.TestCase):
    def test_loto6(self):
        g = GAMES["loto6"]
        self.assertEqual(g.tier(6, 0), 1)
        self.assertEqual(g.tier(5, 1), 2)
        self.assertEqual(g.tier(5, 0), 3)
        self.assertEqual(g.tier(3, 1), 5)
        self.assertIsNone(g.tier(2, 1))

    def test_loto7(self):
        g = GAMES["loto7"]
        self.assertEqual(g.tier(6, 2), 2)
        self.assertEqual(g.tier(3, 1), 6)
        self.assertIsNone(g.tier(3, 0))

    def test_mini(self):
        g = GAMES["mini"]
        self.assertEqual(g.tier(4, 1), 2)
        self.assertEqual(g.tier(3, 0), 4)
        self.assertIsNone(g.tier(2, 1))

    def test_jackpot_odds(self):
        self.assertAlmostEqual(1 / GAMES["loto6"].tier_odds()[0], 6_096_454)
        self.assertAlmostEqual(1 / GAMES["loto7"].tier_odds()[0], 10_295_472)
        self.assertAlmostEqual(1 / GAMES["mini"].tier_odds()[0], 169_911)


class GenerateTest(unittest.TestCase):
    def test_all_strategies_valid(self):
        for g in GAMES.values():
            draws = fake_draws(g)
            for s in STRATEGIES:
                tickets = generate(g, draws, s, 5, random.Random(0))
                self.assertEqual(len(tickets), 5, (g.key, s))
                for t in tickets:
                    self.assertEqual(len(set(t)), g.pick)
                    self.assertTrue(all(1 <= n <= g.max_num for n in t))

    def test_spread_disjoint(self):
        for key in ("loto6", "loto7"):
            g = GAMES[key]
            tickets = spread(g, fake_draws(g), 5, random.Random(0))
            self.assertEqual(len(tickets), 5)
            used = [n for t in tickets for n in t]
            self.assertEqual(len(used), len(set(used)), key)

    def test_max_run(self):
        self.assertEqual(max_run((1, 2, 3, 10, 11)), 3)
        self.assertEqual(max_run((1, 5, 9)), 1)


class ParseTest(unittest.TestCase):
    def test_loto7_row(self):
        text = ("header\n"
                "1,2013/04/05,7,10,12,17,23,28,34,3,15,1,24,168,8254,115022,189593,"
                "301716500,4144600,828900,9800,1700,900,0\n")
        (d,) = parse(GAMES["loto7"], text)
        self.assertEqual(d.numbers, (7, 10, 12, 17, 23, 28, 34))
        self.assertEqual(d.bonus, (3, 15))
        self.assertEqual(d.prizes[0], 301716500)


if __name__ == "__main__":
    unittest.main()
