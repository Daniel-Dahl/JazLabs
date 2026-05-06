# Go to project

Set-Location "C:\Users\pllab-vis\Documents\PWI\pwi-inst\src"

# Activate conda env (PowerShell way)

& "C:\ProgramData\miniconda3\shell\condabin\conda-hook.ps1"

conda activate py311

# Debug (optional)

Write-Host "Active env:" $env:CONDA_DEFAULT_ENV

python -c "import sys; print(sys.executable)"

# Run server

python -m pwi_inst.hardware.SLM.SLM_ServerWindows

Read-Host "Press Enter to exit"

# powershell.exe -NoExit -ExecutionPolicy Bypass -File "C:\Users\pllab-vis\Documents\PWI\pwi-inst\src\pwi_inst\hardware\SLM\launchSLMServer.ps1"