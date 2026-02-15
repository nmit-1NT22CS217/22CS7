# Build script for PII Anonymizer Chrome Extension
# This script creates the extension package for distribution

$ErrorActionPreference = "Stop"

Write-Host "🔒 Building PII Anonymizer Extension..." -ForegroundColor Cyan

# Set paths
$extensionDir = "$PSScriptRoot\extension"
$distDir = "$PSScriptRoot\dist"
$zipName = "pii-anonymizer-extension.zip"

# Create dist directory if it doesn't exist
if (-not (Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir | Out-Null
}

# Check if extension directory exists
if (-not (Test-Path $extensionDir)) {
    Write-Host "❌ Extension directory not found: $extensionDir" -ForegroundColor Red
    exit 1
}

# Remove old zip if exists
$zipPath = "$distDir\$zipName"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

# Create the zip file
Write-Host "📦 Creating extension package..." -ForegroundColor Yellow

# Get all files to include (exclude development files)
$filesToInclude = Get-ChildItem -Path $extensionDir -Recurse | 
    Where-Object { 
        $_.Name -notmatch '^\.' -and 
        $_.Name -notmatch '\.map$' -and
        $_.Name -ne 'node_modules'
    }

# Create zip using Compress-Archive
Compress-Archive -Path "$extensionDir\*" -DestinationPath $zipPath -Force

Write-Host "✅ Extension package created: $zipPath" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Go to chrome://extensions/ in Chrome" -ForegroundColor White
Write-Host "   2. Enable 'Developer mode' (top right toggle)" -ForegroundColor White
Write-Host "   3. Click 'Load unpacked' and select: $extensionDir" -ForegroundColor White
Write-Host ""
Write-Host "   OR for distribution:" -ForegroundColor Cyan
Write-Host "   - Upload $zipPath to Chrome Web Store" -ForegroundColor White
Write-Host ""
