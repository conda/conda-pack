@REM @ symbols in this file indicate that output should not be printed.
@REM   Setting it this way allows us to not touch the user's echo setting.
@REM   For debugging, remove the @ on the section you need to study.
@setlocal enabledelayedexpansion

@CALL :NORMALIZEPATH "%~dp0"
@SET "SCRIPT_DIR=%RETVAL%"
@CALL :NORMALIZEPATH "%SCRIPT_DIR%\.."
@set "NEW_PREFIX=%RETVAL%"

@if "%CONDA_PREFIX%" == "" @goto skipdeactivate
@if "%CONDA_PREFIX%" == "%NEW_PREFIX%" @exit /b

@REM If the current environment is a conda-pack environment, or a root environment
@REM
@if exist "%CONDA_PREFIX%\Scripts\deactivate.bat" @call "%CONDA_PREFIX%\Scripts\deactivate.bat"
@REM Newer versions of conda only have the deactivate script in the root environment
@if exist "%CONDA_PREFIX%\..\..\Scripts\deactivate.bat" @call "%CONDA_PREFIX%\..\..\Scripts\deactivate.bat"
:skipdeactivate

@for /F "delims=" %%i in ("%NEW_PREFIX%") do @SET "ENV_NAME=%%~ni"

@REM take a snapshot of pristine state for later
@SET "CONDA_PS1_BACKUP=%PROMPT%"
@SET "PROMPT=(%ENV_NAME%) %PROMPT%"

@SET "CONDA_PREFIX=%NEW_PREFIX%"
@SET "PATH=%NEW_PREFIX%;%NEW_PREFIX%\Library\mingw-w64\bin;%NEW_PREFIX%\Library\usr\bin;%NEW_PREFIX%\Library\bin;%NEW_PREFIX%\Scripts;%PATH%"

@REM This persists env variables, which are otherwise local to this script right now.
@endlocal & (
    @REM Used for deactivate, to make sure we restore original state after deactivation
    @SET "_CONDA_PACK_OLD_PS1=%CONDA_PS1_BACKUP%"
    @SET "PROMPT=%PROMPT%"
    @SET "PATH=%PATH%"
    @SET "CONDA_PREFIX=%CONDA_PREFIX%"

    @REM Run any activate scripts
    @IF EXIST "%CONDA_PREFIX%\etc\conda\activate.d" (
        @PUSHD "%CONDA_PREFIX%\etc\conda\activate.d"
        @FOR %%g in (*.bat) DO @CALL "%%g"
        @POPD
    )
)

:: ========== FUNCTIONS ==========
@EXIT /B

:NORMALIZEPATH
  @SET RETVAL=%~dpfn1
  @EXIT /B
