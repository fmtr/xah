# Quick start

Install `xah`, start its agent server, and connect an ACP client.

## Start the server

=== "Install with pip"

    ```bash
    pip install xah
    xah
    ```

=== "Run with uv"

    ```bash
    uvx xah
    ```

The server listens on `localhost:8010` by default. Leave it running while you use the client.

!!! warning "Set your OpenAI API key"

    `xah` uses OpenAI's `gpt-6-luna` model by default. Set the `OPENAI_API_KEY` environment variable before sending a prompt. If you use a different provider or model, configure its credentials instead.

!!! note "Connect an ACP client"

    `xah` starts an agent server, not a chat window. An ACP client is the user-facing app where you choose an agent, send messages, and view replies. Clients are most often IDEs or editors, but desktop, terminal, and web interfaces are available too. See [client setup](acp.md).

For custom agents and tools, work through the [tutorials](tutorials/).
