param(
    [Alias("Host")]
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8010,
    [ValidateSet("serve", "dev")]
    [string]$FrontendMode = "serve",
    [int]$WebPort = 4173,
    [bool]$HideBackendWindow = $true
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$webDir = Join-Path $repoRoot "agent_workbench\web"
Set-Location $repoRoot

function Resolve-PythonRunner {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @{ Kind = "python"; Path = $pythonCmd.Source }
    }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        return @{ Kind = "py"; Path = $pyCmd.Source }
    }

    $fallback = "C:\Users\11761\AppData\Local\Python\pythoncore-3.12-64\python.exe"
    if (Test-Path $fallback) {
        return @{ Kind = "python"; Path = $fallback }
    }

    throw "Python interpreter not found. Please configure python in PATH or update start_web.ps1."
}

function Ensure-WebBuild {
    if (-not (Test-Path (Join-Path $webDir "package.json"))) {
        throw "New React frontend directory not found: $webDir"
    }

    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npmCmd) {
        throw "npm not found. Please install Node.js 18+ and retry."
    }

    if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
        Write-Host "Installing web dependencies..."
        Push-Location $webDir
        try {
            & $npmCmd.Source install
        }
        finally {
            Pop-Location
        }
    }

    if (-not (Test-Path (Join-Path $webDir "dist\index.html"))) {
        Write-Host "Building React frontend..."
        Push-Location $webDir
        try {
            & $npmCmd.Source run build
        }
        finally {
            Pop-Location
        }
    }
}

function Start-UvicornForeground([hashtable]$runner) {
    if ($runner.Kind -eq "py") {
        & $runner.Path -3 -m uvicorn agent_workbench.api:app --host $BindHost --port $Port
    }
    else {
        & $runner.Path -m uvicorn agent_workbench.api:app --host $BindHost --port $Port
    }
}

function Start-UvicornBackground([hashtable]$runner) {
    $common = @{
        PassThru         = $true
        WorkingDirectory = $repoRoot
    }
    if ($HideBackendWindow) {
        $common["WindowStyle"] = "Hidden"
    }

    if ($runner.Kind -eq "py") {
        return Start-Process -FilePath $runner.Path -ArgumentList @(
            "-3", "-m", "uvicorn", "agent_workbench.api:app",
            "--host", $BindHost,
            "--port", $Port,
            "--reload"
        ) @common
    }

    return Start-Process -FilePath $runner.Path -ArgumentList @(
        "-m", "uvicorn", "agent_workbench.api:app",
        "--host", $BindHost,
        "--port", $Port,
        "--reload"
    ) @common
}

$pythonRunner = Resolve-PythonRunner

if ($FrontendMode -eq "serve") {
    Ensure-WebBuild
    Write-Host "Starting Ludens-Flow web workbench at http://$BindHost`:$Port/ (mode: serve)"
    Write-Host "Repo root: $repoRoot"
    Start-UvicornForeground $pythonRunner
    exit $LASTEXITCODE
}

$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    throw "npm not found. Please install Node.js 18+ and retry."
}

Write-Host "Starting Ludens-Flow backend at http://$BindHost`:$Port/ and Vite at http://$BindHost`:$WebPort/"
Write-Host "Repo root: $repoRoot"

$backend = Start-UvicornBackground $pythonRunner
Write-Host "Backend PID: $($backend.Id)"

$env:VITE_API_PROXY_TARGET = "http://$BindHost`:$Port"

try {
    Push-Location $webDir
    & $npmCmd.Source run dev -- --host $BindHost --port $WebPort
}
finally {
    Pop-Location
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force
    }
}
