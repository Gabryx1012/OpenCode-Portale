$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$launcherRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $launcherRoot 'OpenCode-Portale-Windows.exe'
$binDir = Join-Path $launcherRoot 'bin'
$binary = Join-Path $binDir 'opencode.exe'
$versionFile = Join-Path $binDir 'version.txt'

if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw 'OpenCode-Portale-Windows.exe non trovato. Estrai l''intero ZIP prima di avviare Avvia-Tutto.bat.'
}

$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
switch ($arch) {
    'x64' { $assetName = 'opencode-windows-x64-baseline.zip' }
    'arm64' { $assetName = 'opencode-windows-arm64.zip' }
    default { throw "Architettura Windows non supportata: $arch" }
}

Write-Host 'OpenCode Portale - preparazione del computer' -ForegroundColor Cyan
Write-Host "Sistema: Windows $arch"

$needsInstall = -not (Test-Path -LiteralPath $binary -PathType Leaf)
if ($needsInstall) {
    Write-Host 'Cerco la release ufficiale di OpenCode...'
    $headers = @{ 'User-Agent' = 'OpenCode-Portale-Bootstrap/1.0'; 'Accept' = 'application/vnd.github+json' }
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/anomalyco/opencode/releases/latest' -Headers $headers -TimeoutSec 30
    $asset = $release.assets | Where-Object { $_.name -eq $assetName } | Select-Object -First 1
    if (-not $asset) { throw "Il pacchetto $assetName non esiste nella release ufficiale." }
    if (-not $asset.digest -or -not $asset.digest.StartsWith('sha256:')) { throw 'Il pacchetto non ha un digest SHA-256 verificabile.' }

    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ('opencode-portale-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    try {
        $archive = Join-Path $tempDir $assetName
        Write-Host "Scarico OpenCode $($release.tag_name)..."
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archive -TimeoutSec 180
        $stream = [System.IO.File]::OpenRead($archive)
        $hasher = [System.Security.Cryptography.SHA256]::Create()
        try {
            $actualHash = [System.BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
        }
        finally {
            $stream.Dispose()
            $hasher.Dispose()
        }
        $expectedHash = $asset.digest.Substring(7).ToLowerInvariant()
        if ($actualHash -ne $expectedHash) { throw 'Il controllo SHA-256 non corrisponde. Installazione interrotta.' }

        Add-Type -AssemblyName 'System.IO.Compression.FileSystem'
        $extractDir = Join-Path $tempDir 'extracted'
        [System.IO.Compression.ZipFile]::ExtractToDirectory($archive, $extractDir)
        $extracted = Get-ChildItem -LiteralPath $extractDir -Recurse -File -Filter 'opencode.exe' | Select-Object -First 1
        if (-not $extracted) { throw "opencode.exe non trovato nell'archivio verificato." }
        New-Item -ItemType Directory -Force -Path $binDir | Out-Null
        Copy-Item -LiteralPath $extracted.FullName -Destination $binary -Force
        Set-Content -LiteralPath $versionFile -Value $release.tag_name -Encoding utf8
        Write-Host "OpenCode $($release.tag_name) installato e verificato." -ForegroundColor Green
    }
    finally {
        if (Test-Path -LiteralPath $tempDir) {
            # tempDir is created above from the OS temp root and a fixed prefix.
            $resolved = [System.IO.Path]::GetFullPath($tempDir)
            $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
            if ($resolved.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
                [System.IO.Path]::GetFileName($resolved).StartsWith('opencode-portale-')) {
                Remove-Item -LiteralPath $resolved -Recurse -Force
            }
        }
    }
}
else {
    $version = if (Test-Path -LiteralPath $versionFile) { (Get-Content -LiteralPath $versionFile -Raw).Trim() } else { 'gia presente' }
    Write-Host "OpenCode $version trovato."
}

$env:OPENCODE_BIN = $binary
Write-Host 'Apro il pannello grafico...'
& $launcher
exit $LASTEXITCODE
