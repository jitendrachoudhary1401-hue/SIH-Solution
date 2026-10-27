# Project instructions

## Graphify

- Graphify is installed on this workstation. Read `C:/Users/rajku/.agents/skills/graphify/SKILL.md` before using it.
- When the user types `/graphify`, follow the installed Graphify skill before doing anything else. Default to this project directory when no path is supplied.
- For codebase questions, check for `graphify-out/graph.json`. If it exists, query the graph first and verify relevant findings against the current source files.
- If no graph exists, inspect source files directly unless the user requests graph generation. Use `/graphify` to build the initial graph and `/graphify --update` to refresh it.
- Keep credentials, private environment files, runtime data, uploaded evidence, dependency directories, and generated build output out of graph inputs.
