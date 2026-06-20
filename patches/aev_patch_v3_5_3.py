from pathlib import Path
import re, sys


def req(pattern, repl, text, label):
    out, n = re.subn(pattern, repl, text, count=1, flags=re.S)
    if not n:
        raise RuntimeError("v3.5.3 target not found: " + label)
    return out


def main():
    if len(sys.argv) < 3:
        return 2
    app_dir, staging = Path(sys.argv[1]), Path(sys.argv[2])
    staging.mkdir(parents=True, exist_ok=True)
    s = (app_dir / "app.py").read_text(encoding="utf-8")

    s = re.sub(r"Auto Video Editor v3\.5(?:\.\d+)?", "Auto Video Editor v3.5.3", s)
    s = re.sub(r'APP_TITLE\s*=\s*"自動短影音剪輯器 v3\.5(?:\.\d+)?[^\"]*"', 'APP_TITLE = "自動短影音剪輯器 v3.5.3｜完整字幕修正版"', s, count=1)
    s = req(r'accuracy_mode\s*:\s*str\s*=\s*"[^"]*"', 'accuracy_mode: str = "快速完整（推薦）"', s, "accuracy default")
    s = req(r'is_turbo\s*=\s*accuracy_mode\.startswith\("極速"\)\s*\n\s*is_balanced\s*=\s*accuracy_mode\.startswith\("平衡"\)\s*\n\s*beam\s*=\s*1 if is_turbo else \(3 if is_balanced else 8\)\s*\n\s*use_word_timestamps\s*=\s*not is_turbo',
            'is_turbo = accuracy_mode.startswith("極速")\n    is_complete_fast = accuracy_mode.startswith("快速完整")\n    is_balanced = accuracy_mode.startswith("平衡")\n    beam = 1 if is_turbo else (2 if is_complete_fast else (3 if is_balanced else 8))\n    use_word_timestamps = not is_turbo', s, "mode setup")
    s = req(r'(segments_a, _ = _run_whisper_pass\([\s\S]*?prompt=prompt,\s*)vad_filter=True,\s*vad_parameters=vad,\s*no_speech_threshold=\.30,\s*condition_on_previous_text=not is_turbo,\s*word_timestamps=use_word_timestamps,',
            r'\1vad_filter=not is_complete_fast,\n        vad_parameters=vad if not is_complete_fast else None,\n        no_speech_threshold=.16 if is_complete_fast else .30,\n        condition_on_previous_text=not (is_turbo or is_complete_fast),\n        word_timestamps=use_word_timestamps,', s, "first recognition pass")
    s = req(r'source_name="極速單輪" if is_turbo else "標準音軌"', 'source_name="極速單輪" if is_turbo else ("快速完整單輪" if is_complete_fast else "標準音軌")', s, "source label")
    s = req(r'if is_turbo:\s*should_rescue = auto_rescue and first_text_len < 4\s*elif is_balanced:\s*should_rescue = auto_rescue and \(analysis\.quality_level != "一般" or first_text_len < 8\)\s*else:\s*should_rescue = auto_rescue or analysis\.quality_level != "一般" or speech_scenario != "單人說話"',
            'if is_turbo:\n        should_rescue = auto_rescue and first_text_len < 4\n    elif is_complete_fast:\n        should_rescue = auto_rescue and (analysis.quality_level != "一般" or first_text_len < 8)\n    elif is_balanced:\n        should_rescue = auto_rescue and (analysis.quality_level != "一般" or first_text_len < 8)\n    else:\n        should_rescue = auto_rescue or analysis.quality_level != "一般" or speech_scenario != "單人說話"', s, "rescue rules")
    s = req(r'need_slow_pass = \(\s*not is_turbo\s*and not is_balanced', 'need_slow_pass = (\n        not is_turbo\n        and not is_complete_fast\n        and not is_balanced', s, "slow pass rules")
    s = req(r'cues = \[c for c in cues if c\.text\.strip\(\) and \(c\.confidence >= \.16 or len\(c\.text\) >= 4\)\]', 'cues = [c for c in cues if c.text.strip() and len(clean_word(c.text)) >= 2]', s, "short phrase filter")

    ui = '''accuracy_mode = st.selectbox(\n                        "字幕處理方式",\n                        ["快速完整（推薦）", "極速優先", "平衡模式", "精準優先"],\n                        index=0,\n                        key="editor_v33_accuracy",\n                        help="快速完整只跑一輪並掃描整段音訊，避免漏掉短句；極速最快，但可能漏掉句首或短句。",\n                    )'''
    s = req(r'accuracy_mode\s*=\s*st\.selectbox\([\s\S]*?key="editor_v33_accuracy",[\s\S]*?\n\s*\)', ui, s, "accuracy UI")
    s = re.sub(r'st\.caption\("建議：[^"]*"\)', 'st.caption("建議：一般影片使用 small＋快速完整。只有急著看初稿才使用極速；背景聲大或多人說話時再開第二輪救援。")', s, count=1)
    spinner = '''if accuracy_mode.startswith("快速完整"):\n                            spinner_text = "正在掃描完整音訊並產生字幕……"\n                        elif accuracy_mode.startswith("極速"):\n                            spinner_text = "正在進行單輪高速字幕辨識……"\n                        else:\n                            spinner_text = "正在分析音訊並進行字幕辨識……"'''
    s = req(r'spinner_text\s*=\s*\([\s\S]*?\n\s*\)', spinner, s, "spinner UI")

    if "editor_v353_preview_size" not in s and "editor_v351_preview_size" not in s:
        s = req(r'(\s+st\.success\(f"剪輯完成，長度約 \{float\(st\.session_state\.get\(\'editor_v33_total_duration\'\) or 0\):\.1f\} 秒。"\)\n)\s*st\.video\(str\(edited_path\)\)',
                r'''\1                preview_size_label = st.radio(\n                    "預覽畫面大小", ["小", "中", "滿版"], horizontal=True, index=0, key="editor_v353_preview_size"\n                )\n                preview_width = {"小": 520, "中": 760, "滿版": "stretch"}[preview_size_label]\n                st.video(str(edited_path), width=preview_width)''', s, "preview size")
    if "st.video(str(output), width=preview_width)" not in s:
        s = s.replace("st.video(str(output))", "st.video(str(output), width=preview_width)", 1)

    (staging / "app.py").write_text(s, encoding="utf-8", newline="\n")
    (staging / "START_EDITOR.cmd").write_text('@echo off\r\ncd /d "%~dp0"\r\nif not exist ".venv312\\Scripts\\python.exe" (echo Please run INSTALL.cmd first.&pause&exit /b 1)\r\nwscript.exe "%~dp0START_EDITOR_HIDDEN.vbs"\r\nexit /b 0\r\n', encoding="utf-8")
    (staging / "START_EDITOR_HIDDEN.vbs").write_text('Option Explicit\r\nDim sh,fs,d,p,cmd\r\nSet sh=CreateObject("WScript.Shell")\r\nSet fs=CreateObject("Scripting.FileSystemObject")\r\nd=fs.GetParentFolderName(WScript.ScriptFullName)\r\nsh.CurrentDirectory=d\r\np=Chr(34)&d&"\\.venv312\\Scripts\\python.exe"&Chr(34)\r\ncmd="cmd.exe /c "&p&" updater.py >> "&Chr(34)&d&"\\update_log.txt"&Chr(34)&" 2>&1"\r\nsh.Run cmd,0,True\r\ncmd="cmd.exe /c "&p&" -m streamlit run app.py --server.port 8501 --server.headless true >> "&Chr(34)&d&"\\server_log.txt"&Chr(34)&" 2>&1"\r\nsh.Run cmd,0,False\r\nWScript.Sleep 3500\r\nsh.Run "http://localhost:8501",1,False\r\n', encoding="utf-8")
    (staging / "STOP_EDITOR.cmd").write_text('@echo off\r\npowershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$p=Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue|Select-Object -ExpandProperty OwningProcess -Unique;if($p){$p|%%{Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue}}"\r\nexit /b 0\r\n', encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
