$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA "WeChatCliWeb"
$AppDir = Join-Path $InstallDir "app"
$ExePath = Join-Path $AppDir "wechat-cli.exe"
$StartScript = Join-Path $InstallDir "start-wechat-cli-web.bat"

function Stop-InstalledWeChatCliWeb {
    param(
        [string]$TargetExePath,
        [string]$TargetInstallDir
    )

    $ResolvedExePath = $null
    if (Test-Path $TargetExePath) {
        $ResolvedExePath = (Resolve-Path $TargetExePath).Path
    }

    $RunningProcesses = Get-CimInstance Win32_Process -Filter "name = 'wechat-cli.exe'" | Where-Object {
        $MatchesExe = $false
        if ($ResolvedExePath -and $_.ExecutablePath) {
            $MatchesExe = [string]::Equals($_.ExecutablePath, $ResolvedExePath, [System.StringComparison]::OrdinalIgnoreCase)
        }

        $MatchesInstallDir = $false
        if ($_.CommandLine) {
            $MatchesInstallDir = $_.CommandLine.IndexOf($TargetInstallDir, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        }

        $MatchesExe -or $MatchesInstallDir
    }

    foreach ($Process in $RunningProcesses) {
        Write-Host "Stopping running WeChat CLI Web process: PID $($Process.ProcessId)"
        Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $Process.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
    }

    $RunningLaunchers = Get-CimInstance Win32_Process -Filter "name = 'cmd.exe'" | Where-Object {
        $_.CommandLine -and $_.CommandLine.IndexOf($StartScript, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
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

if (-not (Test-Path (Join-Path $SourceDir "app\wechat-cli.exe"))) {
    throw "Package is incomplete: app\wechat-cli.exe was not found."
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null

Stop-InstalledWeChatCliWeb -TargetExePath $ExePath -TargetInstallDir $InstallDir

Copy-WithRetry -Recurse -Path (Join-Path $SourceDir "app\*") -Destination $AppDir
Copy-WithRetry -Path (Join-Path $SourceDir "start-wechat-cli-web.bat") -Destination $InstallDir
Copy-WithRetry -Path (Join-Path $SourceDir "README-APP.md") -Destination $InstallDir
if (Test-Path (Join-Path $SourceDir "LICENSE")) {
    Copy-WithRetry -Path (Join-Path $SourceDir "LICENSE") -Destination $InstallDir
}

$Shell = New-Object -ComObject WScript.Shell
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "WeChat CLI Web.lnk"
$Shortcut = $Shell.CreateShortcut($DesktopShortcut)
$Shortcut.TargetPath = $StartScript
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.IconLocation = "$ExePath,0"
$Shortcut.Description = "Start WeChat CLI Web on localhost"
$Shortcut.Save()

$StartMenuDir = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\WeChat CLI Web"
New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null
$StartMenuShortcut = Join-Path $StartMenuDir "WeChat CLI Web.lnk"
$Shortcut = $Shell.CreateShortcut($StartMenuShortcut)
$Shortcut.TargetPath = $StartScript
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.IconLocation = "$ExePath,0"
$Shortcut.Description = "Start WeChat CLI Web on localhost"
$Shortcut.Save()

Write-Host "Installed WeChat CLI Web to: $InstallDir"
Write-Host "Desktop shortcut: $DesktopShortcut"
Write-Host "Opening localhost web console..."
Start-Process -FilePath $StartScript -WorkingDirectory $InstallDir
