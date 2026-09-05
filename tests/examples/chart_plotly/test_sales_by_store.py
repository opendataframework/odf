from app.components import SalesByStore
from app.entities import Sale
from app.repositories import Sales
from opendataframework.component import ChartProtocol

# Deliberately builds Sales/SalesByStore directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_conforms_to_chart_protocol():
    chart = SalesByStore(Sales())

    assert isinstance(chart, ChartProtocol)


def test_chart_returns_self_contained_html_with_inlined_plotly_bundle():
    sales = Sales()
    sales.save(Sale(id=None, store="Downtown", amount=120.0))
    sales.save(Sale(id=None, store="Uptown", amount=45.0))
    chart = SalesByStore(sales)

    html = chart.chart()

    assert html.startswith("<!doctype html>")
    assert "plotly.js" in html
    assert "<script src=" not in html  # inlined, not an external reference


def test_chart_reflects_live_repository_state():
    sales = Sales()
    chart = SalesByStore(sales)

    empty_chart = chart.chart()
    sales.save(Sale(id=None, store="Downtown", amount=120.0))
    populated_chart = chart.chart()

    assert empty_chart != populated_chart
