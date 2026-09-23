from typing import Literal, TypeAlias

PENDING = "pending"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"
BLOCKED = "blocked"
TODO_STATUSES = (PENDING, IN_PROGRESS, COMPLETED, BLOCKED)
TodoStatus: TypeAlias = Literal["pending", "in_progress", "completed", "blocked"]
