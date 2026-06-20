from __future__ import annotations

from pathlib import Path
import re
import sys


def replace_function(source: str, name: str, next_name: str, replacement: str) -> str:
    start = source.find(f"def {name}(")
    if start < 0:
        raise RuntimeError(f"找不到函式：{name}")
    end = source.find(f"\ndef {next_name}", start)
    if end < 0:
        raise RuntimeError(f"找不到下一個函式：{next_name}")
    return source[:start] + replacement.rstrip() + "\n" + source[end:]


def main() -> int:
    if len(sys.argv) < 3:
        return 2

    app_dir = Path(sys.argv[1]).resolve()
    staging = Path(sys.argv[2]).resolve()
    staging.mkdir(parents=True, exist_ok=True)

    app_path = app_dir / "app.py"
    source = app_path.read_text(encoding="utf-8")

    source = re.sub(r"Auto Video Editor v3\.6(?:\.\d+)?", "Auto Video Editor v3.6.2", source)
    source = re.sub(
        r'APP_TITLE\s*=\s*"自動短影音剪輯器 v3\.6(?:\.\d+)?[^\"]*"',
        'APP_TITLE = "自動短影音剪輯器 v3.6.2｜字幕穩定修正版"',
        source,
        count=1,
    )

    clean_marker = 'def clean_word(word: str) -> str:\n    return re.sub(r"\\s+", "", word or "")\n'
    helpers = r'''


def normalize_asr_match(text: str) -> str:
    """Normalize subtitle text for prompt-leak and duplicate detection."""
    value = to_taiwan_traditional(text or "").replace("臺", "台")
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def extract_asr_topic_terms(context_text: str, glossary_terms: Sequence[str]) -> List[str]:
    """Keep topic words only; never feed natural-language instructions back to Whisper."""
    instruction_words = (
        "請", "使用", "辨識", "字幕", "繁體", "簡體", "中文", "影片", "語音",
        "說話者", "完整保留", "優先", "內容", "不要漏", "逐字", "常用文字",
    )
    candidates = re.split(r"[、,，;；。！？!?\n]+", context_text or "")
    result: List[str] = []
    for raw in [*candidates, *glossary_terms]:
        term = raw.strip()
        if not term or len(term) > 24:
            continue
        if any(word in term for word in instruction_words):
            continue
        if term not in result:
            result.append(term)
    return result[:36]


def prompt_block_phrases(context_text: str) -> List[str]:
    known = [
        "請使用台灣常用繁體中文",
        "請使用臺灣常用繁體中文",
        "這是一段台灣中文口語影片",
        "這是一段臺灣中文口語影片",
        "影片主要是一位說話者",
        "請完整保留每位說話者說出的內容",
        "說話速度很快請仔細辨識連音與短句",
        "人聲可能被背景音樂遮蓋請優先辨識對話內容",
    ]
    clauses = [x.strip() for x in re.split(r"[。！？!?；;\n]+", context_text or "") if x.strip()]
    return [x for x in [*known, *clauses] if len(normalize_asr_match(x)) >= 6]


def filter_asr_hallucinations(
    cues: Sequence[SubtitleCue],
    blocked_phrases: Sequence[str],
) -> Tuple[List[SubtitleCue], int]:
    """Remove prompt leakage and collapse repeated Whisper loops without trusting confidence alone."""
    blocked = [normalize_asr_match(x) for x in blocked_phrases if normalize_asr_match(x)]
    generic = {
        normalize_asr_match(x)
        for x in ("謝謝觀看", "感謝觀看", "請訂閱", "字幕由社群提供", "下集再見")
    }
    filtered: List[SubtitleCue] = []
    removed = 0

    def is_blocked(text: str) -> bool:
        norm = normalize_asr_match(text)
        if len(norm) < 4:
            return False
        for phrase in blocked:
            if len(phrase) >= 6 and (phrase in norm or norm in phrase):
                return True
            if min(len(norm), len(phrase)) >= 8 and SequenceMatcher(None, norm, phrase).ratio() >= .78:
                return True
        return False

    for cue in sorted(cues, key=lambda c: (c.start, c.end)):
        norm = normalize_asr_match(cue.text)
        if not norm:
            removed += 1
            continue
        if is_blocked(cue.text):
            removed += 1
            continue

        if filtered:
            prev = filtered[-1]
            prev_norm = normalize_asr_match(prev.text)
            overlap = _cue_overlap(prev, cue)
            gap = cue.start - prev.end
            similarity = SequenceMatcher(None, prev_norm, norm).ratio()
            if similarity >= .90 and (overlap >= .10 or gap <= .22):
                winner = cue if _cue_value(cue) > _cue_value(prev) else prev
                winner.start = min(prev.start, cue.start)
                winner.end = max(prev.end, cue.end)
                winner.source = "+".join(x for x in [prev.source, cue.source, "重複抑制"] if x)
                filtered[-1] = winner
                removed += 1
                continue

        filtered.append(cue)

    keep = [True] * len(filtered)
    for i, cue in enumerate(filtered):
        if not keep[i]:
            continue
        norm = normalize_asr_match(cue.text)
        matches = [i]
        for j in range(i + 1, len(filtered)):
            if filtered[j].start - cue.start > 9.0:
                break
            other = normalize_asr_match(filtered[j].text)
            if SequenceMatcher(None, norm, other).ratio() >= .90:
                matches.append(j)
        if len(matches) >= 3:
            if norm in generic:
                for idx in matches:
                    keep[idx] = False
                    removed += 1
            else:
                best = max(matches, key=lambda idx: _cue_value(filtered[idx]))
                for idx in matches:
                    if idx != best:
                        keep[idx] = False
                        removed += 1
                filtered[best].confidence = min(filtered[best].confidence, .55)
                filtered[best].source = (filtered[best].source + "+重複複核").strip("+")

    return [cue for idx, cue in enumerate(filtered) if keep[idx]], removed
'''
    if "def normalize_asr_match(" not in source:
        if clean_marker not in source:
            raise RuntimeError("找不到 clean_word 插入位置")
        source = source.replace(clean_marker, clean_marker + helpers, 1)

    run_whisper = r'''def _run_whisper_pass(
    model,
    source_path: Path,
    *,
    language: Optional[str],
    beam: int,
    prompt: str,
    hotwords: str,
    vad_filter: bool,
    vad_parameters: Optional[dict],
    no_speech_threshold: float,
    condition_on_previous_text: bool,
    word_timestamps: bool = True,
):
    fast_decode = beam <= 1
    kwargs = dict(
        language=language,
        beam_size=max(1, beam),
        best_of=1 if fast_decode else beam,
        patience=1.0 if fast_decode else 1.08,
        temperature=0.0,
        word_timestamps=word_timestamps,
        vad_filter=vad_filter,
        condition_on_previous_text=condition_on_previous_text,
        initial_prompt=prompt or None,
        hotwords=hotwords or None,
        compression_ratio_threshold=2.4,
        no_speech_threshold=no_speech_threshold,
        hallucination_silence_threshold=1.25,
        repetition_penalty=1.08 if fast_decode else 1.12,
        log_progress=False,
    )
    if vad_filter and vad_parameters:
        kwargs["vad_parameters"] = vad_parameters
    segments, info = model.transcribe(str(source_path), **kwargs)
    return list(segments), info
'''
    source = replace_function(source, "_run_whisper_pass", "_cue_overlap", run_whisper)

    transcribe = r'''def transcribe_video(
    video_path: Path,
    model_name: str,
    sensitivity: str,
    max_chars: int,
    context_prompt: str = "",
    glossary_text: str = "",
    replacement_text: str = "",
    convert_tw: bool = True,
    accuracy_mode: str = "快速完整（推薦）",
    language: str = "zh",
    speech_scenario: str = "自動判斷",
    auto_rescue: bool = False,
) -> Tuple[List[SubtitleCue], AudioAnalysis, dict]:
    import time
    started_at = time.perf_counter()
    analysis = analyze_audio(video_path)
    if not analysis.has_audio:
        return [], analysis, {"passes": 0, "speech_rate": 0.0, "agreement": 0.0, "elapsed_seconds": 0.0}

    model = load_whisper_model(model_name)
    if sensitivity == "高覆蓋｜盡量不要漏掉人聲":
        vad = dict(threshold=.08, min_speech_duration_ms=20, min_silence_duration_ms=60, speech_pad_ms=600)
        pause_threshold = .28
    else:
        vad = dict(threshold=.24, min_speech_duration_ms=60, min_silence_duration_ms=160, speech_pad_ms=320)
        pause_threshold = .42

    glossary_terms = parse_glossary_terms(glossary_text)
    topic_terms = extract_asr_topic_terms(context_prompt, glossary_terms)
    prompt = "，".join(topic_terms[:24])
    hotwords = "，".join(glossary_terms[:40])
    blocked_phrases = prompt_block_phrases(context_prompt)

    is_turbo = accuracy_mode.startswith("極速")
    is_complete_fast = accuracy_mode.startswith("快速完整")
    is_balanced = accuracy_mode.startswith("平衡")
    beam = 1 if is_turbo else (2 if is_complete_fast else (3 if is_balanced else 8))
    use_word_timestamps = not is_turbo

    standard_audio = prepare_asr_audio(video_path, "standard")
    pass_groups: List[List[SubtitleCue]] = []

    segments_a, _ = _run_whisper_pass(
        model,
        standard_audio,
        language=language,
        beam=beam,
        prompt=prompt,
        hotwords=hotwords,
        vad_filter=not is_complete_fast,
        vad_parameters=vad if not is_complete_fast else None,
        no_speech_threshold=.45 if is_complete_fast else .32,
        condition_on_previous_text=not (is_turbo or is_complete_fast),
        word_timestamps=use_word_timestamps,
    )
    cues_a = group_words_to_cues(
        segments_a,
        max_chars=max_chars,
        max_seconds=3.6,
        pause_threshold=pause_threshold,
        source_name="極速單輪" if is_turbo else ("快速完整單輪" if is_complete_fast else "標準音軌"),
    )
    pass_groups.append(cues_a)

    first_text_len = len(_transcript_signature(cues_a))
    if is_turbo:
        should_rescue = auto_rescue and first_text_len < 4
    elif is_complete_fast:
        should_rescue = auto_rescue and (analysis.quality_level != "一般" or first_text_len < 8)
    elif is_balanced:
        should_rescue = auto_rescue and (analysis.quality_level != "一般" or first_text_len < 8)
    else:
        should_rescue = auto_rescue or analysis.quality_level != "一般" or speech_scenario != "單人說話"

    cues_b: List[SubtitleCue] = []
    if should_rescue:
        rescue_audio = prepare_asr_audio(video_path, "rescue")
        segments_b, _ = _run_whisper_pass(
            model,
            rescue_audio,
            language=language,
            beam=1 if is_turbo else max(3, beam),
            prompt=prompt,
            hotwords=hotwords,
            vad_filter=False,
            vad_parameters=None,
            no_speech_threshold=.42,
            condition_on_previous_text=False,
            word_timestamps=not is_turbo,
        )
        cues_b = group_words_to_cues(
            segments_b,
            max_chars=max_chars,
            max_seconds=3.3,
            pause_threshold=.30,
            source_name="強化音軌",
        )
        pass_groups.append(cues_b)

    preliminary = merge_cue_passes(pass_groups, max_chars=max_chars)
    detected_rate = _speech_rate(preliminary)
    agreement = _text_similarity(_transcript_signature(cues_a), _transcript_signature(cues_b)) if cues_b else 1.0

    need_slow_pass = (
        not is_turbo
        and not is_complete_fast
        and not is_balanced
        and (
            speech_scenario == "語速很快"
            or detected_rate >= 6.0
            or (agreement < .58 and cues_b)
        )
    )
    if need_slow_pass:
        slow_audio = prepare_asr_audio(video_path, "slow")
        segments_c, _ = _run_whisper_pass(
            model,
            slow_audio,
            language=language,
            beam=max(6, beam),
            prompt=prompt,
            hotwords=hotwords,
            vad_filter=False,
            vad_parameters=None,
            no_speech_threshold=.42,
            condition_on_previous_text=False,
            word_timestamps=True,
        )
        cues_c = group_words_to_cues(
            segments_c,
            max_chars=max_chars,
            max_seconds=3.7 / .85,
            pause_threshold=.34 / .85,
            source_name="慢速複核",
            timestamp_scale=.85,
        )
        pass_groups.append(cues_c)

    cues = merge_cue_passes(pass_groups, max_chars=max_chars)

    if len(_transcript_signature(cues)) < 4 and analysis.duration > 2.0:
        segments_auto, _ = _run_whisper_pass(
            model,
            standard_audio,
            language=None,
            beam=1 if is_turbo else max(2, beam),
            prompt=prompt,
            hotwords=hotwords,
            vad_filter=False,
            vad_parameters=None,
            no_speech_threshold=.45,
            condition_on_previous_text=False,
            word_timestamps=not is_turbo,
        )
        cues_auto = group_words_to_cues(
            segments_auto,
            max_chars=max_chars,
            max_seconds=3.6,
            pause_threshold=.32,
            source_name="自動語言補救",
        )
        pass_groups.append(cues_auto)
        cues = merge_cue_passes(pass_groups, max_chars=max_chars)

    rules = parse_replacement_rules(replacement_text)
    for cue in cues:
        cue.text = correct_transcript_text(cue.text, glossary_terms, rules, convert_tw)

    cues, removed_hallucinations = filter_asr_hallucinations(cues, blocked_phrases)
    cues = [c for c in cues if c.text.strip() and len(clean_word(c.text)) >= 2]
    cues.sort(key=lambda c: (c.start, c.end))

    avg_conf = sum(c.confidence for c in cues) / len(cues) if cues else 0.0
    low_conf_count = sum(1 for c in cues if c.confidence < .55)
    if removed_hallucinations:
        analysis.warnings.append(f"已自動移除 {removed_hallucinations} 段提示詞外洩或重複循環字幕。")
    if low_conf_count:
        analysis.warnings.append(f"有 {low_conf_count} 段辨識信心較低，建議在輸出前複核。")
    if agreement < .58 and cues_b:
        analysis.warnings.append("不同音訊版本的辨識結果差異較大，可能有多人、背景音樂或部分語音不清楚。")

    metadata = {
        "passes": len(pass_groups),
        "speech_rate": round(_speech_rate(cues), 2),
        "agreement": round(agreement, 3),
        "average_confidence": round(avg_conf, 3),
        "low_confidence_count": low_conf_count,
        "removed_hallucinations": removed_hallucinations,
        "elapsed_seconds": round(time.perf_counter() - started_at, 1),
        "mode": accuracy_mode,
        "model": model_name,
    }
    return cues, analysis, metadata
'''
    source = replace_function(source, "transcribe_video", "srt_time", transcribe)

    old_ui = '''                    context_prompt = st.text_area(
                        "影片情境提示",
                        value="這是一段台灣中文口語影片，請使用台灣常用繁體中文。",
                        height=78,
                        key="editor_v33_context",
                        help="例如：商品介紹、會議評估、文具新品。情境越明確，選字通常越準。",
                    )'''
    new_ui = '''                    context_prompt = st.text_area(
                        "影片主題關鍵字（選填）",
                        value="",
                        height=78,
                        key="editor_v33_context",
                        help="只填主題或場景，例如：端午節、上班日記、商品介紹。請不要輸入『請使用繁體中文』等指令，程式會自動處理。",
                    )'''
    if old_ui in source:
        source = source.replace(old_ui, new_ui, 1)
    elif "影片主題關鍵字（選填）" not in source:
        raise RuntimeError("找不到影片情境提示欄位")

    output = staging / "app.py"
    output.write_text(source, encoding="utf-8", newline="\n")
    compile(source, str(output), "exec")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
