from types import SimpleNamespace

from corio import Path
from corio.shell.dsl import arg, shell
from xah.toolsets.base.input import Input
from xah.toolsets.base.output import Output, OutputString
from xah.toolsets.base.projection.base import InputOutputBase
from xah.toolsets.fs.edit import Edit, FileEditOutput
from xah.toolsets.fs.read import FileReadOutput, Read, ReadLineData
from xah.toolsets.fs.read_line import ReadLine, ReadLineOutput
from xah.toolsets.fs.search import Search, SearchContentOutput, SearchFilesOutput, SearchMatch, SearchMatchGroup
from xah.toolsets.management.activate import Activate
from xah.toolsets.web.fetch import Fetch, FetchOutput
from xah.toolsets.web.search import Search as WebSearch
from xah.toolsets.web.research import Depth, Input as ResearchInput, ResearchOutput
from xah.toolsets.web.base import FetchResult
from xah.toolsets.python.pip import Pip, PipOutput
from xah.toolsets.python.run import PythonRunOutput, Run as PythonRun
from xah.toolsets.python.run_code import RunCode, RunCodeOutput
from xah.toolsets.python.test import Test as PythonTest, TestOutput as PythonTestOutput
from xah.toolsets.shell.run import Run as ShellRun, ShellOutput
from xah.toolsets.terminal.kill import Kill, KillOutput
from xah.toolsets.terminal.status import Status, StatusOutput
from xah.toolsets.terminal.terminal import Terminal, TerminalStatus


def projection_request(input_model, tool_name, status="completed", cwd=None):
    input_model.request = SimpleNamespace(tool_name=tool_name, raw_input={}, cwd=cwd)
    return SimpleNamespace(tool_name=tool_name, status=status, input=input_model, cwd=cwd)


def test_code_blocks_use_safe_fences_and_language_only_on_opening_fence():
    assert InputOutputBase.code_block("```", language="python") == "````python\n```\n````"

def test_activate_projection_identifies_selected_toolsets():
    reason = "Run and inspect code."
    input_model = Activate.input.model_validate(
        {"ids": ["Files", "Python"], "reason": reason}
    )
    content = input_model.content[0].content.text

    assert all(toolset_id in input_model.title for toolset_id in ("Files", "Python"))
    assert all(toolset_id in content for toolset_id in ("Files", "Python"))
    assert reason in content


def test_default_structured_output_projects_json():
    class ExampleOutput(Output):
        value: str

    input_model = Input()
    input_model.request = SimpleNamespace(tool_name="Example", raw_input={}, cwd=None)
    output = ExampleOutput(value="result")
    output.request = SimpleNamespace(
        tool_name="Example",
        status="completed",
        input=input_model,
        cwd=None,
        serialized_output='{"value":"result"}',
    )

    result = output.projection

    assert result.status == "completed"
    assert result.content[0].content.text == f"```json\n{output.serialized_text}\n```"


def test_string_outputs_project_their_content():
    input_model = Input()
    request = projection_request(input_model, "Search")
    output = OutputString(output="a.py\nb.py")
    output.request = request

    result = output.projection

    assert result.content[0].content.text == "a.py\nb.py"


def test_file_edit_output_projects_absolute_diff_and_location():
    input_model = Edit.input.model_validate(
        {"path": "file.txt", "old_text": "old", "new_text": "new"}
    )
    request = projection_request(input_model, "Files-Edit", cwd="/tmp")
    output = FileEditOutput(
        path=Path("file.txt"),
        old_text="old",
        new_text="new",
        occurrence_count=1,
        location_line=2,
    )
    output.request = request

    result = output.projection

    assert result.content == output.content
    assert result.status == "completed"
    assert result.content[0].type == "diff"
    assert result.content[0].old_text == "old"
    assert result.content[0].new_text == "new"
    assert result.content[0].path == "/tmp/file.txt"
    assert result.locations[0].path == "/tmp/file.txt"
    assert result.locations[0].line == 2


def test_file_read_output_projects_diff_and_zero_based_line_location():
    input_model = Read.input.model_validate({"path": "file.txt", "offset": 4})
    request = projection_request(input_model, "Files-Read", cwd="/tmp")
    output = FileReadOutput(
        path=Path("file.txt"),
        lines=[ReadLineData(number=5, text="content")],
        number_width=1,
    )
    output.request = request

    result = output.projection

    assert result.content[0].type == "diff"
    assert result.content[0].old_text == ""
    assert result.content[0].new_text == "5:content"
    assert result.locations[0].path == "/tmp/file.txt"
    assert result.locations[0].line == 4


def test_empty_file_read_output_projects_without_a_line_location():
    input_model = Read.input.model_validate({"path": "empty.txt", "offset": -1})
    request = projection_request(input_model, "Files-Read", cwd="/tmp")
    output = FileReadOutput(path=Path("empty.txt"), lines=[], number_width=1)
    output.request = request

    result = output.projection

    assert result.locations[0].path == "/tmp/empty.txt"
    assert result.locations[0].line is None


