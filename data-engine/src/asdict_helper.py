from datetime import datetime

def _asdict_minus_context_data(record: object) -> dict:
    """Helper to convert dataclass to dict, excluding 'context_data' and converting datetime."""
    result = {}
    if hasattr(record, "__slots__"):
        for key in record.__slots__:
            if key == "context_data":
                continue
            val = getattr(record, key)
            if isinstance(val, datetime):
                val = val.isoformat()
            result[key] = val
    return result
