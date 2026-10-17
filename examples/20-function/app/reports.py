"""The reporting code being adopted: plain functions, as they were written.

Each function only gains ``@Function`` (and a layer on top). Its body and
signature are unchanged, so calling it directly still takes every argument,
as before. Called through the ``Context`` instead, the parameters whose type
it manages are filled in: ``rates`` and ``orders`` here, and ``convert``,
which asks for ``to_eur`` by naming it in ``Annotated``.
"""

from collections.abc import Callable
from typing import Annotated

from opendataframework import Analytics, Function

from app.components import Rates
from app.repositories import Orders


@Function
def to_eur(amount: float, currency: str, rates: Rates) -> float:
    """Convert an amount to euros at the current rate.

    Args:
        amount: The amount to convert.
        currency: The ISO code of its currency.
        rates: The exchange rates, injected by the ``Context``.
    """
    return round(amount * rates.to_eur[currency.upper()], 2)


@Analytics
@Function
def store_total(
    store: str,
    orders: Orders,
    convert: Annotated[Callable[..., float], to_eur],
) -> float:
    """Return a store's takings in euros, across every currency it was paid in.

    Args:
        store: The store's name, such as ``"Berlin"``.
        orders: The orders, injected by the ``Context``.
        convert: ``to_eur``, injected with its own ``rates`` already filled in.
    """
    return round(
        sum(
            convert(order.amount, order.currency) for order in orders.all() if order.store == store
        ),
        2,
    )
