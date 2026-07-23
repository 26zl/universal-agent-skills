[CmdletBinding()]
param(
    [ValidateSet("auto", "link", "copy")]
    [string]$Mode = "auto",

    [string[]]$Agents = @("codex", "claude", "opencode"),

    [string[]]$Skill = @(),

    [ValidateSet("global", "project")]
    [string]$Scope = "global",

    [string]$ProjectDir = (Get-Location).Path,

    [switch]$Update,
    [switch]$Uninstall,
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$SkillsDir = Join-Path $Root "skills"
$AdaptersFile = Join-Path $Root "adapters/agents.tsv"
$UserHome = if ($env:UAS_HOME) { $env:UAS_HOME } else { $HOME }
$StateHome = if ($env:UAS_STATE_HOME) {
    $env:UAS_STATE_HOME
} elseif ($env:LOCALAPPDATA) {
    Join-Path $env:LOCALAPPDATA "universal-agent-skills"
} elseif ($env:XDG_STATE_HOME) {
    Join-Path $env:XDG_STATE_HOME "universal-agent-skills"
} else {
    Join-Path $UserHome ".local/state/universal-agent-skills"
}
$StateFile = Join-Path $StateHome "installed.json"
$MarkerName = ".uas-managed"

function Write-Plan([string]$Message) {
    Write-Information $Message -InformationAction Continue
}

function Write-Banner {
    if ([Console]::IsOutputRedirected) { return }
    $rows = @(
        "███████╗██╗  ██╗██╗██╗     ██╗     ███████╗",
        "██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝",
        "███████╗█████╔╝ ██║██║     ██║     ███████╗",
        "╚════██║██╔═██╗ ██║██║     ██║     ╚════██║",
        "███████║██║  ██╗██║███████╗███████╗███████║",
        "╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝"
    )
    if ($env:NO_COLOR) {
        foreach ($row in $rows) { Write-Plan $row }
        return
    }
    $esc = [char]27
    for ($i = 0; $i -lt $rows.Count; $i++) {
        $color = if ($i -eq 5) { "90" } else { "97" }
        Write-Plan "$esc[${color}m$($rows[$i])$esc[0m"
    }
}

function Test-SkillName([string]$Name) {
    return $Name -match '^[a-z0-9]+(-[a-z0-9]+)*$'
}

function Get-AdapterMap {
    $map = @{}
    foreach ($line in Get-Content -LiteralPath $AdaptersFile) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) { continue }
        $parts = $line -split "`t"
        if ($parts.Count -ne 3) { throw "Invalid adapter row: $line" }
        $map[$parts[0]] = @{ Global = $parts[1]; Project = $parts[2] }
    }
    return $map
}

function Get-InstalledState {
    if (-not (Test-Path -LiteralPath $StateFile)) { return @() }
    $raw = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    if ($null -eq $raw) { return @() }
    return @($raw)
}

function Save-InstalledState([object[]]$Entries) {
    if ($DryRun) { return }
    New-Item -ItemType Directory -Path $StateHome -Force | Out-Null
    $temp = "$StateFile.tmp.$([Guid]::NewGuid().ToString('N'))"
    ConvertTo-Json -InputObject @($Entries) -Depth 4 | Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $StateFile -Force
}

function Test-ManagedCopy([string]$Target) {
    $marker = Join-Path $Target $MarkerName
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { return $false }
    return (Get-Content -LiteralPath $marker -TotalCount 1) -eq "managed-by=universal-agent-skills"
}

function Get-LinkTarget([string]$Target) {
    $item = Get-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
    if ($null -eq $item -or -not $item.LinkType) { return $null }
    $rawTarget = @($item.Target)[0]
    if ([System.IO.Path]::IsPathRooted($rawTarget)) {
        return [System.IO.Path]::GetFullPath($rawTarget)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $item.DirectoryName $rawTarget))
}

# Test-Path reports $false for dangling symbolic links on Windows PowerShell 5.1.
function Test-PathOrLink([string]$Path) {
    return $null -ne (Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue)
}

