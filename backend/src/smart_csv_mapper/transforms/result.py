"""A transform either returns a value or explains why it couldn't. It never raises."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Ok:
    value: str


@dataclass(frozen=True)
class Err:
    reason: str


Result = Ok | Err
