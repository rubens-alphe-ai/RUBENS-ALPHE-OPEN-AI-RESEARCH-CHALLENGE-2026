# RA-PSI local Gmail/Qwen bridge

This bridge connects the authorized RA-PSI mailbox to the local Qwen worker
through durable filesystem queues:

```text
Gmail/DC
  -> local bridge reads marker `RAPC Qven` or `RAPC Qwen`
  -> agent_inbox/<task-id>.json
  -> Ollama/Qwen worker
  -> agent_outbox/<task-id>.result.json
  -> local bridge verifies provenance and deduplicates
  -> Gmail reply in the original thread
```

The bridge creates task IDs deterministically from the Gmail message ID and
the mission hash. Every task contains the source message ID, source thread ID,
UTC timestamp, mission hash, source-payload hash and envelope hash. Every
transition is appended to `bridge_state/ledger.jsonl` and protected by a
cross-process lock.

## Safety defaults

- Gmail OAuth client files and refresh tokens are outside the public project.
- `send_replies` defaults to `false`; use `--send-replies` only after local
  verification and consent.
- The public safety check and CI must pass before publication.
- The bridge never changes canonical RA-PSI state.
- A reply carries `X-RAPC-Task-ID`; a restart checks the original Gmail thread
  for that header before sending again.
- A malformed response or hash mismatch is rejected and recorded.

## Local setup

1. Create a Google OAuth desktop client for Gmail and save its client file in a
   local directory outside this repository. The bridge requests only Gmail
   read and send scopes.
2. Copy `config.example.json` to a local file outside public GitHub content,
   then replace the placeholder paths. Do not commit that local file.
3. Start Ollama and install the configured model, normally
   `qwen3:4b-nothink`.
4. Start the existing local worker so it watches `agent_inbox/` and writes
   `agent_outbox/`.
5. Run one dry poll first:

```text
python project/bridge/run_bridge.py --config C:/path/to/config.local.json --once --dry-run
```

6. After reviewing the ledger and generated task, run the continuous bridge
   with replies enabled only when desired:

```text
python project/bridge/run_bridge.py --config C:/path/to/config.local.json --send-replies
```

The first run opens Google OAuth in a browser if no local refresh token exists.
The token is stored only at the configured local token path.
