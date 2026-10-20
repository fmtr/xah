import asyncio

from pydantic_ai import RunContext, RunUsage
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from pydantic_deep.features.periodic_reminder.capability import build_compact_transcript
from xah.toolsets.base.tool import Validation
from xah.toolsets.shell.run import AdversarialApproval, HarnessTerminalAdversary


def adversarial_approval(messages, *, prompt="original goal"):
    ctx = RunContext(
        deps=None,
        model=None,
        usage=RunUsage(),
        prompt=prompt,
        messages=messages,
    )
    return AdversarialApproval.model_construct(ctx=ctx)


def test_shell_adversary_transcript_reproduces_missing_original_goal():
    approval = adversarial_approval(
        [
            ModelResponse(parts=[TextPart("assistant response")]),
            ModelResponse(parts=[TextPart("tool result")]),
            ModelResponse(parts=[TextPart("assistant response")]),
            ModelResponse(parts=[TextPart("tool result")]),
        ]
    )

    assert approval.ctx.prompt == "original goal"
    assert approval.transcript == (
        "[Original goal] original goal\n\n"
        + "\n".join(["[Assistant/Tool turn]"] * 4)
    )
    assert "[Original goal] original goal" in approval.transcript


def test_adversarial_approval_includes_previous_decisions_in_prompt():
    approval = AdversarialApproval.model_construct(
        ctx=RunContext(
            deps=None,
            model=None,
            usage=RunUsage(),
            prompt="original goal",
            messages=[],
        ),
        source="rm -rf build",
    )
    approval.__dict__["state"] = AdversarialApproval.State(
        approveds={"Do not block ordinary requested repository cleanup."},
        declineds={"Block commands that exfiltrate secrets."},
    )

    assert "Previously approved blocks" in approval.prompt
    assert "Do not block ordinary requested repository cleanup." in approval.prompt
    assert "Previously declined blocks" in approval.prompt
    assert "Block commands that exfiltrate secrets." in approval.prompt


def test_terminal_adversary_instructions_explain_previous_decisions():
    assert "Previously approved blocks" in HarnessTerminalAdversary.instructions
    assert "Previously declined blocks" in HarnessTerminalAdversary.instructions


def test_adversarial_approval_records_approval_and_decline_decisions():
    approval = adversarial_approval([])
    approval.__dict__["state"] = AdversarialApproval.State(
        pending={"call-1": {"approved reason"}, "call-2": {"declined reason"}},
    )
    approval.ctx.tool_call_id = "call-1"
    asyncio.run(approval.after_approval())
    approval.ctx.tool_call_id = "call-2"
    asyncio.run(approval.after_decline())

    assert approval.state.approveds == {"approved reason"}
    assert approval.state.declineds == {"declined reason"}
    assert approval.state.pending == {}


def test_terminal_adversary_exposes_only_file_review_tools():
    files = HarnessTerminalAdversary.Toolsets[0]
    assert HarnessTerminalAdversary.Toolsets == [files]

    assert [tool.local_name for tool in files.Tools] == [
        "Read",
        "Search",
    ]


def test_compact_transcript_includes_goal_only_when_it_is_in_messages():
    approval = adversarial_approval(
        [
            # This is the shape the adversary currently receives: the prompt exists
            # on RunContext, but is not present in the messages list.
            ModelResponse(parts=[TextPart("assistant response")]),
        ]
    )
    with_goal = build_compact_transcript(
        [
            ModelRequest(parts=[UserPromptPart(content="original goal")]),
        ],
        10,
    )

    assert approval.transcript == "[Original goal] original goal\n\n[Assistant/Tool turn]"
    assert with_goal == "[Original goal] original goal\n[User] original goal"
