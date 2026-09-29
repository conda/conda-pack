# Activate a conda-pack environment in PowerShell.

$newPrefix = Split-Path -Parent $PSScriptRoot

if ($env:CONDA_PREFIX -eq $newPrefix) {
    return
}

if ($env:CONDA_PREFIX) {
    $deactivate = Join-Path $env:CONDA_PREFIX 'Scripts\deactivate.ps1'
    if (-not (Test-Path -LiteralPath $deactivate)) {
        $deactivate = Join-Path (Join-Path $env:CONDA_PREFIX '..\..') 'Scripts\deactivate.ps1'
    }
    if (Test-Path -LiteralPath $deactivate) {
        & $deactivate
    }
}

$envName = Split-Path -Leaf $newPrefix
Set-Item Function:\global:_conda_pack_prompt_backup -Value (Get-Item Function:\prompt).ScriptBlock
$env:_CONDA_PACK_PROMPT_MODIFIER = "($envName) "
$env:CONDA_PREFIX = $newPrefix
$env:PATH = "$newPrefix;$newPrefix\Library\mingw-w64\bin;$newPrefix\Library\usr\bin;$newPrefix\Library\bin;$newPrefix\Scripts;$env:PATH"

function global:prompt {
    $prompt = if (Test-Path Function:\_conda_pack_prompt_backup) {
        & (Get-Item Function:\_conda_pack_prompt_backup).ScriptBlock
    } else {
        "PS $($executionContext.SessionState.Path.CurrentLocation)> "
    }
    "$env:_CONDA_PACK_PROMPT_MODIFIER$prompt"
}

$activateScripts = Join-Path $env:CONDA_PREFIX 'etc\conda\activate.d'
if (Test-Path -LiteralPath $activateScripts) {
    Get-ChildItem -LiteralPath $activateScripts -Filter '*.ps1' -File |
        Sort-Object Name |
        ForEach-Object { . $_.FullName }
}
