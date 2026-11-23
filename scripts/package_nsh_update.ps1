[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $Archive,
    [Parameter(Mandatory)] [string] $BaseUrl,
    [string] $AppDir = (Join-Path $PSScriptRoot '../nsh')
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
if ([string]::IsNullOrWhiteSpace($env:NSH_UPDATE_SIGNING_KEY)) {
    Write-Output '::warning title=NSH update feed omitted::Configure NSH_UPDATE_SIGNING_KEY for Windows self-updates. Users must update manually until a signed feed is published.'
    return
}

$archivePath = (Resolve-Path -LiteralPath $Archive).Path
$scratch = Join-Path ([IO.Path]::GetTempPath()) ("nsh-update-" + [guid]::NewGuid().ToString('N'))
$key = Join-Path $scratch 'update.secret'
try {
    New-Item -ItemType Directory -Path $scratch | Out-Null
    [IO.File]::WriteAllText($key, $env:NSH_UPDATE_SIGNING_KEY)
    Remove-Item Env:NSH_UPDATE_SIGNING_KEY
    & nsh update-manifest $archivePath --entry $AppDir --key $key --base-url $BaseUrl --out $scratch

    # Keep the legacy updater's latest.json separate. NSH resolves latest.json.sig beside either manifest name.
    $destination = Split-Path -Parent $archivePath
    Move-Item -LiteralPath (Join-Path $scratch 'latest.json') -Destination (Join-Path $destination 'latest-nsh.json')
    Move-Item -LiteralPath (Join-Path $scratch 'latest.json.sig') -Destination $destination
} finally {
    if (Test-Path -LiteralPath $scratch) { Remove-Item -LiteralPath $scratch -Recurse -Force }
}
