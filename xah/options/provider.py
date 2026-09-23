from __future__ import annotations

from corio import Constants
from xah.obs import logger
from pydantic_acp import AcpSessionContext, ConfigOptionsProvider as AcpConfigOptionsProvider


class ConfigOptionsProvider(AcpConfigOptionsProvider):
    """Expose session dependency options through the ACP configuration API."""

    def __init__(self, source):
        self._source = source

    def get_config_options(self, session: AcpSessionContext, agent):
        del agent
        return self._source.get_runtime(session).deps.options

    def set_config_option(self, session: AcpSessionContext, agent, config_id, value):
        del agent
        runtime = self._source.get_runtime(session)
        logger.info(f"Setting config option {config_id} {Constants.ARROW_RIGHT} {value}")
        runtime.set_config_option(config_id, value)
