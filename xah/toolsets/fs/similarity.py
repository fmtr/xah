from difflib import SequenceMatcher


def get_similarity(old: str, new: str) -> int | None:
    similarity = round(SequenceMatcher(None, old, new).ratio() * 100)
    return similarity if similarity >= 80 else None
