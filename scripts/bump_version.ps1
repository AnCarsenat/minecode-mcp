<#
.SYNOPSIS
  Bump patch version in pyproject.toml and optionally commit/tag/push.

.DESCRIPTION
  Finds the first line matching `version = "X.Y.Z"` in `pyproject.toml`,
  increments the patch (Z) by one, writes the file, prints the new version,
  and if `-Git` is supplied runs git add/commit/tag/push.

.EXAMPLE
  .\scripts\bump_version.ps1
  .\scripts\bump_version.ps1 -Git
#>

param(
    [switch]$Git
)

$pyproject = "pyproject.toml"
if (-not (Test-Path $pyproject)) {
    Write-Error "pyproject.toml not found in current directory"
    exit 1
}

$content = Get-Content -Path $pyproject -Raw -ErrorAction Stop
$pattern = 'version\s*=\s*"(\d+)\.(\d+)\.(\d+)"'

$match = [regex]::Match($content, $pattern)
if (-not $match.Success) {
    Write-Error "Could not find version = \"X.Y.Z\" in pyproject.toml"
    exit 1
}

$major = [int]$match.Groups[1].Value
$minor = [int]$match.Groups[2].Value
$patch = [int]$match.Groups[3].Value
$patch += 1
$newVersion = "$major.$minor.$patch"

# Replace the first occurrence, preserving surrounding whitespace
$newContent = [regex]::Replace($content, $pattern, "version = \"$newVersion\"", 1)

Set-Content -Path $pyproject -Value $newContent -Encoding UTF8
Write-Output $newVersion

if ($Git) {
    try {
        git add $pyproject
        git commit -m "Bump version to $newVersion"
        $tag = "v$newVersion"
        git tag $tag
        git push
        git push origin $tag
    }
    catch {
        Write-Error "Git operations failed: $_"
        exit 1
    }
}
