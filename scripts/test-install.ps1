$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "uas-test-$PID-$(Get-Random)"
$env:UAS_HOME = Join-Path $TempRoot "home"
$env:UAS_STATE_HOME = Join-Path $TempRoot "state"

function Assert-True([bool]$Value, [string]$Message) {
    if (-not $Value) { throw "Test failure: $Message" }
}

try {
    New-Item -ItemType Directory -Path $env:UAS_HOME -Force | Out-Null
    & (Join-Path $Root "install.ps1") -Mode copy -Agents codex,claude,opencode
    Assert-True (Test-Path (Join-Path $env:UAS_HOME ".agents/skills/coding-style/SKILL.md")) "Codex copy missing"
    Assert-True (Test-Path (Join-Path $env:UAS_HOME ".agents/skills/surgical-implementation/SKILL.md")) "Surgical implementation copy missing"
    Assert-True (Test-Path (Join-Path $env:UAS_HOME ".claude/skills/coding-style/SKILL.md")) "Claude copy missing"
    Assert-True (Test-Path (Join-Path $env:UAS_HOME ".config/opencode/skills/coding-style/SKILL.md")) "OpenCode copy missing"

    & (Join-Path $Root "install.ps1") -Mode copy -Agents codex,claude,opencode
    & (Join-Path $Root "install.ps1") -Uninstall -Agents codex,claude,opencode
    Assert-True (-not (Test-Path (Join-Path $env:UAS_HOME ".agents/skills/coding-style"))) "Codex uninstall failed"
    Assert-True (-not (Test-Path (Join-Path $env:UAS_HOME ".agents/skills/surgical-implementation"))) "Surgical implementation uninstall failed"

    & (Join-Path $Root "install.ps1") -Mode copy -Agents copilot -Skill simplify-code
    Assert-True (Test-Path (Join-Path $env:UAS_HOME ".agents/skills/simplify-code/SKILL.md")) "Copilot alias copy missing"
    & (Join-Path $Root "install.ps1") -Uninstall -Agents copilot -Skill simplify-code
    Assert-True (-not (Test-Path (Join-Path $env:UAS_HOME ".agents/skills/simplify-code"))) "Copilot alias uninstall failed"

    $conflictTarget = Join-Path $env:UAS_HOME ".agents/skills/coding-style"
    New-Item -ItemType Directory -Path $conflictTarget -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $conflictTarget "owner.txt") -Value "unmanaged"
    $conflictRejected = $false
    try {
        & (Join-Path $Root "install.ps1") -Mode copy -Agents codex -Skill coding-style
    } catch {
        $conflictRejected = $true
    }
    Assert-True $conflictRejected "Unmanaged conflict should fail without -Force"
    & (Join-Path $Root "install.ps1") -Mode copy -Agents codex -Skill coding-style -Force
    $backups = @(Get-ChildItem -LiteralPath (Join-Path $env:UAS_HOME ".agents/skills") -Filter "coding-style.uas-backup-*")
    Assert-True ($backups.Count -ge 1) "Backup missing after -Force"
    & (Join-Path $Root "install.ps1") -Uninstall -Agents codex -Skill coding-style
    Assert-True (-not (Test-Path $conflictTarget)) "Forced install uninstall failed"

    & (Join-Path $Root "install.ps1") -Mode copy -Agents codex -Skill coding-style
    Remove-Item -LiteralPath $conflictTarget -Recurse -Force
    New-Item -ItemType Directory -Path $conflictTarget -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $conflictTarget "notes.txt") -Value "user-content"
    & (Join-Path $Root "install.ps1") -Uninstall -Agents codex -Skill coding-style 3>$null
    Assert-True (Test-Path (Join-Path $conflictTarget "notes.txt")) "Uninstall removed an unmanaged replacement"
    Remove-Item -LiteralPath $conflictTarget -Recurse -Force

    if (-not $IsWindows) {
        & (Join-Path $Root "install.ps1") -Mode link -Agents claude -Skill coding-style
        $linkItem = Get-Item -LiteralPath (Join-Path $env:UAS_HOME ".claude/skills/coding-style") -Force
        Assert-True ([bool]$linkItem.LinkType) "Expected a symbolic link"
        & (Join-Path $Root "install.ps1") -Uninstall -Agents claude -Skill coding-style
        Assert-True (-not (Test-Path (Join-Path $env:UAS_HOME ".claude/skills/coding-style"))) "Link uninstall failed"
    }

    $project = Join-Path $TempRoot "project"
    New-Item -ItemType Directory -Path $project -Force | Out-Null
    & (Join-Path $Root "install.ps1") -Mode copy -Scope project -ProjectDir $project -Agents claude
    Assert-True (Test-Path (Join-Path $project ".claude/skills/verify-changes/SKILL.md")) "Project copy missing"
    & (Join-Path $Root "install.ps1") -Uninstall -Scope project -ProjectDir $project -Agents claude
    Assert-True (-not (Test-Path (Join-Path $project ".claude/skills/verify-changes"))) "Project uninstall failed"

    $dryHome = Join-Path $TempRoot "dry-home"
    $env:UAS_HOME = $dryHome
    & (Join-Path $Root "install.ps1") -DryRun -Agents all
    Assert-True (-not (Test-Path $dryHome)) "Dry-run wrote to disk"

    $bootstrapHome = Join-Path $TempRoot "bootstrap-home"
    $env:UAS_HOME = $bootstrapHome
    & (Join-Path $Root "bootstrap.ps1") -DryRun -Agents all
    Assert-True (-not (Test-Path $bootstrapHome)) "Bootstrap dry-run wrote to disk"
    $unsafeRefRejected = $false
    try {
        & (Join-Path $Root "bootstrap.ps1") -DryRun -Repo "https://github.com/example/repository.git" -Ref "-unsafe"
    } catch {
        $unsafeRefRejected = $true
    }
    Assert-True $unsafeRefRejected "Bootstrap accepted an option-like Git ref"

    if ($IsWindows) {
        $fakeClaude = Join-Path $TempRoot "fake-claude.cmd"
        Set-Content -LiteralPath $fakeClaude -Value "@echo off`r`necho []`r`n"
    } else {
        $fakeClaude = Join-Path $TempRoot "fake-claude"
        Set-Content -LiteralPath $fakeClaude -Value "#!/bin/sh`nprintf '%s\n' '[]'`n"
        & chmod +x $fakeClaude
    }
    $env:UAS_CLAUDE_COMMAND = $fakeClaude
    if ($IsWindows) {
        $fakeCodex = Join-Path $TempRoot "fake-codex.cmd"
        $fakeCodexContent = @'
@echo off
if "%*"=="plugin marketplace list --json" echo {"marketplaces":[]}
if "%*"=="plugin list --available --json" echo {"installed":[],"available":[]}
if "%*"=="mcp list --json" echo []
'@
        Set-Content -LiteralPath $fakeCodex -Value $fakeCodexContent
        $fakeText = Join-Path $TempRoot "fake-text.cmd"
        Set-Content -LiteralPath $fakeText -Value "@echo off`r`n"
    } else {
        $fakeCodex = Join-Path $TempRoot "fake-codex"
        $fakeCodexContent = @'
#!/bin/sh
case "$*" in
  "plugin marketplace list --json") printf '%s\n' '{"marketplaces":[]}' ;;
  "plugin list --available --json") printf '%s\n' '{"installed":[],"available":[]}' ;;
  "mcp list --json") printf '%s\n' '[]' ;;
