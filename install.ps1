param(
    [switch]$DryRun,
    [switch]$SkipHermes,
    [switch]$NonInteractive,
    [string]$Answers = "",
    [string]$SourceDir = "",
    [string]$HermesRef = $(if ($env:HERMES_REF) { $env:HERMES_REF } else { "v2026.8.3" }),
    [string]$HermesCommit = $(if ($env:HERMES_COMMIT) { $env:HERMES_COMMIT } else { "" }),
    [string]$BuilderRepo = $(if ($env:HERMES_BUILDER_REPO) { $env:HERMES_BUILDER_REPO } else { "kousoeie-beep/hermes-builder" }),
    [string]$BuilderRef = $(if ($env:HERMES_BUILDER_REF) { $env:HERMES_BUILDER_REF } else { "v0.1.1" })
)

$ErrorActionPreference = "Stop"
$defaultHermesRef = "v2026.8.3"
$defaultHermesCommit = "3c27eb6234bf91b8ceee9e9071591b31e9b148cb"
$builderHome = if ($env:HERMES_BUILDER_HOME) { $env:HERMES_BUILDER_HOME } else { "$env:LOCALAPPDATA\hermes-builder\app" }
$binDir = "$env:LOCALAPPDATA\hermes-builder\bin"
$hermesHome = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { "$env:LOCALAPPDATA\hermes" }
$env:Path = "$hermesHome\bin;$env:Path"

function Invoke-WithRetry {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Operation,
        [int]$MaxAttempts = 5
    )
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return & $Operation
        } catch {
            if ($attempt -eq $MaxAttempts) { throw }
            $delay = [Math]::Min(2 * $attempt, 10)
            Write-Warning "Temporary download failure ($attempt/$MaxAttempts). Retry in ${delay}s."
            Start-Sleep -Seconds $delay
        }
    }
}

if ($NonInteractive -and -not $Answers) {
    throw "-NonInteractive requires -Answers <path>"
}

if (-not $HermesCommit) {
    if ($HermesRef -eq $defaultHermesRef) {
        $HermesCommit = $defaultHermesCommit
    } elseif ($HermesRef -match '^[0-9a-fA-F]{40}$') {
        $HermesCommit = $HermesRef
    } elseif (-not $DryRun -and -not $SkipHermes) {
        $encodedRef = [Uri]::EscapeDataString($HermesRef)
        Write-Host "-> Resolve Hermes ref to commit SHA: $HermesRef"
        $commitInfo = Invoke-WithRetry {
            Invoke-RestMethod -Headers @{ Accept = "application/vnd.github+json" } -Uri "https://api.github.com/repos/NousResearch/hermes-agent/commits/$encodedRef"
        }
        $HermesCommit = $commitInfo.sha
    }
}

if ($HermesCommit -and $HermesCommit -notmatch '^[0-9a-fA-F]{40}$') {
    throw "HermesCommit must be a full 40-character commit SHA: $HermesCommit"
}

Write-Host "Hermes Builder v0.1.1"
Write-Host "  Hermes ref: $HermesRef"
Write-Host "  Hermes commit: $(if ($HermesCommit) { $HermesCommit } else { '<resolve during install>' })"
Write-Host "  Builder:    $BuilderRepo@$BuilderRef"

if ($DryRun) {
    $commitLabel = if ($HermesCommit) { $HermesCommit.Substring(0, 12) } else { "resolve during install" }
    Write-Host "[dry-run] Install Hermes $HermesRef ($commitLabel)"
    Write-Host "[dry-run] Install Builder into $builderHome"
    Write-Host "[dry-run] Run hermes-builder setup"
    exit 0
}

if (-not $SkipHermes) {
    if (-not $HermesCommit) {
        throw "Hermes refのcommit SHAを解決できませんでした: $HermesRef"
    }
    $installer = Join-Path $env:TEMP "hermes-install-$([guid]::NewGuid()).ps1"
    $installerUrl = "https://raw.githubusercontent.com/NousResearch/hermes-agent/$HermesCommit/scripts/install.ps1"
    Write-Host "-> Download official Hermes installer"
    Invoke-WithRetry {
        Invoke-WebRequest -UseBasicParsing $installerUrl -OutFile $installer
    } | Out-Null
    try {
        & $installer -SkipSetup -Commit $HermesCommit
    } finally {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    }
} elseif (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
    throw "-SkipHermesが指定されましたがhermesがPATHにありません。"
}

$staging = Join-Path $env:TEMP "hermes-builder-$([guid]::NewGuid())"
if ($SourceDir) {
    if (-not (Test-Path (Join-Path $SourceDir "src\hermes_builder"))) {
        throw "Hermes Builder sourceではありません: $SourceDir"
    }
    Copy-Item -Recurse -Force $SourceDir $staging
} else {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Hermes導入後もgitが見つかりません。新しいPowerShellで再実行してください。"
    }
    & git clone --depth 1 --branch $BuilderRef "https://github.com/$BuilderRepo.git" $staging
    if ($LASTEXITCODE -ne 0) { throw "Hermes Builderのdownloadに失敗しました" }
}

if (Test-Path $builderHome) {
    $backup = "$builderHome.backup.$(Get-Date -Format yyyyMMddHHmmssfff).$([guid]::NewGuid().ToString('N').Substring(0, 8))"
    Move-Item $builderHome $backup
    Write-Host "-> Existing Builder moved to $backup"
}
New-Item -ItemType Directory -Force -Path (Split-Path $builderHome -Parent), $binDir | Out-Null
Move-Item $staging $builderHome

$python = Join-Path $hermesHome "hermes-agent\venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

$wrapper = Join-Path $binDir "hermes-builder.cmd"
$wrapperText = "@echo off`r`nchcp 65001 >nul`r`nset `"PYTHONUTF8=1`"`r`nset `"PYTHONPATH=$builderHome\src`"`r`n`"$python`" -m hermes_builder %*`r`n"
$utf8WithoutBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText($wrapper, $wrapperText, $utf8WithoutBom)

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ';') -notcontains $binDir) {
    $updatedUserPath = if ($userPath) { "$userPath;$binDir" } else { $binDir }
    [Environment]::SetEnvironmentVariable("Path", $updatedUserPath, "User")
}
$env:Path = "$binDir;$hermesHome\bin;$env:Path"

$arguments = @("-m", "hermes_builder", "setup", "--yes")
if ($Answers) { $arguments += @("--answers", $Answers) }
if ($NonInteractive) { $arguments += "--non-interactive" }
$env:PYTHONPATH = "$builderHome\src"
$env:PYTHONUTF8 = "1"
& $python @arguments
exit $LASTEXITCODE
