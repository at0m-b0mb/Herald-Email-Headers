"""
The window.

Left: the raw source of a message — pasted, opened from a ``.eml``, or loaded
from a sample. Right: the reading — a grade, who it claims to be from, the
authentication the receiver reported, the itinerary it travelled, and every
finding in plain words. The window holds the current source and re-renders the
whole right side on a theme change, so chips and the painted timeline always
match the active palette.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core.grade import analyze
from ..core.model import AuthState, Message, Severity
from . import theme
from .timeline import Timeline
from .widgets import Card, Chip, hrule, key_value, label, mini_label

_SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "samples")

_AUTH_TOKEN = {
    AuthState.PASS: "sev_good",
    AuthState.FAIL: "sev_alert",
    AuthState.SOFTFAIL: "sev_warning",
    AuthState.PERMERROR: "sev_warning",
    AuthState.NEUTRAL: "sev_notice",
    AuthState.NONE: "sev_notice",
    AuthState.TEMPERROR: "sev_notice",
    AuthState.ABSENT: "sev_info",
}

_SEV_TOKEN = {
    Severity.GOOD: "sev_good",
    Severity.INFO: "sev_info",
    Severity.NOTICE: "sev_notice",
    Severity.WARNING: "sev_warning",
    Severity.ALERT: "sev_alert",
}


class MainWindow(QWidget):
    def __init__(self, mode: str = theme.AUTO):
        super().__init__()
        self._mode_choice = mode
        self._mode = theme.resolve(mode)
        self._message: Message | None = None

        self.setWindowTitle("Herald")
        self.resize(1140, 760)
        self._build()
        self._apply_theme()

    # --- construction -------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._build_source_pane())
        split.addWidget(self._build_report_pane())
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 6)
        split.setSizes([460, 680])
        host = QWidget()
        host.setObjectName("PageHost")
        host_lay = QVBoxLayout(host)
        host_lay.setContentsMargins(16, 12, 16, 16)
        host_lay.addWidget(split)
        root.addWidget(host, 1)

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Rail")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 12, 20, 12)

        mark = QLabel("HERALD")
        mark.setObjectName("Wordmark")
        sub = QLabel("read the headers")
        sub.setObjectName("WordmarkSub")
        wm = QVBoxLayout()
        wm.setSpacing(0)
        wm.addWidget(mark)
        wm.addWidget(sub)
        lay.addLayout(wm)
        lay.addStretch(1)

        lay.addWidget(mini_label("THEME"))
        self.theme_box = QComboBox()
        self.theme_box.addItems(["Auto", "Light", "Dark"])
        self.theme_box.setCurrentText(self._mode_choice.capitalize())
        self.theme_box.setFixedWidth(110)
        self.theme_box.currentTextChanged.connect(self._on_theme_changed)
        lay.addWidget(self.theme_box)
        return bar

    def _build_source_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(theme.SPACE["base"])

        lay.addWidget(label("Paste a message source", "PageTitle"))
        lay.addWidget(label(
            "Use your mail client's “Show original” or “View "
            "source”, paste the whole thing below, and read what it really "
            "says about itself.", "PageIntro"))

        self.source = QPlainTextEdit()
        self.source.setObjectName("Mono")
        self.source.setPlaceholderText(
            "Received: from ...\nFrom: ...\nTo: ...\nSubject: ...\n\n(headers "
            "and body)")
        lay.addWidget(self.source, 1)

        row = QHBoxLayout()
        analyze_btn = QPushButton("Analyse")
        analyze_btn.setObjectName("Primary")
        analyze_btn.clicked.connect(self._on_analyze)
        row.addWidget(analyze_btn)

        open_btn = QPushButton("Open .eml…")
        open_btn.clicked.connect(self._on_open)
        row.addWidget(open_btn)

        self.sample_btn = QPushButton("Load sample")
        self._build_sample_menu()
        row.addWidget(self.sample_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("Quiet")
        clear_btn.clicked.connect(self._on_clear)
        row.addWidget(clear_btn)
        row.addStretch(1)
        lay.addLayout(row)
        return pane

    def _build_sample_menu(self) -> None:
        menu = QMenu(self)
        try:
            names = sorted(f for f in os.listdir(_SAMPLES_DIR) if f.endswith(".eml"))
        except OSError:
            names = []
        if not names:
            act = QAction("(no samples found)", self)
            act.setEnabled(False)
            menu.addAction(act)
        for name in names:
            pretty = name[:-4].replace("-", " ").title()
            act = QAction(pretty, self)
            act.triggered.connect(lambda _=False, n=name: self._load_sample(n))
            menu.addAction(act)
        self.sample_btn.setMenu(menu)

    def _build_report_pane(self) -> QWidget:
        self.report_scroll = QScrollArea()
        self.report_scroll.setWidgetResizable(True)
        self._set_placeholder()
        return self.report_scroll

    # --- behaviour ----------------------------------------------------------
    def _on_theme_changed(self, text: str) -> None:
        self._mode_choice = text.lower()
        self._mode = theme.resolve(self._mode_choice)
        self._apply_theme()
        if self._message is not None:
            self._render_report(self._message)
        else:
            self._set_placeholder()

    def _apply_theme(self) -> None:
        app = self.window()
        self.setStyleSheet(theme.stylesheet(self._mode))

    def _on_analyze(self) -> None:
        src = self.source.toPlainText()
        if not src.strip():
            self._set_placeholder("Paste a message, or load a sample, to begin.")
            return
        self._message = analyze(src)
        self._render_report(self._message)

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open an .eml file", "", "Email (*.eml *.txt);;All files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                self.source.setPlainText(fh.read())
        except OSError as exc:
            self._set_placeholder(f"Could not open the file: {exc}")
            return
        self._on_analyze()

    def _load_sample(self, name: str) -> None:
        path = os.path.join(_SAMPLES_DIR, name)
        try:
            with open(path, encoding="utf-8") as fh:
                self.source.setPlainText(fh.read())
        except OSError as exc:
            self._set_placeholder(f"Could not load the sample: {exc}")
            return
        self._on_analyze()

    def _on_clear(self) -> None:
        self.source.clear()
        self._message = None
        self._set_placeholder()

    # --- report rendering ---------------------------------------------------
    def _set_placeholder(self, text: str = "") -> None:
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.addStretch(1)
        lay.addWidget(label("Nothing read yet", "Figure"))
        lay.addWidget(label(
            text or "Herald reads the headers a mail server already wrote, and "
            "tells you what they say about a message's origin, its "
            "authentication, and the path it took. It reports the receiver's "
            "claims — it never re-verifies cryptography, and it never calls a "
            "message safe.", "PageIntro"))
        lay.addStretch(2)
        self.report_scroll.setWidget(host)

    def _render_report(self, msg: Message) -> None:
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(8, 4, 8, 16)
        lay.setSpacing(theme.SPACE["base"])

        lay.addWidget(self._grade_card(msg))
        lay.addWidget(self._identity_card(msg))
        lay.addWidget(self._auth_card(msg))
        lay.addWidget(self._itinerary_card(msg))
        lay.addWidget(self._findings_card(msg))
        if msg.parse_notes:
            notes = Card("Notes", flat=True)
            for n in msg.parse_notes:
                notes.add(label(n, muted=True))
            lay.addWidget(notes)
        lay.addStretch(1)
        self.report_scroll.setWidget(host)

    def _grade_card(self, msg: Message) -> QWidget:
        g = msg.grade
        card = Card()
        top = QHBoxLayout()

        letter = QLabel(g.letter)
        letter.setStyleSheet(
            f"{theme.font_css('grade')} color: {theme.color(theme.grade_token(g.letter), self._mode)};")
        top.addWidget(letter)

        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(mini_label(f"EXPOSURE GRADE  ·  SCORE {g.score}/100"))
        col.addWidget(label(g.headline, "PageTitle"))
        col.addStretch(1)
        top.addLayout(col, 1)
        card.add_layout(top)
        card.add(hrule())
        note = label(g.ceiling_note, "Faint")
        card.add(note)
        return card

    def _identity_card(self, msg: Message) -> QWidget:
        card = Card("Who it claims to be")
        card.add(key_value("Subject", msg.subject, self._mode))
        if msg.from_addr:
            card.add(key_value("From", msg.from_addr.rendered, self._mode, mono=True))
        if msg.return_path:
            tok = None
            if msg.from_addr and msg.return_path.domain:
                from ..core.domains import same_registrable
                if not same_registrable(msg.from_addr.domain, msg.return_path.domain):
                    tok = "sev_warning"
            card.add(key_value("Return-Path", msg.return_path.full, self._mode,
                               value_token=tok, mono=True))
        if msg.reply_to:
            card.add(key_value("Reply-To", msg.reply_to.full, self._mode, mono=True))
        if msg.to_addrs:
            card.add(key_value("To", ", ".join(a.full for a in msg.to_addrs),
                               self._mode, mono=True))
        if msg.date_header:
            card.add(key_value("Date", msg.date_header.strftime("%Y-%m-%d %H:%M %z"),
                               self._mode))
        return card

    def _auth_card(self, msg: Message) -> QWidget:
        card = Card("Authentication, as the receiver reported it")
        grid = QHBoxLayout()
        grid.setSpacing(theme.SPACE["wide"])
        for name, state, dom in (
            ("SPF", msg.auth.spf, msg.auth.spf_domain),
            ("DKIM", msg.auth.dkim, msg.auth.dkim_domain),
            ("DMARC", msg.auth.dmarc, msg.auth.dmarc_domain),
        ):
            col = QVBoxLayout()
            col.setSpacing(theme.SPACE["tight"])
            col.addWidget(mini_label(name))
            col.addWidget(Chip(state.value, _AUTH_TOKEN[state], self._mode))
            if dom:
                col.addWidget(label(dom, "Faint"))
            col.addStretch(1)
            wrap = QWidget()
            wrap.setLayout(col)
            grid.addWidget(wrap)
        grid.addStretch(1)
        card.add_layout(grid)
        if msg.auth.authserv:
            card.add(label(f"Checked by {msg.auth.authserv}.", "Faint"))
        return card

    def _itinerary_card(self, msg: Message) -> QWidget:
        tt = msg.travel_time_seconds
        title = "The path it took"
        card = Card(title)
        if tt is not None:
            mins = f"{tt / 60:.1f} min" if tt >= 90 else f"{tt:.0f} s"
            card.add(label(
                f"{len(msg.hops)} hops, {mins} in transit. Solid nodes crossed "
                f"the open internet; hollow nodes were internal hand-offs.",
                "Faint"))
        timeline = Timeline()
        timeline.set_data(msg.hops, self._mode)
        card.add(timeline)
        return card

    def _findings_card(self, msg: Message) -> QWidget:
        card = Card(f"Findings ({len(msg.findings)})")
        for i, f in enumerate(msg.findings):
            if i:
                card.add(hrule())
            row = QHBoxLayout()
            row.setSpacing(theme.SPACE["base"])
            chip = Chip(f.severity.value, _SEV_TOKEN[f.severity], self._mode)
            chip.setFixedWidth(84)
            row.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)

            col = QVBoxLayout()
            col.setSpacing(2)
            head = QHBoxLayout()
            head.addWidget(label(f.title, "body"))
            head.addStretch(1)
            if f.points:
                head.addWidget(label(f"−{f.points}", "Faint"))
            col.addLayout(head)
            col.addWidget(label(f.detail, muted=True))
            row.addLayout(col, 1)
            card.add_layout(row)
        return card
