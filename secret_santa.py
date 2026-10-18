#!/usr/bin/env python3
"""Secret Santa: trage la sorti perechile si anunta fiecare participant
in privat (email sau SMS) pe cine are de facut cadou.

Organizatorul primeste local lista completa a perechilor in folderul `rezultate/`.

Exemple:
    python secret_santa.py participanti.csv                # simulare, nu trimite nimic
    python secret_santa.py participanti.csv --trimite      # trimite email/SMS
    python secret_santa.py                                 # introduci participantii de la tastatura
"""

import argparse
import base64
import csv
import json
import os
import random
import re
import smtplib
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+\d{8,15}$")


@dataclass
class Participant:
    name: str
    contact: str

    @property
    def is_email(self) -> bool:
        return "@" in self.contact


# ---------------------------------------------------------------------------
# Citire si validare participanti
# ---------------------------------------------------------------------------

def normalize_contact(raw: str) -> str:
    """Returneaza emailul sau numarul de telefon in format international (+40...)."""
    contact = raw.strip()
    if "@" in contact:
        if not EMAIL_RE.match(contact):
            raise ValueError(f"Email invalid: {raw!r}")
        return contact.lower()

    phone = re.sub(r"[\s\-().]", "", contact)
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    elif phone.startswith("0"):
        phone = "+40" + phone[1:]  # numar romanesc, ex. 0722... -> +40722...
    if not PHONE_RE.match(phone):
        raise ValueError(f"Numar de telefon invalid: {raw!r}")
    return phone


def load_participants_csv(path: Path) -> list[Participant]:
    """Citeste un CSV cu coloanele `nume` si `contact` (email sau telefon)."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        reader = csv.DictReader(f, dialect=dialect)
        fields = {(h or "").strip().lower(): h for h in reader.fieldnames or []}
        if "nume" not in fields or "contact" not in fields:
            raise ValueError("CSV-ul trebuie sa aiba coloanele: nume, contact")
        participants = []
        for row in reader:
            name = (row[fields["nume"]] or "").strip()
            contact = (row[fields["contact"]] or "").strip()
            if not name and not contact:
                continue
            participants.append(Participant(name, contact))
    return participants


def read_participants_interactive() -> list[Participant]:
    print("Introdu participantii (lasa numele gol ca sa termini).")
    participants = []
    while True:
        name = input(f"\nNume participant #{len(participants) + 1}: ").strip()
        if not name:
            break
        while True:
            contact = input(f"Email sau telefon pentru {name}: ").strip()
            try:
                normalize_contact(contact)
                break
            except ValueError as e:
                print(f"  {e}. Incearca din nou.")
        participants.append(Participant(name, contact))
    return participants


def validate_participants(participants: list[Participant]) -> list[Participant]:
    if len(participants) < 3:
        raise ValueError("Ai nevoie de cel putin 3 participanti ca sa ramana secret.")
    cleaned, seen_names, seen_contacts = [], set(), set()
    for p in participants:
        if not p.name:
            raise ValueError(f"Lipseste numele pentru contactul {p.contact!r}")
        contact = normalize_contact(p.contact)
        if p.name.lower() in seen_names:
            raise ValueError(f"Nume duplicat: {p.name!r}")
        if contact in seen_contacts:
            raise ValueError(f"Contact duplicat: {contact!r}")
        seen_names.add(p.name.lower())
        seen_contacts.add(contact)
        cleaned.append(Participant(p.name, contact))
    return cleaned


# ---------------------------------------------------------------------------
# Tragerea la sorti
# ---------------------------------------------------------------------------

def draw_pairs(participants: list[Participant], rng: random.Random | None = None):
    """Amesteca participantii si ii aseaza intr-un cerc: fiecare ii face cadou
    urmatorului. Nimeni nu se trage pe sine si nu exista perechi reciproce
    (A->B si B->A), deci nimeni nu poate ghici cine il are."""
    rng = rng or random.SystemRandom()
    order = participants[:]
    rng.shuffle(order)
    return [(order[i], order[(i + 1) % len(order)]) for i in range(len(order))]


# ---------------------------------------------------------------------------
# Mesaje si trimitere
# ---------------------------------------------------------------------------

def build_message(giver: Participant, receiver: Participant, budget: str | None,
                  event_date: str | None) -> str:
    lines = [
        f"Salut, {giver.name}!",
        "",
        f"La Secret Santa tu faci cadou pentru: {receiver.name}",
    ]
    if budget:
        lines.append(f"Buget cadou: {budget}")
    if event_date:
        lines.append(f"Schimbul de cadouri: {event_date}")
    lines += ["", "Pastreaza secretul! Craciun fericit!"]
    return "\n".join(lines)


def load_dotenv(path: Path = Path(".env")) -> None:
    """Incarca variabilele din .env (fara dependinte externe)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class EmailSender:
    def __init__(self):
        self.host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.user = os.environ.get("SMTP_USER")
        self.password = os.environ.get("SMTP_PASSWORD")
        self.sender = os.environ.get("SMTP_FROM") or self.user
        self._server = None

    def check_config(self):
        if not (self.user and self.password):
            raise RuntimeError("Lipsesc SMTP_USER / SMTP_PASSWORD in .env")

    def send(self, to: str, subject: str, body: str):
        if self._server is None:
            context = ssl.create_default_context()
            if self.port == 465:
                self._server = smtplib.SMTP_SSL(self.host, self.port, context=context)
            else:
                self._server = smtplib.SMTP(self.host, self.port)
                self._server.starttls(context=context)
            self._server.login(self.user, self.password)
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = to
        msg.set_content(body)
        self._server.send_message(msg)

    def close(self):
        if self._server is not None:
            self._server.quit()


