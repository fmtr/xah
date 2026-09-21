from corio import logging, debug, Constants

from package.paths import paths

debug.trace()

logger = logging.get_logger(
    name=paths.name,
    stream=Constants.DEVELOPMENT,
    version=paths.metadata.version,
)
