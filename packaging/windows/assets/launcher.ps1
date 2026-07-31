$ErrorActionPreference = 'Stop'

function Write-LauncherError([string]$Message) {
    [Console]::Error.WriteLine("[ERROR] $Message")
}

function Get-PythonCandidate {
    $candidates = @()
    if ($env:LORE2MUD_PYTHON) {
        $candidates += @{ Command = $env:LORE2MUD_PYTHON; Prefix = @() }
    }
    $candidates += @{ Command = 'py.exe'; Prefix = @('-3') }
    $candidates += @{ Command = 'python.exe'; Prefix = @() }

    foreach ($candidate in $candidates) {
        try {
            $command = Get-Command $candidate.Command -ErrorAction Stop
            $versionText = (& $command.Source @($candidate.Prefix) -c "import sys; print('.'.join(str(n) for n in sys.version_info[:3]))")
            if ($LASTEXITCODE -ne 0) { continue }
            $version = [version]::Parse(($versionText | Select-Object -First 1).Trim())
            if ($version.Major -gt 3 -or ($version.Major -eq 3 -and $version.Minor -ge 11)) {
                return @{ Path = $command.Source; Prefix = @($candidate.Prefix); Version = $version }
            }
        } catch {
            continue
        }
    }
    return $null
}

try {
    $bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $archive = Join-Path $bundleRoot 'lore2mud.pyz'
    $content = Join-Path $bundleRoot 'original_demo'
    $metadataPath = Join-Path $bundleRoot 'bundle.json'
    if (-not (Test-Path -LiteralPath $archive -PathType Leaf) -or
        -not (Test-Path -LiteralPath $content -PathType Container) -or
        -not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) {
        throw 'The bundle is incomplete (expected lore2mud.pyz, original_demo, and bundle.json).'
    }

    $metadata = Get-Content -Raw -LiteralPath $metadataPath | ConvertFrom-Json
    $contentVersion = [string]$metadata.content_pack_version
    if ($contentVersion -notmatch '^[0-9A-Za-z][0-9A-Za-z._-]*$') {
        throw 'The bundle metadata contains an invalid content_pack_version.'
    }
    $packMetadata = Get-Content -Raw -LiteralPath (Join-Path $content 'pack.json') | ConvertFrom-Json
    if ([string]$packMetadata.version -ne $contentVersion) {
        throw 'The bundled content version does not match bundle.json.'
    }
    $dataRoot = if ($env:LORE2MUD_DATA_DIR) {
        [IO.Path]::GetFullPath($env:LORE2MUD_DATA_DIR)
    } else {
        Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'lore2mud'
    }
    $saveRoot = Join-Path $dataRoot 'saves'
    $saveDir = Join-Path $saveRoot "content-$contentVersion"
    New-Item -ItemType Directory -Force -Path $saveDir | Out-Null
    $legacySaves = @(Get-ChildItem -LiteralPath $saveRoot -File -Filter '*.json' -ErrorAction SilentlyContinue)
    if ($legacySaves.Count -gt 0) {
        Write-Output "[WARN] Legacy saves remain in $saveRoot and are not migrated. Back up the data directory before removing them."
    }
    $otherVersionDirs = @(
        Get-ChildItem -LiteralPath $saveRoot -Directory -Filter 'content-*' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -ne $saveDir }
    )
    if ($otherVersionDirs.Count -gt 0) {
        Write-Output "[WARN] Other content-version saves remain in $saveRoot and are not loaded by this bundle. Back up the data directory before removing them."
    }

    $python = Get-PythonCandidate
    if ($null -eq $python) {
        throw 'Python 3.11 or newer was not found. Install Python from python.org, then run this entry again.'
    }

    $mode = if ($args.Count -gt 0) { $args[0] } else { '' }
    if ($mode -eq '--diagnose') {
        Write-Output "lore2mud bundle $($metadata.version)"
        Write-Output "Content pack version: $contentVersion"
        Write-Output "Bundle root: $bundleRoot"
        Write-Output "Content pack: $content"
        Write-Output "Data directory: $dataRoot"
        Write-Output "Save directory: $saveDir"
        Write-Output "Python: $($python.Path) ($($python.Version))"
        & $python.Path @($python.Prefix) $archive validate --content $content
        exit $LASTEXITCODE
    }

    $gameArgs = @($archive, 'play', '--content', $content, '--save-dir', $saveDir)
    if ($args.Count -gt 0) {
        $extra = if ($mode -eq '--smoke' -and $args.Count -eq 1) {
            @()
        } elseif ($mode -eq '--smoke') {
            @($args[1..($args.Count - 1)])
        } else {
            @($args)
        }
        if ($extra.Count -gt 0) { $gameArgs += $extra }
    }
    & $python.Path @($python.Prefix) @gameArgs
    exit $LASTEXITCODE
} catch {
    Write-LauncherError $_.Exception.Message
    exit 2
}
