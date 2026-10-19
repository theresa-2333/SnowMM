# Build a wheel and source distribution, including every offline resource.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
if (Test-Path -LiteralPath (Join-Path $root ".build-deps")) {
    $env:PYTHONPATH = (Join-Path $root ".build-deps")
}
python -m build --no-isolation
if ($LASTEXITCODE -ne 0) { throw "Python package build failed: $LASTEXITCODE" }
