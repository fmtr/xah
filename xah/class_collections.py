from collections.abc import Callable

from corio.function import ccp
from corio.iterator import ilist


def classes(function: Callable) -> ccp:
    @ccp
    def declaration(cls):
        return ilist(function(cls))

    return declaration
