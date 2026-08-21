from enum import Enum


class StatusMessageType(str, Enum):
    """Canonical severity vocabulary for InSAR Explorer status messages."""

    INFO = "info"
    INSTRUCTION = "instruction"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# Deprecated rendering-boundary compatibility only. Active plugin emitters must not use these.
_LEGACY_STATUS_ALIASES = {
    "": StatusMessageType.INFO.value,
    "i": StatusMessageType.INFO.value,
    "t": StatusMessageType.INSTRUCTION.value,
    "done": StatusMessageType.SUCCESS.value,
    "w": StatusMessageType.WARNING.value,
    "e": StatusMessageType.ERROR.value,
    "error": StatusMessageType.ERROR.value,
    "c": StatusMessageType.ERROR.value,
}


def normalize_status_message_type(value):
    """Return one canonical status severity string for legacy or current input."""
    if isinstance(value, StatusMessageType):
        return value.value
    text = str(value or "").strip().lower()
    if text in {item.value for item in StatusMessageType}:
        return text
    return _LEGACY_STATUS_ALIASES.get(text, StatusMessageType.INFO.value)


STATUS_INFO = StatusMessageType.INFO.value
STATUS_INSTRUCTION = StatusMessageType.INSTRUCTION.value
STATUS_SUCCESS = StatusMessageType.SUCCESS.value
STATUS_WARNING = StatusMessageType.WARNING.value
STATUS_ERROR = StatusMessageType.ERROR.value
