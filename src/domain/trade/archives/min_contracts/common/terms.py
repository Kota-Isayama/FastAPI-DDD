from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Term(Generic[T]):
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class ConstantTerm(Term[T]):
    value: T

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "constant", "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstantTerm[T]":
        return cls(value=data["value"])


@dataclass(frozen=True)
class StepByIndexTerm(Term[T]):
    steps: tuple[tuple[int, T], ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("steps must not be empty")
        indexes = [x[0] for x in self.steps]
        if indexes != sorted(indexes):
            raise ValueError("step indexes must be ascending")
        if indexes[0] != 0:
            raise ValueError("first step index must be 0")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "step_by_index", "steps": list(self.steps)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepByIndexTerm[T]":
        return cls(steps=tuple((int(idx), value) for idx, value in data["steps"]))


def term_from_dict(data: dict[str, Any]) -> Term[Any]:
    kind = data["kind"]
    if kind == "constant":
        return ConstantTerm.from_dict(data)
    if kind == "step_by_index":
        return StepByIndexTerm.from_dict(data)
    raise ValueError(f"unknown term kind: {kind}")
