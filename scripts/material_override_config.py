"""Validation shared by the sprite pipeline and Blender render worker."""

import math


def validate_overrides(value, field):
    if value is None:
        return None
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{field} must be a non-empty object")
    result = {}
    for name, entries in value.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{field} requires non-empty names")
        if not isinstance(entries, dict) or not entries:
            raise ValueError(f"{field}.{name} must be a non-empty object")
        result[name] = {}
        for key, entry in entries.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{field}.{name} requires non-empty names")
            if field == "materialOverrides":
                if not isinstance(entry, str) or not entry.strip():
                    raise ValueError(f"{field}.{name}.{key} must name a material")
            elif field == "colorOverrides":
                if (not isinstance(entry, list) or len(entry) not in (3, 4)
                        or any(isinstance(v, bool) or not isinstance(v, (int, float))
                               or not math.isfinite(v) or not 0 <= v <= 1 for v in entry)):
                    raise ValueError(f"{field}.{name}.{key} must be RGB or RGBA numbers in [0, 1]")
                entry = [*entry, 1.0] if len(entry) == 3 else list(entry)
            else:
                raise ValueError(f"Unknown override field: {field}")
            result[name][key] = entry
    return result
