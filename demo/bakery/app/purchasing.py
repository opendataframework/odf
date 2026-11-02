"""Buying: reading the suppliers' invoices, and keeping what each ingredient costs.

An invoice is a fact, not a decision: nothing goes out, and nobody is
committed to anything. So when the rules read a typed invoice cleanly (every
line is an ingredient on the sheet, and its sums add up), the invoice-clerk
records its prices at once. When only a model can read it, or nothing can,
its reading becomes a draft for a person, like everything else an agent is
unsure of.
"""

import json
import re
from datetime import datetime

from opendataframework import Agent, Notifications, Publisher

from app.allergens import declared
from app.clients import Clock
from app.entities import Draft, Ingredient, IngredientPrice, Invoice
from app.model import Model
from app.pdf import pdf_rows, pdf_text
from app.repositories import Drafts, IngredientPrices, Ingredients, Invoices

# A price that moves by at least this share is worth a notice.
NOTICE_CHANGE = 0.05
# A rise of at least this share makes the notice a warning.
WARNING_RISE = 0.10
# How far a line's or an invoice's sums may be out, in pounds (rounding).
TOLERANCE = 0.02
# A model's unit price this many times off the sheet price, either way, isn't believed.
IMPLAUSIBLE = 5.0

_MONEY = re.compile(r"^-?£?\s*(-?[\d,]*\.?\d+)$")


def money(text: str) -> float | None:
    """Return a cell such as ``"£1,234.50"`` as a number, or ``None`` if it isn't money."""
    found = _MONEY.match(text.strip())
    return float(found.group(1).replace(",", "")) if found else None


def read_invoice(rows: list[list[str]]) -> dict | None:
    """Read a typed invoice's rows: its number, date, lines and total.

    Expects what most suppliers send: ``Invoice no.`` and ``Date`` beside
    their values, a table headed ``Description``, ``Qty``, ``Unit``, ``Unit
    price``, ``Amount``, and a ``Total`` row. A row of one cell in the table
    is a note about the line above it, such as a substitution.

    Returns:
        ``{"number", "date", "lines": [{"description", "quantity", "unit",
        "unit_price", "amount", "note"}], "total"}``, or ``None`` if it isn't
        laid out that way.
    """
    found: dict = {"number": None, "date": None, "lines": [], "total": None}
    in_table = False
    for row in rows:
        labels = [cell.lower().rstrip(":") for cell in row]
        if len(row) >= 2 and labels[-2] in ("invoice no.", "invoice number", "invoice no"):
            found["number"] = row[-1]
        elif len(row) >= 2 and labels[-2] == "date":
            found["date"] = row[-1]
        elif {"description", "qty", "amount"} <= set(labels):
            in_table = True
        elif len(row) >= 2 and labels[-2] == "total":
            found["total"] = money(row[-1])
            in_table = False
        elif in_table and len(row) == 1 and found["lines"]:
            note = found["lines"][-1]["note"]
            found["lines"][-1]["note"] = f"{note} {row[0]}".strip()
        elif in_table and len(row) == 5:
            quantity, unit_price, amount = money(row[1]), money(row[3]), money(row[4])
            if None in (quantity, unit_price, amount):
                return None
            found["lines"].append(
                {
                    "description": row[0],
                    "quantity": quantity,
                    "unit": row[2],
                    "unit_price": unit_price,
                    "amount": amount,
                    "note": "",
                }
            )
    if not found["lines"] or found["total"] is None:
        return None
    return found


def match_lines(
    lines: list[dict], ingredients: list[Ingredient], supplier: str
) -> tuple[list[dict], list[str]]:
    """Match an invoice's lines to the supplier's ingredients, and check its sums.

    Returns:
        The lines as ``{"ingredient", "quantity", "unit_price", "amount",
        "note"}``, and the problems found: a line that isn't an ingredient on the
        sheet, a unit that differs, or an amount that isn't quantity times
        price. Empty problems mean the reading can be trusted.
    """
    by_name = {
        i.invoice_name.lower(): i for i in ingredients if i.supplier.lower() == supplier.lower()
    }
    matched, problems = [], []
    for line in lines:
        ingredient = by_name.get(line["description"].lower())
        if ingredient is None:
            problems.append(
                f"{line['description']!r} isn't on the ingredients sheet for {supplier}"
            )
            continue
        if line.get("unit") and line["unit"] != ingredient.unit:
            problems.append(f"{ingredient.name} is priced by {line['unit']}, not {ingredient.unit}")
        if abs(line["quantity"] * line["unit_price"] - line["amount"]) > TOLERANCE:
            problems.append(f"{ingredient.name}'s amount isn't its quantity times its price")
        matched.append(
            {
                "ingredient": ingredient.code,
                "quantity": line["quantity"],
                "unit_price": line["unit_price"],
                "amount": line["amount"],
                "note": line.get("note", ""),
            }
        )
    return matched, problems


