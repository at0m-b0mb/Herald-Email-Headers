# Changelog

All notable changes to Herald are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/).

## [1.0.0] — 2026-10-02

First release.

### The reader
- Parses the full source of an e-mail into a structured message: sender,
  reply-to, envelope, subject, Message-ID, and the complete `Received` chain.
- **Itinerary** — the `Received` headers redrawn as the route the message took,
  origin first, with the real IP under each hop, internal hand-offs drawn hollow
  and external jumps solid, and the measured delay on every segment.
- **Authentication** — SPF, DKIM and DMARC read out of `Authentication-Results`,
  `Received-SPF` and `DKIM-Signature`, reported as the receiver's claims rather
  than re-verified.
- **Findings** — envelope and alignment mismatches, reply-to redirection, a
  display name hiding another address, punycode and digit-for-letter look-alike
  domains, and weaker corroborating tells (Message-ID origin, Date skew).
- **Grade** — A+ to F, with an honesty ceiling: A+ is reserved for a fully
  authenticated, aligned message; an unauthenticated message is capped at C and
  labelled *unknown*; the word "safe" never appears.

### Interfaces
- A PyQt6 window in the house style — warm paper and gold, true-black dark mode,
  and an Auto theme that follows the OS.
- A dependency-free command line sharing the same engine, with text and `--json`
  output and standard-input support.

### Engineering
- The engine (`herald.core`) is pure standard library — no third-party
  dependencies, no network, no sockets.
- 157 tests across the `Received` parser, the authentication reader, the domain
  reasoning, the full grading pipeline, and a WCAG-AA contrast suite covering
  every text/background pairing in both themes.
- Off-screen screenshot capture and a repository-art generator whose social card
  is held inside GitHub's safe border by a registered-rectangle check.
