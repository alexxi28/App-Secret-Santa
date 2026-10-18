# 🎅 Secret Santa

Aplicație Python care trage la sorți perechile pentru Secret Santa și trimite
**fiecărui participant, în privat**, un mesaj cu persoana căreia îi face cadou.
Organizatorul primește local lista completă cu toate perechile.

Nu are nevoie de biblioteci externe, doar Python 3.10+.

## Varianta simplă: site-ul (gratis, fără conturi)

```bash
python app.py
```

Se deschide în browser o pagină în care:

1. **Bagi participanții**: nume + telefon sau email. Cu `Enter` treci la următorul rând.
   Dacă ai deja lista, o poți lipi dintr-o dată (`Ana, 0722 123 456` pe fiecare rând).
2. Completezi opțional bugetul și data, apoi apeși **🎲 Trage la sorți**.
3. Pentru fiecare persoană apeși **WhatsApp**, **SMS** sau **Email**. Se deschide
   aplicația ta cu mesajul deja scris, iar tu doar apeși „Trimite”. Bifa „trimis” se pune
   singură, ca să știi la cine ai rămas.

Mesajele pleacă din WhatsApp-ul, telefonul sau emailul tău, deci **nu plătești nimic și
nu trebuie să schimbi nimic în contul Google**.

Lista completă cu perechile se salvează automat pe calculator în `rezultate/`. Pe
pagină e ascunsă (ca să nu o vezi din greșeală dacă participi și tu), dar o poți afișa
sau descărca oricând. Dacă închizi pagina, la redeschidere găsești tot acolo.

**De pe telefon:** butonul SMS funcționează doar pe telefon. Pornește site-ul cu
`python app.py --host 0.0.0.0`, apoi deschide pe telefon `http://<IP-ul calculatorului>:8000`
(telefonul și calculatorul trebuie să fie pe același Wi-Fi). WhatsApp merge și de pe
calculator, prin WhatsApp Web/Desktop.

## Cum funcționează tragerea

Participanții sunt amestecați aleatoriu și așezați „în cerc”: fiecare îi face
cadou următorului. Astfel:
- nimeni nu se trage pe sine;
- fiecare face exact un cadou și primește exact unul;
- nu există perechi reciproce (A → B și B → A), deci nimeni nu poate ghici cine l-a tras.

## Varianta din linia de comandă (trimitere automată)

Dacă vrei ca mesajele să plece automat, fără click-uri, există și `secret_santa.py`.
Acesta are nevoie de un cont de email configurat (de ex. o parolă de aplicație Gmail)
și, pentru SMS, de un cont Twilio (cu plată).

### 1. Lista de participanți

Creează `participanti.csv` (vezi `participanti.example.csv`), cu coloanele `nume` și `contact`.
Contactul poate fi email sau număr de telefon (separator `,` sau `;`):

```csv
nume,contact
Ana,ana@example.com
Mihai,0722 123 456
Ioana,ioana@example.com
```

Numerele care încep cu `0` sunt considerate românești (`0722...` → `+40722...`).

Fără fișier CSV, aplicația îți cere numele și contactele de la tastatură.

### 2. Configurare trimitere

Copiază `.env.example` în `.env` și completează:

- **Email** – pentru Gmail activează verificarea în 2 pași și creează o
  [parolă de aplicație](https://myaccount.google.com/apppasswords); pune-o în `SMTP_PASSWORD`.
- **SMS** – doar dacă ai participanți cu număr de telefon. Se folosește
  [Twilio](https://www.twilio.com) (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`).

`.env`, `participanti.csv` și `rezultate/` sunt în `.gitignore`, deci nu ajung pe GitHub.

### 3. Rulare

```bash
# simulare: trage perechile și salvează lista, dar NU trimite nimic
python secret_santa.py participanti.csv --buget "100 lei" --data "24 decembrie"

# trimite efectiv mesajele
python secret_santa.py participanti.csv --buget "100 lei" --data "24 decembrie" --trimite
```

În terminal nu se afișează perechile (ca să nu le vezi din greșeală dacă vrei să participi și tu).
Lista completă se salvează în `rezultate/perechi_<data>_<ora>.csv`, cu coloanele:
cine oferă cadoul, contactul lui, cui îi face cadou, statusul trimiterii și mesajul trimis.

Dacă trimiterea eșuează pentru cineva, ceilalți primesc mesajul în continuare,
iar eroarea apare în coloana `status` – poți să-i trimiți manual mesajul din fișier.

Mesajul arată așa:

```
Salut, Ana!

La Secret Santa tu faci cadou pentru: Ioana
Buget cadou: 100 lei
Schimbul de cadouri: 24 decembrie

Pastreaza secretul! Craciun fericit!
```

## Teste

```bash
python -m unittest discover -s tests
```
