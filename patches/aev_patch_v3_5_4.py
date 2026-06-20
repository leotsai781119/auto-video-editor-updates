from pathlib import Path
import subprocess
import sys


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")


def main() -> int:
    if len(sys.argv) < 3:
        return 2

    app_dir = Path(sys.argv[1]).resolve()
    staging = Path(sys.argv[2]).resolve()
    staging.mkdir(parents=True, exist_ok=True)

    start_vbs = r'''Option Explicit
Dim sh, fs, appDir, py, cmd, portReady, i
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
appDir = fs.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = appDir
py = Chr(34) & appDir & "\.venv312\Scripts\python.exe" & Chr(34)

If Not fs.FileExists(appDir & "\.venv312\Scripts\python.exe") Then
    MsgBox "尚未完成安裝，請先執行 INSTALL.cmd。", 48, "Auto Video Editor"
    WScript.Quit 1
End If

cmd = "cmd.exe /c " & py & " updater.py >> " & Chr(34) & appDir & "\update_log.txt" & Chr(34) & " 2>&1"
sh.Run cmd, 0, True

cmd = "cmd.exe /c " & py & " -m streamlit run app.py --server.port 8501 --server.headless true >> " & Chr(34) & appDir & "\server_log.txt" & Chr(34) & " 2>&1"
sh.Run cmd, 0, False

For i = 1 To 30
    WScript.Sleep 500
    On Error Resume Next
    portReady = sh.Run("powershell.exe -NoLogo -NoProfile -WindowStyle Hidden -Command " & Chr(34) & "$c=Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue;if($c){exit 0}else{exit 1}" & Chr(34), 0, True)
    On Error GoTo 0
    If portReady = 0 Then Exit For
Next

sh.Run "http://localhost:8501", 1, False
'''

    start_cmd = r'''@echo off
cd /d "%~dp0"
if not exist ".venv312\Scripts\python.exe" (
  echo Please run INSTALL.cmd first.
  pause
  exit /b 1
)
start "" wscript.exe "%~dp0START_EDITOR_HIDDEN.vbs"
exit /b 0
'''

    stop_vbs = r'''Option Explicit
Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "powershell.exe -NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command " & Chr(34) & "$p=Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue|Select-Object -ExpandProperty OwningProcess -Unique;if($p){$p|ForEach-Object{Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue}}" & Chr(34), 0, True
'''

    stop_cmd = r'''@echo off
cd /d "%~dp0"
start "" wscript.exe "%~dp0STOP_EDITOR_HIDDEN.vbs"
exit /b 0
'''

    for name, content in {
        "START_EDITOR_HIDDEN.vbs": start_vbs,
        "START_EDITOR.cmd": start_cmd,
        "STOP_EDITOR_HIDDEN.vbs": stop_vbs,
        "STOP_EDITOR.cmd": stop_cmd,
    }.items():
        write_text(staging / name, content)
        write_text(app_dir / name, content)

    ps_script = staging / "repair_shortcuts.ps1"
    app_ps = str(app_dir).replace("'", "''")
    ps = f'''$ErrorActionPreference = 'Stop'
$appDir = '{app_ps}'
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell

$startLink = $shell.CreateShortcut((Join-Path $desktop '自動短影音剪輯器.lnk'))
$startLink.TargetPath = (Join-Path $env:WINDIR 'System32\\wscript.exe')
$startLink.Arguments = '"' + (Join-Path $appDir 'START_EDITOR_HIDDEN.vbs') + '"'
$startLink.WorkingDirectory = $appDir
$startLink.Description = 'Auto Video Editor'
$startLink.Save()

$stopLink = $shell.CreateShortcut((Join-Path $desktop '關閉自動短影音剪輯器.lnk'))
$stopLink.TargetPath = (Join-Path $env:WINDIR 'System32\\wscript.exe')
$stopLink.Arguments = '"' + (Join-Path $appDir 'STOP_EDITOR_HIDDEN.vbs') + '"'
$stopLink.WorkingDirectory = $appDir
$stopLink.Description = 'Stop Auto Video Editor'
$stopLink.Save()
'''
    write_text(ps_script, ps)

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps_script),
        ],
        cwd=app_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        (staging / "shortcut_repair_error.txt").write_text(
            (result.stdout or "") + "\n" + (result.stderr or ""),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
