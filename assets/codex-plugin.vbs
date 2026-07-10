' Codex-Plugin silent launcher
' Sets LLANFENG_INJECT_MODE so the app skips the GUI and runs injection only.
' Uses wscript.exe so no console window appears.

Dim objShell
Set objShell = CreateObject("WScript.Shell")

' Inherit + override the env var in this wscript process so the child
' inherits it automatically.
Dim objEnv
Set objEnv = objShell.Environment("Process")
objEnv("LLANFENG_INJECT_MODE") = "1"

' Resolve the main exe path relative to this vbs file.
Dim scriptDir
scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
Dim appExe
appExe = scriptDir & "llanfeng-code-assistant.exe"

' Run the app. WindowStyle 1 = normal window (so ChatGPT appears).
' Wait = False so this script exits immediately.
objShell.Run Chr(34) & appExe & Chr(34), 1, False
Set objShell = Nothing
