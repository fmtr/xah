from xah.toolsets.base.projection import Projection as BaseProjection
from xah.toolsets.fs.edit import Edit
from xah.toolsets.fs.mkdir import Mkdir
from xah.toolsets.fs.read import Read
from xah.toolsets.fs.read_line import ReadLine
from xah.toolsets.fs.remove import Remove
from xah.toolsets.fs.search import Search
from xah.toolsets.fs.write import Write
from xah.toolsets.web.fetch import Fetch
from xah.toolsets.web.search import Search as WebSearch
from xah.toolsets.skills.load import Load


def test_tools_expose_their_local_projection_type():
    tools = (Read, ReadLine, Write, Edit, Search, Mkdir, Remove)

    for tool in tools:
        assert tool.Projection is not BaseProjection
        assert tool.Projection.__module__ == tool.__module__


def test_search_projection_returns_regular_output():
    projection = Search.Projection(
        tool_cls=Search,
        toolset_cls=type("Toolset", (), {"get_name": staticmethod(lambda _: "Search")}),
        raw_input={"path": ".", "glob": "*.py"},
        raw_output="a.py\nb.py",
        status="completed",
    )

    result = projection.progress()

    assert result.content[0].content.text == "a.py\nb.py"
    assert "Tree:" not in result.content[0].content.text


def test_skills_load_projection_titles_skill_ids():
    projection = Load.Projection(
        tool_cls=Load,
        toolset_cls=type("Toolset", (), {"get_name": staticmethod(lambda _: "Skills-Load")}),
        raw_input={"skill_ids": ["python/style", "python/tests"]},
    )

    assert projection.title() == "python/style and python/tests"


def test_web_search_projection_mirrors_web_projection_map():
    projection = WebSearch.Projection(
        tool_cls=WebSearch,
        toolset_cls=type("Toolset", (), {"get_name": staticmethod(lambda _: "Web-Search")}),
        raw_input={"query": "python projections"},
    )

    result = projection.start()

    assert result.title == "Search web for python projections"
    assert result.content[0].content.text == "Query: python projections"


def test_web_fetch_projection_mirrors_web_projection_map():
    projection = Fetch.Projection(
        tool_cls=Fetch,
        toolset_cls=type("Toolset", (), {"get_name": staticmethod(lambda _: "Web-Fetch")}),
        raw_input={"urls": ["https://example.com"]},
    )

    result = projection.start()

    assert result.title == "Fetching https://example.com"
    assert result.content[0].content.text == "https://example.com"

    projection = Fetch.Projection(
        tool_cls=Fetch,
        toolset_cls=type("Toolset", (), {"get_name": staticmethod(lambda _: "Web-Fetch")}),
        raw_input={"urls": ["https://one.example", "https://two.example"]},
    )
    result = projection.start()

    assert result.title == "Fetching 2 URLs"
    assert result.content[0].content.text == "https://one.example\nhttps://two.example"


def test_write_projection_uses_signature_content():
    projection = Write.Projection(
        tool_cls=Write,
        toolset_cls=type("Toolset", (), {"get_name": staticmethod(lambda _: "Write")}),
        raw_input={"path": "file.txt", "content": "new content"},
        cwd=".",
    )

    assert projection.new_text == "new content"
