"""Small, Qt-free change tracking primitives for runtime settings."""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, Mapping


@dataclass(frozen=True)
class SettingsChangeSet:
    """Describe settings domains and properties changed by one logical update."""

    domains: FrozenSet[str] = frozenset()
    properties: Mapping[str, FrozenSet[str]] = field(default_factory=dict)

    @classmethod
    def for_properties(cls, domain: str, properties: Iterable[str]):
        """Build a change set for one domain."""
        names = frozenset(properties)
        return cls(frozenset((domain,)) if names else frozenset(), {domain: names} if names else {})

    def merge(self, other: "SettingsChangeSet") -> "SettingsChangeSet":
        """Combine changes while de-duplicating domains and property names."""
        merged: Dict[str, FrozenSet[str]] = dict(self.properties)
        for domain, names in other.properties.items():
            merged[domain] = frozenset(merged.get(domain, frozenset())) | frozenset(names)
        return SettingsChangeSet(self.domains | other.domains, merged)
