# Dot-source to keep $Config, $Data, $Run and environment variables in your shell.
[CmdletBinding()]
param(
    [string]$Workspace = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$GodotBin = 'D:\tools\Godot_v4.3-stable_win64\Godot_v4.3-stable_win64.exe',
    [ValidateSet('cpu', 'cuda')][string]$Device = 'cpu',
    [switch]$ImportAssets,
    [switch]$Smoke
)

$ErrorActionPreference = 'Stop'
$Workspace = (Resolve-Path -LiteralPath $Workspace).Path
$RocketProject = Join-Path $Workspace 'GodotRocketLanding'
$ModelProject = Join-Path $Workspace 'world_model'
$Activate = Join-Path $Workspace '.venv_3.11\Scripts\Activate.ps1'

foreach ($RequiredPath in @($GodotBin, $Activate,
        (Join-Path $RocketProject 'scripts\world_model_bridge.gd'),
        (Join-Path $ModelProject 'pyproject.toml'))) {
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
        throw "Required file not found: $RequiredPath"
    }
}

. $Activate
Set-Location -LiteralPath $ModelProject
$env:GODOT_BIN = (Resolve-Path -LiteralPath $GodotBin).Path
$env:GRL_PROJECT_PATH = (Resolve-Path -LiteralPath $RocketProject).Path
$Config = Join-Path $RocketProject 'configs\world_model_smoke.json'
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
    throw "Smoke configuration not found: $Config"
}

# Leaves are intentionally absent: collect/train create their own output folders.
$RunId = 'grl-smoke-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' +
    ([guid]::NewGuid().ToString('N').Substring(0, 6))
$Data = Join-Path $ModelProject "data\$RunId"
$Run = Join-Path $ModelProject "runs\$RunId"
foreach ($OutputPath in @($Data, $Run)) {
    if (Test-Path -LiteralPath $OutputPath) { throw "Output already exists: $OutputPath" }
}

if ($ImportAssets) {
    # The console executable is useful for manual import logs. The adapter uses
    # the main executable directly so its process ownership/PID check stays valid.
    $GodotConsole = Join-Path (Split-Path $env:GODOT_BIN -Parent) (
        [IO.Path]::GetFileNameWithoutExtension($env:GODOT_BIN) + '_console.exe')
    if (-not (Test-Path -LiteralPath $GodotConsole)) { $GodotConsole = $env:GODOT_BIN }
    & $GodotConsole --headless --path $env:GRL_PROJECT_PATH --editor --import --quit
    if ($LASTEXITCODE -ne 0) { throw "Godot asset import failed ($LASTEXITCODE)." }
}

Write-Host "Prepared $RunId"
Write-Host "Config: $Config"
Write-Host "Data:   $Data"
Write-Host "Run:    $Run"
Write-Host 'Output folders will be created by collect/train.'

if ($Smoke) {
    $Commands = @(
        @('collect', '--config', $Config, '--output', $Data),
        @('train', '--config', $Config, '--data', $Data, '--output', $Run, '--device', $Device),
        @('eval-model', '--checkpoint', "$Run\best.pt", '--data', $Data,
            '--horizon', '3', '--output', "$Run\model-eval.json"),
        @('eval', '--checkpoint', "$Run\best.pt", '--episodes', '2', '--output', "$Run\mpc-eval.json"),
        @('eval', '--checkpoint', "$Run\best.pt", '--episodes', '2', '--random',
            '--output', "$Run\random-eval.json")
    )
    foreach ($CommandArguments in $Commands) {
        & world-model @CommandArguments
        if ($LASTEXITCODE -ne 0) { throw "world-model $($CommandArguments[0]) failed ($LASTEXITCODE)." }
    }
    & python -m examples.inference --checkpoint "$Run\best.pt"
    if ($LASTEXITCODE -ne 0) { throw "Inference failed ($LASTEXITCODE)." }
}