def record_prices(
    invoice: Invoice,
    lines: list[dict],
    ingredients: Ingredients,
    prices: IngredientPrices,
    invoices: Invoices,
) -> list[dict]:
    """Record each line's price in IngredientPrices, and mark the invoice recorded.

    Returns:
        Each ingredient's change: ``{"ingredient", "name", "unit", "was",
        "now"}``, ``was`` being its latest price before (or the sheet's).
    """
    sheet = {i.code: i for i in ingredients.all()}
    before = {code: i.price for code, i in sheet.items()} | prices.latest()
    changes = []
    for line in lines:
        ingredient = sheet[line["ingredient"]]
        prices.save(
            IngredientPrice(
                id=None,
                priced_at=invoice.received_at,
                ingredient=ingredient.code,
                name=ingredient.name,
                unit=ingredient.unit,
                unit_price=float(line["unit_price"]),
                supplier=invoice.supplier,
                invoice=invoice.id,
            )
        )
        changes.append(
            {
                "ingredient": ingredient.code,
                "name": ingredient.name,
                "unit": ingredient.unit,
                "was": before.get(ingredient.code, ingredient.price),
                "now": float(line["unit_price"]),
            }
        )
    invoice.status = "recorded"
    invoices.save(invoice)
    return changes


def announce_prices(notifications: Notifications, invoice: Invoice, changes: list[dict]) -> None:
    """Publish ``prices.changed`` for an invoice's recorded prices.

    It has a summary, and so a notice, only when a price moved by at least
    ``NOTICE_CHANGE``: a warning for a rise of ``WARNING_RISE`` or more.
    Otherwise it's for components only: the same prices as last week aren't
    news.
    """
    moved = [c for c in changes if c["was"] and abs(c["now"] / c["was"] - 1) >= NOTICE_CHANGE]
    summary, level = None, "info"
    if moved:
        parts = [
            f"{c['name'].lower()} {'up' if c['now'] > c['was'] else 'down'} "
            f"{abs(c['now'] / c['was'] - 1):.0%} (£{c['was']:.2f} to £{c['now']:.2f} a {c['unit']})"
            for c in moved
        ]
        summary = f"{invoice.supplier}: " + ", ".join(parts)
        if any(c["now"] / c["was"] - 1 >= WARNING_RISE for c in moved):
            level = "warning"
    notifications.publish(
        "prices.changed",
        {"invoice": invoice.id, "supplier": invoice.supplier, "changes": changes},
        summary=summary,
        level=level,
        subject=IngredientPrices,
    )


def announce_substitutions(
    notifications: Notifications, invoice: Invoice, lines: list[dict], ingredients: Ingredients
) -> list[dict]:
    """Publish ``ingredients.changed`` for each line whose note declares an allergen.

    A supplier that substitutes an ingredient says so under its line: "May
    contain sesame". Recording what that means for the labels is
    ``Labelling``'s job; this only says what the invoice declared.

    Returns:
        The changes published: ``{"ingredient", "name", "note", "allergens",
        "invoice", "supplier"}``.
    """
    names = {i.code: i.name for i in ingredients.all()}
    published = []
    for line in lines:
        found = declared(line.get("note", ""))
        if not found:
            continue
        change = {
            "ingredient": line["ingredient"],
            "name": names.get(line["ingredient"], line["ingredient"]),
            "note": line["note"],
            "allergens": [{"allergen": a, "kind": k} for a, k in found],
            "invoice": invoice.id,
            "supplier": invoice.supplier,
        }
        what = ", ".join(f"{k} {a}" for a, k in found)
        notifications.publish(
            "ingredients.changed",
            change,
            summary=f"{invoice.supplier}: {change['name'].lower()} now {what}",
            level="warning",
            subject=Invoices,
            record=invoice.id,
        )
        published.append(change)
    return published


