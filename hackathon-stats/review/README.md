# Hackathon Review

This directory contains repo-level analysis for the Tokyo set in [tokyo/README.md](/home/lhl/github/lhl/vibecheck/hackathon-stats/review/tokyo/README.md) and the selected global set in [global/README.md](/home/lhl/github/lhl/vibecheck/hackathon-stats/review/global/README.md).

I was curious to see what the AI Tool usage looks like on these projects. 

## AI Tool Usage Summary

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

## AI Usage Signal Analysis

Detecting AI-assisted development from repo artifacts is an imperfect science. Below is a taxonomy of signals we look for, split into what we currently implement in our analysis tooling and what we think would be useful future work.

### Implemented Signals

**Explicit tool artifacts.** The strongest signal — checked-in config files and directories that only exist if a specific tool was used:

- `CLAUDE.md`, `.claude/` directory (Claude Code)
- `AGENTS.md` (Claude Code or other agentic tools)
- `.cursor/`, `.cursorrules` (Cursor)
- Tool-specific branch naming patterns (`codex/`, `copilot/`, `cursor/`, `claude/`)
- Commit messages referencing specific tools ("claude", "codex", etc.)

**Code volume.** Non-lib lines of code counted via `scc` with vendored/generated directories excluded. For a ~30-hour hackathon, producing 10k+ lines of genuinely new code by hand is unusual. High volume suggests AI assistance, a pre-existing codebase, or heavy scaffolding — any of which is worth flagging.

**Commit size patterns.** Distribution of insertions across commits: large initial commits (possible existing codebase), large mid-project commits (code drops or agent-generated bulk), large final commits (poor version control or last-minute AI sprint). We flag projects where any single commit accounts for >40% of total insertions.

**Documentation density.** Markdown file count. Dense project-local documentation (plans, task lists, architecture docs, handoff notes) correlates with agentic workflows that benefit from explicit written context, or unusually disciplined teams — both worth noting.

**Commit timing.** Commits before or after the official hackathon window, useful for identifying pre-existing work or post-deadline polish.

### Future Signals (Not Yet Implemented)

These are signals we believe would be informative but haven't built automated detection for yet. They range from straightforward to compute to requiring heuristic judgment.

**Throughput: lines per person-hour.** Probably the single strongest quantitative signal we're not yet computing. We already have code lines, committer count, and hackathon duration. A productive human developer sustains maybe 100–200 lines of meaningful code per hour at peak. Over 30 hours, that's a generous ceiling of 3–6k lines per person. A solo committer with 15k+ non-lib lines is almost certainly getting AI assistance, working from a pre-existing codebase, or both. Cross-referencing throughput with the commit pattern flags (large initial commit = probably imported) would help separate "AI-productive" from "brought existing code."

**Commit message style.** AI coding tools produce distinctive commit messages:

- *Conventional commit format prevalence* — `feat:`, `fix:`, `refactor:`, `docs:` prefixes. Claude Code and Codex both default to conventional commits. A project that suddenly has perfect conventional commit discipline from a committer who doesn't use it in other repos is a tell.
- *Message length and descriptiveness* — AI-generated messages tend to be longer, more structured, and more descriptive than typical hackathon commits ("wip", "fix stuff", "asdf"). Average message length is easy to compute; a project with a mean commit message of 80+ characters in a hackathon is notable.
- *Bot markers* — some tools leave explicit footprints like `Co-authored-by:` trailers or emoji-prefixed generated messages.

**Commit cadence and burst patterns.** The temporal shape of commits tells a story:

- *Commits per hour over time* — AI-assisted work often shows bursts of very rapid commits (multiple within minutes when an agent loop is running), vs. human work which is more evenly paced.
- *Inter-commit time deltas* — a histogram of gaps between consecutive commits. Very short gaps (<2 minutes) with large diffs are hard to explain with human authoring alone.
- *Late-night sustained output* — high-volume, high-quality commits at 3–4am with no degradation is more plausible with AI assistance than with tired humans.
- *Single committer + bursty cadence + descriptive messages* — the combination is especially telling. One person producing rapid, well-described, large commits is a strong composite signal.

**Code style tells.** AI-generated code has stylistic fingerprints that are hard to suppress:

- *Over-documentation* — comprehensive JSDoc, docstrings on every function, thorough inline comments. Humans under hackathon time pressure skip this; AI does it eagerly and consistently.
- *Comment-to-code ratio* — `scc` already provides comment line counts per language, so this is nearly free to compute. A hackathon project with a 15–20% comment ratio is unusual for human authoring.
- *Boilerplate completeness* — comprehensive `.gitignore`, `.env.example`, properly configured `tsconfig.json`, ESLint/Prettier configs, Docker setups. Humans under time pressure skip setup polish; AI generates it by default.
- *Test presence* — actual test files (`test_*`, `*.test.*`, `*.spec.*`) in a 30-hour hackathon are uncommon without AI. Most human hackathon teams skip tests entirely.

**File structure and content tells.** Some artifacts are almost exclusively AI-generated:

