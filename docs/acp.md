# Connect an ACP client

`xah` separates the **agent server** from its **client**. The server runs the agent; an ACP client provides the interface where you start a session, send prompts, and read replies. Most clients are IDEs or code editors, but terminal and web interfaces are also available.

!!! info "The server and client are separate"

    Start the `xah` server first. An IDE's ACP configuration starts a small `xah acp` proxy that connects to that server; it does not start the server itself.

## Other client options

- [ACP UI](https://github.com/formulahendry/acp-ui) is a cross-platform chat client for desktop, mobile, and web. Its browser and mobile versions connect to remote agents over WebSocket. They cannot launch local stdio agents directly; exposing a local agent may require a WebSocket bridge.
- [ACP Web Gateway](https://github.com/jamesward/acp-web-gateway) provides a browser interface through a gateway. Its documented setup relays an agent's ACP stdio connection over WebSocket; follow that project's instructions to run the gateway and agent.

These are third-party projects with their own setup and transport requirements. The IDE setup below connects the `xah` proxy to the local server directly.

## Start the server and connect a client

1. Install `xah` and start its server:

    ```bash
    pip install xah
    xah
    ```

    The default HTTP address is `http://localhost:8010`; the ACP WebSocket endpoint is `ws://localhost:8010/acp/ws`.
2. Configure your ACP client to launch `xah acp --url=ws://localhost:8010/acp/ws`.
3. Use `xah` from the client's agent or chat interface. Keep the server running while you use the proxy.

## Use an IDE as your ACP client

In each editor, add the configuration for an ACP agent. The `command` and `args` start `xah`'s stdio proxy; the server must already be running. Follow the editor's setup flow to open the right configuration file.

=== "PyCharm"

    JetBrains stores custom agents in the user-level `~/.jetbrains/acp.json`. Open AI Chat, choose **Add Custom Agent**, and add this entry to `agent_servers`, preserving other entries:

    ```json
    {
      "default_mcp_settings": {},
      "agent_servers": {
        "xah": {
          "command": "xah",
          "args": [
            "acp",
            "--url=ws://localhost:8010/acp/ws"
          ]
        }
      }
    }
    ```

    Use the full path to the `xah` executable if the IDE cannot find it on its process `PATH`. See [JetBrains' ACP setup guide](https://www.jetbrains.com/help/ai-assistant/acp.html) for details.

=== "Zed"

    In Zed, open **Agent Settings → External Agents → Add Agent → Add Custom Agent**; Zed opens the active settings file. On macOS and Linux without a custom `XDG_CONFIG_HOME`, it is typically `~/.config/zed/settings.json`. Merge this entry into the existing JSON settings object:

    ```json
    {
      "agent_servers": {
        "xah": {
          "type": "custom",
          "command": "xah",
          "args": [
            "acp",
            "--url=ws://localhost:8010/acp/ws"
          ],
          "env": {}
        }
      }
    }
    ```

    Zed starts the proxy process; the `xah` server must still be running separately. Use **dev: open acp logs** from the command palette to inspect ACP messages if a connection fails. See [Zed's external agents guide](https://zed.dev/docs/ai/external-agents).
