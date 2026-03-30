# saskan_lore/analyzer/character_counter.py
"""Count character name occurrences across text chunks. Stub."""

from collections import Counter


def count_characters(chunks: list[str], character_list: list[str]) -> Counter:
    """Return a Counter of how many chunks each character name appears in."""
    character_counts: Counter = Counter()
    for chunk in chunks:
        for name in character_list:
            if name in chunk:
                character_counts[name] += 1
    return character_counts
