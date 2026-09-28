from app.components import StockRoom
from app.repositories import Items
from opendataframework.component import McpTool, McpToolsProtocol

# Deliberately builds Items/StockRoom directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/table_view/test_books.py.


def test_low_stock_uses_each_items_own_reorder_level_by_default():
    stock_room = StockRoom(Items())

    result = stock_room.low_stock()

    assert {item["name"] for item in result} == {"Packing tape", "Shipping labels"}


def test_low_stock_threshold_overrides_reorder_level():
    stock_room = StockRoom(Items())

    result = stock_room.low_stock(threshold=30)

    assert {item["name"] for item in result} == {
        "Packing tape",
        "Bubble wrap",
        "Shipping labels",
    }


def test_stock_room_implements_mcp_tools_protocol():
    stock_room = StockRoom(Items())

    assert isinstance(stock_room, McpToolsProtocol)
    tools = stock_room.mcp_tools()
    assert [t.name for t in tools] == ["low_stock"]
    assert isinstance(tools[0], McpTool)
    assert tools[0].handler() == stock_room.low_stock()
