# Delivering evidence to any tracker

The workflow names no single tracker. Detect it with the project's normal order (`CLAUDE.md`,
`docs/workflow/README.md`, `.delivery/orchestrator.json`, connected tools, then `gh`), and load
deferred tools with ToolSearch before deciding a capability is missing.

## The delivery ladder

Use the first route that works, then **read the ticket again to confirm the file is there**.

1. **Native attachment** through the tracker's connector, CLI or API.
2. **File in a comment**, when the tracker stores uploads through comments.
3. **Signed-in browser**, using the ticket's or comment's file input.
4. **PR attachment** with `gh pr comment <n> --attach <file>` (`gh` 2.99+), linked from the ticket.
5. **Keep it local.** Say `Evidence incomplete`, list the file and path, and add the project's
   evidence-missing label. Never delete the local copy.

A link to a local path is not delivery. Never upload to a public file host.

## Tracker notes

| Tracker | Try first | Fallback | Index comment |
|---|---|---|---|
| Jira | Issue attachments API | Signed-in browser, then PR | `--format jira` |
| Linear | File upload, then attach the URL to the issue | File in a comment, browser, then PR | `--format markdown` |
| GitHub Issues | Browser upload to the issue comment | `gh pr comment --attach` on the linked PR | `--format markdown` |
| Azure Boards | Work item attachments | Browser, then PR | `--format markdown` |
| ClickUp, Asana, Trello, Monday, Shortcut | Task or card attachment | File in a comment, browser, then PR | `--format text`, or Markdown if rendered |
| Local backlog | Keep in `.delivery/evidence/<KEY-n>/` and name it in the ticket Log | PR attachment | `--format markdown` |
| Any other tool | Check its tools for attachment or upload | File in a comment, browser, then PR | `--format text` |

Tools change, so check what the connector offers now instead of assuming this table is complete.
Use only an account or token the operator already configured. Do not ask for a token in chat.

## Comment and label rules

- Keep **one** `📁 Evidence Index · <KEY-n>` comment. Search for it and edit it. If the tool cannot
  edit comments, post a new one and start it with `Replaces the previous index`.
- If the tracker has no labels, put the same state in the first line of the comment, such as
  `qa:failed`.
- Use the tracker's status names from `docs/workflow/README.md`. Never guess a status.
