# Build a portable Windows application folder with PyInstaller.
#   pip install pyinstaller
#   pwsh tools/build_exe.ps1
param(
    [string]$Name = "SnowMM",
    [string]$Python = "python",
    [switch]$Console
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

# Keep unrelated tools (for example Poppler/Conda ICU DLLs) out of binary
# dependency resolution. Qt on Windows uses the operating system ICU API.
$pythonExecutable = (Get-Command $Python -ErrorAction Stop).Source
$pythonDirectory = Split-Path -Parent $pythonExecutable
$env:PATH = @($pythonDirectory, (Join-Path $pythonDirectory "Scripts"),
    (Join-Path $env:SystemRoot "System32"), $env:SystemRoot) -join ";"

if (Test-Path -LiteralPath (Join-Path $root ".build-deps")) {
    $env:PYTHONPATH = (Join-Path $root ".build-deps")
}

$windowMode = if ($Console) { "--console" } else { "--windowed" }
& $pythonExecutable -m PyInstaller --noconfirm --clean --onedir $windowMode --name $Name `
    --icon snowmm/assets/icons/app.ico `
    --version-file tools/version_info.txt `
    --add-data "snowmm/assets;snowmm/assets" `
    --collect-submodules snowmm `
    main.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

Write-Host "Built dist/$Name/$Name.exe"
