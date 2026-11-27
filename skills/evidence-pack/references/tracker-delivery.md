# Delivering evidence to any tracker

The workflow names no single tracker. Detect it with the project's normal order (`CLAUDE.md`,
`docs/workflow/README.md`, `.delivery/orchestrator.json`, connected tools, then `gh`), and load
deferred tools with ToolSearch before deciding a capability is missing.

## The delivery ladder

Use the first route that works, then **read the ticket again to confirm the file is there**.
Work down the ladder: "the connector has no upload tool" is the reason to try step 3, never a
reason to stop.

1. **Native attachment** through the tracker's connector, CLI or API.
2. **File in a comment**, when the tracker stores uploads through comments.
3. **Signed-in browser**, using the ticket's file input. Load the browser tools with ToolSearch
   first (for Claude in Chrome: `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__find,mcp__claude-in-chrome__file_upload,mcp__claude-in-chrome__tabs_close_mcp`;
   Playwright and Chrome DevTools MCP have their own upload actions). Then:
   1. Open the ticket in a new tab. If the page asks you to sign in, stop this route: never type
      a password.
   2. `find` the hidden attachment `<input type=file>` and give `file_upload` the absolute local
      paths, every file in one call.
   3. Wait for the upload, read the ticket through the connector, and check that each file name
      is listed with its size. Then close your tab.
4. **PR attachment** with `gh pr comment <n> --attach <file>` (`gh` 2.99+), linked from the ticket.
5. **Keep it local**, only after steps 3 and 4 were tried. Then:
   - Write `.delivery/evidence/<KEY-n>/PENDING-UPLOAD` in the main checkout, one file path per
     line, then a line `reason: <why steps 3 and 4 failed>`.
   - Say `Evidence incomplete` in the ticket comment, name each file, and add the project's
     evidence-missing label.
   - Never delete the local copy. The next `/deliver` cycle or `/merge-ticket` retries the upload
     from the main session (see "Pending uploads").

A link to a local path is not delivery. Never upload to a public file host.

## Pending uploads

A worker session often has no browser. The main session usually does. So the orchestrator and
`/merge-ticket` retry every pending upload:

```text
ls .delivery/evidence/*/PENDING-UPLOAD
```

For each marker: upload the listed files with steps 1 to 4, confirm they are on the ticket,
update the `📁 Evidence Index` with attachment links, remove the evidence-missing label, then
delete the marker. If the upload still fails, keep the marker and list the ticket under
**Needs you** as "Evidence to attach", with the file paths.

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
