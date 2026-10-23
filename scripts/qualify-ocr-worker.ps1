# DEFERRED: not part of C07 or the two-device critical path.
# Use only after a measured need and a new device-based setup checkpoint.
# Any Windows device may still build modules; no execution role is assigned.
# Read-only, Windows PowerShell 5.1+. Paste into PowerShell from the repo root.
# No installs, downloads, service starts, elevation, or execution-policy changes.
$ErrorActionPreference = 'Continue'
Write-Output "OCR worker qualification $(Get-Date -Format o)"
Write-Output "Directory: $((Get-Location).Path)"
Write-Output "Architecture: $env:PROCESSOR_ARCHITECTURE"
Get-PSDrive -Name C,D -PSProvider FileSystem -ErrorAction SilentlyContinue |
    Select-Object Name, @{Name='FreeGiB'; Expression={[math]::Round($_.Free / 1GB, 1)}}
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    & nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader
} else { Write-Output 'NVIDIA driver probe unavailable' }
if (Get-Command py -ErrorAction SilentlyContinue) { & py -0p }
if (Get-Command python -ErrorAction SilentlyContinue) {
    $ocrPython = (Get-Command python).Source
    if ($ocrPython -notmatch 'WindowsApps') { & $ocrPython --version }
    else { Write-Output 'python is a Store alias, not a verified interpreter' }
}
if (Get-Command wsl -ErrorAction SilentlyContinue) { & wsl --list --verbose }
if (Get-Command docker -ErrorAction SilentlyContinue) {
    & docker --host npipe:////./pipe/docker_engine info --format 'Docker={{.ServerVersion}} OS={{.OSType}} Arch={{.Architecture}} Memory={{.MemTotal}}'
} else { Write-Output 'Docker unavailable' }
# No Ollama CLI heartbeat: it can start a stopped service. Disable proxies.
foreach ($ocrEndpoint in @('version', 'tags')) {
    $ocrResponse = $null
    $ocrReader = $null
    try {
        $ocrRequest = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:11434/api/$ocrEndpoint")
        $ocrRequest.Proxy = $null
        $ocrRequest.AllowAutoRedirect = $false
        $ocrRequest.Timeout = 3000
        $ocrRequest.ReadWriteTimeout = 3000
        $ocrResponse = $ocrRequest.GetResponse()
        $ocrReader = New-Object System.IO.StreamReader($ocrResponse.GetResponseStream())
        $ocrResult = $ocrReader.ReadToEnd() | ConvertFrom-Json
        if ($ocrEndpoint -eq 'version') { Write-Output "Ollama $($ocrResult.version)" }
        else { $ocrResult.models | Select-Object name, size, digest }
    } catch { Write-Output "Ollama /api/$ocrEndpoint unavailable; leave it stopped if stopped" }
    finally {
        if ($ocrReader) { $ocrReader.Dispose() }
        if ($ocrResponse) { $ocrResponse.Dispose() }
    }
}
