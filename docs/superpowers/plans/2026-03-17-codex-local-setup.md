# Codex Local Setup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подготовить локальный репозиторий для работы через Codex, нормализовать текстовые файлы, добавить Codex-документацию и привязать git workflow к форку пользователя.

**Architecture:** Изменения ограничены документацией, служебными файлами репозитория и локальной git-настройкой. Продуктовый код приложения не меняется, кроме возможной нормализации строк/описаний, если это нужно для читаемости.

**Tech Stack:** Python 3.14, FastAPI, SQLite, pytest, PowerShell, git

---

## Chunk 1: Repository Audit And Text Normalization

### Task 1: Inspect text files and capture current state

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `main.md`
- Modify: `mozg.md`

- [ ] **Step 1: Read current text files and identify encoding/readability problems**

Run: `Get-Content -Raw README.md`, `Get-Content -Raw pyproject.toml`, `Get-Content -Raw main.md`, `Get-Content -Raw mozg.md`
Expected: visible list of files needing rewrite or normalization

- [ ] **Step 2: Decide which files need rewrite versus minimal normalization**

Expected: documented internal choice for each file

- [ ] **Step 3: Rewrite or normalize the files in UTF-8**

Expected: files are readable and useful for local development

- [ ] **Step 4: Re-read the files to verify readability**

Run: `Get-Content -Raw <file>`
Expected: human-readable output without mojibake in file contents

## Chunk 2: Codex Repository Metadata

### Task 2: Add repository-level helper files

**Files:**
- Create: `.editorconfig`
- Create: `.gitattributes`
- Create: `AGENTS.md`

- [ ] **Step 1: Write `.editorconfig` for text, Python, Markdown, JS, CSS, HTML**

- [ ] **Step 2: Write `.gitattributes` to normalize text handling**

- [ ] **Step 3: Write `AGENTS.md` with local Codex instructions**

- [ ] **Step 4: Re-read these files to verify clarity**

Run: `Get-Content -Raw .editorconfig`, `Get-Content -Raw .gitattributes`, `Get-Content -Raw AGENTS.md`
Expected: concise, readable local instructions

## Chunk 3: Codex Documentation

### Task 3: Add compact documentation under `docs/codex`

**Files:**
- Create: `docs/codex/project-overview.md`
- Create: `docs/codex/architecture.md`
- Create: `docs/codex/workflow.md`
- Create: `docs/codex/backlog-notes.md`
- Create: `docs/codex/file-map.md`
- Create: `docs/codex/commands.md`

- [ ] **Step 1: Create project overview**

- [ ] **Step 2: Create architecture summary**

- [ ] **Step 3: Create workflow guide**

- [ ] **Step 4: Create backlog notes**

- [ ] **Step 5: Create file map**

- [ ] **Step 6: Create commands cheat sheet**

- [ ] **Step 7: Re-read docs to verify they are concise and non-duplicative**

Run: `Get-ChildItem docs/codex`, `Get-Content -Raw docs/codex/<file>.md`
Expected: complete compact doc set

## Chunk 4: Local Verification Workflow

### Task 4: Add lightweight verification script

**Files:**
- Create: `scripts/verify.ps1`

- [ ] **Step 1: Write failing test for script presence and intended behavior if practical**

Expected: if no reasonable automated test exists for repo scripts, explicitly skip test creation because this is configuration, not production behavior

- [ ] **Step 2: Implement `scripts/verify.ps1`**

- [ ] **Step 3: Run the script and confirm it executes expected checks**

Run: `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`
Expected: test command runs and exits based on verification results

## Chunk 5: Git Fork Alignment

### Task 5: Point the local repository at the user fork

**Files:**
- Modify: local git config for `origin`
- Modify: `README.md`
- Modify: `docs/codex/workflow.md`
- Modify: `docs/codex/commands.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Verify current remotes**

Run: `git remote -v`
Expected: existing upstream-style remote visible

- [ ] **Step 2: Update `origin`**

Run: `git remote set-url origin https://github.com/lamantinX/perenoska`
Expected: command succeeds with exit code 0

- [ ] **Step 3: Re-run remote check**

Run: `git remote -v`
Expected: both fetch and push point to `https://github.com/lamantinX/perenoska`

- [ ] **Step 4: Ensure docs reference the user fork where appropriate**

Expected: local workflow docs no longer mention the previous GitHub repository

## Chunk 6: Final Verification

### Task 6: Verify repository state

**Files:**
- Modify: none expected

- [ ] **Step 1: Run pytest**

Run: `pytest`
Expected: passing test suite

- [ ] **Step 2: Run lightweight verification script**

Run: `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`
Expected: successful verification output

- [ ] **Step 3: Check git status**

Run: `git status --short --branch`
Expected: only intended file changes are present

- [ ] **Step 4: Summarize what changed and any residual risks**

Expected: concise handoff with evidence-based verification
