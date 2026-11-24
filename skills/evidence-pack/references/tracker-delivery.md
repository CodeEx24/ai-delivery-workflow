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
| Jira | Issue attachments API | Signed-in browser, then PR | `--format markdown` |
| Linear | File upload, then attach the URL to the issue | File in a comment, browser, then PR | `--format markdown` |
| GitHub Issues | Browser upload to the issue comment | `gh pr comment --attach` on the linked PR | `--format markdown` |
| Azure Boards | Work item attachments | Browser, then PR | `--format markdown` |
| ClickUp, Asana, Trello, Monday, Shortcut | Task or card attachment | File in a comment, browser, then PR | `--format text`, or Markdown if rendered |
| Local backlog | Keep in `.delivery/evidence/<KEY-n>/` and name it in the ticket Log | PR attachment | `--format markdown` |
| Any other tool | Check its tools for attachment or upload | File in a comment, browser, then PR | `--format text` |

Tools change, so check what the connector offers now instead of assuming this table is complete.
Use only an account or token the operator already configured. Do not ask for a token in chat.

## Links in comments

**Every link in a tracker or PR comment must be clickable, with readable text.** People open
tickets to click through, so a raw or broken link is a defect in the comment.

| Link to | Write |
|---|---|
| A PR | `[PR #456](https://github.com/<owner>/<repo>/pull/456)` |
| A ticket | `[ABC-123](https://<site>/browse/ABC-123)`, or the tracker's own issue URL |
| A CI run, deploy, preview or evidence file | `[Deploy run 789](https://…)`, `[Preview](https://…)` |
| A file in the repo | `[docs/tickets/ABC-123-title.md](https://github.com/<owner>/<repo>/blob/<base>/docs/tickets/ABC-123-title.md)` |

- Use the full `https://` URL. Link a ticket or PR the first time each comment mentions it.
- **Never put a link inside backticks or a code block.** It will not be clickable.
- Write the comment in **Markdown**, and send it in the format the tool expects:

| Tool | How |
|---|---|
| Jira, through the Atlassian connector | Pass `contentFormat: "markdown"`. **Never use Jira wiki links** (`[text\|url]`): the connector posts them as plain text |
| Jira, older REST API with wiki markup | `[text\|https://url]` |
| Jira, Atlassian Document Format | A `link` mark on the text |
| Linear, GitHub, Azure Boards, ClickUp, Shortcut and others | Markdown links |
| A tool that shows plain text only | The full URL on its own line, so it becomes clickable |

- **After posting, read the comment back.** If `[`, `](` or `|` still show around a URL, edit the
  comment and fix it.

## Comment and label rules

- Keep **one** `📁 Evidence Index · <KEY-n>` comment. Search for it and edit it. If the tool cannot
  edit comments, post a new one and start it with `Replaces the previous index`.
- If the tracker has no labels, put the same state in the first line of the comment, such as
  `qa:failed`.
- Use the tracker's status names from `docs/workflow/README.md`. Never guess a status.
