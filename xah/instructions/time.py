from corio import dt
from xah.instructions.base import Instruction


class Time(Instruction):
    async def run(self) -> str:
        now = dt.now().astimezone()
        current_datetime = now.strftime("%A, %B %d, %Y %H:%M %Z")
        return f"Current local time: {current_datetime}."