function Test-OwnedTarget([string]$Target, [string]$Source) {
    $linkTarget = Get-LinkTarget $Target
    if ($null -ne $linkTarget) {
        return $linkTarget -eq [System.IO.Path]::GetFullPath($Source)
    }
    return Test-ManagedCopy $Target
}

function Invoke-OwnedTargetRemoval([string]$Target, [string]$Source) {
    if (-not (Test-PathOrLink $Target)) { return $true }
    if (-not (Test-OwnedTarget $Target $Source)) { return $false }
    if ($DryRun) {
        Write-Plan "would remove: $Target"
    } else {
        if ($null -ne (Get-LinkTarget $Target)) {
            Remove-Item -LiteralPath $Target -Force
        } else {
            Remove-Item -LiteralPath $Target -Recurse -Force
        }
    }
    return $true
}

function Backup-Or-RemoveTarget([string]$Target, [string]$Source, [bool]$AllowBackup) {
    if (-not (Test-PathOrLink $Target)) { return }
    if (Test-OwnedTarget $Target $Source) {
        if ($DryRun) {
            Write-Plan "would replace managed target: $Target"
        } else {
            if ($null -ne (Get-LinkTarget $Target)) {
                Remove-Item -LiteralPath $Target -Force
            } else {
                Remove-Item -LiteralPath $Target -Recurse -Force
            }
        }
        return
    }
    if (-not $AllowBackup) {
        throw "Refusing to overwrite unmanaged target: $Target (use -Force to back it up)"
    }
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $backup = "$Target.uas-backup-$stamp.$([Guid]::NewGuid().ToString('N'))"
    if ($DryRun) {
        Write-Plan "would back up unmanaged target: $Target -> $backup"
    } else {
        Move-Item -LiteralPath $Target -Destination $backup
        Write-Plan "backed up unmanaged target: $backup"
    }
}

function Test-SymlinkSupport {
    if ($DryRun) { return $true }
    New-Item -ItemType Directory -Path $StateHome -Force | Out-Null
    $probe = Join-Path $StateHome ".link-test-$PID"
    try {
        New-Item -ItemType SymbolicLink -Path $probe -Target $SkillsDir -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    } finally {
        if (Test-Path -LiteralPath $probe) { Remove-Item -LiteralPath $probe -Force }
    }
}

if (-not (Test-Path -LiteralPath $SkillsDir -PathType Container)) {
    throw "Missing canonical skills directory: $SkillsDir"
}
if (-not (Test-Path -LiteralPath $AdaptersFile -PathType Leaf)) {
    throw "Missing adapter registry: $AdaptersFile"
}

Write-Banner
$Adapters = Get-AdapterMap
$ExpandedAgents = @()
foreach ($value in $Agents) {
    $ExpandedAgents += $value -split ','
}
if ($ExpandedAgents -contains "all") {
    $ExpandedAgents = @("codex", "claude", "opencode")
}
$SelectedAgents = @()
foreach ($agentValue in $ExpandedAgents) {
    $agent = $agentValue.Trim().ToLowerInvariant()
    if ($agent -in @("universal", "copilot")) { $agent = "codex" }
    if (-not $Adapters.ContainsKey($agent)) { throw "Unsupported agent: $agent" }
    if ($SelectedAgents -notcontains $agent) { $SelectedAgents += $agent }
}
if ($SelectedAgents.Count -eq 0) { throw "At least one agent is required" }

$SkillFilter = @()
foreach ($value in $Skill) {
    foreach ($name in ($value -split ',')) {
        $name = $name.Trim()
        if (-not (Test-SkillName $name)) { throw "Invalid skill name: $name" }
        # Uninstall must keep working for skills that were removed from the repository.
        if (-not $Uninstall -and
            -not (Test-Path -LiteralPath (Join-Path $SkillsDir "$name/SKILL.md") -PathType Leaf)) {
            throw "Unknown skill: $name"
        }
        if ($SkillFilter -notcontains $name) { $SkillFilter += $name }
    }
}

