from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Item:
    id: int | None
    name: str
    quantity: int = 0