esac
'@
        Set-Content -LiteralPath $fakeCodex -Value $fakeCodexContent
        & chmod +x $fakeCodex
        $fakeText = Join-Path $TempRoot "fake-text"
        Set-Content -LiteralPath $fakeText -Value "#!/bin/sh`nexit 0`n"
        & chmod +x $fakeText
    }
    $env:UAS_CODEX_COMMAND = $fakeCodex
    $env:UAS_COPILOT_COMMAND = $fakeText
    $env:UAS_OPENCODE_COMMAND = $fakeText
    $env:UAS_CODE_COMMAND = $fakeText
    $stackOutput = @(& (Join-Path $Root "bootstrap.ps1") -DryRun -Agents all -WithAgentStack)
    Assert-True (($stackOutput -join "`n") -match "audit complete; no changes were made") "Bootstrap did not run the agent stack audit"
    Assert-True (-not (Test-Path $bootstrapHome)) "Agent stack dry-run wrote to the test home"

    Write-Output "PowerShell installer tests passed."
} finally {
    Remove-Item Env:UAS_CLAUDE_COMMAND -ErrorAction SilentlyContinue
    Remove-Item Env:UAS_CODEX_COMMAND -ErrorAction SilentlyContinue
    Remove-Item Env:UAS_COPILOT_COMMAND -ErrorAction SilentlyContinue
    Remove-Item Env:UAS_OPENCODE_COMMAND -ErrorAction SilentlyContinue
    Remove-Item Env:UAS_CODE_COMMAND -ErrorAction SilentlyContinue
    Remove-Item Env:UAS_HOME -ErrorAction SilentlyContinue
    Remove-Item Env:UAS_STATE_HOME -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $TempRoot) { Remove-Item -LiteralPath $TempRoot -Recurse -Force }
}
