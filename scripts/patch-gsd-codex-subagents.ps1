param(
    [switch]$Apply,
    [switch]$Force
)

$skillRoot = Join-Path $HOME ".codex\skills"

$newBlock = @'
## C. Task() -> Codex Subagent Strategy
GSD workflows use `Task(...)` (Claude Code syntax). In Codex, prefer built-in subagent delegation when the current runtime supports it, but do not assume low-level agent tools exist.

Direct mapping:
- `Task(subagent_type="X", prompt="Y")` -> delegate the work to Codex as agent `X` with prompt `Y`, using the runtime's native subagent mechanism when available
- `Task(model="...")` -> omit (Codex uses per-agent config/runtime defaults, not inline model selection)
- Keep context explicit via `<files_to_read>` blocks; subagents should not inherit parent session history unless the runtime does that automatically

Capability check:
- If this Codex runtime supports subagents, use them for `Task(...)`
- If subagents are unavailable in this environment, do not fail on missing `spawn_agent`/`wait`/`close_agent`; continue in the main session and preserve the workflow intent
- Without subagents, use `multi_tool_use.parallel` only for safe independent developer-tool calls (reads, searches, non-conflicting commands)

Parallel fan-out:
- When subagents are available, run independent `Task(...)` items concurrently
- Otherwise, keep execution sequential unless only tool-level parallelism is needed and safe

Result parsing:
- Look for structured markers in delegated output: `CHECKPOINT`, `PLAN COMPLETE`, `SUMMARY`, etc.
'@

$taskSectionPattern = '(?s)## C\. Task\(\).*?(?=</codex_skill_adapter>)'

if (-not (Test-Path $skillRoot)) {
    Write-Error "Codex skills directory not found: $skillRoot"
    exit 1
}

$files = Get-ChildItem $skillRoot -Directory |
    Where-Object { $_.Name -like "gsd-*" } |
    ForEach-Object { Join-Path $_.FullName "SKILL.md" } |
    Where-Object { Test-Path $_ }

$needsPatch = @()
$alreadyPatched = @()
$notApplicable = @()

foreach ($file in $files) {
    $content = Get-Content -Raw $file

    $hasNew = $content.Contains($newBlock)
    $hasLegacyTail = $content -match 'close_agent\(id\)|delegated output: `CHECKPOINT`, `PLAN COMPLETE`, `SUMMARY`, etc\.\s+in agent output'

    if ($hasNew -and -not $hasLegacyTail -and -not $Force) {
        $alreadyPatched += $file
        continue
    }

    if ($content -match $taskSectionPattern) {
        $needsPatch += $file

        if ($Apply) {
            $updated = [System.Text.RegularExpressions.Regex]::Replace(
                $content,
                $taskSectionPattern,
                $newBlock.TrimEnd() + "`r`n`r`n",
                [System.Text.RegularExpressions.RegexOptions]::Singleline
            )
            [System.IO.File]::WriteAllText($file, $updated, [System.Text.UTF8Encoding]::new($false))
        }

        continue
    }

    $notApplicable += $file
}

if ($Apply) {
    Write-Host "Patched files: $($needsPatch.Count)"
} else {
    Write-Host "Dry run. Files that would be patched: $($needsPatch.Count)"
}

if ($needsPatch.Count -gt 0) {
    $needsPatch | ForEach-Object { Write-Host "  PATCH  $_" }
}

if ($alreadyPatched.Count -gt 0) {
    Write-Host "Already patched: $($alreadyPatched.Count)"
}

if ($notApplicable.Count -gt 0) {
    Write-Host "Skipped (pattern not found): $($notApplicable.Count)"
    $notApplicable | ForEach-Object { Write-Host "  SKIP   $_" }
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "Run with -Apply to update the files."
    Write-Host "Use -Force to repair files that were partially patched."
}
