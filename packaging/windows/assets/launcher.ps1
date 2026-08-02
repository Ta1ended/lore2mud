$ErrorActionPreference = 'Stop'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:LORE2MUD_UTF8_IO = '1'

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
                return [pscustomobject]@{
                    Path = $command.Source
                    Prefix = @($candidate.Prefix)
                    Label = "Python $version"
                }
            }
        } catch {
            continue
        }
    }
    return $null
}

function Resolve-BundleRuntime([string]$BundleRoot, [object]$Metadata) {
    $runtimeName = [string]$Metadata.runtime
    if ($runtimeName -eq 'pyinstaller') {
        $executable = Join-Path $BundleRoot 'runtime\lore2mud.exe'
        if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
            throw 'The PyInstaller runtime is incomplete (expected runtime\lore2mud.exe).'
        }
        return [pscustomobject]@{
            Name = $runtimeName
            Path = $executable
            Prefix = @()
            Label = 'bundled PyInstaller runtime'
        }
    }
    if ($runtimeName -eq 'zipapp') {
        $archive = Join-Path $BundleRoot 'lore2mud.pyz'
        if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
            throw 'The zipapp runtime is incomplete (expected lore2mud.pyz).'
        }
        $python = Get-PythonCandidate
        if ($null -eq $python) {
            throw 'Python 3.11 or newer was not found. Install Python from python.org, then run this entry again.'
        }
        return [pscustomobject]@{
            Name = $runtimeName
            Path = $python.Path
            Prefix = @($python.Prefix) + @($archive)
            Label = $python.Label
        }
    }
    throw "Unsupported bundle runtime: $runtimeName"
}

function ConvertTo-CommandLineArgument([string]$Value) {
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') {
        return $Value
    }

    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $backslashes += 1
            continue
        }
        if ($character -eq '"') {
            [void]$builder.Append(('\' * (($backslashes * 2) + 1)))
            [void]$builder.Append('"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append(('\' * $backslashes))
            $backslashes = 0
        }
        [void]$builder.Append($character)
    }
    if ($backslashes -gt 0) {
        [void]$builder.Append(('\' * ($backslashes * 2)))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Start-BundleProcess(
    [object]$Runtime,
    [string[]]$Arguments,
    [string]$WorkingDirectory
) {
    $allArguments = @($Runtime.Prefix) + @($Arguments)
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Runtime.Path
    $startInfo.Arguments = (($allArguments | ForEach-Object {
        ConvertTo-CommandLineArgument ([string]$_)
    }) -join ' ')
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $false

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'The game runtime did not start.'
    }
    return $process
}

function Wait-ForWebHealth(
    [System.Diagnostics.Process]$Process,
    [string]$HealthUrl,
    [string]$ExpectedContentVersion,
    [int]$TimeoutSeconds
) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) {
            throw "The Web runtime exited before it became healthy (exit $($Process.ExitCode))."
        }
        try {
            $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 1
            if ($response.StatusCode -eq 200) {
                $snapshot = $response.Content | ConvertFrom-Json
                if ([string]$snapshot.pack.id -eq 'original_demo' -and
                    [string]$snapshot.pack.version -eq $ExpectedContentVersion) {
                    return
                }
            }
        } catch {
            # Startup connection failures are expected until the child binds.
        }
        Start-Sleep -Milliseconds 200
    }
    throw "The Web runtime did not become healthy within $TimeoutSeconds seconds."
}

