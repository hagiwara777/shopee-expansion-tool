@echo off
title Sora
"%~1" "%~dp0sora_launcher.py" --sp-api-env "%~2"
if errorlevel 1 pause
