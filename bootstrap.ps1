[CmdletBinding()]
param(
    [string]$Repo = $env:UAS_REPO_URL,
    [string]$Ref = $(if ($env:UAS_REF) { $env:UAS_REF } else { "main" }),
    [string]$InstallDir = $env:UAS_INSTALL_DIR,
    [ValidateSet("auto", "link", "copy")]
    [string]$Mode = "auto",
    [string[]]$Agents = @("codex", "claude", "opencode"),
    [string[]]$Skill = @(),
    [ValidateSet("global", "project")]
    [string]$Scope = "global",
    [string]$ProjectDir = (Get-Location).Path,
    [switch]$Uninstall,
    [switch]$DryRun,
    [switch]$Force,
    [switch]$WithAgentStack,
    [switch]$UpdateAgentStack,
    [switch]$IncludeSensitivePlugins,
    [switch]$AllowInsecureRepo
)

$ErrorActionPreference = "Stop"
$UserHome = if ($env:UAS_HOME) { $env:UAS_HOME } else { $HOME }
$DataHome = if ($env:LOCALAPPDATA) {
    $env:LOCALAPPDATA
} elseif ($env:XDG_DATA_HOME) {
    $env:XDG_DATA_HOME
} else {
    Join-Path $UserHome ".local/share"
}
if (-not $InstallDir) { $InstallDir = Join-Path $DataHome "universal-agent-skills/repo" }
if ([string]::IsNullOrWhiteSpace($Ref) -or $Ref.StartsWith("-") -or $Ref.IndexOfAny([char[]]"`r`n") -ge 0) {
    throw "-Ref must be non-empty, contain no line breaks, and not start with '-'"
}
if (-not ($IsWindows -or $env:OS -eq "Windows_NT")) {
    $uid = & id -u 2>$null
    if ($LASTEXITCODE -eq 0 -and "$uid" -eq "0") {
        throw "Do not run the bootstrap as root"
    }
}

$LocalRoot = $null
if ($PSScriptRoot -and
    (Test-Path -LiteralPath (Join-Path $PSScriptRoot "install.ps1")) -and
    (Test-Path -LiteralPath (Join-Path $PSScriptRoot "skills") -PathType Container)) {
    $LocalRoot = $PSScriptRoot
}

if ($Repo) {
    if ($Repo.IndexOfAny([char[]]"`r`n`t") -ge 0) {
        throw "Repository URL must not contain control characters"
    }
    if ($Repo -match '^https?://') {
        $authority = ($Repo -replace '^[^:]+://', '').Split('/')[0]
        if ($authority.Contains('@')) {
            throw "Repository URL must not include credentials; use a credential helper or SSH"
        }
        $repoUri = $null
        if (-not [Uri]::TryCreate($Repo, [UriKind]::Absolute, [ref]$repoUri) -or
            $repoUri.Scheme -notin @("http", "https") -or -not $repoUri.Host) {
            throw "Repository URL is malformed"
        }
    }
    $secure = $Repo -match '^(https://|ssh://|git@[^:]+:)'
    if (-not $secure -and -not $AllowInsecureRepo) {
        throw "Repository URL must use HTTPS or SSH"
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git is required" }

    if ($DryRun) {
        Write-Information "would sync $Repo at $Ref into $InstallDir" -InformationAction Continue
        exit 0
    } else {
        $parent = Split-Path -Parent $InstallDir
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        if (Test-Path -LiteralPath $InstallDir) {
            if (-not (Test-Path -LiteralPath (Join-Path $InstallDir ".git") -PathType Container)) {
                throw "Install directory exists but is not a managed git checkout: $InstallDir"
            }
            $origin = & git -C $InstallDir remote get-url origin
            if ($LASTEXITCODE -ne 0) { throw "Cannot read the origin of the existing checkout: $InstallDir" }
            $origin = "$origin".Trim()
            if ($origin -ne $Repo) { throw "Existing checkout uses a different origin: $origin" }
            $dirty = & git -C $InstallDir status --porcelain
            if ($dirty) { throw "Managed checkout has local changes: $InstallDir" }
            & git -C $InstallDir fetch --depth 1 origin $Ref
            if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
            & git -C $InstallDir checkout --detach --force FETCH_HEAD
            if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }
        } else {
            $temp = Join-Path $parent ".repo.uas-tmp.$([Guid]::NewGuid().ToString('N'))"
            try {
                New-Item -ItemType Directory -Path $temp | Out-Null
                & git init -q $temp
                if ($LASTEXITCODE -ne 0) { throw "git init failed" }
                & git -C $temp remote add origin $Repo
                if ($LASTEXITCODE -ne 0) { throw "git remote add failed" }
                & git -C $temp fetch --depth 1 origin $Ref
                if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
                & git -C $temp checkout -q --detach FETCH_HEAD
                if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }
                Move-Item -LiteralPath $temp -Destination $InstallDir
            } finally {
                if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
            }
        }
    }
    $LocalRoot = $InstallDir
}

if (-not $LocalRoot) {
    throw "-Repo is required when bootstrap.ps1 is not run from a repository checkout"
}
if ($Uninstall -and ($WithAgentStack -or $UpdateAgentStack -or $IncludeSensitivePlugins)) {
    throw "Agent stack sync cannot be combined with -Uninstall"
}

$installer = Join-Path $LocalRoot "install.ps1"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Checkout does not contain install.ps1"
}

$arguments = @{
    Mode = $Mode
    Agents = $Agents
    Skill = $Skill
    Scope = $Scope
    ProjectDir = $ProjectDir
    Uninstall = $Uninstall
    DryRun = $DryRun
    Force = $Force
}
& $installer @arguments

if ($WithAgentStack -or $UpdateAgentStack -or $IncludeSensitivePlugins) {
    $python = $null
    $pythonPrefix = @()
    if (Get-Command python3 -ErrorAction SilentlyContinue) {
        $python = "python3"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $python = "python"
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $python = "py"
        $pythonPrefix = @("-3")
    } else {
        throw "Python 3.9 or newer is required for agent stack sync"
    }
    & $python @pythonPrefix -c "import sys; raise SystemExit(sys.version_info < (3, 9))"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.9 or newer is required for agent stack sync"
    }

    $syncScript = Join-Path $LocalRoot "scripts/sync_agent_stack.py"
    $syncArguments = @($pythonPrefix) + @($syncScript)
    if (-not $DryRun) { $syncArguments += "--apply" }
    if ($UpdateAgentStack) { $syncArguments += "--update" }
    if ($IncludeSensitivePlugins) { $syncArguments += "--include-sensitive" }
    & $python @syncArguments
    if ($LASTEXITCODE -ne 0) { throw "Agent stack sync failed" }
}
