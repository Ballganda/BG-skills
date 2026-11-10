# Session floor

Every session starts with some tokens already spent before you type anything. That starting count is the session floor. It is the same cost every time you open a session, so it is worth knowing what makes it up and what you can turn off.

## What makes up the floor

The floor has three contributors:

| Contributor | What it is | Can you change it? |
|---|---|---|
| Harness system prompt | The instructions Claude Code itself sends: how to use tools, how to behave, how to format output. | No. It is fixed by the harness. |
| Connector tool definitions | Each connected MCP server (a "connector") sends the schema of every tool it offers. | Yes. Disconnect or disable connectors you do not use. |
| Installed skill descriptions | Each installed skill contributes its name and one-line description to the list the agent sees. | Yes. Disable or uninstall plugins and skills you do not use. |

The split above is an inference from how the harness is built, not a measurement. The total is measured, and you can see it in the context breakdown (see below). The per-contributor numbers are estimates.

## What you can turn off

Lower the floor by removing what you do not use:

- **Unused connectors.** Each connector adds its full tool list to every session. In Claude Code's MCP settings, disable or remove any connector you do not use in the project you are working in.
- **Unused plugins.** Each plugin brings its skills, and each skill adds a description to the floor. Use `/plugin` to see what is installed and disable the plugins you rarely reach for.

Do not expect the harness system prompt to shrink. You cannot turn it off, and it is the same for everyone.

## How to view the context breakdown

Type `/context` in a session. It shows how much of the context window each part is using, so you can check the floor against your own setup after you change connectors or plugins. Run it once before you change anything, then again after, to see the difference.

## Where it fits

The floor is paid once per session, before the first message, so it matters most in short sessions and in sessions you open often. For the decision of when to start a fresh session as the context grows, see [skill-map](./engineering/skill-map.md).
