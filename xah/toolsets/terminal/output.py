from pydantic_ai import ToolFailed, ModelRetry
from pydantic_ai import ToolFailed

from xah.toolsets.terminal.base import TerminalManagementTool



class Output(TerminalManagementTool):
    """Return output produced since the previous call."""

    EVENT = "produced output"

    async def run(self) -> str:
        output = await self.terminal.get()
        if not output:
            from xah.toolsets.utils.toolset import Utils
            from xah.toolsets.utils.sleep import Sleep
            self.feedback(f"Use the {Utils.tool_name(Sleep)} tool if you need to wait for output.")
            raise ModelRetry("No output since last call.")

        return output
