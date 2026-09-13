# Start both llama.cpp model servers (Windows PowerShell).
#
# Usage:
#   .\scripts\start_models.ps1 -ModelDir "C:\models"
#
# Opens each server in its own window so you can watch the logs.

param(
    [string]$ModelDir = ".\models"
)

$ReasoningModel = Join-Path $ModelDir "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
$CodeModel      = Join-Path $ModelDir "Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf"

foreach ($m in @($ReasoningModel, $CodeModel)) {
    if (-not (Test-Path $m)) {
        Write-Host "ERROR: model file not found: $m" -ForegroundColor Red
        Write-Host "Download the GGUF files listed in docs/SETUP.md into $ModelDir"
        exit 1
    }
}

Write-Host "Starting reasoning model on :8080 ..."
Start-Process -NoNewWindow:$false llama-server -ArgumentList "-m `"$ReasoningModel`" --port 8080 --ctx-size 4096"

Write-Host "Starting code model on :8081 ..."
Start-Process -NoNewWindow:$false llama-server -ArgumentList "-m `"$CodeModel`" --port 8081 --ctx-size 4096"

Start-Sleep -Seconds 5

Write-Host "`nHealth checks:"
try { Invoke-RestMethod http://localhost:8080/health; Write-Host " <- reasoning (8080)" } catch { Write-Host "reasoning server not responding" -ForegroundColor Yellow }
try { Invoke-RestMethod http://localhost:8081/health; Write-Host " <- code (8081)" } catch { Write-Host "code server not responding" -ForegroundColor Yellow }

Write-Host "`nNow set USE_REAL_MODEL=true in your .env and restart the backend."
