---
name: feedback-local-claude-storage
description: User wants all Claude context files (plans, memory) stored in the project-local .claude folder, not in home/.claude
metadata:
  type: feedback
---

All context files that would normally be stored under `/home/server/.claude/` (plan files, persistent memory, etc.) must instead be stored locally within this project, under `/home/server/database/onyks-bloodstone/.claude/`.

**Why:** explicit instruction from the user at the start of the onyks-bloodstone UI-fixes planning session — they want project-specific Claude context to travel with the project directory rather than living in the global home-level Claude config.

**How to apply:** when working in `/home/server/database/onyks-bloodstone`, write plan files to `.claude/plans/` and memory files to `.claude/memory/` inside the project root instead of the global paths. The auto-memory system's hardcoded read path is still `/home/server/.claude/projects/.../memory/`, so also consider whether a pointer or duplicate is needed there for the harness to auto-load this context in future sessions — check current state before assuming the global index already links here.
