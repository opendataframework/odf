"""Stock-room component exposing a custom MCP tool for the custom-mcp-tool example."""

from opendataframework import Analytics, Component
from opendataframework.component import McpTool

from app.repositories import Items


@Analytics
@Component
class StockRoom:
    """Wraps ``Items`` with a low-stock query exposed as a custom MCP tool.

    Isolates the concept this example demonstrates: a component's own
    ``mcp_tools()`` can accept a typed parameter the caller controls per
    call (here, an optional ``threshold`` override) — something the six
    fixed tools can't do as cleanly, since ``execute_task()`` takes no
    arguments at all and ``query_repository()``'s filters are
    substring-only, not numeric comparisons.
    """

    def __init__(self, items: Items) -> None:
        """Store the items source to query.

        Args:
            items: The repository to scan for low-stock items.
        """
        self.items = items

    def low_stock(self, threshold: int | None = None) -> list[dict]:
        """Return items at or below their reorder level (or an explicit override).

        Args:
            threshold: If given, used instead of each item's own
                ``reorder_level`` as the cutoff.

        Returns:
            A list of ``{"name", "quantity", "reorder_level"}`` dicts, one
            per item whose quantity is at or below the cutoff.
        """
        return [
            {"name": item.name, "quantity": item.quantity, "reorder_level": item.reorder_level}
            for item in self.items.all()
            if item.quantity <= (threshold if threshold is not None else item.reorder_level)
        ]

    def mcp_tools(self) -> list[McpTool]:
        """Expose ``low_stock`` as a custom MCP tool, registered as ``stock-room.low_stock``."""
        return [
            McpTool(
                name="low_stock",
                description=(
                    "List items at or below their reorder level, optionally "
                    "overriding the cutoff with an explicit threshold."
                ),
                handler=self.low_stock,
            )
        ]
