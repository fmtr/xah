from difflib import SequenceMatcher


def get_similarity(old: str, new: str) -> int:
    return round(SequenceMatcher(None, old, new).ratio() * 100)