$CanonicalSkills = @(Get-ChildItem -LiteralPath $SkillsDir -Directory | Where-Object {
    Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md") -PathType Leaf
} | Sort-Object Name)
if ($SkillFilter.Count -gt 0) {
    $CanonicalSkills = @($CanonicalSkills | Where-Object { $SkillFilter -contains $_.Name })
}

$BaseDir = if ($Scope -eq "project") {
    if (-not (Test-Path -LiteralPath $ProjectDir -PathType Container)) {
        throw "Project directory does not exist: $ProjectDir"
    }
    (Get-Item -LiteralPath $ProjectDir).FullName
} else {
    [System.IO.Path]::GetFullPath($UserHome)
}

if ($Update -and -not $Uninstall) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git is required for -Update" }
    & git -C $Root rev-parse --is-inside-work-tree | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Source is not a git repository" }
    $dirty = & git -C $Root status --porcelain
    if ($dirty) { throw "Source repository has local changes; commit or stash them before -Update" }
    if ($DryRun) {
        Write-Plan "would run: git -C $Root pull --ff-only"
    } else {
        & git -C $Root pull --ff-only
        if ($LASTEXITCODE -ne 0) { throw "git pull failed" }
    }
}

$EffectiveMode = $Mode
if ($Mode -eq "auto") {
    $EffectiveMode = if (Test-SymlinkSupport) { "link" } else { "copy" }
    if ($EffectiveMode -eq "copy") {
        Write-Plan "symbolic links are unavailable; using copy mode"
    }
}

if ($Uninstall) {
    $state = @(Get-InstalledState)
    if ($state.Count -eq 0) {
        Write-Warning "No installer state found; checking current canonical skills only"
        foreach ($agent in $SelectedAgents) {
            $relative = if ($Scope -eq "project") { $Adapters[$agent].Project } else { $Adapters[$agent].Global }
            foreach ($skillDir in $CanonicalSkills) {
                $target = Join-Path (Join-Path $BaseDir $relative) $skillDir.Name
                if (Invoke-OwnedTargetRemoval $target $skillDir.FullName) {
                    if ($DryRun) {
                        Write-Plan "would unregister [$agent]: $($skillDir.Name)"
                    } else {
                        Write-Plan "removed [$agent]: $($skillDir.Name)"
                    }
                }
            }
        }
        exit 0
    }

    $kept = @()
    foreach ($entry in $state) {
        $selected = $entry.scope -eq $Scope -and
            $SelectedAgents -contains $entry.agent -and
            ($SkillFilter.Count -eq 0 -or $SkillFilter -contains $entry.skill)
        if (-not $selected) {
            $kept += $entry
            continue
        }
        if (-not $Adapters.ContainsKey([string]$entry.agent)) {
            Write-Warning "State references unsupported agent: $($entry.agent)"
            $kept += $entry
            continue
        }
        $relative = if ($Scope -eq "project") { $Adapters[$entry.agent].Project } else { $Adapters[$entry.agent].Global }
        $expected = [System.IO.Path]::GetFullPath((Join-Path (Join-Path $BaseDir $relative) $entry.skill))
        if ([System.IO.Path]::GetFullPath([string]$entry.target) -ne $expected) {
            Write-Warning "State target is outside the expected adapter path: $($entry.target)"
            $kept += $entry
            continue
        }
        if (Invoke-OwnedTargetRemoval $entry.target $entry.source) {
            if ($DryRun) {
                Write-Plan "would unregister [$($entry.agent)]: $($entry.skill)"
            } else {
                Write-Plan "removed [$($entry.agent)]: $($entry.skill)"
            }
        } else {
            Write-Warning "Target is no longer owned by this installer: $($entry.target)"
            $kept += $entry
        }
    }
    Save-InstalledState $kept
    exit 0
}