def test_file_read_line_projects_file_path_and_line_location():
    input_model = ReadLine.input.model_validate(
        {"path": "long.py", "line_number": 8}
    )
    request = projection_request(input_model, "Files-Read-Line", cwd="/tmp")
    input_projection = input_model.projection
    output = ReadLineOutput(line_number=8, text="long line")
    output.request = request
    output_projection = output.projection

    assert input_projection.locations[0].path == "/tmp/long.py"
    assert input_projection.locations[0].line == 7
    assert output_projection.locations[0].line == 7
def test_file_search_output_projects_match_line_locations():
    input_model = Search.input.model_validate({"path": "src", "regex": "class"})
    request = projection_request(input_model, "Files-Search", cwd="/tmp")
    output = SearchContentOutput(
        root=Path("/tmp/src"),
        pattern="class",
        groups=[
            SearchMatchGroup(
                path=Path("file.py"),
                matches=[SearchMatch(line_number=12, line_text="class A")],
            ),
            SearchMatchGroup(
                path=Path("other.py"),
                matches=[SearchMatch(line_number=4, line_text="class B")],
            ),
        ],
    )
    output.request = request

    locations = output.projection.locations

    projected_text = output.projection.content[0].content.text
    assert "file.py" in projected_text
    assert "12:class A" in projected_text
    assert "other.py" in projected_text
    assert "4:class B" in projected_text
    assert [(location.path, location.line) for location in locations] == [
        ("/tmp/src/file.py", 11),
        ("/tmp/src/other.py", 3),
    ]


def test_empty_file_search_outputs_render_nonempty_content():
    input_model = Search.input.model_validate({"regex": "missing"})
    request = projection_request(input_model, "Files-Search")
    output = SearchContentOutput(root=Path("/tmp"), pattern="missing", groups=[])
    output.request = request

    listing = SearchFilesOutput(path=Path("/tmp"), root=Path("/tmp"), files=[])
    listing.request = request

    assert output.groups == []
    assert output.projection.content[0].content.text
    assert listing.files == []
    assert listing.projection.content[0].content.text

def test_web_search_input_projects_query():
    input_model = WebSearch.input.model_validate({"query": "python projections"})
    input_model.request = SimpleNamespace(tool_name="Web-Search", raw_input={}, cwd=None)
    result = input_model.projection

    assert result.content[0].content.text == "Query: python projections"


def test_web_fetch_input_projects_urls():
    input_model = Fetch.input.model_validate({"urls": ["https://example.com"]})
    input_model.request = SimpleNamespace(tool_name="Web-Fetch", raw_input={}, cwd=None)
    result = input_model.projection

    assert result.content[0].content.text == "https://example.com"


def test_web_fetch_output_projects_markdown_and_resource_link():
    input_model = Fetch.input.model_validate({"urls": ["https://example.com"]})
    request = projection_request(input_model, "Web-Fetch")
    output = FetchOutput(
        results=[
            FetchResult(
                url="https://example.com",
                title="Example",
                text="# Page content",
            )
        ]
    )
    output.request = request

    result = output.projection

    assert result.content[0].content.text == "## Example\n\n# Page content"
    assert result.content[1].content.type == "resource_link"
    assert result.content[1].content.uri == "https://example.com"
    assert result.content[1].content.name == "Example"


def test_research_output_projects_answer_and_source_links():
    input_model = ResearchInput(depth=Depth.QUICK, prompt="research question")
    request = projection_request(input_model, "Web-Research")
    output = ResearchOutput(
        urls=["https://example.com"],
        answer="A concise answer.",
        desc="Research summary.",
    )
    output.request = request

    result = output.projection

    assert result.content[0].content.text == "Research summary."
    assert result.content[1].content.text == "A concise answer."
    assert result.content[2].content.type == "resource_link"
    assert result.content[2].content.uri == "https://example.com"


def test_terminal_tools_select_specific_output_subclasses():
    assert Pip.Output is PipOutput
    assert PythonRun.Output is PythonRunOutput
    assert RunCode.Output is RunCodeOutput
    assert PythonTest.Output is PythonTestOutput
    assert ShellRun.Output is ShellOutput
    assert Kill.Output is KillOutput
    assert Status.Output is StatusOutput


def test_terminal_output_projects_terminal_summary_and_status_title(tmp_path):
    output_path = Path(tmp_path) / "terminal.log"
    output_path.write_text("printed")
    terminal = Terminal(
        id="abcd",
        expression=shell.python(-arg.c + "print('ok')"),
        cwd=str(tmp_path),
        output_path=output_path,
        status=TerminalStatus.COMPLETED,
        output_size=7,
        exit_code=0,
    )
    input_model = RunCode.input.model_validate({"code": "print('ok')"})
    request = projection_request(input_model, "Python-RunCode")
    output = RunCodeOutput(terminal=terminal, cwd_default=Path(tmp_path))
    output.request = request

    result = output.projection

    assert RunCode.Output is RunCodeOutput
    assert len(result.content) == 3
    assert result.content[0].type == "content"
    assert "Terminal `abcd`" in result.content[0].content.text
    assert result.content[1].content.text == "```python\nprint('ok')\n```"
    assert result.content[2].type == "diff"
    assert result.content[2].path == str(output_path)
    assert result.content[2].new_text == "printed"
    assert "printed" in output.agent
    assert result.locations[0].path == str(output_path)
    assert result.status == "completed"
