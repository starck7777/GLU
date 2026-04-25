param(
    [string]$RemoteUrl = "",
    [string]$Branch = "main",
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Require-Git {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git is not installed or not available in PATH."
    }
}

function Ensure-Repository {
    if (-not (Test-Path ".git")) {
        Write-Step "Initializing a new Git repository"
        git init | Out-Host
    }
}

function Ensure-Branch {
    $currentBranch = (git branch --show-current).Trim()
    if (-not $currentBranch) {
        Write-Step "Creating branch '$Branch'"
        git checkout -b $Branch | Out-Host
        return
    }

    if ($currentBranch -ne $Branch) {
        Write-Step "Switching to branch '$Branch'"
        $branchExists = git branch --list $Branch
        if ($branchExists) {
            git checkout $Branch | Out-Host
        } else {
            git checkout -b $Branch | Out-Host
        }
    }
}

function Ensure-Remote {
    $existingOrigin = ""
    try {
        $existingOrigin = (git remote get-url origin 2>$null).Trim()
    } catch {
        $existingOrigin = ""
    }

    if (-not $existingOrigin) {
        if (-not $RemoteUrl) {
            $RemoteUrl = Read-Host "Paste your GitHub repository URL"
        }

        if (-not $RemoteUrl) {
            throw "A GitHub remote URL is required."
        }

        Write-Step "Adding origin remote"
        git remote add origin $RemoteUrl | Out-Host
        return
    }

    Write-Step "Using existing origin remote"
    Write-Host $existingOrigin -ForegroundColor Yellow
}

function Create-Commit {
    Write-Step "Staging files"
    git add . | Out-Host

    $statusLines = git status --short
    if (-not $statusLines) {
        Write-Step "Nothing to commit"
        return $false
    }

    if (-not $Message) {
        $Message = Read-Host "Commit message"
    }

    if (-not $Message) {
        $Message = "Update project files"
    }

    Write-Step "Creating commit"
    git commit -m $Message | Out-Host
    return $true
}

function Push-Branch {
    Write-Step "Pushing to GitHub"
    git push -u origin $Branch | Out-Host
}

try {
    Set-Location $PSScriptRoot
    Require-Git
    Ensure-Repository
    Ensure-Branch
    Ensure-Remote
    [void](Create-Commit)
    Push-Branch

    Write-Host ""
    Write-Host "Push complete." -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "Push failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
