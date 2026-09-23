from cached_classproperty import cached_classproperty
from xah.toolsets.base.sig import Sig


class ParentSig(Sig):
    @cached_classproperty
    def toolset_type(cls):
        from xah.toolsets.subagent.parent import Parent
        return Parent


class SubagentSig(Sig):
    @cached_classproperty
    def toolset_type(cls):
        from xah.toolsets.subagent.toolset import Subagent
        return Subagent
