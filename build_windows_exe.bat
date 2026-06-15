@echo off
setlocal
cd /d "%~dp0"

set "CONDA_EXE=conda"
where conda >nul 2>nul
if errorlevel 1 (
  if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_EXE=%USERPROFILE%\anaconda3\condabin\conda.bat"
  if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" set "CONDA_EXE=%USERPROFILE%\miniconda3\condabin\conda.bat"
  if exist "%USERPROFILE%\miniforge3\condabin\conda.bat" set "CONDA_EXE=%USERPROFILE%\miniforge3\condabin\conda.bat"
  if exist "%LOCALAPPDATA%\anaconda3\condabin\conda.bat" set "CONDA_EXE=%LOCALAPPDATA%\anaconda3\condabin\conda.bat"
  if exist "%LOCALAPPDATA%\miniconda3\condabin\conda.bat" set "CONDA_EXE=%LOCALAPPDATA%\miniconda3\condabin\conda.bat"
  if exist "%ProgramData%\anaconda3\condabin\conda.bat" set "CONDA_EXE=%ProgramData%\anaconda3\condabin\conda.bat"
  if exist "%ProgramData%\miniconda3\condabin\conda.bat" set "CONDA_EXE=%ProgramData%\miniconda3\condabin\conda.bat"
)


call "%CONDA_EXE%" run -n pyinstaller python -m pip install -r requirements-production.txt
if errorlevel 1 exit /b %errorlevel%
call "%CONDA_EXE%" run -n pyinstaller python -m pip install -e .
if errorlevel 1 exit /b %errorlevel%
call "%CONDA_EXE%" run -n pyinstaller python -m knit_grid_catalog_delivery_v14.production.build_executable
if errorlevel 1 exit /b %errorlevel%
endlocal
