import pytest

from xah.toolsets.fs.similarity import get_similarity


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("a", "a", 100),
        ("", "", 100),
        ("abc", "xyz", 0),
    ],
)
def test_similarity_scores_identical_and_unrelated_text(old, new, expected):
    assert get_similarity(old, new) == expected
