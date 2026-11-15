@echo off
pushd "%~dp0"
".venv\Scripts\python.exe" -m app.explore.warm_demo %*
set "demo_exit=%errorlevel%"
popd
exit /b %demo_exit%
