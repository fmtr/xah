from cached_classproperty import cached_classproperty

from xah.toolsets.base.sig import Sig


class PythonSig(Sig):
    @cached_classproperty
    def toolset_type(cls):
        from xah.toolsets.python.toolset import Python

        return Python
