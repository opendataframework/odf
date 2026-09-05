"""Entities for the data-engineering example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Reading:
    """A single sensor reading.

    Attributes:
        id: Primary key, ``None`` until ``Readings.save()`` inserts the row
            and sets it to the row's autoincremented primary key.
        sensor: Name of the sensor that produced the reading.
        celsius: The measured temperature, in degrees Celsius.
    """

    id: int | None
    sensor: str
    celsius: float
