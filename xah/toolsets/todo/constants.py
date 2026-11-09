from corio.enums import MapEnum


class TodoStatus(MapEnum):
    PENDING = "pending", "The todo has not been started.", "[ ]"
    IN_PROGRESS = "in_progress", "The todo is currently being worked on.", "[*]"
    COMPLETED = "completed", "The todo is finished.", "[x]"
    BLOCKED = "blocked", "The todo is blocked.", "[!]"

    def __new__(cls, value: str, description: str, icon: str):
        member = str.__new__(cls, value)
        member._value_ = value
        member.description = description
        member.icon = icon
        return member
