"""Exchange rates for the function example."""

from opendataframework import Component


@Component
class Rates:
    """Fixed exchange rates to euros, standing in for a rates service."""

    def __init__(self) -> None:
        """Set the rate of each currency, in euros per unit."""
        self.to_eur = {"EUR": 1.0, "USD": 0.9, "GBP": 1.2}
