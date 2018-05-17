@REM You're probably wondering what's going on here.
@REM %0 is full path to this file
@REM ~d is a paramater modifier[1] which cuts out the Drive letter.
@REM ~p is a paramater modifier which cuts out the Base path.
@REM [1]: https://ss64.com/nt/syntax-args.html
%~d0
cd %~dp0
pyinstaller build.spec