- *ASCII Mermaid-style diagrams in Markdown* — especially ones with misaligned `|` characters on some lines. These are a near-certain tell for AI generation; humans either use a rendering tool (producing clean output) or don't bother with ASCII diagrams at all.
- *README quality relative to project maturity* — a polished multi-section README with badges, architecture sections, setup instructions, and API documentation for a hackathon prototype is unusual for human authoring.
- *Files touched per commit* — AI agents tend to create or modify many files in a single commit (implementing a feature across multiple files atomically), while humans tend to work one file at a time and commit incrementally.
- *Deep, well-organized directory structures* — AI tends to scaffold clean separation-of-concerns directory layouts from the start, while hackathon teams typically start flat and never reorganize.

### Composite Scoring (Future)

No single signal is definitive. The real power would be in combining signals into a composite score:

- A project with 15k LoC, a solo committer, conventional commit messages averaging 70 characters, bursty commit cadence, comprehensive tests, and ASCII architecture diagrams in the README is almost certainly AI-assisted — even with zero explicit tool artifacts.
- A project with 3k LoC, four committers, terse commit messages, steady cadence, no tests, and a bare-minimum README is probably mostly human-authored — even if it happens to have a `.cursor/` directory.

The challenge is calibration: we'd need ground truth (teams self-reporting their AI usage) to validate any scoring model. For now, the taxonomy above is useful as a qualitative checklist when reviewing individual projects.

### Ground Truth: vibecheck Self-Analysis

We can validate the signal taxonomy against our own project, vibecheck, which was built at the Tokyo hackathon by a small team running an aggressive multi-agent workflow. This is not a typical AI-assisted project — it represents what a leading-edge agentic workflow looks like when pushed hard over a weekend, and serves as a useful ceiling reference for what the signals look like when every dial is turned to maximum.

The workflow used here was a lightweight hackathon adaptation of an established multi-agent development process: Claude Code (Opus) for orchestration, planning, architecture, and interactive development; OpenAI Codex CLI (GPT-5.2/5.3-Codex) for autonomous work unit execution; and a multiple independent reviewer pattern where independent Claude/Codex sessions reviewed code changes after a primary coding agent completed work. One motivation for the hackathon was demonstrating this workflow to a colleague — the session data below reflects what it actually looks like in practice, including some impressively long concurrent session times driven by the reviewer pipeline.

#### Signal scorecard

| Signal | Value | Notes |
|--------|-------|-------|
| Explicit tool artifacts | `CLAUDE.md`, `AGENTS.md`, `.claude/` dir, `codex/` branches | Every artifact type present |
| Code volume | ~23k code lines (Python + JS + Svelte + Shell) | Solo-ish team, 31h hackathon window |
| Markdown files | **46** non-vendored `.md` files | Plans, analysis docs, worklogs, task lists, handoff notes, demo scripts, reference materials |
| Commit count | **238** commits in ~31h | ~7.7 commits/hour sustained |
| Conventional commits | **202 / 238** (85%) | `feat:`, `fix:`, `docs:`, `test:`, `refactor:` — consistent machine-generated formatting |
| Avg commit message length | **47.6 characters** | Structured and descriptive, not hackathon-typical "wip" or "fix stuff" |
| Inter-commit gaps < 2 min | **65 / 237** (27%) | Over a quarter of all gaps are under 2 minutes — agents committing autonomously |
| Test files | **55** test files | In a 30-hour hackathon; humans do not write 55 test files under time pressure |
| Committers | 3 | Small team, enormous output ratio |
| AI session data | 69 sessions (32 Claude Code, 37 Codex CLI), **727M tokens** | Fully instrumented — see `hackathon-stats/` |
| ASCII architecture diagrams | Yes, in README | Box-drawing diagrams in Markdown — the classic AI tell |
| README quality | Full API docs, tech stack tables, demo script, project structure tree | Polished well beyond hackathon norms |
| Directory structure | `vibecheck/`, `docs/`, `demo/`, `prototypes/`, `scripts/`, `resources/` | Clean separation-of-concerns layout from early commits |

#### Throughput

The throughput number is the most concrete signal: **~23k code lines / 2 people / ~31 hours ≈ 250 lines/person/hour sustained**. That is at the absolute ceiling of human capability for a peak sprint, and this was sustained across 31 hours including overnight work. For context, a productive human developer might sustain 100–200 lines/hour during focused coding; 250 lines/hour sustained over a full hackathon weekend — including architecture, debugging, testing, and documentation — is not plausible without heavy AI assistance.

Combined with 727M tokens of documented AI usage across 69 sessions, there is no ambiguity here.

#### Session intensity

The session data (detailed in `hackathon-stats/README.md`) shows patterns that are distinctive to multi-agent workflows:

- **69 total sessions** over a 31-hour span, with many running concurrently
- **68h 56m total wall time** across all sessions (sum exceeds real time because of parallelism)
- **27h 42m active time** (40% of wall time — the rest is agents waiting or humans context-switching)
- Peak concurrency around 07:00–08:00 JST Sunday with multiple overlapping Codex sessions running the coder + reviewer pipeline simultaneously
- The reviewer pattern is visible in the session data: short Codex sessions (1–5 minutes) interleaved with longer coding sessions, where "Reviewer 1/2/3" agents independently audited changes

This is what it looks like when AI is not just a suggestion engine but the primary authoring and review pipeline. Every signal in the taxonomy fires at maximum.

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
