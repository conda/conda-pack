@REM @ symbols in this file indicate that output should not be printed.
@REM   Setting it this way allows us to not touch the user's echo setting.
@REM   For debugging, remove the @ on the section you need to study.

@REM If there's no active environment, there's nothing to do
@IF "%CONDA_PREFIX%" == "" @GOTO skipdeactivate

@REM Run any activate scripts
@REM Do this before running setlocal so that variables are cleared properly
@IF EXIST "%CONDA_PREFIX%\etc\conda\deactivate.d" (
    @PUSHD "%CONDA_PREFIX%\etc\conda\deactivate.d"
    @FOR %%g in (*.bat) DO @CALL "%%g"
    @POPD
)

@setlocal enabledelayedexpansion

@REM Remove path entries for this environment
@SET "TARGETS=;%CONDA_PREFIX%;%CONDA_PREFIX%\Library\mingw-w64\bin;%CONDA_PREFIX%\Library\usr\bin;%CONDA_PREFIX%\Library\bin;%CONDA_PREFIX%\Scripts"
@SET "NEW_PATH="
@FOR %%i IN ("%PATH:;=";"%") DO @(CALL :filterPath "%%~i")

@REM Restore the command prompt
@SET "PROMPT=%_CONDA_PACK_OLD_PS1%"
@SET "CONDA_PS1_BACKUP="

@REM This persists env variables, which are otherwise local to this script right now.
@endlocal & (
    @REM Used for deactivate, to make sure we restore original state after deactivation
    @SET "_CONDA_PACK_OLD_PS1=%CONDA_PS1_BACKUP%"
    @SET "PROMPT=%PROMPT%"
    @SET "PATH=%NEW_PATH:~1%"
    @SET "CONDA_PREFIX="

)

:skipdeactivate
@EXIT /b

:filterPath
  @IF "%~1" == "" @GOTO :filterOut
  @FOR %%j IN ("%TARGETS:;=";"%") DO @IF /i "%~1" == "%%~j" @GOTO :filterOut
  @SET "NEW_PATH=%NEW_PATH%;%~1"
:filterOut
  @EXIT /b
