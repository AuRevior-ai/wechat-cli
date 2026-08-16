param(
    [switch]$NoStart,
    [switch]$NoShortcuts,
    [switch]$SkipWebView2Check,
    [switch]$SkipProcessStop
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageMetadataPath = Join-Path $SourceDir "bootstrap-package.json"
$InstallDir = Join-Path $env:LOCALAPPDATA "WeChatCliWeb"
$LauncherDir = Join-Path $InstallDir "launcher"
$VersionsDir = Join-Path $InstallDir "versions"
$StateDir = Join-Path $InstallDir "state"
$RuntimeDir = Join-Path $InstallDir "runtime"
$CacheDir = Join-Path $InstallDir "cache"
$LogsDir = Join-Path $InstallDir "logs"
$LegacyAppDir = Join-Path $InstallDir "app"
$LegacyExePath = Join-Path $LegacyAppDir "wechat-cli.exe"
$StartScript = Join-Path $InstallDir "start-wechat-cli-web.bat"
$LauncherExePath = Join-Path $LauncherDir "wechat-cli-launcher.exe"
$CurrentStatePath = Join-Path $StateDir "current.json"
$InstallTransactionPath = Join-Path $StateDir "install-transaction.json"
$WebView2ProductId = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
$WebView2BootstrapperUrl = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

function Stop-InstalledWeChatCliWeb {
    param(
        [string]$TargetExePath,
        [string]$TargetInstallDir
    )

    $ResolvedExePath = $null
    if (Test-Path $TargetExePath) {
        $ResolvedExePath = (Resolve-Path $TargetExePath).Path
    }

    $RunningProcesses = Get-CimInstance Win32_Process | Where-Object {
        $MatchesName = $_.Name -in @("wechat-cli.exe", "wechat-cli-launcher.exe")
        $MatchesExe = $false
        if ($ResolvedExePath -and $_.ExecutablePath) {
            $MatchesExe = [string]::Equals(
                $_.ExecutablePath,
                $ResolvedExePath,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        }

        $MatchesInstallDir = $false
        if ($_.CommandLine) {
            $MatchesInstallDir = $_.CommandLine.IndexOf(
                $TargetInstallDir,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -ge 0
        }

        $MatchesDefaultWebServer = $false
        if ($_.CommandLine) {
            $MatchesDefaultWebServer = (
                $_.CommandLine -match '(^|\s)web(\s|$)' -and
                $_.CommandLine -match '--port(?:\s+|=)8787(?:\s|$)'
            )
        }

        $MatchesName -and ($MatchesExe -or $MatchesInstallDir -or $MatchesDefaultWebServer)
    }

    $StoppedServerParentIds = @(
        $RunningProcesses |
            ForEach-Object { $_.ParentProcessId } |
            Where-Object { $_ }
    )

    foreach ($Process in $RunningProcesses) {
        Write-Host "Stopping running WeChat CLI Web process: PID $($Process.ProcessId)"
        Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $Process.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
    }

    $RunningLaunchers = Get-CimInstance Win32_Process -Filter "name = 'cmd.exe'" | Where-Object {
        (
            $_.CommandLine -and
            $_.CommandLine.IndexOf($StartScript, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        ) -or (
            $StoppedServerParentIds -contains $_.ProcessId
        )
    }

    foreach ($Process in $RunningLaunchers) {
        Write-Host "Closing old WeChat CLI Web launcher window: PID $($Process.ProcessId)"
        Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $Process.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
    }
}

function Copy-WithRetry {
    param(
        [string]$Path,
        [string]$Destination,
        [switch]$Recurse,
        [int]$Attempts = 5
    )

    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        try {
            if ($Recurse) {
                Copy-Item -Force -Recurse -Path $Path -Destination $Destination
            } else {
                Copy-Item -Force -Path $Path -Destination $Destination
            }
            return
        } catch {
            if ($Attempt -eq $Attempts) {
                Write-Host ""
                Write-Host "Could not copy package files after stopping the old server."
                Write-Host "Please close any remaining WeChat CLI Web command windows and run install-and-start.bat again."
                throw
            }
            Start-Sleep -Milliseconds (500 * $Attempt)
        }
    }
}

function Write-JsonAtomic {
    param(
        [string]$Path,
        [object]$Value
    )

    $Parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    $Temporary = Join-Path $Parent (".{0}.{1}.tmp" -f ([IO.Path]::GetFileName($Path)), [Guid]::NewGuid().ToString("N"))
    try {
        $Json = $Value | ConvertTo-Json -Depth 10 -Compress
        [IO.File]::WriteAllText($Temporary, $Json, [Text.UTF8Encoding]::new($false))
        Move-Item -Force -Path $Temporary -Destination $Path
    } finally {
        if (Test-Path $Temporary) {
            Remove-Item -Force $Temporary -ErrorAction SilentlyContinue
        }
    }
}

function Write-InstallTransaction {
    param(
        [string]$Stage,
        [string]$TransactionId,
        [string]$Version,
        [string]$LegacyVersion,
        [string]$ErrorMessage = $null
    )

    $Value = [ordered]@{
        schema_version = 1
        transaction_id = $TransactionId
        stage = $Stage
        target_version = $Version
        legacy_version = $LegacyVersion
        updated_at = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    }
    if ($ErrorMessage) {
        $Value.error = $ErrorMessage
    }
    Write-JsonAtomic -Path $InstallTransactionPath -Value $Value
}

function Get-WebView2RuntimeVersion {
    $RegistryPaths = @(
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$WebView2ProductId",
        "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$WebView2ProductId",
        "HKCU:\Software\Microsoft\EdgeUpdate\Clients\$WebView2ProductId"
    )
    foreach ($RegistryPath in $RegistryPaths) {
        try {
            $Version = (Get-ItemProperty -Path $RegistryPath -Name "pv" -ErrorAction Stop).pv
            if ($Version -and $Version -ne "0.0.0.0" -and $Version -match '^\d+(\.\d+){3}$') {
                return $Version
            }
        } catch {
            continue
        }
    }
    return $null
}

function Ensure-WebView2Runtime {
    $ExistingVersion = Get-WebView2RuntimeVersion
    if ($ExistingVersion) {
        Write-Host "WebView2 Runtime detected: $ExistingVersion"
        return
    }

    $WebView2CacheDir = Join-Path $CacheDir "webview2"
    New-Item -ItemType Directory -Force -Path $WebView2CacheDir | Out-Null
    $Bootstrapper = Join-Path $WebView2CacheDir "MicrosoftEdgeWebview2Setup.exe"
    Write-Host "WebView2 Runtime is missing. Downloading the official Microsoft bootstrapper..."
    Invoke-WebRequest -Uri $WebView2BootstrapperUrl -OutFile $Bootstrapper -UseBasicParsing
    if (-not (Test-Path $Bootstrapper) -or (Get-Item $Bootstrapper).Length -le 0) {
        throw "Microsoft WebView2 bootstrapper download was empty."
    }
    $Process = Start-Process -FilePath $Bootstrapper -ArgumentList "/silent", "/install" -Wait -PassThru
    if ($Process.ExitCode -ne 0) {
        throw "Microsoft WebView2 Runtime installer failed with exit code $($Process.ExitCode)."
    }
    $InstalledVersion = Get-WebView2RuntimeVersion
    if (-not $InstalledVersion) {
        throw "WebView2 installer completed but the Runtime is still not detected."
    }
    Write-Host "WebView2 Runtime installed: $InstalledVersion"
}

function New-AppShortcut {
    param(
        [string]$ShortcutPath,
        [string]$TargetPath,
        [string]$WorkingDirectory
    )

    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.WorkingDirectory = $WorkingDirectory
    $Shortcut.IconLocation = "$TargetPath,0"
    $Shortcut.Description = "Start licensed WeChat CLI Web"
    $Shortcut.Save()
}

function Restore-InstallState {
    param(
        [bool]$HadCurrentState,
        [string]$CurrentStateBackupPath,
        [bool]$HadLauncher,
        [string]$LauncherBackupDir,
        [bool]$InstalledVersionCreated,
        [string]$InstalledVersionDir,
        [bool]$LegacyVersionCreated,
        [string]$LegacyVersionDir,
        [bool]$HadDesktopShortcut,
        [string]$DesktopShortcut,
        [string]$DesktopShortcutBackup,
        [bool]$HadStartMenuShortcut,
        [string]$StartMenuShortcut,
        [string]$StartMenuShortcutBackup
    )

    if ($HadCurrentState -and (Test-Path $CurrentStateBackupPath)) {
        Copy-Item -Force -Path $CurrentStateBackupPath -Destination $CurrentStatePath
    } elseif (-not $HadCurrentState -and (Test-Path $CurrentStatePath)) {
        Remove-Item -Force $CurrentStatePath -ErrorAction SilentlyContinue
    }

    if (Test-Path $LauncherDir) {
        Remove-Item -Force -Recurse $LauncherDir -ErrorAction SilentlyContinue
    }
    if ($HadLauncher -and (Test-Path $LauncherBackupDir)) {
        Move-Item -Path $LauncherBackupDir -Destination $LauncherDir
    }

    if ($InstalledVersionCreated -and (Test-Path $InstalledVersionDir)) {
        Remove-Item -Force -Recurse $InstalledVersionDir -ErrorAction SilentlyContinue
    }
    if ($LegacyVersionCreated -and (Test-Path $LegacyVersionDir)) {
        Remove-Item -Force -Recurse $LegacyVersionDir -ErrorAction SilentlyContinue
    }

    if ($HadDesktopShortcut -and (Test-Path $DesktopShortcutBackup)) {
        Copy-Item -Force -Path $DesktopShortcutBackup -Destination $DesktopShortcut
    } elseif (-not $HadDesktopShortcut) {
        Remove-Item -Force $DesktopShortcut -ErrorAction SilentlyContinue
    }
    if ($HadStartMenuShortcut -and (Test-Path $StartMenuShortcutBackup)) {
        Copy-Item -Force -Path $StartMenuShortcutBackup -Destination $StartMenuShortcut
    } elseif (-not $HadStartMenuShortcut) {
        Remove-Item -Force $StartMenuShortcut -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $PackageMetadataPath)) {
    throw "Package is incomplete: bootstrap-package.json was not found."
}
$PackageMetadata = Get-Content -Raw -Encoding UTF8 $PackageMetadataPath | ConvertFrom-Json
if ($PackageMetadata.schema_version -ne 1 -or $PackageMetadata.product -ne "wechat-cli-web") {
    throw "Package metadata is invalid."
}
$Version = [string]$PackageMetadata.version
$LegacyVersion = [string]$PackageMetadata.legacy_version
foreach ($CandidateVersion in @($Version, $LegacyVersion)) {
    if ($CandidateVersion -notmatch '^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') {
        throw "Package version metadata is invalid."
    }
}
if ($LegacyVersion -eq $Version) {
    throw "Legacy bootstrap version cannot equal the target version."
}

$SourceLauncherDir = Join-Path $SourceDir "launcher"
$SourceVersionDir = Join-Path $SourceDir ("versions\{0}" -f $Version)
$SourceLauncherExe = Join-Path $SourceLauncherDir "wechat-cli-launcher.exe"
$SourceConfig = Join-Path $SourceLauncherDir "launcher-config.json"
$SourceAppExe = Join-Path $SourceVersionDir "wechat-cli.exe"
$SourceAppManifest = Join-Path $SourceVersionDir "app-manifest.json"
foreach ($RequiredPath in @($SourceLauncherExe, $SourceConfig, $SourceAppExe, $SourceAppManifest)) {
    if (-not (Test-Path $RequiredPath)) {
        throw "Package is incomplete: $RequiredPath was not found."
    }
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $VersionsDir | Out-Null
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

if (($SkipWebView2Check -or $SkipProcessStop) -and (-not $NoStart -or -not $NoShortcuts)) {
    throw "Isolation switches require -NoStart and -NoShortcuts."
}
if (-not $SkipWebView2Check) {
    Ensure-WebView2Runtime
}
if (-not $SkipProcessStop) {
    Stop-InstalledWeChatCliWeb -TargetExePath $LegacyExePath -TargetInstallDir $InstallDir
}

$InstallTransactionId = [Guid]::NewGuid().ToString("N")
$StagingRoot = Join-Path $InstallDir ("cache\installer\{0}" -f $InstallTransactionId)
$StagedLauncherDir = Join-Path $StagingRoot "launcher"
$StagedVersionDir = Join-Path $StagingRoot ("versions\{0}" -f $Version)
$StagedLegacyVersionDir = Join-Path $StagingRoot ("versions\{0}" -f $LegacyVersion)
$CurrentStateBackupPath = Join-Path $StagingRoot "current.json.backup"
$LauncherBackupDir = Join-Path $InstallDir "launcher.previous"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "WeChat CLI Web.lnk"
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\WeChat CLI Web"
$StartMenuShortcut = Join-Path $StartMenuDir "WeChat CLI Web.lnk"
$DesktopShortcutBackup = Join-Path $StagingRoot "desktop-shortcut.lnk"
$StartMenuShortcutBackup = Join-Path $StagingRoot "start-menu-shortcut.lnk"
$InstalledVersionDir = Join-Path $VersionsDir $Version
$LegacyVersionDir = Join-Path $VersionsDir $LegacyVersion
$HadCurrentState = Test-Path $CurrentStatePath
$HadLauncher = Test-Path $LauncherDir
$HadDesktopShortcut = Test-Path $DesktopShortcut
$HadStartMenuShortcut = Test-Path $StartMenuShortcut
$InstalledVersionCreated = $false
$LegacyVersionCreated = $false
$Committed = $false

New-Item -ItemType Directory -Force -Path $StagedLauncherDir | Out-Null
New-Item -ItemType Directory -Force -Path $StagedVersionDir | Out-Null
Write-InstallTransaction -Stage "preparing" -TransactionId $InstallTransactionId -Version $Version -LegacyVersion $LegacyVersion

try {
    if ($HadCurrentState) {
        Copy-Item -Force -Path $CurrentStatePath -Destination $CurrentStateBackupPath
    }
    if (-not $NoShortcuts) {
        if ($HadDesktopShortcut) {
            Copy-Item -Force -Path $DesktopShortcut -Destination $DesktopShortcutBackup
        }
        if ($HadStartMenuShortcut) {
            Copy-Item -Force -Path $StartMenuShortcut -Destination $StartMenuShortcutBackup
        }
    }

    Copy-WithRetry -Recurse -Path (Join-Path $SourceLauncherDir "*") -Destination $StagedLauncherDir
    Copy-WithRetry -Recurse -Path (Join-Path $SourceVersionDir "*") -Destination $StagedVersionDir

    if (-not (Test-Path $InstalledVersionDir)) {
        Move-Item -Path $StagedVersionDir -Destination $InstalledVersionDir
        $InstalledVersionCreated = $true
    } else {
        $InstalledManifest = Join-Path $InstalledVersionDir "app-manifest.json"
        if (-not (Test-Path $InstalledManifest)) {
            throw "Existing version directory is incomplete: $InstalledVersionDir"
        }
        $ExistingMetadata = Get-Content -Raw -Encoding UTF8 $InstalledManifest | ConvertFrom-Json
        if ([string]$ExistingMetadata.version -ne $Version) {
            throw "Existing version directory metadata does not match $Version."
        }
    }

    $PreviousVersion = $null
    $SourceConfigData = Get-Content -Raw -Encoding UTF8 $SourceConfig | ConvertFrom-Json
    $Channel = $null
    if ($SourceConfigData.PSObject.Properties.Name -contains "channel") {
        $Channel = [string]$SourceConfigData.channel
    } elseif ($PackageMetadata.PSObject.Properties.Name -contains "channel") {
        $Channel = [string]$PackageMetadata.channel
    }
    if ($HadCurrentState) {
        try {
            $ExistingCurrent = Get-Content -Raw -Encoding UTF8 $CurrentStatePath | ConvertFrom-Json
            if ([string]$ExistingCurrent.current_version -ne $Version) {
                $PreviousVersion = [string]$ExistingCurrent.current_version
            } else {
                $PreviousVersion = $ExistingCurrent.previous_version
            }
            if ($ExistingCurrent.channel) {
                $Channel = [string]$ExistingCurrent.channel
            }
        } catch {
            throw "Existing current.json is invalid. Run repair or restore it before reinstalling."
        }
    } elseif (Test-Path $LegacyExePath) {
        if (-not (Test-Path $LegacyVersionDir)) {
            New-Item -ItemType Directory -Force -Path $StagedLegacyVersionDir | Out-Null
            Copy-WithRetry -Recurse -Path (Join-Path $LegacyAppDir "*") -Destination $StagedLegacyVersionDir
            if (-not (Test-Path (Join-Path $StagedLegacyVersionDir "wechat-cli.exe"))) {
                throw "Legacy installation is missing app\wechat-cli.exe."
            }
            Write-JsonAtomic -Path (Join-Path $StagedLegacyVersionDir "app-manifest.json") -Value ([ordered]@{
                product = "wechat-cli-web"
                version = $LegacyVersion
                platform = "windows"
                architecture = "x86_64"
                entrypoint = "wechat-cli.exe"
                build_id = "legacy-bootstrap"
            })
            Move-Item -Path $StagedLegacyVersionDir -Destination $LegacyVersionDir
            $LegacyVersionCreated = $true
        }
        $PreviousVersion = $LegacyVersion
    }
    if ($Channel -notin @("stable", "beta")) {
        throw "Package channel metadata is invalid."
    }

    Write-InstallTransaction -Stage "staged" -TransactionId $InstallTransactionId -Version $Version -LegacyVersion $LegacyVersion

    if (Test-Path $LauncherBackupDir) {
        Remove-Item -Force -Recurse $LauncherBackupDir
    }
    if ($HadLauncher) {
        Move-Item -Path $LauncherDir -Destination $LauncherBackupDir
    }
    Move-Item -Path $StagedLauncherDir -Destination $LauncherDir

    $ManifestHash = (Get-FileHash -Algorithm SHA256 $SourceAppManifest).Hash.ToLowerInvariant()
    Write-JsonAtomic -Path $CurrentStatePath -Value ([ordered]@{
        current_version = $Version
        previous_version = $PreviousVersion
        channel = $Channel
        activated_at = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
        manifest_sha256 = $ManifestHash
    })
    Write-InstallTransaction -Stage "switched" -TransactionId $InstallTransactionId -Version $Version -LegacyVersion $LegacyVersion

    if (-not $NoStart) {
        Write-Host "Starting licensed Launcher..."
        $LauncherProcess = Start-Process -FilePath $LauncherExePath -WorkingDirectory $LauncherDir -Wait -PassThru
        if ($LauncherProcess.ExitCode -ne 0) {
            throw "Launcher did not complete successfully (exit code $($LauncherProcess.ExitCode)). The legacy app remains untouched."
        }
    }
    Write-InstallTransaction -Stage "validated" -TransactionId $InstallTransactionId -Version $Version -LegacyVersion $LegacyVersion

    foreach ($Name in @(
        "start-wechat-cli-web.bat",
        "repair-wechat-cli-web.bat",
        "uninstall-wechat-cli-web.bat",
        "uninstall.ps1",
        "README-APP.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md"
    )) {
        $SourcePath = Join-Path $SourceDir $Name
        if (Test-Path $SourcePath) {
            Copy-WithRetry -Path $SourcePath -Destination $InstallDir
        }
    }

    if (-not $NoShortcuts) {
        New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null
        New-AppShortcut -ShortcutPath $DesktopShortcut -TargetPath $LauncherExePath -WorkingDirectory $LauncherDir
        New-AppShortcut -ShortcutPath $StartMenuShortcut -TargetPath $LauncherExePath -WorkingDirectory $LauncherDir
    }

    Write-InstallTransaction -Stage "committed" -TransactionId $InstallTransactionId -Version $Version -LegacyVersion $LegacyVersion
    $Committed = $true
    Remove-Item -Force $InstallTransactionPath -ErrorAction SilentlyContinue

    Write-Host "Installed WeChat CLI Web bootstrap to: $InstallDir"
    Write-Host "Current application version: $Version"
    if (Test-Path $LegacyExePath) {
        Write-Host "Existing legacy app was preserved at: $LegacyAppDir"
    }
} catch {
    $FailureMessage = $_.Exception.Message
    Restore-InstallState `
        -HadCurrentState $HadCurrentState `
        -CurrentStateBackupPath $CurrentStateBackupPath `
        -HadLauncher $HadLauncher `
        -LauncherBackupDir $LauncherBackupDir `
        -InstalledVersionCreated $InstalledVersionCreated `
        -InstalledVersionDir $InstalledVersionDir `
        -LegacyVersionCreated $LegacyVersionCreated `
        -LegacyVersionDir $LegacyVersionDir `
        -HadDesktopShortcut $HadDesktopShortcut `
        -DesktopShortcut $DesktopShortcut `
        -DesktopShortcutBackup $DesktopShortcutBackup `
        -HadStartMenuShortcut $HadStartMenuShortcut `
        -StartMenuShortcut $StartMenuShortcut `
        -StartMenuShortcutBackup $StartMenuShortcutBackup
    Write-InstallTransaction -Stage "rolled_back" -TransactionId $InstallTransactionId -Version $Version -LegacyVersion $LegacyVersion -ErrorMessage $FailureMessage
    throw
} finally {
    if (Test-Path $StagingRoot) {
        Remove-Item -Force -Recurse $StagingRoot -ErrorAction SilentlyContinue
    }
    if ($Committed -and (Test-Path $LauncherBackupDir)) {
        Write-Host "Previous launcher backup retained for repair: $LauncherBackupDir"
    }
}
