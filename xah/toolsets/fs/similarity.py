from difflib import SequenceMatcher
from typing import ClassVar


class SimilarityValidator:
    SIMILARITY_MIN_LENGTH: ClassVar[int] = 250
    SIMILARITY_MIN_PERCENT: ClassVar[int] = 80

    def similarity_warnings(
        self,
        before: str,
        after: str,
        message: str,
    ) -> list[str]:
        if min(len(before), len(after)) < self.SIMILARITY_MIN_LENGTH:
            return []

        similarity = get_similarity(before, after)
        if similarity < self.SIMILARITY_MIN_PERCENT:
            return []

        return [message.format(similarity=similarity)]


def get_similarity(old: str, new: str) -> int:
    return round(SequenceMatcher(None, old, new).ratio() * 100)
