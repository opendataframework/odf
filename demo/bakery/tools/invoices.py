"""The suppliers' invoices, as the PDFs they attach to their emails.

A tiny PDF writer, enough for a one-page invoice in the standard fonts, so
the tools image needs no PDF library. The bakery reads these the way it
would read any supplier's: from the PDF, not from this module.
"""

import random
from dataclasses import dataclass
from datetime import date

from tools.data import BY_INGREDIENT, INGREDIENTS, Supplier

# The standard fonts a page uses, by resource name.
FONTS = {"F1": "Helvetica", "F2": "Helvetica-Bold", "F3": "Times-Italic"}


def _literal(text: str) -> bytes:
    """Return ``text`` as a PDF literal string in WinAnsi (so "£" survives)."""
    raw = text.encode("cp1252", errors="replace")
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def pdf(items: list[tuple[float, float, str, int, str]]) -> bytes:
    """Return a one-page A4 PDF with each ``(x, y, font, size, text)`` placed on it.

    ``font`` is a key of ``FONTS``; ``x`` and ``y`` are points from the
    bottom left. The content isn't compressed.
    """
    content = b"".join(
        b"BT /%s %d Tf 1 0 0 1 %.1f %.1f Tm %s Tj ET\n"
        % (font.encode(), size, x, y, _literal(text))
        for x, y, font, size, text in items
    )
    fonts = b" ".join(b"/%s %d 0 R" % (name.encode(), 5 + n) for n, name in enumerate(FONTS))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R"
        b" /Resources << /Font << " + fonts + b" >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream",
        *(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>"
            % base.encode()
            for base in FONTS.values()
        ),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


@dataclass(frozen=True)
class Line:
    """One line of an invoice: so much of an ingredient, at a price per unit."""

    code: str
    quantity: float
    unit_price: float

    @property
    def amount(self) -> float:
        """What the line comes to, in pounds."""
        return round(self.quantity * self.unit_price, 2)


def delivery(supplier: Supplier, prices: dict[str, float], r: random.Random) -> list[Line]:
    """Return a week's delivery from ``supplier``: each of its ingredients, at ``prices``."""
    lines = []
    for ingredient in INGREDIENTS:
        if ingredient.supplier != supplier.name:
            continue
        quantity = ingredient.weekly * r.uniform(0.8, 1.2)
        # Eggs come in trays of 30.
        quantity = round(quantity / 30) * 30 if ingredient.unit == "each" else round(quantity, 1)
        lines.append(Line(ingredient.code, quantity, prices[ingredient.code]))
    return lines


def total(lines: list[Line]) -> float:
    """Return what an invoice's lines come to."""
    return round(sum(line.amount for line in lines), 2)


def _money(value: float) -> str:
    return f"£{value:,.2f}"


def _quantity(value: float) -> str:
    return f"{value:g}"


def invoice_pdf(supplier: Supplier, number: str, day: date, lines: list[Line]) -> bytes:
    """Return ``supplier``'s invoice for ``lines`` as a PDF, in its own layout."""
    if supplier.layout == "note":
        return _note_pdf(supplier, day, lines)
    items = [
        (50, 790, "F2", 18, supplier.name),
        (50, 772, "F1", 9, supplier.email),
        (420, 790, "F2", 16, "INVOICE"),
        (380, 760, "F1", 10, "Invoice no."),
        (470, 760, "F1", 10, number),
        (380, 745, "F1", 10, "Date"),
        (470, 745, "F1", 10, day.isoformat()),
        (50, 730, "F1", 10, "Bill to: The Bakery, orders@bakery.example"),
        (50, 690, "F2", 10, "Description"),
        (300, 690, "F2", 10, "Qty"),
        (350, 690, "F2", 10, "Unit"),
        (410, 690, "F2", 10, "Unit price"),
        (490, 690, "F2", 10, "Amount"),
    ]
    y = 670
    for line in lines:
        ingredient = BY_INGREDIENT[line.code]
        items += [
            (50, y, "F1", 10, ingredient.invoice_name),
            (300, y, "F1", 10, _quantity(line.quantity)),
            (350, y, "F1", 10, ingredient.unit),
            (410, y, "F1", 10, _money(line.unit_price)),
            (490, y, "F1", 10, _money(line.amount)),
        ]
        y -= 18
    items += [
        (410, y - 10, "F2", 11, "Total"),
        (490, y - 10, "F2", 11, _money(total(lines))),
        (50, 80, "F1", 8, "Payment within 30 days. Thank you for your business."),
    ]
    return pdf(items)


def _note_pdf(supplier: Supplier, day: date, lines: list[Line]) -> bytes:
    """The farm's invoice: a few lines, as if written out by hand and scanned."""
    items = [(60, 780, "F3", 16, f"{supplier.name}: eggs delivered {day:%A %-d %B}")]
    y = 750
    for line in lines:
        trays = line.quantity / 30
        items.append(
            (60, y, "F3", 13, f"{trays:g} trays of 30 at {_money(line.unit_price * 30)} a tray")
        )
        y -= 24
    items.append((60, y - 10, "F3", 13, f"comes to {_money(total(lines))}, cheers, Tom"))
    return pdf(items)