_INVOICE_SYSTEM = """You read a bakery supplier's invoice. List each ingredient \
delivered: its code (one of the codes given), the quantity in that ingredient's \
unit, and the price per unit in pounds. Convert packs to units: a tray of 30 eggs \
at £9.00 is 30 eggs at £0.30. Give the invoice's total in pounds, and its number \
and date if it has them (date as YYYY-MM-DD), else empty strings. Use only what \
the invoice says."""

_INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "number": {"type": "string"},
        "date": {"type": "string"},
        "total": {"type": "number"},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ingredient": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_price": {"type": "number"},
                },
                "required": ["ingredient", "quantity", "unit_price"],
            },
        },
    },
    "required": ["total", "lines"],
}


@Publisher("prices.changed", "ingredients.changed", "drafts.created")
@Agent
class InvoiceClerk:
    """Reads a supplier's invoice, and records what it charged for each ingredient.

    ``invoke(invoice_id)`` reads one invoice from Invoices. Rules read the
    typed ones; when they read it cleanly, its prices go straight into
    IngredientPrices and ``prices.changed`` is published, with
    ``ingredients.changed`` for a line whose note declares an allergen (a
    substitution). One the rules
    can't read goes to the model, if there is one, and its reading becomes a
    draft to confirm; with no model, a draft for a person to review.
    """

    def __init__(
        self,
        clock: Clock,
        invoices: Invoices,
        ingredients: Ingredients,
        prices: IngredientPrices,
        drafts: Drafts,
        model: Model,
        notifications: Notifications,
    ) -> None:
        """Store what the agent reads and where it records.

        Args:
            clock: The demo clock, for when it drafted.
            invoices: The invoices it reads.
            ingredients: What each line can be.
            prices: Where the prices go.
            drafts: Where a reading it isn't sure of goes.
            model: Asked to read what the rules can't.
            notifications: Bound to this agent.
        """
        self.clock, self.invoices, self.ingredients = clock, invoices, ingredients
        self.prices, self.drafts = prices, drafts
        self.model, self.notifications = model, notifications

    def invoke(self, invoice_id: int) -> dict:
        """Read invoice ``invoice_id``: record its prices, or draft its reading.

        An invoice already recorded or drafted is left as it is.

        Args:
            invoice_id: The invoice's id in Invoices.

        Returns:
            ``{"invoice", "status", "lines", "draft"}``.

        Raises:
            KeyError: If there's no such invoice.
        """
        invoice = self.invoices.get(invoice_id)
        if invoice.status != "new":
            return {"invoice": invoice.id, "status": invoice.status, "lines": [], "draft": None}
        ingredients = self.ingredients.all()
        read = read_invoice(pdf_rows(invoice.pdf))
        problems = ["the rules don't know this invoice's layout"]
        if read is not None:
            lines, problems = match_lines(read["lines"], ingredients, invoice.supplier)
            if abs(sum(line["amount"] for line in lines) - read["total"]) > TOLERANCE:
                problems.append("its lines don't add up to its total")
            invoice.number, invoice.date, invoice.total = (
                read["number"],
                read["date"],
                read["total"],
            )
            if not problems:
                changes = record_prices(
                    invoice, lines, self.ingredients, self.prices, self.invoices
                )
                announce_prices(self.notifications, invoice, changes)
                announce_substitutions(self.notifications, invoice, lines, self.ingredients)
                return {"invoice": invoice.id, "status": "recorded", "lines": lines, "draft": None}
        lines, author, note = [], "nobody", "; ".join(problems).capitalize() + "."
        if self.model.available():
            lines, model_note = self._ask_model(invoice, ingredients)
            if lines:
                author, note = self.model.author, ""
            else:
                note += f" The model couldn't read it either: {model_note}"
        else:
            note += " There's no model to read it. Check the PDF, then reject this draft."
        draft = self._draft(invoice, ingredients, lines, author, note)
        invoice.status = "drafted"
        self.invoices.save(invoice)
        return {"invoice": invoice.id, "status": "drafted", "lines": lines, "draft": draft.id}

    def _ask_model(self, invoice: Invoice, ingredients: list[Ingredient]) -> tuple[list[dict], str]:
        """Ask the model to read the invoice, and check its answer.

        Returns:
            The lines, or ``[]`` and why the answer wasn't believed.
        """
        own = {i.code: i for i in ingredients if i.supplier.lower() == invoice.supplier.lower()}
        if not own:
            return [], f"{invoice.supplier} isn't a supplier on the ingredients sheet."
        text = pdf_text(invoice.pdf)
        codes = "\n".join(f"- {i.code}: {i.name}, priced per {i.unit}" for i in own.values())
        answer = self.model.ask(
            _INVOICE_SYSTEM, f"Ingredient codes:\n{codes}\n\nInvoice:\n{text}", _INVOICE_SCHEMA
        )
        if not isinstance(answer, dict) or not isinstance(answer.get("lines"), list):
            return [], "it gave no answer."
        lines = []
        for item in answer["lines"]:
            ingredient = own.get(str(item.get("ingredient", "")).upper())
            try:
                quantity, unit_price = float(item["quantity"]), float(item["unit_price"])
            except KeyError, TypeError, ValueError:
                return [], "a line had no quantity or price."
            if ingredient is None or quantity <= 0 or unit_price <= 0:
                return [], "a line wasn't one of the supplier's ingredients."
            if not 1 / IMPLAUSIBLE <= unit_price / ingredient.price <= IMPLAUSIBLE:
                return (
                    [],
                    f"£{unit_price:.2f} a {ingredient.unit} of {ingredient.name} isn't plausible.",
                )
            lines.append(
                {
                    "ingredient": ingredient.code,
                    "quantity": quantity,
                    "unit_price": round(unit_price, 4),
                    "amount": round(quantity * unit_price, 2),
                }
            )
        try:
            stated = float(answer["total"])
        except KeyError, TypeError, ValueError:
            return [], "it gave no total."
        if not lines or abs(sum(line["amount"] for line in lines) - stated) > TOLERANCE * 5:
            return [], "its lines don't add up to its total."
        if f"{stated:,.2f}" not in text and f"{stated:.2f}" not in text:
            return [], f"the invoice doesn't say £{stated:.2f} anywhere."
        if answer.get("number"):
            invoice.number = str(answer["number"])[:40]
        invoice.total = stated
        return lines, ""

    def _draft(
        self,
        invoice: Invoice,
        ingredients: list[Ingredient],
        lines: list[dict],
        author: str,
        note: str,
    ) -> Draft:
        """Save and announce the draft of an invoice's reading."""
        names = {i.code: i for i in ingredients}
        before = {i.code: i.price for i in ingredients} | self.prices.latest()
        rows = [
            f"| {names[line['ingredient']].name} | {line['quantity']:g} "
            f"{names[line['ingredient']].unit} | £{line['unit_price']:.2f} | "
            f"£{before.get(line['ingredient'], 0):.2f} | £{line['amount']:.2f} |"
            for line in lines
        ]
        received = datetime.fromtimestamp(invoice.received_at)
        title = f"Invoice from {invoice.supplier}"
        body = [
            f"## {title}",
            "",
            f"Emailed {received:%a %-d %b, %H:%M} as {invoice.filename}: open it in Invoices"
            f" (invoice {invoice.id}).",
            "",
        ]
        if lines:
            body += [
                f"Read by {author}. Check it against the PDF; confirming records these prices.",
                "",
                "| Ingredient | Delivered | Price | Was | Amount |",
                "|---|---|---|---|---|",
                *rows,
                "",
                f"**Total: £{sum(line['amount'] for line in lines):,.2f}**",
            ]
        else:
            body += [f"**Needs review.** {note}"]
        draft = Draft(
            id=None,
            created_at=self.clock.now().timestamp(),
            kind="invoice",
            status="pending" if lines else "needs-review",
            title=title,
            date=received.date().isoformat(),
            restaurant=None,
            message=None,
            changes=json.dumps({"invoice": invoice.id, "lines": lines}),
            reply="",
            author=author,
            note=note,
            body="\n".join(body),
        )
        self.drafts.save(draft)
        waiting = "awaits confirmation" if lines else "needs review"
        self.notifications.publish(
            "drafts.created",
            {"draft": draft.id, "kind": "invoice", "status": draft.status},
            summary=f"{title} {waiting}",
            level="info" if lines else "warning",
            subject=Drafts,
            record=draft.id,
        )
        return draft
