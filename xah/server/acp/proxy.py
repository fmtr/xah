from acp.schema import (
    BooleanConfigOptionCapabilities,
    ClientSessionCapabilities,
    SessionConfigOptionsCapabilities,
)
from acpremote import RemoteProxyAgent


class Proxy(RemoteProxyAgent):
    async def initialize(
        self,
        protocol_version,
        client_capabilities=None,
        client_info=None,
        **kwargs,
    ):
        client_capabilities = client_capabilities.model_copy(
            update={
                "session": ClientSessionCapabilities(
                    configOptions=SessionConfigOptionsCapabilities(
                        boolean=BooleanConfigOptionCapabilities(),
                    ),
                ),
            },
        )
        return await super().initialize(
            protocol_version,
            client_capabilities=client_capabilities,
            client_info=client_info,
            **kwargs,
        )