class SmsSender:
    """Trimite SMS prin API-ul Twilio (https://www.twilio.com)."""

    def __init__(self):
        self.sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self.token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.sender = os.environ.get("TWILIO_FROM")

    def check_config(self):
        if not (self.sid and self.token and self.sender):
            raise RuntimeError(
                "Lipsesc TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM in .env")

    def send(self, to: str, body: str):
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json"
        data = urllib.parse.urlencode({"To": to, "From": self.sender, "Body": body}).encode()
        auth = base64.b64encode(f"{self.sid}:{self.token}".encode()).decode()
        req = urllib.request.Request(url, data=data, headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                json.load(resp)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise RuntimeError(f"Twilio HTTP {e.code}: {detail}") from e


def send_all(pairs, messages, subject: str) -> list[str]:
    """Trimite fiecare mesaj si intoarce statusul pentru fiecare pereche."""
    email = EmailSender()
    sms = SmsSender()
    if any(g.is_email for g, _ in pairs):
        email.check_config()
    if any(not g.is_email for g, _ in pairs):
        sms.check_config()

    statuses = []
    try:
        for (giver, _), body in zip(pairs, messages):
            try:
                if giver.is_email:
                    email.send(giver.contact, subject, body)
                else:
                    sms.send(giver.contact, body)
                statuses.append("trimis")
                print(f"  ✔ {giver.name} ({giver.contact})")
            except Exception as e:  # continua cu ceilalti participanti
                statuses.append(f"EROARE: {e}")
                print(f"  ✘ {giver.name} ({giver.contact}): {e}")
    finally:
        email.close()
    return statuses


# ---------------------------------------------------------------------------
# Salvare locala pentru organizator
# ---------------------------------------------------------------------------

def save_results(pairs, messages, statuses, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"perechi_{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ofera_cadou", "contact", "primeste_cadou", "status", "mesaj"])
        for (giver, receiver), body, status in zip(pairs, messages, statuses):
            writer.writerow([giver.name, giver.contact, receiver.name, status, body])
    return csv_path


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Secret Santa - tragere la sorti si notificare")
    parser.add_argument("csv", nargs="?", type=Path,
                        help="fisier CSV cu coloanele nume,contact (fara el se citesc de la tastatura)")
    parser.add_argument("--trimite", action="store_true",
                        help="trimite efectiv mesajele (implicit e doar simulare)")
    parser.add_argument("--buget", help='ex. "100 lei"')
    parser.add_argument("--data", help='data schimbului de cadouri, ex. "24 decembrie"')
    parser.add_argument("--subiect", default="🎅 Secret Santa - perechea ta",
                        help="subiectul emailului")
    parser.add_argument("--rezultate", type=Path, default=Path("rezultate"),
                        help="folderul unde se salveaza lista cu perechi")
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        raw = load_participants_csv(args.csv) if args.csv else read_participants_interactive()
        participants = validate_participants(raw)
    except (OSError, ValueError, csv.Error) as e:
        print(f"Eroare: {e}", file=sys.stderr)
        return 1

    pairs = draw_pairs(participants)
    messages = [build_message(g, r, args.buget, args.data) for g, r in pairs]

    print(f"\nAu fost trase la sorti {len(pairs)} perechi.")
    if args.trimite:
        print("Trimit mesajele...")
        try:
            statuses = send_all(pairs, messages, args.subiect)
        except RuntimeError as e:
            print(f"Eroare de configurare: {e}", file=sys.stderr)
            return 1
    else:
        statuses = ["simulare (netrimis)"] * len(pairs)
        print("Mod SIMULARE: nu s-a trimis nimic. Foloseste --trimite pentru trimitere.")
        for giver, _ in pairs:
            canal = "email" if giver.is_email else "SMS"
            print(f"  -> {giver.name}: {canal} la {giver.contact}")

    path = save_results(pairs, messages, statuses, args.rezultate)
    print(f"\nLista completa cu perechile a fost salvata in: {path}")
    return 0 if all(not s.startswith("EROARE") for s in statuses) else 2


if __name__ == "__main__":
    sys.exit(main())
