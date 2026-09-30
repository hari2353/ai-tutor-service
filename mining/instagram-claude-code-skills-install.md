# Instagram-Derived Claude Code Skills

This is the install list derived from the saved Instagram crawl and verified
against the public GitHub repositories. The commands install portable
`SKILL.md` packages into Claude Code and OpenCode-compatible global locations.

## Portable Skills Installed

### Archify

- Source: <https://github.com/tt-a1i/archify>
- Purpose: architecture, workflow, sequence, data-flow, and lifecycle diagrams
- Claude Code/OpenCode install:

```powershell
npx -y skills add tt-a1i/archify --skill archify --agent claude-code opencode --global --copy --yes
```

### Anthropic Skills

- Source: <https://github.com/anthropics/skills>
- Installed:
  - `mcp-builder`
  - `skill-creator`
  - `webapp-testing`
- Install:

```powershell
npx -y skills add anthropics/skills --skill mcp-builder skill-creator webapp-testing --agent claude-code opencode --global --copy --yes
```

### Addy Osmani Agent Skills

- Source: <https://github.com/addyosmani/agent-skills>
- Installed:
  - `spec-driven-development`
  - `test-driven-development`
  - `code-review-and-quality`
  - `security-and-hardening`
  - `source-driven-development`
  - `planning-and-task-breakdown`
  - `observability-and-instrumentation`
  - `git-workflow-and-versioning`
  - `incremental-implementation`
- Install:

```powershell
npx -y skills add addyosmani/agent-skills --skill spec-driven-development test-driven-development code-review-and-quality security-and-hardening source-driven-development planning-and-task-breakdown observability-and-instrumentation git-workflow-and-versioning incremental-implementation --agent claude-code opencode --global --copy --yes
```

### Matt Pocock Skills

- Source: <https://github.com/mattpocock/skills>
- Installed:
  - `tdd`
  - `code-review`
  - `codebase-design`
  - `diagnosing-bugs`
  - `domain-modeling`
  - `grill-with-docs`
  - `research`
  - `writing-for-agents`
- Install:

```powershell
npx -y skills add mattpocock/skills --skill tdd code-review codebase-design diagnosing-bugs domain-modeling grill-with-docs research writing-for-agents --agent claude-code opencode --global --copy --yes
```

### HumanLayer Skills

- Source: <https://github.com/humanlayer/skills>
- Installed:
  - `show-me`
  - `improve-claude-md`
- Install:

```powershell
npx -y skills add humanlayer/skills --skill show-me improve-claude-md --agent claude-code opencode --global --copy --yes
```

`build-iterated-agentic-loop` was not retained because the installer reported
a critical Snyk risk and socket alerts. Review it manually before considering
it for work use.

## Optional Claude Code Plugins

These are not ordinary portable skills. Install them separately, and do not
stack their full installs on top of equivalent manual skills without review.

### ECC

- Source: <https://github.com/affaan-m/ECC>
- Provides a large engineering operating system: planning, TDD, code review,
  security, memory, agents, commands, and hooks.
- Claude Code native plugin:

```text
/plugin marketplace add https://github.com/affaan-m/ECC
/plugin install ecc@ecc
```

- Guided Windows setup:

```powershell
npx ecc-universal@2.2.2 setup
```

Use ECC as an alternative larger bundle, not as an automatic addition to the
portable core above. Its own documentation warns against stacking a full
manual install and plugin install.

### Superpowers

- Source: <https://github.com/obra/superpowers>
- Provides brainstorming, plans, worktrees, TDD, subagents, review, and branch
  completion workflows.
- Claude Code native plugin:

```text
/plugin install superpowers@claude-plugins-official
```

Use Superpowers as an alternative methodology bundle. Do not install it blindly
alongside ECC because both control the development workflow.

## Where They Install

Claude Code:

```text
%USERPROFILE%\.claude\skills
```

OpenCode and compatible agents:

```text
%USERPROFILE%\.agents\skills
```

List installed skills:

```powershell
npx -y skills list --global --json
```

## Source Confidence

- `tt-a1i/archify`: user supplied directly and also present in the Instagram
  repository index.
- `anthropics/skills`: explicit repository reference from the Claude skills
  discovery material.
- `addyosmani/agent-skills`: explicit repository reference from saved posts.
- `mattpocock/skills`: explicit repository reference from saved posts.
- `humanlayer/skills`: explicit repository reference from saved posts.
- `affaan-m/ECC`: explicit saved Instagram repository reference.
- `obra/superpowers`: explicit saved Instagram repository reference.

Instagram is a discovery source, not a security guarantee. Review `SKILL.md`,
scripts, hooks, MCP configuration, and permissions before installing any new
third-party skill on an employer-managed machine.
