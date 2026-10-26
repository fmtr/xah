import asyncio

from corio import Path

from xah.tests.test_fs import context, make
from xah.toolsets.fs.read import Read
from xah.toolsets.fs.read_line import ReadLine


def test_read_supports_negative_offsets(tmp_path):
    path = Path(tmp_path / "lines.txt")
    path.write_text("one\ntwo\nthree\nfour\n")
    ctx = context(tmp_path)

    result = asyncio.run(make(Read, ctx, path="lines.txt", offset=-2, limit=2).run())

    assert result == "3:three\n4:four"


def test_read_line_pages_long_lines(tmp_path, monkeypatch):
    path = Path(tmp_path / "long.txt")
    path.write_text("0123456789abcdefghijklmnopqrstuvwxyz" * 400 + "\n")
    ctx = context(tmp_path)

    tool = make(
        ReadLine,
        ctx,
        path="long.txt",
        line_number=1,
        offset=10,
        limit=10,
    )
    feedback = []
    monkeypatch.setattr(ReadLine, "feedback", lambda self, message: feedback.append(message))

    result = asyncio.run(tool.run())

    assert result == "1:abcdefghij"
    assert feedback == ["The line contains 14380 characters beyond the displayed range."]
