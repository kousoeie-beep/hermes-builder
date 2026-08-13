from __future__ import annotations


def reject_excessive_nesting(text: str, *, maximum: int = 100) -> None:
    """Reject deeply nested JSON before parser/version-specific recursion behavior."""
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > maximum:
                raise ValueError(f"JSONのnestingが深すぎます（上限{maximum}階層）")
        elif character in "]}":
            depth = max(0, depth - 1)
