from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Generic, Protocol, TypeVar

T = TypeVar("T")


class Term(Protocol, Generic[T]):
    kind: str

    def to_dict(self) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ConstantTerm(Generic[T]):
    value: T
    kind: str = "constant"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}


@dataclass(frozen=True)
class StepByIndexTerm(Generic[T]):
    steps: tuple[tuple[int, T], ...]
    kind: str = "step_by_index"

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("steps must not be empty")
        indexes = [i for i, _ in self.steps]
        if indexes[0] != 0:
            raise ValueError("first step index must be 0")
        if indexes != sorted(indexes):
            raise ValueError("step indexes must be ascending")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "steps": [{"index": i, "value": v} for i, v in self.steps]}


@dataclass(frozen=True)
class DateRangeTerm(Generic[T]):
    ranges: tuple[tuple[date, date, T], ...]
    kind: str = "date_range"

    def __post_init__(self) -> None:
        if not self.ranges:
            raise ValueError("ranges must not be empty")
        for start, end, _ in self.ranges:
            if start > end:
                raise ValueError("range start must be <= end")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ranges": [
                {"start_date": start.isoformat(), "end_date": end.isoformat(), "value": value}
                for start, end, value in self.ranges
            ],
        }


@dataclass(frozen=True)
class FormulaTerm(Generic[T]):
    formula: str
    inputs: dict[str, Any]
    kind: str = "formula"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "formula": self.formula, "inputs": self.inputs}


AnyTerm = ConstantTerm[Any] | StepByIndexTerm[Any] | DateRangeTerm[Any] | FormulaTerm[Any]


def term_from_dict(data: dict[str, Any]) -> AnyTerm:
    kind = data["kind"]
    if kind == "constant":
        return ConstantTerm(data["value"])
    if kind == "step_by_index":
        return StepByIndexTerm(tuple((int(item["index"]), item["value"]) for item in data["steps"]))
    if kind == "date_range":
        return DateRangeTerm(
            tuple(
                (date.fromisoformat(item["start_date"]), date.fromisoformat(item["end_date"]), item["value"])
                for item in data["ranges"]
            )
        )
    if kind == "formula":
        return FormulaTerm(formula=data["formula"], inputs=dict(data.get("inputs", {})))
    raise ValueError(f"unknown term kind: {kind}")
