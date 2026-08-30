def exec_qt(obj, *args, **kwargs):
    """Execute a Qt object using the modern API with a Qt5 fallback."""
    execute = getattr(obj, "exec", None)
    if callable(execute):
        return execute(*args, **kwargs)
    return getattr(obj, "exec_")(*args, **kwargs)
