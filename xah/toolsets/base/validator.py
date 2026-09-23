from functools import cached_property


class Validator:
    @cached_property
    def enabled(self) -> bool:
        return self.policy.approval

    async def validate(self) -> list[str]:
        raise NotImplementedError
