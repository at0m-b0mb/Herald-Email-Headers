"""
The itinerary — Herald's signature.

Every e-mail carries its own route in its ``Received`` headers, and this widget
draws that route as the message actually travelled it: origin at the top,
recipient at the bottom, one node per server, the real IP under each, and the
measured delay written on the line between hops. Internal hand-offs inside an
organisation are drawn hollow and external jumps solid, so you can see where the
message crossed the open internet.

It is painted rather than assembled from labels because the connective tissue —
the line, the delays, the hollow-versus-solid nodes — *is* the information. No
other tool in the catalogue could draw this particular picture, which is exactly
why it earns the space.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from . import theme
from ..core.model import Hop

_ROW = 66          # vertical pixels per hop
_PAD_TOP = 14
_NODE_X = 22
_NODE_R = 6
_TEXT_X = 48


def _fmt_delay(seconds: float | None) -> str:
    if seconds is None:
        return ""
    if seconds < 0:
        return f"-{_fmt_delay(-seconds)}"  # clock ran backwards between hops
    if seconds < 1:
        return "<1s"
    if seconds < 90:
        return f"+{int(round(seconds))}s"
    if seconds < 5400:
        return f"+{int(round(seconds / 60))}m"
    return f"+{seconds / 3600:.1f}h"


class Timeline(QWidget):
    """A vertical chain of hops in travel order (origin first)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hops: list[Hop] = []
        self._mode = theme.LIGHT
        self.setMinimumHeight(_ROW)

    def set_data(self, hops: list[Hop], mode: str) -> None:
        self._hops = hops
        self._mode = mode
        self.setMinimumHeight(max(_ROW, _PAD_TOP * 2 + _ROW * max(1, len(hops))))
        self.updateGeometry()
        self.update()

    def sizeHint(self):  # noqa: N802  (Qt override)
        from PyQt6.QtCore import QSize
        n = max(1, len(self._hops))
        return QSize(420, _PAD_TOP * 2 + _ROW * n)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        c = lambda n: QColor(theme.color(n, self._mode))  # noqa: E731

        if not self._hops:
            p.setPen(c("ink_faint"))
            p.setFont(self._font("subtitle"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No itinerary in these headers.")
            p.end()
            return

        n = len(self._hops)
        line_pen = QPen(c("rule_strong"), 2)

        # the spine connecting every node
        top_y = _PAD_TOP + _ROW // 2
        bottom_y = _PAD_TOP + _ROW * (n - 1) + _ROW // 2
        if n > 1:
            p.setPen(line_pen)
            p.drawLine(_NODE_X, top_y, _NODE_X, bottom_y)

        for i, hop in enumerate(self._hops):
            y = _PAD_TOP + _ROW * i + _ROW // 2
            external = not hop.is_internal
            node_color = c("hop_external") if external else c("hop_internal")

            # node: solid for an external jump, hollow for an internal hand-off
            p.setPen(QPen(node_color, 2))
            p.setBrush(QBrush(node_color) if external else QBrush(Qt.BrushStyle.NoBrush))
            p.drawEllipse(_NODE_X - _NODE_R, y - _NODE_R, _NODE_R * 2, _NODE_R * 2)

            # delay annotation on the segment leading into this hop
            if i > 0 and hop.delay_seconds is not None:
                p.setPen(c("ink_faint"))
                p.setFont(self._font("mono_small"))
                p.drawText(QRectF(_NODE_X + 10, y - _ROW // 2 - 2, 60, 16),
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           _fmt_delay(hop.delay_seconds))

            # endpoint markers
            marker = ""
            if i == 0:
                marker = "ORIGIN"
            elif i == n - 1:
                marker = "DELIVERED"

            # host name
            host = hop.from_host or hop.by_host or "unknown host"
            p.setPen(c("ink"))
            p.setFont(self._font("body_bold"))
            host_rect = QRectF(_TEXT_X, y - 20, self.width() - _TEXT_X - 90, 18)
            p.drawText(host_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       self._elide(host, host_rect.width(), "body_bold"))

            if marker:
                p.setPen(node_color)
                p.setFont(self._font("label"))
                p.drawText(QRectF(self.width() - 86, y - 20, 78, 18),
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                           marker)

            # ip + tags line
            bits = []
            if hop.from_ip:
                bits.append(hop.from_ip)
            bits.append("internal" if hop.is_internal else "external")
            if hop.with_tls:
                bits.append("TLS")
            elif external:
                bits.append("no TLS")
            if hop.protocol:
                bits.append(hop.protocol)
            p.setPen(c("ink_muted"))
            p.setFont(self._font("mono_small"))
            p.drawText(QRectF(_TEXT_X, y + 1, self.width() - _TEXT_X - 8, 16),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       "  ·  ".join(bits))

        p.end()

    # --- helpers ------------------------------------------------------------
    def _font(self, role: str) -> QFont:
        family, size, weight = theme.TYPE[role]
        f = QFont()
        f.setFamilies([family.split(",")[0].strip().strip('"')])
        f.setPixelSize(size)
        f.setWeight(QFont.Weight.DemiBold if weight >= 600 else QFont.Weight.Normal)
        return f

    def _elide(self, text: str, width: float, role: str) -> str:
        from PyQt6.QtGui import QFontMetrics
        fm = QFontMetrics(self._font(role))
        return fm.elidedText(text, Qt.TextElideMode.ElideMiddle, int(width))
