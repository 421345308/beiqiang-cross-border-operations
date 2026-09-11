---
name: compshare-cli
description: Manage CompShare GPU instances, durable remote jobs, images and storage with the compshare CLI. Use for explicit CompShare cloud work or diagnostics; discover current commands with structured help before execution.
---

# CompShare CLI

Use the installed CLI and structured JSON help rather than guessing flags. Detailed command examples, SSH/file transfer, durable jobs, billing and error handling are in [references/operations.md](references/operations.md); read only the relevant section.

## Operating rules

- Use `compshare --json COMMAND --help` for the exact command before an unfamiliar operation. Put global flags before the command group. Current help overrides reference examples.
- Inspect the target resource, location and price. Run `instance create --dry-run` before real creation. Example regions, GPU models and prices are placeholders, never Beiqiang defaults.
- Execute writes only within the user's authorized targets, budget and scope. Add `--yes` only when that operation is already authorized; do not request the same authorization again.
- Check process exit status and JSON `ok`; batch output may contain partial failure. Retain resource IDs and per-item results.
- Bound lifecycle waits and remote jobs with timeouts. A timeout does not cancel remote work: query state before retrying to avoid duplicate charged resources or jobs.
- Use `instance job` for remote work that must survive disconnects. Place remote command arguments after `--` and copy remote paths with a leading `:`.
- Prefer the existing credential profile. Never print, log or commit keys. Do not use `--show-sensitive` unless the user needs the raw connection details. On Windows, follow PowerShell environment syntax rather than copying Bash `export` examples.
- Installation, upgrades, team changes and feedback submissions are separate actions; run them only when needed within the user's request. Sending feedback requires the user's explicit request.

## Quick discovery

```text
compshare --json --help
compshare --json doctor
compshare --json instance --help
compshare --json instance create --help
```

`doctor` checks the environment; it is not a reason to create or resize resources. For a timeout, credential failure or unexpected option, inspect current state/help before applying the relevant recovery in the operation reference.
