param(
    [Alias("Host")]
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8010
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
Set-Location $repoRoot

$python = $null
$pyLauncher = $null

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
    $python = $pythonCmd.Source
}

if (-not $python) {
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $pyLauncher = $pyCmd.Source
    }
}

if (-not $python -and -not $pyLauncher) {
    $fallback = "C:\\Users\\11761\\AppData\\Local\\Python\\pythoncore-3.12-64\\python.exe"
    if (Test-Path $fallback) {
        $python = $fallback
    }
}

if (-not $python -and -not $pyLauncher) {
    throw "Python interpreter not found. Please configure python in PATH or update start_web.ps1."
}

Write-Host "Starting Ludens-Flow web workbench at http://$BindHost`:$Port/"
Write-Host "Repo root: $repoRoot"

if ($pyLauncher) {
    & $pyLauncher -3 -m uvicorn agent_workbench.api:app --host $BindHost --port $Port
} else {
    & $python -m uvicorn agent_workbench.api:app --host $BindHost --port $Port
}
