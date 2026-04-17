.. _mcp:

mcp
===
**Usage:**

.. code-block:: shell

    git machete mcp

Run a **Model Context Protocol** (MCP) server on standard input and standard output.

The server uses JSON-RPC 2.0 with newline-delimited messages.
It exposes git-machete operations as MCP tools so that clients such as **Claude Code**, Cursor, or other MCP-aware assistants can query branch layout, status, and related history using structured tool calls instead of ad hoc shell commands.

The server is implemented with only the Python standard library (no extra pip packages).
Point your MCP client at ``git machete mcp`` as the command to run, typically with the working directory set to the git repository you want the assistant to operate on.
