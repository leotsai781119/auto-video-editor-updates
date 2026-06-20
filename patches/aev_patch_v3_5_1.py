from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"v3.5.1 update target not found: {old[:80]!r}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) < 3:
        return 2

    app_dir = Path(sys.argv[1])
    staging = Path(sys.argv[2])
    staging.mkdir(parents=True, exist_ok=True)

    app_path = app_dir / "app.py"
    source = app_path.read_text(encoding="utf-8")

    if "Auto Video Editor v3.5.1" not in source:
        source = replace_once(source, "Auto Video Editor v3.5", "Auto Video Editor v3.5.1")

    old_title = 'APP_TITLE = "自動短影音剪輯器 v3.5｜高速字幕版"'
    new_title = 'APP_TITLE = "自動短影音剪輯器 v3.5.1｜高速字幕版"'
    if old_title in source:
        source = source.replace(old_title, new_title, 1)

    old_preview = '''                st.success(f"剪輯完成，長度約 {float(st.session_state.get('editor_v33_total_duration') or 0):.1f} 秒。")
                st.video(str(edited_path))'''
    new_preview = '''                st.success(f"剪輯完成，長度約 {float(st.session_state.get('editor_v33_total_duration') or 0):.1f} 秒。")
                preview_size_label = st.radio(
                    "預覽畫面大小",
                    ["小", "中", "滿版"],
                    horizontal=True,
                    index=0,
                    key="editor_v351_preview_size",
                )
                preview_width = {"小": 520, "中": 760, "滿版": "stretch"}[preview_size_label]
                st.video(str(edited_path), width=preview_width)'''
    if "editor_v351_preview_size" not in source:
        source = replace_once(source, old_preview, new_preview)

    source = replace_once(
        source,
        '                                st.video(str(output))',
        '                                st.video(str(output), width=preview_width)',
    )

    (staging / "app.py").write_text(source, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
