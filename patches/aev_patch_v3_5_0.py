from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError("v3.5 update target not found")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) < 3:
        return 2
    app_dir = Path(sys.argv[1])
    staging = Path(sys.argv[2])
    staging.mkdir(parents=True, exist_ok=True)
    source = (app_dir / "app.py").read_text(encoding="utf-8")

    replacements = [
        ('Auto Video Editor v3.4', 'Auto Video Editor v3.5'),
        ('APP_TITLE = "自動短影音剪輯器 v3.4"', 'APP_TITLE = "自動短影音剪輯器 v3.5｜高速字幕版"'),
        ('beam = 10 if accuracy_mode == "精準優先" else 5', 'beam = 6 if accuracy_mode == "精準優先" else 1'),
        (
            'should_rescue = auto_rescue or analysis.quality_level != "一般" or speech_scenario != "單人說話"',
            'should_rescue = auto_rescue and (accuracy_mode == "精準優先" or analysis.quality_level != "一般")',
        ),
        (
            '''need_slow_pass = (\n        speech_scenario == "語速很快"\n        or detected_rate >= 6.0\n        or (accuracy_mode == "精準優先" and agreement < .58)\n    )''',
            '''need_slow_pass = (\n        accuracy_mode == "精準優先"\n        and (speech_scenario == "語速很快" or detected_rate >= 6.0 or agreement < .58)\n    )''',
        ),
        (
            'model_label = st.selectbox("語音辨識模型", list(WHISPER_MODELS.keys()), index=2, key="editor_v33_model")',
            'model_label = st.selectbox("語音辨識模型", list(WHISPER_MODELS.keys()), index=0, key="editor_v33_model", help="一般電腦建議先用 small；turbo 與 large-v3 會慢很多。")',
        ),
        (
            'accuracy_mode = st.selectbox("辨識模式", ["精準優先", "速度優先"], index=0, key="editor_v33_accuracy")',
            'accuracy_mode = st.selectbox("辨識模式", ["精準優先", "速度優先"], index=1, key="editor_v33_accuracy", help="速度優先只跑一輪；精準優先可能跑 2～3 輪。")',
        ),
        (
            'auto_rescue = st.checkbox("自動音訊救援與雙版本交叉辨識", value=True, key="editor_v33_rescue")',
            'auto_rescue = st.checkbox("音訊不清楚時才啟用第二輪救援（會增加時間）", value=False, key="editor_v33_rescue")',
        ),
        (
            'with st.spinner("正在分析剪輯後影片的音量、語速與人聲區段，再進行交叉辨識……"):',
            'with st.spinner("正在進行高速字幕辨識……" if accuracy_mode == "速度優先" else "正在進行精準字幕辨識……"):',
        ),
    ]
    for old, new in replacements:
        source = replace_once(source, old, new)

    (staging / "app.py").write_text(source, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
