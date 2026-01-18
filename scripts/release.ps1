<#
.SYNOPSIS
  Clean old builds, build package, push to GitHub, and publish to PyPI.

.DESCRIPTION
  Usage:
    .\scripts\release.ps1 [-Bump] [-Publish] [-TokenFile <path>]

  -Bump: run scripts\bump_version.ps1 -Git to bump patch, commit, tag and push
  -Publish: upload built artifacts to PyPI (reads token from $TokenFile or env PYPI_API_TOKEN)
  -TokenFile: path to a file containing a PyPI API token (default: .\pip_token.txt)

.NOTES
  The script runs from the repository root. It will remove `dist/`, `build/`,
  and any `*.egg-info` directories before building.
#>

param(
    [switch]$Bump,
    [switch]$Publish,
    [string]$TokenFile = "pip_token.txt"
)

set -e

function Write-Info($m) { Write-Host "[info] $m" -ForegroundColor Cyan }
function Write-Err($m) { Write-Host "[error] $m" -ForegroundColor Red }

# Move to repo root (one level up from scripts folder)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

Write-Info "Repository root: $repoRoot"

# Remove previous build artifacts
Write-Info "Cleaning previous build files..."
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }
Get-ChildItem -Path . -Filter "*.egg-info" -Recurse -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}

# Optional bump (inline implementation: update pyproject.toml, commit, tag, push)
function Get-VersionFromPyproject {
    param($path)
    $text = Get-Content -Raw $path -ErrorAction Stop
    $m = [regex]::Match($text, 'version\s*=\s*"(\d+)\.(\d+)\.(\d+)"')
    if ($m.Success) { return @([int]$m.Groups[1].Value, [int]$m.Groups[2].Value, [int]$m.Groups[3].Value) }
    return $null
}

function Set-VersionInPyproject {
    param($path, $newVersion)
    $text = Get-Content -Raw $path -ErrorAction Stop
    $newText = [regex]::Replace($text, 'version\s*=\s*"\d+\.\d+\.\d+"', "version = \"$newVersion\"")
    Set-Content -Path $path -Value $newText -Encoding UTF8
}

if ($Bump) {
    $py = Join-Path $repoRoot "pyproject.toml"
    if (-not (Test-Path $py)) { Write-Err "pyproject.toml not found - cannot bump"; exit 1 }

    $v = Get-VersionFromPyproject $py
    if (-not $v) { Write-Err "Could not parse version from pyproject.toml"; exit 1 }
    $major = $v[0]; $minor = $v[1]; $patch = $v[2]
    $patch += 1
    $newVersion = "$major.$minor.$patch"
    Write-Info "Bumping version: $major.$minor.$($patch-1) -> $newVersion"
    Set-VersionInPyproject $py $newVersion

    # Commit, tag and push
    git add pyproject.toml
    git commit -m "Bump version to $newVersion"
    $tag = "v$newVersion"
    git tag $tag
    git push
    git push origin $tag
}
else {
    Write-Info "Skipping version bump"
}

# Determine python executable (prefer venv)
$venvPy = Join-Path $repoRoot "venv\Scripts\python.exe"
if (Test-Path $venvPy) { $python = $venvPy } else { $python = "python" }
Write-Info "Using Python: $python"

# Build distributions
Write-Info "Building distributions (sdist + wheel)..."
& $python -m build
if ($LASTEXITCODE -ne 0) { Write-Err "Build failed"; exit $LASTEXITCODE }

# If bump was not used, commit any local changes and push (optional)
if (-not $Bump) {
    $status = git status --porcelain
    if ($status) {
        Write-Info "Uncommitted changes detected — committing and pushing"
        git add -A
        git commit -m "Prepare release: build artifacts and metadata"
        git push
    }
    else {
        Write-Info "No local changes to commit"
    }
}
else {
    Write-Info "Version bump already handled pushing/tagging"
}

# Publish to PyPI
if ($Publish) {
    Write-Info "Publishing to PyPI..."

    if (Test-Path $TokenFile) {
        $token = (Get-Content -Raw $TokenFile).Trim()
        if (-not $token) { Write-Err "Token file is empty"; exit 1 }
        $env:TWINE_USERNAME = "__token__"
        $env:TWINE_PASSWORD = $token
    }
    elseif ($env:PYPI_API_TOKEN) {
        $env:TWINE_USERNAME = "__token__"
        $env:TWINE_PASSWORD = $env:PYPI_API_TOKEN
    }
    else {
        Write-Err "No PyPI token found. Provide a token file or set PYPI_API_TOKEN env var.";
        exit 1
    }

    # Upload only files for the current project version
    $distFiles = Get-ChildItem -Path dist -File | Where-Object { $_.Name -match "minecode_mcp-" }
    if (-not $distFiles) { Write-Err "No distribution files found in dist/"; exit 1 }

    & $python -m twine upload --non-interactive dist/*
    if ($LASTEXITCODE -ne 0) { Write-Err "Upload failed"; exit $LASTEXITCODE }
    Write-Info "Publish complete"
}
else {
    Write-Info "Skipping publish to PyPI"
}

Write-Info "Release script finished"
