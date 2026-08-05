param(
    [switch]$Force,
    [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$InstallDir = Join-Path $env:LOCALAPPDATA "WeChatCliWeb"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "WeChat CLI Web.lnk"
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\WeChat CLI Web"
$UserDataDir = Join-Path $HOME ".wechat-cli"

if (-not $Force) {
    $Answer = Read-Host "Remove WeChat CLI Web program, launcher, license state and update cache? Type REMOVE to continue"
    if ($Answer -ne "REMOVE") {
        Write-Host "Uninstall cancelled."
        exit 2
    }
}

$Processes = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @("wechat-cli.exe", "wechat-cli-launcher.exe") -and
    $_.CommandLine -and
    $_.CommandLine.IndexOf($InstallDir, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}
foreach ($Process in $Processes) {
    Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
    Wait-Process -Id $Process.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
}

if (-not $NoShortcuts) {
    Remove-Item -Force $DesktopShortcut -ErrorAction SilentlyContinue
    Remove-Item -Force -Recurse $StartMenuDir -ErrorAction SilentlyContinue
}

if (Test-Path $InstallDir) {
    $RemovalDir = Join-Path $env:TEMP ("WeChatCliWeb-uninstall-{0}" -f [Guid]::NewGuid().ToString("N"))
    Move-Item -Path $InstallDir -Destination $RemovalDir
    Start-Process -WindowStyle Hidden -FilePath "cmd.exe" -ArgumentList @(
        "/d", "/c", "timeout /t 2 /nobreak >nul & rmdir /s /q `"$RemovalDir`""
    ) | Out-Null
}

Write-Host "WeChat CLI Web was removed."
Write-Host "User data was intentionally preserved at: $UserDataDir"
Write-Host "Delete that directory manually only if you also want to remove local WeChat CLI configuration and indexes."
