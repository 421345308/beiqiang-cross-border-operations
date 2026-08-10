@echo off
set "PATH=C:\Users\spq\.bun\bin;%PATH%"
cd /d "C:\Users\spq\Desktop\贝强\tools\opencut-classic"
start "" "http://localhost:3000"
bun run --cwd apps/web dev
pause
