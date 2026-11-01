# System Architectural Assumptions & Design Choices

1. **Slack Integration & Sockets:**
   - Using Slack Bolt in Socket Mode (`SLACK_APP_TOKEN` + `SLACK_BOT_TOKEN`) allows the app to operate behind NAT/firewalls without exposing a public webhook URL while maintaining real-time two-way interaction.
   - For environments without active Slack credentials, full mock and headless modes are provided so all capabilities can be verified offline and headlessly via `scripts/smoke.sh`.

2. **Session Keying & Persistence:**
   - Sessions are keyed by composite `(channel_id, thread_ts, user_id)`.
   - SQLite is configured with WAL (Write-Ahead Logging) mode and busy timeout enabled for robust concurrent reads/writes and zero data loss across application restarts.

3. **Embedding Engine:**
   - `sentence-transformers` with model `BAAI/bge-small-en-v1.5` (384 dimensions) running locally on CPU. Embeddings are L2-normalized for cosine similarity. No external API quotas are consumed for embeddings.

4. **10 Seed Proposals Scope:**
   - All 10 proposal files (`proposal_construction.txt`, `proposal_consulting.txt`, `proposal_distribution.txt`, `proposal_fintech.txt`, `proposal_fleet.txt`, `proposal_healthcare.txt`, `proposal_logistics.txt`, `proposal_manufacturing.txt`, `proposal_retail.txt`, `proposal_retail2.txt`) in `data/proposals/` are ingested on boot idempotently using SHA-256 content hashes.

5. **Multi-Agent Roster & Separation:**
   - **Intake Agent:** Pure extraction from transcript into structured `ClientProfile` with exact quotes and confidence scores. No inference or extrapolation.
   - **Research Agent:** Performs metadata-filtered semantic retrieval with a fallback ladder across the past proposal database and the transcript.
   - **Writer Agent:** Assembles draft sections with explicit source citations and placeholders for unconfirmed fields.
   - **Critic Agent:** Enforces strict anti-hallucination rubric (Appendix A). Runs prior to user delivery. Triggers automated repair loop if defects are detected.

6. **Section-Scoped Revision:**
   - When a user requests a change to a specific section (e.g. "make the timeline more detailed"), only that specific `DraftSection` is updated and versioned in the database. The surrounding sections remain byte-for-byte identical. The DOCX renderer re-assembles the document from the updated section set.

7. **Human Approval Gate:**
   - Once Critic passes, draft summary and section list are posted to Slack with interactive Block Kit action buttons: `Approve & Generate DOCX`, `Request Changes`, `Regenerate Section`. The final DOCX file is delivered upon approval or explicit user request.