$webProcess = $null
try {
    $bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $content = Join-Path $bundleRoot 'original_demo'
    $metadataPath = Join-Path $bundleRoot 'bundle.json'
    if (-not (Test-Path -LiteralPath $content -PathType Container) -or
        -not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) {
        throw 'The bundle is incomplete (expected original_demo and bundle.json).'
    }

    $metadata = Get-Content -Raw -LiteralPath $metadataPath | ConvertFrom-Json
    if ([int]$metadata.format -ne 2 -or [string]$metadata.product -ne 'lore2mud') {
        throw 'The bundle metadata format is not supported by this launcher.'
    }
    if ([string]$metadata.default_mode -ne 'web') {
        throw 'The bundle metadata does not declare Web as the default mode.'
    }
    $contentVersion = [string]$metadata.content_pack_version
    if ($contentVersion -notmatch '^[0-9A-Za-z][0-9A-Za-z._-]*$') {
        throw 'The bundle metadata contains an invalid content_pack_version.'
    }
    $packMetadata = Get-Content -Raw -LiteralPath (Join-Path $content 'pack.json') | ConvertFrom-Json
    if ([string]$packMetadata.version -ne $contentVersion) {
        throw 'The bundled content version does not match bundle.json.'
    }

    $dataRoot = if ($env:LORE2MUD_DATA_DIR) {
        if (-not [IO.Path]::IsPathRooted($env:LORE2MUD_DATA_DIR)) {
            throw 'LORE2MUD_DATA_DIR must be an absolute path.'
        }
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

    $runtime = Resolve-BundleRuntime $bundleRoot $metadata
    $mode = if ($args.Count -eq 0) { '--web' } else { [string]$args[0] }
    $extra = if ($args.Count -gt 1) { @($args[1..($args.Count - 1)]) } else { @() }

    if ($mode -eq '--diagnose') {
        if ($extra.Count -gt 0) {
            throw '--diagnose does not accept additional arguments.'
        }
        Write-Output "lore2mud bundle $($metadata.version)"
        Write-Output "Bundle format: $($metadata.format)"
        Write-Output "Bundle runtime: $($runtime.Name)"
        if ($runtime.Name -eq 'pyinstaller') {
            Write-Output "Bundled Python version: $($metadata.bundled_python_version)"
            Write-Output "PyInstaller version: $($metadata.pyinstaller_version)"
        }
        Write-Output "Content pack version: $contentVersion"
        Write-Output "Bundle root: $bundleRoot"
        Write-Output "Content pack: $content"
        Write-Output "Data directory: $dataRoot"
        Write-Output "Save directory: $saveDir"
        Write-Output "Runtime: $($runtime.Path) ($($runtime.Label))"
        $diagnosticArgs = @($runtime.Prefix) + @('validate', '--content', $content)
        & $runtime.Path @diagnosticArgs
        exit $LASTEXITCODE
    }

    if ($mode -eq '--console' -or $mode -eq '--smoke') {
        $gameArgs = @($runtime.Prefix) + @('play') + @($extra) + @(
            '--content', $content,
            '--save-dir', $saveDir
        )
        & $runtime.Path @gameArgs
        exit $LASTEXITCODE
    }

    if ($mode -ne '--web' -and $mode -ne '--smoke-web') {
        throw "Unknown launcher mode '$mode'. Use --web, --console, or --diagnose."
    }

    $portText = if ($env:LORE2MUD_WEB_PORT) { $env:LORE2MUD_WEB_PORT } else { '8765' }
    $port = 0
    if (-not [int]::TryParse($portText, [ref]$port) -or $port -lt 1 -or $port -gt 65535) {
        throw 'LORE2MUD_WEB_PORT must be an integer from 1 through 65535.'
    }
    $gameArgs = @('web') + @($extra) + @(
        '--content', $content,
        '--save-dir', $saveDir,
        '--host', '127.0.0.1',
        '--port', [string]$port
    )
    $webProcess = Start-BundleProcess $runtime $gameArgs $bundleRoot
    $url = "http://127.0.0.1:$port/"
    Wait-ForWebHealth $webProcess ($url + 'api/snapshot') $contentVersion 30
    Write-Output "[OK] Web player ready: $url"
    if ($env:LORE2MUD_WEB_READY_FILE) {
        if (-not [IO.Path]::IsPathRooted($env:LORE2MUD_WEB_READY_FILE)) {
            throw 'LORE2MUD_WEB_READY_FILE must be an absolute path.'
        }
        $readyFile = [IO.Path]::GetFullPath($env:LORE2MUD_WEB_READY_FILE)
        $readyDirectory = Split-Path -Parent $readyFile
        if (-not (Test-Path -LiteralPath $readyDirectory -PathType Container)) {
            throw 'LORE2MUD_WEB_READY_FILE parent directory does not exist.'
        }
        [IO.File]::WriteAllText(
            $readyFile,
            ($url + [Environment]::NewLine),
            $utf8NoBom
        )
    }

    $suppressBrowser = $mode -eq '--smoke-web' -or $env:LORE2MUD_NO_BROWSER -eq '1'
    if (-not $suppressBrowser) {
        try {
            Start-Process -FilePath $url | Out-Null
        } catch {
            Write-Warning "Could not open the default browser. Open $url manually."
        }
    }

    $webProcess.WaitForExit()
    exit $webProcess.ExitCode
} catch {
    Write-LauncherError $_.Exception.Message
    exit 2
} finally {
    if ($null -ne $webProcess -and -not $webProcess.HasExited) {
        Stop-Process -Id $webProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
