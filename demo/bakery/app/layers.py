"""The bakery's layers: one per area, each a band of ``layout.json``.

Every component, function, agent, task and pipeline is tagged with the area
it belongs to, so the topology's sidebar groups them the way the canvas lays
them out: the integrations on the left, then wholesale, the café, production,
purchasing and margins, allergens, and the drafts every agent's work ends in.
"""

from opendataframework import Layer, Namespace


@Layer("integrations")
class Integrations(Namespace):
    """The tools' clients, the services taking their items in, and the imports."""


@Layer("wholesale")
class Wholesale(Namespace):
    """The restaurants, their standing orders and contracts, and their messages."""


@Layer("cafe")
class Cafe(Namespace):
    """The café's sales, its forecast, its leftovers and tomorrow's specials."""


@Layer("production")
class Production(Namespace):
    """The products, their recipes, the night's bake sheet and the delivery runs."""


@Layer("purchasing")
class Purchasing(Namespace):
    """Suppliers' invoices, ingredient prices and the margins they leave."""


@Layer("allergens")
class Allergens(Namespace):
    """What each ingredient declares, the labels it gives and the notices."""


@Layer("drafts")
class Drafts(Namespace):
    """The agents' drafts, waiting for a person to confirm or reject them."""
