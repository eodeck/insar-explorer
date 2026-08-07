"""Semantic range-source state for Map Settings."""

from enum import Enum


class RangeSource(Enum):
    """Describe how the current Map Settings numeric range was derived."""

    CUSTOM = "custom"
    DATA_EXTENT = "data_extent"
    STD_1 = "std_1"
    STD_2 = "std_2"
    STD_3 = "std_3"

    @property
    def display_name(self):
        """Return the concise user-facing source label."""
        return {
            RangeSource.CUSTOM: "Custom",
            RangeSource.DATA_EXTENT: "Data extent",
            RangeSource.STD_1: "1 × Std",
            RangeSource.STD_2: "2 × Std",
            RangeSource.STD_3: "3 × Std",
        }[self]

    @property
    def standard_deviations(self):
        """Return the requested standard-deviation multiplier, if any."""
        return {
            RangeSource.CUSTOM: None,
            RangeSource.DATA_EXTENT: None,
            RangeSource.STD_1: 1,
            RangeSource.STD_2: 2,
            RangeSource.STD_3: 3,
        }[self]


COMPUTED_RANGE_SOURCES = (
    RangeSource.DATA_EXTENT,
    RangeSource.STD_1,
    RangeSource.STD_2,
    RangeSource.STD_3,
)
