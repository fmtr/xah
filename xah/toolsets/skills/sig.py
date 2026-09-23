from cached_classproperty import cached_classproperty
from xah.toolsets.base.sig import Sig


class SkillsSig(Sig):
    @cached_classproperty
    def toolset_type(cls):
        from xah.toolsets.skills.toolset import Skills
        return Skills
