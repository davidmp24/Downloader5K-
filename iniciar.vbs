Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = currentDir

' Executa python.exe de forma 100% invisivel (janela 0 = oculta)
WshShell.Run Chr(34) & currentDir & "\.venv\Scripts\python.exe" & Chr(34) & " main.py", 0, False
