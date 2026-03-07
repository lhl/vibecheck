# Hackathon Review

This directory contains repo-level analysis for the Tokyo set in [tokyo/README.md](/home/lhl/github/lhl/vibecheck/hackathon-stats/review/tokyo/README.md) and the selected global set in [global/README.md](/home/lhl/github/lhl/vibecheck/hackathon-stats/review/global/README.md).

## Summary

Across the two datasets we analyzed **72 projects**:

- **46** Tokyo projects
- **26** selected global projects
- **15 / 72** projects with a checked-in `AGENTS.md` or `CLAUDE.md`
- **19 / 72** projects with any explicit AI-tool evidence in the repo history or checked-in config

The main takeaway is that checked-in agent support files are clearly a minority workflow.

## Analysis Hypothesis

The repo evidence is best treated as a **lower bound** on AI usage, not a full count.

My working hypothesis is:

- Many more than **19 / 72** teams probably used AI in some form.
- Most projects probably **did not** use repo-committed custom agent instruction files.
- The more likely pattern is ad hoc AI usage: ChatGPT/Claude/Cursor/Copilot/API prompting without maintaining a checked-in `AGENTS.md` or `CLAUDE.md`.
- So the absence of those files should usually be read as **"no repo-specific agent workflow visible"**, not **"no AI was used"**.

In other words: most projects may well have used AI, but most do **not** look like they were using structured, repo-local agent instruction setups.

Tokyo also shows a stronger visible agent-tool signal than the selected global set.

## Analysis Tool Usage

Counts below are based on explicit evidence in the repo contents or git metadata. A single project can appear under multiple tools.

### Combined

| Tool | Projects |
|------|----------|
| Claude Code | 15 |
| OpenAI Codex | 5 |
| Cursor | 2 |
| GitHub Copilot | 1 |

### Tokyo

| Tool | Projects |
|------|----------|
| Claude Code | 12 |
| OpenAI Codex | 4 |
| GitHub Copilot | 1 |
| Cursor | 1 |

- Projects analyzed: **46**
- Projects with `AGENTS.md` or `CLAUDE.md`: **11**
- Projects with any explicit AI-tool evidence: **15**

### Global

| Tool | Projects |
|------|----------|
| Claude Code | 3 |
| OpenAI Codex | 1 |
| Cursor | 1 |

- Projects analyzed: **26**
- Projects with `AGENTS.md` or `CLAUDE.md`: **4**
- Projects with any explicit AI-tool evidence: **4**
