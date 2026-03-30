_ABBREVIATIONS = {
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "sr",
    "jr",
    "vs",
    "etc",
    "inc",
    "ltd",
    "dept",
    "approx",
    "est",
    "fig",
    "no",
    "vol",
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
    "st",
    "ave",
    "blvd",
}


def _is_sentence_end(word):
    """Return True if word ends a sentence.

    Rejects ellipses (two or more consecutive trailing periods), single-letter
    initials, words with internal periods (abbreviations like e.g. or U.S.),
    and known title/common abbreviations.
    """
    if not word.endswith("."):
        return False
    # Ellipsis: two or more trailing periods
    if word.endswith(".."):
        return False
    core = word[:-1]  # strip the single trailing period
    # Single letter: initial (A.) or lone abbreviation unit (U.)
    if len(core) <= 1:
        return False
    # Internal period: e.g., U.S., i.e.
    if "." in core:
        return False
    # Known abbreviation
    if core.lower() in _ABBREVIATIONS:
        return False
    return True


def chunk_text(text, max_len=800, max_sentences=2):
    """Split text into chunks ending on sentence boundaries.

    A chunk ends after max_sentences sentence-ending periods are encountered,
    or at max_len words if that threshold is not reached first, or at end of file.
    Ellipses and mid-word abbreviations are not counted as sentence endings.

    Args:
        text: The input string to split.
        max_len: Maximum number of words per chunk (default 800).
        max_sentences: Number of sentence-ending periods before splitting (default 2).

    Returns:
        A list of strings, each representing one chunk.
    """
    words = text.split()
    chunks = []
    current = []
    period_count = 0

    for w in words:
        current.append(w)
        if _is_sentence_end(w):
            period_count += 1
        if period_count >= max_sentences or len(current) >= max_len:
            chunks.append(" ".join(current))
            current = []
            period_count = 0

    if current:
        chunks.append(" ".join(current))

    return chunks
