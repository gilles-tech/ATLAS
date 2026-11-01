$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw 'Python 3 required on BUILD machine only. Recipients do not need Python.'
}
py -3 -m venv .atlas-build-win
$python = Join-Path (Get-Location) '.atlas-build-win\Scripts\python.exe'
& $python -m pip install --disable-pip-version-check 'pyinstaller>=6,<7' 'pywebview>=5,<7'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $python packaging/build.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
New-Item -ItemType Directory -Force -Path release | Out-Null
& (Join-Path (Get-Location) 'dist\AtlasMarches\AtlasMarches.exe') --self-check --report (Join-Path (Get-Location) 'release\standalone-self-check-win.json')
if ($LASTEXITCODE -ne 0) { throw 'Standalone self-check failed; installer not produced' }
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
  $candidates = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe")
  $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $found) { throw 'Install Inno Setup 6 on BUILD machine, then run again.' }
  $isccPath = $found
} else { $isccPath = $iscc.Source }
& $isccPath packaging\AtlasMarches.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
Write-Host 'Installer generated: release\AtlasMarches-Setup-win64.exe'
Write-Host 'Unsigned test installer; production distribution requires Authenticode signing.'
