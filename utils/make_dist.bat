@echo off
del /q /s dist\plaso 2> NUL

rmdir /q /s dist\plaso 2> NUL

mkdir dist\plaso

xcopy /q /y /s dist\log2timeline\* dist\plaso
xcopy /q /y /s dist\plaso_console\* dist\plaso
xcopy /q /y /s dist\plaso_information\* dist\plaso
xcopy /q /y /s dist\pprof\* dist\plaso
xcopy /q /y /s dist\psort\* dist\plaso