$state = @(Get-InstalledState)
foreach ($agent in $SelectedAgents) {
    $relative = if ($Scope -eq "project") { $Adapters[$agent].Project } else { $Adapters[$agent].Global }
    if ([System.IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\\/])\.\.([\\/]|$)') {
        throw "Unsafe adapter path for ${agent}: $relative"
    }
    foreach ($skillDir in $CanonicalSkills) {
        $source = $skillDir.FullName
        $target = Join-Path (Join-Path $BaseDir $relative) $skillDir.Name
        $currentLink = Get-LinkTarget $target
        if ($EffectiveMode -eq "link" -and $currentLink -eq [System.IO.Path]::GetFullPath($source)) {
            Write-Plan "unchanged [$agent]: $($skillDir.Name)"
        } elseif ($DryRun) {
            Backup-Or-RemoveTarget $target $source $Force.IsPresent
            Write-Plan "would install [$agent/$EffectiveMode]: $($skillDir.Name) -> $target"
        } elseif ($EffectiveMode -eq "link") {
            Backup-Or-RemoveTarget $target $source $Force.IsPresent
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            New-Item -ItemType SymbolicLink -Path $target -Target $source | Out-Null
            Write-Plan "installed [$agent/$EffectiveMode]: $($skillDir.Name)"
        } else {
            $parent = Split-Path -Parent $target
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
            $staged = Join-Path $parent ".$($skillDir.Name).uas-tmp.$([Guid]::NewGuid().ToString('N'))"
            New-Item -ItemType Directory -Path $staged | Out-Null
            $rollback = $null
            $backup = $null
            try {
                try {
                    Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $staged -Recurse -Force
                    @("managed-by=universal-agent-skills", "source=$source") |
                        Set-Content -LiteralPath (Join-Path $staged $MarkerName) -Encoding UTF8
                } catch {
                    throw "Cannot stage skill copy $($skillDir.Name): $($_.Exception.Message)"
                }

                if (Test-PathOrLink $target) {
                    if (Test-OwnedTarget $target $source) {
                        $rollback = Join-Path $parent ".$($skillDir.Name).uas-old.$([Guid]::NewGuid().ToString('N'))"
                        New-Item -ItemType Directory -Path $rollback | Out-Null
                        Move-Item -LiteralPath $target -Destination (Join-Path $rollback "target")
                    } elseif (-not $Force) {
                        throw "Refusing to overwrite unmanaged target: $target (use -Force to back it up)"
                    } else {
                        $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
                        $backup = "$target.uas-backup-$stamp.$([Guid]::NewGuid().ToString('N'))"
                        Move-Item -LiteralPath $target -Destination $backup
                        Write-Plan "backed up unmanaged target: $backup"
                    }
                }

                try {
                    Move-Item -LiteralPath $staged -Destination $target
                } catch {
                    if ($rollback -and (Test-Path -LiteralPath (Join-Path $rollback "target"))) {
                        Move-Item -LiteralPath (Join-Path $rollback "target") -Destination $target
                    } elseif ($backup -and (Test-PathOrLink $backup)) {
                        Move-Item -LiteralPath $backup -Destination $target
                    }
                    throw
                }
                if ($rollback) {
                    Remove-Item -LiteralPath $rollback -Recurse -Force -ErrorAction SilentlyContinue
                }
                Write-Plan "installed [$agent/$EffectiveMode]: $($skillDir.Name)"
            } finally {
                if (Test-Path -LiteralPath $staged) {
                    Remove-Item -LiteralPath $staged -Recurse -Force
                }
                if ($rollback -and (Test-Path -LiteralPath $rollback)) {
                    $recoveryTarget = Join-Path $rollback "target"
                    if (-not (Test-PathOrLink $recoveryTarget)) {
                        Remove-Item -LiteralPath $rollback -Recurse -Force
                    }
                }
            }
        }

        if (-not $DryRun) {
            $state = @($state | Where-Object { $_.target -ne $target })
            $state += [pscustomobject]@{
                scope = $Scope
                agent = $agent
                skill = $skillDir.Name
                mode = $EffectiveMode
                source = $source
                target = $target
            }
            # Persist per skill so an aborted run never leaves installed targets untracked.
            Save-InstalledState $state
        }
    }
}
Write-Plan "done"
