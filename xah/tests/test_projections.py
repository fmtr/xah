from xah.toolsets.base.output import OutputString
from xah.toolsets.base.input import Input
from xah.toolsets.fs.edit import Edit, FileEditOutput
from xah.toolsets.fs.read import FileReadOutput, Read
from xah.toolsets.fs.search import Search
from xah.toolsets.fs.write import Write
from xah.toolsets.kb.list import List as KnowledgeList
from xah.toolsets.skills.load import Load
from xah.toolsets.web.fetch import Fetch
from xah.toolsets.web.search import Search as WebSearch


def test_tools_expose_their_local_input_type():
    tools = (Search, Write, Edit, KnowledgeList)

    for tool in tools:
        assert tool.input is not Input
        assert tool.input.__module__ == tool.__module__


def test_string_outputs_project_their_content():
    output = OutputString(output="a.py\nb.py")
    request = type("Request", (), {"tool_name": "Search", "status": "completed"})()

    output.request = request
    result = output.projection

    assert result.content[0].content.text == "a.py\nb.py"


def test_file_edit_output_projects_diff():
    output = FileEditOutput(output="Edited file.txt")
    request = type(
        "Request",
        (),
        {
            "tool_name": "Files-Edit",
            "status": "completed",
            "input": Edit.input.model_validate(
                {"path": "file.txt", "old_text": "old", "new_text": "new"}
            ),
        },
    )()

    output.request = request
    result = output.projection

    assert result.content[0].type == "diff"
    assert result.content[0].old_text == "old"
    assert result.content[0].new_text == "new"


def test_file_read_output_projects_content_diff():
    output = FileReadOutput(output="1:content")
    request = type(
        "Request",
        (),
        {
            "tool_name": "Files-Read",
            "status": "completed",
            "input": Read.input.model_validate({"path": "file.txt"}),
        },
    )()

    output.request = request
    result = output.projection

    assert result.content[0].type == "diff"
    assert result.content[0].old_text == ""
    assert result.content[0].new_text == "1:content"


def test_skills_load_input_titles_skill_ids():
    input = Load.input.model_validate({"skill_ids": ["python/style", "python/tests"]})
    request = type("Request", (), {"tool_name": "Skills-Load"})()

    input.request = request
    assert input.projection.title == "python/style and python/tests"


def test_web_search_input_projects_query():
    input = WebSearch.input.model_validate({"query": "python projections"})
    request = type("Request", (), {"tool_name": "Web-Search"})()
    input.request = request
    result = input.projection

    assert result.title == "Search web for python projections"
    assert result.content[0].content.text == "Query: python projections"


def test_web_fetch_input_projects_urls():
    input = Fetch.input.model_validate({"urls": ["https://example.com"]})
    request = type("Request", (), {"tool_name": "Web-Fetch"})()
    input.request = request
    result = input.projection

    assert result.title == "Fetching https://example.com"
    assert result.content[0].content.text == "https://example.com"
