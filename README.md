<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/banner-dark.png">
  <img src="images/banner.png" alt="Herald — read the headers" width="100%">
</picture>

<br>

**Read the headers.** An offline reader for e-mail headers that reconstructs the
path a message took, reports the authentication the receiving server recorded,
flags the tells of a forgery, and grades what it finds — without ever claiming a
message is safe.

<br>

![Python](https://img.shields.io/badge/Python-3.10%2B-7A5D18?style=flat-square)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-7A5D18?style=flat-square)
![Offline](https://img.shields.io/badge/network-never-2C6249?style=flat-square)
![Tests](https://img.shields.io/badge/tests-157%20passing-2C6249?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-847D6E?style=flat-square)

</div>

---

## Why

A phishing e-mail is a confidence trick played on a single line: the name in the
*From* field. People read that name, recognise it, and stop reading — which is
exactly what the rest of the headers are there to catch. Every mail server that
touches a message leaves a stamp, and those stamps say where it really came
from, whether it was authenticated, and how its route lines up with its claims.

Herald reads them for you and explains them in plain words. Paste a message's
source, or open a saved `.eml`, and it shows you three things the *From* line
cannot hide:

- **The path it took** — the `Received` chain redrawn as the itinerary it
  actually was: origin at the top, recipient at the bottom, the real IP under
  each hop, and the delay between them.
- **Its authentication** — the SPF, DKIM and DMARC verdicts the receiving server
  wrote down, and whether they *align* with the domain in the *From* field.
- **The tells** — envelope mismatches, look-alike domains, a display name hiding
  a different address, a reply that would go somewhere else.

Then it grades the whole thing, A+ to F.

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/screens-dark.png">
  <img src="images/screens.png" alt="A forged invoice graded F, and a clean newsletter graded A+" width="100%">
</picture>
<br>
<sub>A forged invoice (F) beside a well-authenticated newsletter (A+).</sub>
</div>

## The honest part

Herald reads verdicts; it does not re-compute them. An SPF or DKIM "pass" here is
the *receiving server's* claim, recorded in the headers — Herald does not fetch a
DNS key and re-verify the cryptography, and it never sees your own spam filtering.
So a high grade means **every signal Herald can read is consistent**, never that
a message is genuine or safe. The word "safe" appears nowhere in a result, by
design.

That line is deliberate, and it shapes the whole tool:

- **A+ is reserved** for a message whose SPF, DKIM *and* DMARC all pass and align
  — and it still carries the caveat above.
- **Unknown beats a guess.** A message with no authentication headers at all is
  capped at **C**, labelled *authentication unknown*, rather than being waved
  through because nothing looked wrong.
- **Tells, not brands.** Every penalty is a property of the message itself — a
  mismatch, a failed check, a domain written to deceive. Herald never compares a
  sender against a list of who is "really" who, because that list is a losing
  game and it teaches nothing.

## Install

```bash
git clone https://github.com/at0m-b0mb/Herald.git
cd Herald
python3 -m pip install -r requirements.txt   # just PyQt6, for the window
```

The analysis engine and the command line need **no dependencies at all** — only
the standard library. PyQt6 is required solely for the graphical reader.

## Run

**The window:**

```bash
python3 -m herald          # or:  python3 run.py
```

Paste a message source (your mail client's *Show original* / *View source*),
open an `.eml`, or load one of the bundled samples. Switch between **Light**,
**Dark** and **Auto** from the top-right.

**The command line** — same engine, no Qt, pipe-friendly:

```bash
herald message.eml                 # a readable report
cat message.eml | herald -         # from a pipe
herald message.eml --json          # machine-readable
python3 -m herald message.eml      # without installing
```

```
  F   Strong signs this message is not what it claims  (0/100)
  Herald grades the authentication the receiving server reported; it does not
  re-verify signatures… never that a message is safe.

  Authentication (as the receiver reported it)
    SPF    fail   mailer-bounce.ru
    DKIM   none
    DMARC  fail   paypa1-billing.com

  Findings (9)
    [ alert ] SPF failed
    [ alert ] The display name hides another address
    [warning] Digit-for-letter look-alike in the domain
    …
```

## How the grade is built

Herald starts every message at 100 and subtracts for what it finds. Each
subtraction is a finding, written so you can act on it:

| Signal | What trips it |
|---|---|
| **SPF** | failed, soft-failed, or no usable policy |
| **DKIM** | signature failed, present-but-unverified, or absent |
| **DMARC** | failed alignment, or no policy published |
| **Envelope** | *From* and *Return-Path* on different registrable domains |
| **Alignment** | a valid DKIM signature for a domain other than *From* |
| **Reply-To** | replies routed to a different domain |
| **Display name** | a name that hides a different real address |
| **Look-alike** | a punycode domain, or digit-for-letter spelling (`paypa1`) |
| **Corroborating** | Message-ID from another domain, Date far from the itinerary |

Findings are sorted most-severe first and shown with the points they cost, so
the reasoning behind the letter is always on screen.

## Privacy

Herald never touches the network. It opens no sockets, resolves no names, and
sends nothing anywhere — the whole analysis is the standard library reading text
you already have. A message you paste in stays on your machine.

## Tests

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

157 tests cover the `Received` parser, the authentication reader, the domain
reasoning, the full grading pipeline against the sample set, and — as the house
style demands — every text/background colour pairing against WCAG AA in both
themes.

## Layout

```
herald/
  core/            the engine — pure standard library, no Qt
    model.py         the dataclasses everything speaks in
    received.py      the Received-header parser
    auth.py          SPF / DKIM / DMARC, read as claims
    domains.py       registrable domains and look-alike tells
    parse.py         raw source  ->  a structured Message
    grade.py         findings and the letter, with the honesty ceiling
  ui/              the window
    theme.py         the design system: one place for every token
    timeline.py      the itinerary — Herald's signature element
    widgets.py       cards, chips, key/value rows
    main_window.py   the reader itself
  cli.py           the same engine on the command line
samples/           synthetic messages: clean, mailing-list, forged
tests/             157 tests, including the contrast suite
tools/             screenshot capture and repository art
```

## Colophon

Set in **Iowan Old Style** for identity and figures, the system **sans** for
anything you read, and a **mono** for the raw headers — a serif/sans/mono mix
that reads as authored rather than assembled. The palette is warm paper and two
golds: a deep brass legible as small text, and a brighter shine used only on
marks that carry no words. Dark mode is true black, with nothing in the ramp
that reads as blue. Every colour is declared as a light/dark pair, and a test
suite holds every pairing to WCAG AA so the theme can never quietly regress.

## License

MIT — see [LICENSE](LICENSE). For authorised, educational, and personal use:
Herald is a reader, not a sender.
