param([string]$Python = '.\.venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $taskRoot
$env:PYTHONIOENCODING = 'utf-8'
$originalPath = $env:PATH
$basePython = & $Python -c 'import sys; print(sys.base_prefix)'
if ($LASTEXITCODE -ne 0) { throw 'Python is not available' }
$env:PATH = "$(Split-Path -Parent $Python);$basePython;$env:SystemRoot\System32;$env:SystemRoot"
try {
    & $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name SnowMMEnhanced `
        --icon snowmm/assets/icons/app.ico --version-file tools/version_info_enhanced.txt `
        --add-data 'snowmm/assets;snowmm/assets' --collect-submodules snowmm `
        --hidden-import rarfile --hidden-import psutil enhanced_main.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
} finally { $env:PATH = $originalPath }
$output = Join-Path $taskRoot 'dist\SnowMMEnhanced'
Copy-Item -LiteralPath 'README_ENHANCED.md','THIRD_PARTY_NOTICES.md','requirements-enhanced.txt' -Destination $output -Force
Write-Output $output
# The public build intentionally includes no data profile, repair engine or Python repair runtime.
