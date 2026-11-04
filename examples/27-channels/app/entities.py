"""Entities for the channels example: a help desk's messages and tickets."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Message:
    """A message from a customer, or one the help desk sent them.

    Attributes:
        id: Primary key.
        sent_at: When it was sent, as a Unix time.
        customer: The customer on the other side.
        direction: ``"in"``, from the customer, or ``"out"``, to them.
        sender: The customer's email address.
        text: What it says.
    """

    id: int
    sent_at: float
    customer: str
    direction: str
    sender: str
    text: str


@Entity
@dataclass
class Ticket:
    """What the help desk is doing about a customer's messages, with the reply it'll send.

    Attributes:
        id: Primary key.
        opened_at: When it was opened, in ISO 8601.
        customer: The customer it's for.
        body: The ticket as the help desk reads it, in Markdown.
        reply: The reply sending it sends.
        status: ``"open"`` until its reply is sent, then ``"answered"``.
    """

    id: int
    opened_at: str
    customer: str
    body: str
    reply: str
    status: str = "open"
