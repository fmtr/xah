from acp import telemetry
from corio import logs, debug, Constants

from xah.paths import paths

debug.trace()

logger = logs.get_logger(
    name=paths.name,
    stream=Constants.DEVELOPMENT,
    version=paths.metadata.version,
)

# ACP's optional telemetry creates duplicate console spans when Logfire is active.
# Keep application INFO logs, but turn off only ACP's request-span instrumentation.
telemetry.logfire_span = None
telemetry.TRACER = None
