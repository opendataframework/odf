"""Pricing function for the flat-grid example."""

from opendataframework import Function


@Function
def shipping_cost(weight_kg: float) -> float:
    """Return what shipping a parcel costs, in euros.

    Args:
        weight_kg: The parcel's weight, in kilograms.
    """
    return round(4.5 + 1.2 * weight_kg, 2)
