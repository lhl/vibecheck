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

## Code Volume Signal

Another strong signal is plain code volume.

- **12 / 46** Tokyo projects have at least **10k** non-lib code lines
- **8 / 26** Global projects have at least **10k** non-lib code lines
- **20 / 72** projects overall have at least **10k** non-lib code lines

That matters because, for a short hackathon, producing a genuinely new five-figure codebase by hand is uncommon. Substantial non-lib LoC makes it more likely that at least one of the following is true:

- the team used AI-assisted coding heavily
- the team started from a meaningful pre-existing codebase
- the project includes a large scaffold, generated code, or imported app skeleton committed as first-party code

So large codebases should not be read as proof of AI usage by themselves, but they are strong evidence against a simplistic reading of "no `AGENTS.md` / `CLAUDE.md`, therefore no AI".

The commit-pattern analysis also shows several projects with very large initial or mid-project commits, which is a reminder that some of this volume likely comes from existing codebases or large code drops rather than incremental hackathon-only authoring.

## Documentation Signal

Markdown volume is another useful workflow signal.

- **23 / 46** Tokyo projects have at least **5** Markdown files
- **10 / 26** Global projects have at least **5** Markdown files
- **33 / 72** projects overall have at least **5** Markdown files
- **15 / 46** Tokyo projects have at least **10** Markdown files
- **4 / 26** Global projects have at least **10** Markdown files
- **19 / 72** projects overall have at least **10** Markdown files

This is not as strong a signal as code volume, but it still matters. In practice, dense project-local documentation usually correlates with one of these:

- an agentic workflow that benefits from explicit plans, task lists, handoff notes, and operating instructions
- a team with unusually disciplined engineering habits for a short hackathon
- both

Put differently, normal hackathon teams do not usually produce deep Markdown structure unless they are either highly process-oriented or leaning on tools that reward explicit written context. That makes lots of Markdown files another reason not to assume "no visible agent files" means "no AI-assisted workflow".

It is still not definitive proof of AI usage. Some teams document heavily without agents, and some teams use AI heavily with almost no checked-in docs. But documentation density is a useful maturity signal, and weak documentation often lines up with weaker code quality and weaker agent performance.

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
