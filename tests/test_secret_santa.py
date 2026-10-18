import csv
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import secret_santa as ss


def people(n):
    return [ss.Participant(f"P{i}", f"p{i}@example.com") for i in range(n)]


class DrawPairsTest(unittest.TestCase):
    def test_everyone_gives_and_receives_once_never_self(self):
        for n in range(3, 15):
            for seed in range(30):
                pairs = ss.draw_pairs(people(n), random.Random(seed))
                givers = [g.name for g, _ in pairs]
                receivers = [r.name for _, r in pairs]
                self.assertEqual(sorted(givers), sorted(p.name for p in people(n)))
                self.assertEqual(sorted(receivers), sorted(givers))
                self.assertTrue(all(g != r for g, r in pairs))
                gives_to = {g.name: r.name for g, r in pairs}
                self.assertTrue(all(gives_to[gives_to[g]] != g for g in gives_to))


class ContactTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(ss.normalize_contact(" Ana@Example.com "), "ana@example.com")
        self.assertEqual(ss.normalize_contact("0722 123 456"), "+40722123456")
        self.assertEqual(ss.normalize_contact("0040-722-123-456"), "+40722123456")
        self.assertEqual(ss.normalize_contact("+40733111222"), "+40733111222")
        for bad in ["ana@", "abc", "12", ""]:
            with self.assertRaises(ValueError):
                ss.normalize_contact(bad)

    def test_validate_rejects_duplicates_and_too_few(self):
        with self.assertRaises(ValueError):
            ss.validate_participants(people(2))
        dup = people(3) + [ss.Participant("P0", "x@example.com")]
        with self.assertRaises(ValueError):
            ss.validate_participants(dup)
        dup = people(3) + [ss.Participant("Nou", "P1@example.com")]
        with self.assertRaises(ValueError):
            ss.validate_participants(dup)


class EndToEndTest(unittest.TestCase):
    def test_dry_run_writes_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "p.csv"
            src.write_text("nume;contact\nAna;ana@example.com\nMihai;0722123456\nIoana;ioana@example.com\n",
                           encoding="utf-8")
            out = Path(tmp) / "rez"
            code = ss.main([str(src), "--buget", "100 lei", "--rezultate", str(out)])
            self.assertEqual(code, 0)
            files = list(out.glob("perechi_*.csv"))
            self.assertEqual(len(files), 1)
            with files[0].open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertIn(row["primeste_cadou"], row["mesaj"])
                self.assertIn("100 lei", row["mesaj"])


if __name__ == "__main__":
    unittest.main()
