"""Pure splitter-size helpers for collapsible workspace side panels."""


def collapse_side_panel_sizes(sizes, index, collapsed_width):
    """Return three splitter sizes with one side collapsed into the center."""
    result = list(sizes)
    current_width = result[index]
    released = max(0, current_width - collapsed_width)
    result[index] = min(current_width, collapsed_width)
    result[1] += released
    return result


def expand_side_panel_sizes(sizes, index, target_width):
    """Return three splitter sizes restoring one side from the center first."""
    result = list(sizes)
    current_width = result[index]
    needed = max(0, target_width - current_width)
    recovered = min(needed, max(0, result[1]))
    result[index] = current_width + recovered
    result[1] -= recovered
    return result
