from cached_classproperty import cached_classproperty
from xah.toolsets.base.sig import Sig


class ShellSig(Sig):
    @cached_classproperty
    def toolset_type(cls):
        from xah.toolsets.shell.toolset import Shell
        return Shell
