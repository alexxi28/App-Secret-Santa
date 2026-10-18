#!/usr/bin/env python3
"""Site local pentru Secret Santa.

Pornesti cu `python app.py`, se deschide browserul, introduci numele si
telefonul/emailul fiecaruia, apesi „Trage la sorti” si apoi trimiti fiecaruia
mesajul cu un click: WhatsApp, SMS sau email, din aplicatiile tale. Nu ai nevoie
de conturi, servicii platite sau setari speciale.

Lista completa cu perechile se salveaza local in folderul `rezultate/`.
"""

import argparse
import json
import sys
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import secret_santa as ss

WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_BODY = 1_000_000


def send_links(giver: ss.Participant, subject: str, body: str) -> dict:
    """Linkuri care deschid aplicatia potrivita cu mesajul deja scris."""
    if giver.is_email:
        query = urllib.parse.urlencode({"subject": subject, "body": body},
                                       quote_via=urllib.parse.quote)
        return {"email": f"mailto:{giver.contact}?{query}"}
    text = urllib.parse.quote(body)
    return {
        "whatsapp": f"https://wa.me/{giver.contact.lstrip('+')}?text={text}",
        # `?&body=` merge si pe Android si pe iPhone
        "sms": f"sms:{giver.contact}?&body={text}",
    }


def draw(payload: dict, results_dir: Path) -> dict:
    raw = [ss.Participant(str(p.get("nume", "")).strip(), str(p.get("contact", "")).strip())
           for p in payload.get("participanti", [])]
    raw = [p for p in raw if p.name or p.contact]
    participants = ss.validate_participants(raw)
    budget = str(payload.get("buget") or "").strip() or None
    event_date = str(payload.get("data") or "").strip() or None
    subject = "Secret Santa - perechea ta"

    pairs = ss.draw_pairs(participants)
    messages = [ss.build_message(g, r, budget, event_date) for g, r in pairs]
    path = ss.save_results(pairs, messages, ["de trimis din site"] * len(pairs), results_dir)

    return {
        "fisier": str(path),
        "perechi": [
            {
                "nume": giver.name,
                "contact": giver.contact,
                "primeste": receiver.name,
                "mesaj": body,
                "linkuri": send_links(giver, subject, body),
            }
            for (giver, receiver), body in zip(pairs, messages)
        ],
    }


class Handler(BaseHTTPRequestHandler):
    results_dir = Path("rezultate")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(HTTPStatus.OK, (WEB_DIR / "index.html").read_bytes(),
                       "text/html; charset=utf-8")
        else:
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/trage":
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY:
                raise ValueError("Cererea este prea mare.")
            payload = json.loads(self.rfile.read(length) or b"{}")
            result, status = draw(payload, self.results_dir), HTTPStatus.OK
        except (ValueError, json.JSONDecodeError) as e:
            result, status = {"eroare": str(e)}, HTTPStatus.BAD_REQUEST
        self._send(status, json.dumps(result, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def _send(self, status, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # nu afisam cererile in terminal


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Site local pentru Secret Santa")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1",
                        help="pune 0.0.0.0 ca sa deschizi site-ul si de pe telefon (aceeasi retea Wi-Fi)")
    parser.add_argument("--rezultate", type=Path, default=Path("rezultate"),
                        help="folderul unde se salveaza lista cu perechi")
    parser.add_argument("--fara-browser", action="store_true", help="nu deschide browserul automat")
    args = parser.parse_args(argv)

    Handler.results_dir = args.rezultate
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as e:
        print(f"Nu pot porni serverul pe portul {args.port}: {e}", file=sys.stderr)
        return 1

    url = f"http://localhost:{args.port}"
    print(f"Secret Santa ruleaza la {url}  (Ctrl+C ca sa opresti)")
    if args.host == "0.0.0.0":
        print("Pe telefon deschide http://<IP-ul calculatorului>:" f"{args.port}")
    if not args.fara_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nOprit.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
