from functools import partial

from app.components import Rates
from app.reports import store_total, to_eur
from app.repositories import Orders
from app.tasks import ReportTotals

# Calls the adopted functions directly, passing every argument, the way their
# tests ran before @Function was added — no Project/Context needed.


def test_to_eur_converts_at_the_rate_of_the_currency():
    rates = Rates()

    assert to_eur(100, "USD", rates) == 90.0
    assert to_eur(50, "gbp", rates) == 60.0
    assert to_eur(40, "EUR", rates) == 40.0


def test_store_total_sums_a_store_s_orders_in_euros():
    convert = partial(to_eur, rates=Rates())

    assert store_total("Berlin", Orders(), convert) == 192.0
    assert store_total("London", Orders(), convert) == 240.0
    assert store_total("Paris", Orders(), convert) == 0


def test_report_totals_reports_every_store():
    total = partial(store_total, orders=Orders(), convert=partial(to_eur, rates=Rates()))

    assert ReportTotals(Orders(), total).execute() == {
        "Berlin": 192.0,
        "Lisbon": 40.0,
        "London": 240.0,
    }
