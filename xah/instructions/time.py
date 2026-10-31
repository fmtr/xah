from corio import dt
import humanize
from xah.instructions.base import Instruction


class Time(Instruction):
    async def run(self) -> str:
        now = dt.now().astimezone()
        current_time = now.strftime("%I:%M %p %Z")
        current_date = humanize.naturaldate(now)
        return f"Current local time: {current_time} ({current_date})."
