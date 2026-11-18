# supervise

Supervises an orchestrator run that another agent, the manager, is executing, and reports to the sponsor. It reads the run issue's coordination record, corroborates every claim against the repositories, interrupts on unsafe or irreversible action, and drafts replies for decisions the sponsor owns. `SKILL.md` defines its authority and procedure; `references/` holds the channel, interrupt, headless launch and shared run-state contracts.

## Requirements

- A GitHub Project board tracking the run issue, with a Backlog status and a Priority field, and repository-scope labels; deferred follow-up capture files each confirmed follow-up in Backlog with its label and a Priority value.
- A coordination issue in `coordination_repository`, with one sub-issue per participating repository.
- `git` and authenticated `gh`, with access to the repositories, issues, pull requests and Project board.
- A gitignored `.prompts/` directory in the supervisor's checkout for kickoff files, drafts, findings and headless run files.
- A sandboxed environment. The readiness path launches the manager headless by default, and headless launch starts it with `--dangerously-skip-permissions` (Claude Code) or `--dangerously-bypass-approvals-and-sandbox` (Codex), so the manager runs without permission prompts. This skill is intended for sandboxed environments only.

## Sponsor guidance for supervisor drafts

A supervisor's draft is a proposal to understand before approving. Once approved, its technical constraints can become binding on the run. You can rely on the supervisor to explain technical details; you do not need to independently verify commands or credential handling.

When reviewing a draft, these optional questions may help:

- What decision am I making?
- What changes if I approve?
- What could this wording unintentionally require or prohibit?

Ask the supervisor to explain technical or absolute wording, its consequences, and relevant exceptions in plain language. Request a revised draft if that explanation differs from what you intend. For example, an approved list of commands can be treated as binding, so a run fails verification when a client uses other read-only commands. An absolute restriction on credential handling can be read to include the client's own sign-in, so a corrective run stops when the client cannot authenticate.

For a proposed scope or acceptance correction, ask which binding sources support it, whether it changes a requirement or only its proof, and what approval would mean for the run. You can request the relevant passages and a plain-language explanation of how the proposal fits current requirements and workflow rules. Ask for a revised proposal if that distinction is unclear; you do not need to audit every source yourself. For example, a scope correction can classify a positive requirement as nonbinding, which an evidence audit then finds and the run must revise. The source and effect of a proposed correction deserve a clear explanation before approval.
