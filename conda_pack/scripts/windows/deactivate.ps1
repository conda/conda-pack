# Deactivate a conda-pack environment in PowerShell.

if (-not $env:CONDA_PREFIX) {
    return
}

$activePrefix = $env:CONDA_PREFIX
$deactivateScripts = Join-Path $activePrefix 'etc\conda\deactivate.d'
if (Test-Path -LiteralPath $deactivateScripts) {
    Get-ChildItem -LiteralPath $deactivateScripts -Filter '*.ps1' -File |
        Sort-Object Name |
        ForEach-Object { . $_.FullName }
}

$targets = @(
    $activePrefix,
    (Join-Path $activePrefix 'Library\mingw-w64\bin'),
    (Join-Path $activePrefix 'Library\usr\bin'),
    (Join-Path $activePrefix 'Library\bin'),
    (Join-Path $activePrefix 'Scripts')
)
$env:PATH = ($env:PATH -split ';' | Where-Object {
    $entry = $_
    $entry -and -not ($targets | Where-Object { $_ -ieq $entry })
}) -join ';'
$env:CONDA_PREFIX = $null

if ($env:_CONDA_PACK_OLD_PS1) {
    Set-Item Function:\global:prompt ([scriptblock]::Create($env:_CONDA_PACK_OLD_PS1))
}
$env:_CONDA_PACK_OLD_PS1 = $null
$env:_CONDA_PACK_PROMPT_MODIFIER = $null
