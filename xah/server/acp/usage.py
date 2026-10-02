from dataclasses import dataclass, field


@dataclass
class UsageReporter:
    """Collect context usage reported by the context manager for one run."""

    active_model: object | None = None
    used: int | None = None
    size: int | None = None

    def report(self, _fraction: float, used: int, size: int) -> None:
        self.used = used
        self.size = size

    def begin(self, active_model: object) -> None:
        self.active_model = active_model
        self.used = None
        self.size = None


@dataclass
class UsageReporterRegistry:
    """Keep independent context usage state for each ACP session."""

    reporters: dict[str, UsageReporter] = field(default_factory=dict)

    def for_session(self, session_id: str) -> UsageReporter:
        reporter = self.reporters.get(session_id)
        if reporter is None:
            reporter = UsageReporter()
            self.reporters[session_id] = reporter
        return reporter
