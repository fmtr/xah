from json import dumps
from dataclasses import dataclass
from typing import Generic, TypeVar
from acp.exceptions import RequestError
from acp.schema import ContentToolCallContent, TextContentBlock, ToolCallUpdate
from corio import Path, Constants, strings
from corio.iterator import ilist
from xah.obs import logger
from xah.server.acp.usage import UsageReporterRegistry
from pydantic_ai.tools import DeferredToolRequests, DeferredToolResults, ToolDenied
from pydantic_ai import Agent
from pydantic_acp import (
    AcpSessionContext,
    NativeApprovalBridge,
    PermissionRequestContext,
    DefaultPermissionToolCallBuilder,
)
from pydantic_acp.approvals import ApprovalResolution
from xah.harness.base import Harness
from xah.harness.deps import HarnessDeps
from xah.toolsets.base.tool import ValidationResult


DepsT = TypeVar("DepsT", bound=HarnessDeps)


@dataclass(frozen=True, slots=True, kw_only=True)
class PermissionRequestContextMetadata(PermissionRequestContext):
    metadata: ValidationResult


class PermissionToolCallBuilderMetadata(DefaultPermissionToolCallBuilder):
    def build_tool_call_update(
        self,
        context: PermissionRequestContextMetadata,
    ) -> ToolCallUpdate:
        update = super().build_tool_call_update(context)
        if not context.metadata.text:
            return update

        content = list(update.content or [])
        content.append(
            ContentToolCallContent(
                type="content",
                content=TextContentBlock(
                    type="text",
                    text=context.metadata.text,
                ),
            ),
        )
        return update.model_copy(update={"content": content})


class ApprovalBridgeMetadata(NativeApprovalBridge):
    async def resolve_deferred_approvals(
        self,
        *,
        client,
        session: AcpSessionContext,
        requests: DeferredToolRequests,
        classifier,
        projection_map=None,
    ):
        deferred_results = DeferredToolResults(metadata=dict(requests.metadata))
        for tool_call in requests.approvals:
            raw_input = tool_call.args_as_dict()
            approval_policy_key = classifier.approval_policy_key(tool_call.tool_name, raw_input)
            remembered_policy = self._get_remembered_policy(session, approval_policy_key)
            if remembered_policy is not None:
                deferred_results.approvals[tool_call.tool_call_id] = self._policy_to_result(
                    remembered_policy,
                )
                continue

            metadata = ValidationResult(
                **requests.metadata.get(tool_call.tool_call_id, {})
            )

            permission_response = await client.request_permission(
                options=self._build_permission_options(),
                session_id=session.session_id,
                tool_call=PermissionToolCallBuilderMetadata().build_tool_call_update(
                    PermissionRequestContextMetadata(
                        session=session,
                        tool_call=tool_call,
                        raw_input=dict(raw_input),
                        cwd=session.cwd,
                        classifier=classifier,
                        projection_map=projection_map,
                        metadata=metadata,
                    ),
                ),
            )
            outcome = permission_response.outcome
            if outcome.outcome == "cancelled":
                return ApprovalResolution(
                    deferred_tool_results=deferred_results,
                    cancelled=True,
                    cancelled_tool_call=tool_call,
                )

            selected_result = self._selected_option_to_result(outcome.option_id)
            if selected_result is None:
                raise RequestError.invalid_request({"optionId": outcome.option_id})
            if isinstance(selected_result, ToolDenied):

                if metadata.text:
                    msg = strings.trim(
                        "The tool call was denied.",
                        metadata.text
                    )

                    selected_result = ToolDenied(message=msg)

            self._remember_policy(
                session=session,
                approval_policy_key=approval_policy_key,
                option_id=outcome.option_id,
            )
            deferred_results.approvals[tool_call.tool_call_id] = selected_result

        return ApprovalResolution(deferred_tool_results=deferred_results)


class SessionAgentSource(ilist[Harness[DepsT]], Generic[DepsT]):
    """

    Provide harness agents and dependencies for ACP sessions.

    """

    def __init__(
        self,
        harness_type: type[Harness[DepsT]],
        settings,
        usage_reporters: UsageReporterRegistry,
        capability_bridges=(),
        projection_maps=None,
    ):
        super().__init__()
        self.harness_type = harness_type
        self.settings = settings
        self.bridges = tuple(capability_bridges)
        self.projection_maps = projection_maps
        self.usage_reporters = usage_reporters

    def get_runtime(self, session: AcpSessionContext) -> Harness[DepsT]:
        runtime = self.session_id.get(session.session_id)
        if runtime is not None:
            return runtime

        runtime = self.harness_type(
            session=session,
            bridges=self.bridges,
            usage_reporters=self.usage_reporters,
        )
        reporter = self.usage_reporters.for_session(session.session_id)
        logger.info(f"ACP session runtime uses usage reporter {id(reporter)}")
        runtime.restore_session()
        if self.projection_maps is not None and not self.projection_maps:
            # AdapterConfig is created before ACP supplies a session and keeps
            # this same list. Populate it in place once tools can be built.
            self.projection_maps.extend(runtime.projections)
        self.append(runtime)
        return runtime

    async def get_agent(self, session: AcpSessionContext) -> Agent[DepsT, str]:
        return self.get_runtime(session).agent

    async def get_deps(
        self,
        session: AcpSessionContext,
        agent: Agent[DepsT, str],
    ) -> DepsT:
        del agent
        return self.get_runtime(session).deps
