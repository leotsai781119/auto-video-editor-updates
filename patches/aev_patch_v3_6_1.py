from pathlib import Path
import re
import sys


def main() -> int:
    if len(sys.argv) < 3:
        return 2
    app_dir = Path(sys.argv[1])
    staging = Path(sys.argv[2])
    staging.mkdir(parents=True, exist_ok=True)
    app_path = app_dir / "app.py"
    source = app_path.read_text(encoding="utf-8")

    source = source.replace("Auto Video Editor v3.6.0", "Auto Video Editor v3.6.1")
    source = source.replace(
        'APP_TITLE = "自動短影音剪輯器 v3.6.0｜整合安裝版"',
        'APP_TITLE = "自動短影音剪輯器 v3.6.1｜整合安裝版"',
    )

    if "def _hidden_popen" not in source:
        marker = "import subprocess\n"
        block = '''import subprocess\n\n# Windows 背景執行時，統一隱藏 FFmpeg、ffprobe 與其他子程序視窗。\n_ORIGINAL_POPEN = subprocess.Popen\n\ndef _hidden_popen(*args, **kwargs):\n    if os.name == "nt":\n        kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))\n        if kwargs.get("startupinfo") is None:\n            startupinfo = subprocess.STARTUPINFO()\n            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW\n            startupinfo.wShowWindow = subprocess.SW_HIDE\n            kwargs["startupinfo"] = startupinfo\n    return _ORIGINAL_POPEN(*args, **kwargs)\n\nsubprocess.Popen = _hidden_popen\n'''
        if marker not in source:
            raise RuntimeError("cannot find subprocess import")
        source = source.replace(marker, block, 1)

    (staging / "app.py").write_text(source, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
