<#
.SYNOPSIS
  Installs the AI delivery workflow kit into ~/.claude (Windows PowerShell 5.1+ / PowerShell 7).

.EXAMPLE
  pwsh ./install.ps1 -DryRun
  pwsh ./install.ps1 -WithBlueprint -SkipThirdParty
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$WithBlueprint,
    [switch]$SkipThirdParty,
    [string]$ClaudeHome = ''
)

if (-not $ClaudeHome) {
    $userHome = $env:USERPROFILE
    if (-not $userHome) { $userHome = $HOME }
    $ClaudeHome = Join-Path $userHome '.claude'
}

$ErrorActionPreference = 'Stop'
$KitDir = $PSScriptRoot

$ThirdParty = @(
    'getsentry/skills@security-review',
    'obra/superpowers@test-driven-development',
    'microsoft/playwright-cli@playwright-cli',
    'anthropics/skills@webapp-testing',
    'vercel-labs/skills@find-skills'
)

$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupDir = Join-Path $ClaudeHome "backups\ai-delivery-workflow-$Stamp"

function Say([string]$msg) { Write-Host $msg }

function Do-Action([string]$label, [scriptblock]$action) {
    if ($DryRun) { Say "[dry-run] $label" } else { Say $label; & $action }
}

function Backup-Item([string]$target, [string]$relative) {
    if (-not (Test-Path -LiteralPath $target)) { return }
    $dest = Join-Path $BackupDir $relative
    Do-Action "backup  $target -> $dest" {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $target -Destination $dest -Recurse -Force
    }
}

function Install-Item([string]$source, [string]$target) {
    Do-Action "install $source -> $target" {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
    }
}

Say "AI delivery workflow kit -> $ClaudeHome"
if ($DryRun) { Say '(dry run: nothing will be changed)' }
Say ''

# 1. Collect what to install: skills, agents, workflow file.
$items = @()
foreach ($skill in Get-ChildItem -LiteralPath (Join-Path $KitDir 'skills') -Directory) {
    if ($skill.Name -eq 'delivery-blueprint' -and -not $WithBlueprint) {
        Say "skip    skills/delivery-blueprint (synced from claude.ai; use -WithBlueprint to install)"
        continue
    }
    $items += ,@($skill.FullName, "skills\$($skill.Name)")
}
foreach ($agent in Get-ChildItem -LiteralPath (Join-Path $KitDir 'agents') -Filter '*.md' -File) {
    $items += ,@($agent.FullName, "agents\$($agent.Name)")
}
$items += ,@((Join-Path $KitDir 'workflow\ai-delivery-workflow.md'), 'workflows\ai-delivery-workflow.md')

# 2. Back up whatever already exists at those targets.
foreach ($item in $items) { Backup-Item (Join-Path $ClaudeHome $item[1]) $item[1] }

# 3. Copy the kit in.
foreach ($item in $items) { Install-Item $item[0] (Join-Path $ClaudeHome $item[1]) }

# 4. Third-party skills (global, through the skills CLI).
Say ''
if ($SkipThirdParty) {
    Say 'skip    third-party skills (-SkipThirdParty)'
} elseif (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    Say 'warn    npx not found: install Node.js, then run the commands in third-party.md'
} else {
    foreach ($pkg in $ThirdParty) {
        Do-Action "npx -y skills add $pkg -g -y" {
            & npx -y skills add $pkg -g -y
            if ($LASTEXITCODE -ne 0) { Say "warn    failed: $pkg (install it by hand, see third-party.md)" }
        }
    }
}

# 5. Next steps. settings.json is never touched.
Say ''
if (-not $DryRun -and (Test-Path -LiteralPath $BackupDir)) { Say "Backup: $BackupDir" }
Say 'Done. Next steps:'
Say '  1. In each project, add this line to CLAUDE.md:  @~/.claude/workflows/ai-delivery-workflow.md'
Say "     plus the '# Compact instructions' section from settings/claude-md-snippet.md"
Say '  2. Create docs/workflow/README.md from settings/docs-workflow-README.template.md'
Say '  3. Merge what you want from settings/settings.recommended.json into .claude/settings.json by hand'
Say '  4. Optional tools (Orca, PM tool MCP, gh, Context7, ...): see third-party.md'
Say '  5. Start:  /loop /deliver <PROJECT-KEY>   (new project: /delivery-blueprint first)'
