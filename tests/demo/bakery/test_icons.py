import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEMO_DIR = ROOT / "demo" / "bakery"
BUILT_IN_ICONS = ROOT / "src" / "odf" / "ui" / "static" / "icons"

# `add('key', draw, ...)`, the registration every icon group file uses.
REGISTERED = re.compile(r"\badd\('([a-z0-9-]+)'")


def registered(path: Path) -> set[str]:
    return set(REGISTERED.findall(path.read_text()))


BAKERY_ICONS = registered(DEMO_DIR / "icons" / "bakery.js")
BUILT_INS = set().union(*(registered(path) for path in BUILT_IN_ICONS.glob("*.js")))
LAYOUT = json.loads((DEMO_DIR / "layout.json").read_text())
USED = {
    entry["icon"] for key, entry in LAYOUT.items() if not key.startswith("_") and "icon" in entry
}


def test_the_icon_script_is_configured():
    config = (DEMO_DIR / "config.toml").read_text()

    assert 'icon-scripts = ["icons/bakery.js"]' in config


def test_every_icon_in_the_layout_exists():
    # An unknown key silently falls back to the node's type default.
    assert BAKERY_ICONS
    assert USED - BAKERY_ICONS - BUILT_INS == set()


def test_every_bakery_icon_is_used():
    assert BAKERY_ICONS - USED == set()


def test_bakery_icons_do_not_shadow_built_ins():
    assert BAKERY_ICONS & BUILT_INS == set()


def test_every_node_wears_a_bakery_icon():
    nodes = {key: entry for key, entry in LAYOUT.items() if not key.startswith("_")}

    assert {key for key, entry in nodes.items() if entry.get("icon") not in BAKERY_ICONS} == set()


def test_each_agent_has_its_own_icon():
    agents = [entry["icon"] for key, entry in LAYOUT.items() if key.startswith("agent.")]

    assert len(agents) == len(set(agents))
