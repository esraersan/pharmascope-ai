"""Deterministic leakage-resistant splits for protein-ligand records."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Sequence

from .schema import ProteinLigandRecord


@dataclass(frozen=True)
class SplitIndices:
    """Indices assigned to train, validation, and test partitions."""

    train: tuple[int, ...]
    validation: tuple[int, ...]
    test: tuple[int, ...]

    def as_dict(self) -> dict[str, list[int]]:
        return {
            "train": list(self.train),
            "validation": list(self.validation),
            "test": list(self.test),
        }


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _validate_fractions(validation_fraction: float, test_fraction: float) -> None:
    if not 0.0 <= validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in [0, 1)")
    if not 0.0 <= test_fraction < 1.0:
        raise ValueError("test_fraction must be in [0, 1)")
    if validation_fraction + test_fraction >= 1.0:
        raise ValueError("validation_fraction + test_fraction must be less than 1")


def _connected_components(
    records: Sequence[ProteinLigandRecord],
) -> list[tuple[int, ...]]:
    groups: dict[tuple[str, str], int] = {}
    disjoint = _DisjointSet(len(records))
    for index, record in enumerate(records):
        identifiers = (
            ("protein_family", record.protein_family),
            ("ligand_group", record.ligand_group),
        )
        for identifier in identifiers:
            if identifier in groups:
                disjoint.union(index, groups[identifier])
            else:
                groups[identifier] = index

    components: dict[int, list[int]] = {}
    for index in range(len(records)):
        components.setdefault(disjoint.find(index), []).append(index)
    return [tuple(indices) for indices in components.values()]


def _component_key(
    component: Iterable[int],
    records: Sequence[ProteinLigandRecord],
    seed: int,
) -> str:
    record_ids = "\x1f".join(sorted(records[index].record_id for index in component))
    return hashlib.sha256(f"{seed}\x1e{record_ids}".encode()).hexdigest()


def deterministic_group_split(
    records: Sequence[ProteinLigandRecord],
    *,
    validation_fraction: float = 0.1,
    test_fraction: float = 0.2,
    seed: int = 0,
) -> SplitIndices:
    """Split connected family/group components deterministically.

    Records are joined when they share a protein family *or* ligand group.
    Entire connected components are assigned to one partition, guaranteeing
    that neither grouping identifier appears in multiple partitions. Exact
    requested proportions are not always possible when components are large.
    """

    _validate_fractions(validation_fraction, test_fraction)
    if not records:
        raise ValueError("records must not be empty")
    if len({record.record_id for record in records}) != len(records):
        raise ValueError("record_id values must be unique")

    components = _connected_components(records)
    requested_nonempty = 1 + int(validation_fraction > 0) + int(test_fraction > 0)
    if len(components) < requested_nonempty:
        raise ValueError(
            "not enough independent family/group components for requested splits"
        )

    components.sort(key=lambda item: _component_key(item, records, seed))
    partition_names = ["train"]
    fractions = {"train": 1.0 - validation_fraction - test_fraction}
    if validation_fraction > 0:
        partition_names.append("validation")
        fractions["validation"] = validation_fraction
    if test_fraction > 0:
        partition_names.append("test")
        fractions["test"] = test_fraction

    assignments: dict[str, list[int]] = {name: [] for name in partition_names}
    remaining = list(components)

    # Seed every requested partition, smallest target first, so no requested
    # holdout is silently empty. The hash ordering keeps this reproducible.
    for name in sorted(partition_names, key=lambda item: fractions[item]):
        component = remaining.pop(0)
        assignments[name].extend(component)

    targets = {name: fractions[name] * len(records) for name in partition_names}
    for component in remaining:
        name = max(
            partition_names,
            key=lambda item: (
                targets[item] - len(assignments[item]),
                -partition_names.index(item),
            ),
        )
        assignments[name].extend(component)

    return SplitIndices(
        train=tuple(sorted(assignments["train"])),
        validation=tuple(sorted(assignments.get("validation", []))),
        test=tuple(sorted(assignments.get("test", []))),
    )


def assert_group_isolation(
    records: Sequence[ProteinLigandRecord], split: SplitIndices
) -> None:
    """Raise when indices overlap, are incomplete, or leak grouping IDs."""

    partitions = {
        "train": split.train,
        "validation": split.validation,
        "test": split.test,
    }
    flattened = [index for indices in partitions.values() for index in indices]
    if sorted(flattened) != list(range(len(records))):
        raise ValueError("split indices must cover each record exactly once")

    owners: dict[tuple[str, str], str] = {}
    for partition, indices in partitions.items():
        for index in indices:
            record = records[index]
            for identifier in (
                ("protein_family", record.protein_family),
                ("ligand_group", record.ligand_group),
            ):
                previous = owners.setdefault(identifier, partition)
                if previous != partition:
                    raise ValueError(
                        f"{identifier[0]} {identifier[1]!r} leaks between "
                        f"{previous} and {partition}"
                    )
