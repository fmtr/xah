from acp import telemetry
from corio import debug, logs

from xah.paths import paths

debug.trace()

logger = logs.from_paths(paths)

# ACP's optional telemetry creates duplicate console spans when Logfire is active.
# Keep application INFO logs, but turn off only ACP's request-span instrumentation.
telemetry.logfire_span = None
telemetry.TRACER = None
