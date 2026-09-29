from xah.toolsets.fs.similarity import get_similarity


def test_similarity_returns_a_number():
    assert get_similarity("a", "a") == 100
    assert get_similarity("", "") == 100
