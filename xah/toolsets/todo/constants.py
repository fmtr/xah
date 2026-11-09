from corio.enums import MapEnum


class TodoStatus(MapEnum):
    PENDING = "pending", "The todo has not been started.", "[ ]"
    IN_PROGRESS = "in_progress", "The todo is currently being worked on.", "[*]"
    COMPLETED = "completed", "The todo is finished.", "[x]"
    BLOCKED = "blocked", "The todo is blocked.", "[!]"
