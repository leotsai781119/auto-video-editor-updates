from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"v3.5.2 update target not found: {old[:100]!r}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) < 3:
        return 2

    app_dir = Path(sys.argv[1])
    staging = Path(sys.argv[2])
    staging.mkdir(parents=True, exist_ok=True)

    source = (app_dir / "app.py").read_text(encoding="utf-8")

    if "Auto Video Editor v3.5.2" not in source:
        if "Auto Video Editor v3.5.1" in source:
            source = source.replace("Auto Video Editor v3.5.1", "Auto Video Editor v3.5.2", 1)
        else:
            source = replace_once(source, "Auto Video Editor v3.5", "Auto Video Editor v3.5.2")

    for old_title in (
        'APP_TITLE = "自動短影音剪輯器 v3.5.1｜高速字幕版"',
        'APP_TITLE = "自動短影音剪輯器 v3.5｜高速字幕版"',
    ):
        if old_title in source:
            source = source.replace(
                old_title,
                'APP_TITLE = "自動短影音剪輯器 v3.5.2｜完整字幕修正版"',
                1,
            )
            break

    source = replace_once(
        source,
        '    accuracy_mode: str = "極速優先（推薦）",',
        '    accuracy_mode: str = "快速完整（推薦）",',
    )

    source = replace_once(
        source,
        '''    is_turbo = accuracy_mode.startswith("極速")
    is_balanced = accuracy_mode.startswith("平衡")
    beam = 1 if is_turbo else (3 if is_balanced else 8)
    use_word_timestamps = not is_turbo''',
        '''    is_turbo = accuracy_mode.startswith("極速")
    is_complete_fast = accuracy_mode.startswith("快速完整")
    is_balanced = accuracy_mode.startswith("平衡")
    beam = 1 if is_turbo else (2 if is_complete_fast else (3 if is_balanced else 8))
    use_word_timestamps = not is_turbo''',
    )

    source = replace_once(
        source,
        '''        vad_filter=True,
        vad_parameters=vad,
        no_speech_threshold=.30,
        condition_on_previous_text=not is_turbo,
        word_timestamps=use_word_timestamps,''',
        '''        # 快速完整模式只跑一輪，但不使用 VAD 切掉語音，避免清楚短句被漏掉。
        vad_filter=not is_complete_fast,
        vad_parameters=vad if not is_complete_fast else None,
        no_speech_threshold=.18 if is_complete_fast else .30,
        condition_on_previous_text=not (is_turbo or is_complete_fast),
        word_timestamps=use_word_timestamps,''',
    )

    source = replace_once(
        source,
        '        source_name="極速單輪" if is_turbo else "標準音軌",',
        '        source_name="極速單輪" if is_turbo else ("快速完整單輪" if is_complete_fast else "標準音軌"),',
    )

    source = replace_once(
        source,
        '''    if is_turbo:
        should_rescue = auto_rescue and first_text_len < 4
    elif is_balanced:
        should_rescue = auto_rescue and (analysis.quality_level != "一般" or first_text_len < 8)
    else:
        should_rescue = auto_rescue or analysis.quality_level != "一般" or speech_scenario != "單人說話"''',
        '''    if is_turbo:
        should_rescue = auto_rescue and first_text_len < 4
    elif is_complete_fast:
        should_rescue = auto_rescue and (analysis.quality_level != "一般" or first_text_len < 8)
    elif is_balanced:
        should_rescue = auto_rescue and (analysis.quality_level != "一般" or first_text_len < 8)
    else:
        should_rescue = auto_rescue or analysis.quality_level != "一般" or speech_scenario != "單人說話"''',
    )

    source = replace_once(
        source,
        '    cues = [c for c in cues if c.text.strip() and (c.confidence >= .16 or len(c.text) >= 4)]',
        '    cues = [c for c in cues if c.text.strip() and (c.confidence >= .08 or len(clean_word(c.text)) >= 2)]',
    )

    source = replace_once(
        source,
        '''                    accuracy_mode = st.selectbox(
                        "字幕處理速度",
                        ["極速優先（推薦）", "平衡模式", "精準優先"],
                        index=0,
                        key="editor_v33_accuracy",
                        help="極速只跑一輪並略過逐字時間戳；平衡保留逐字時間；精準會視情況跑 2～3 輪。",
                    )''',
        '''                    accuracy_mode = st.selectbox(
                        "字幕處理方式",
                        ["快速完整（推薦）", "極速優先", "平衡模式", "精準優先"],
                        index=0,
                        key="editor_v33_accuracy",
                        help="快速完整只跑一輪，但會掃描整段音訊，避免 VAD 漏掉清楚短句；極速最快，但可能漏掉短句。",
                    )''',
    )

    source = replace_once(
        source,
        '                    st.caption("建議：2 分鐘一般口語影片先用 small＋極速模式。字幕不完整時，再改用平衡或開啟第二輪救援。")',
        '                    st.caption("建議：一般影片使用 small＋快速完整。只有急著看初稿才使用極速；背景聲大或多人說話時再開第二輪救援。")',
    )

    source = replace_once(
        source,
        '''                        spinner_text = (
                            "正在進行單輪高速字幕辨識……"
                            if accuracy_mode.startswith("極速")
                            else "正在分析音訊並進行字幕辨識……"
                        )''',
        '''                        if accuracy_mode.startswith("快速完整"):
                            spinner_text = "正在掃描完整音訊並產生字幕……"
                        elif accuracy_mode.startswith("極速"):
                            spinner_text = "正在進行單輪高速字幕辨識……"
                        else:
                            spinner_text = "正在分析音訊並進行字幕辨識……"''',
    )

    (staging / "app.py").write_text(source, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
