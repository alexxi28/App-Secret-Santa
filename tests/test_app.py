import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app
import secret_santa as ss


class SendLinksTest(unittest.TestCase):
    def test_phone_gets_whatsapp_and_sms(self):
        links = app.send_links(ss.Participant("Ana", "+40722123456"), "subiect", "Salut & pa!")
        self.assertEqual(set(links), {"whatsapp", "sms"})
        self.assertTrue(links["whatsapp"].startswith("https://wa.me/40722123456?text="))
        text = links["whatsapp"].split("text=", 1)[1]
        self.assertEqual(urllib.parse.unquote(text), "Salut & pa!")

    def test_email_gets_mailto(self):
        links = app.send_links(ss.Participant("Ana", "ana@x.ro"), "Subiect", "Linia 1\nLinia 2")
        self.assertEqual(set(links), {"email"})
        query = urllib.parse.parse_qs(links["email"].split("?", 1)[1])
        self.assertEqual(query["body"], ["Linia 1\nLinia 2"])
        self.assertEqual(query["subject"], ["Subiect"])


class DrawTest(unittest.TestCase):
    def test_draw_returns_one_message_per_person_and_saves_list(self):
        payload = {
            "participanti": [
                {"nume": "Ana", "contact": "0722 123 456"},
                {"nume": "Mihai", "contact": "mihai@x.ro"},
                {"nume": "", "contact": ""},
                {"nume": "Ioana", "contact": "0733111222"},
            ],
            "buget": "100 lei",
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = app.draw(payload, Path(tmp))
            self.assertTrue(Path(result["fisier"]).exists())
        pairs = result["perechi"]
        self.assertEqual(sorted(p["nume"] for p in pairs), ["Ana", "Ioana", "Mihai"])
        self.assertEqual(sorted(p["primeste"] for p in pairs), ["Ana", "Ioana", "Mihai"])
        for p in pairs:
            self.assertNotEqual(p["nume"], p["primeste"])
            self.assertIn(p["primeste"], p["mesaj"])
            self.assertIn("100 lei", p["mesaj"])

    def test_draw_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            app.draw({"participanti": [{"nume": "Ana", "contact": "0722123456"}]}, Path("."))


if __name__ == "__main__":
    unittest.main()
