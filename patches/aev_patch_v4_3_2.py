from pathlib import Path
import re
import sys

SEARCH_REGION = 'def search_openverse_bgm(category: str, count: int = 10) -> Tuple[List[dict], str]:\n    """\n    Low-request Openverse search.\n\n    Important:\n    - Anonymous requests use no more than 20 items per page.\n    - A 429 response immediately stops all further requests.\n    - Results are stored by the Streamlit UI in session_state, so normal\n      reruns do not query Openverse again.\n    """\n    queries = BGM_CATEGORIES.get(category, [category])\n    found: List[dict] = []\n    seen = set()\n    last_error = ""\n    headers = {\n        "User-Agent": "AutoVideoEditor/4.3.2 (local desktop app)",\n        "Accept": "application/json",\n    }\n    endpoint = OPENVERSE_AUDIO_ENDPOINTS[0]\n    page_size = 20\n\n    def add_results(results) -> None:\n        for raw in results if isinstance(results, list) else []:\n            license_code = str(raw.get("license", "")).lower().strip()\n            if license_code not in BGM_ALLOWED_LICENSES:\n                continue\n\n            media_url = str(raw.get("url") or raw.get("audio_url") or "").strip()\n            if not media_url.startswith(("http://", "https://")):\n                continue\n\n            identity = str(raw.get("id") or media_url)\n            if identity in seen:\n                continue\n            seen.add(identity)\n\n            found.append({\n                "id": identity,\n                "title": str(raw.get("title") or "未命名配樂").strip(),\n                "creator": str(raw.get("creator") or "未知創作者").strip(),\n                "license": license_code.upper(),\n                "license_version": str(raw.get("license_version") or "").strip(),\n                "category": category,\n                "duration": raw.get("duration"),\n                "source": str(raw.get("source") or raw.get("provider") or "Openverse"),\n                "source_url": str(\n                    raw.get("foreign_landing_url")\n                    or raw.get("detail_url")\n                    or ""\n                ).strip(),\n                "download_url": media_url,\n                "attribution": str(raw.get("attribution") or "").strip(),\n            })\n\n    # Usually one request is enough. At most three different search phrases\n    # are tried, and a rate-limit response stops the loop immediately.\n    for query in queries[:3]:\n        try:\n            response = requests.get(\n                endpoint,\n                params={\n                    "q": query,\n                    "page_size": page_size,\n                    "page": 1,\n                    "license": "cc0,pdm,by",\n                },\n                headers=headers,\n                timeout=25,\n            )\n\n            if response.status_code == 429:\n                retry_after = str(response.headers.get("Retry-After") or "").strip()\n                wait_text = f"請等約 {retry_after} 秒再試" if retry_after.isdigit() else "請稍後再試"\n                return found[:count], (\n                    f"Openverse 暫時限制搜尋次數（HTTP 429），{wait_text}。"\n                    "程式已停止繼續重試，避免延長限制。"\n                )\n\n            if response.status_code >= 400:\n                try:\n                    detail = str(response.json().get("detail") or "").strip()\n                except Exception:\n                    detail = ""\n                response.raise_for_status()\n                if detail:\n                    last_error = detail\n                continue\n\n            payload = response.json()\n            add_results(payload.get("results", []))\n            if len(found) >= count:\n                return found[:count], ""\n\n        except requests.RequestException as exc:\n            last_error = str(exc)\n            break\n        except Exception as exc:\n            last_error = str(exc)\n            break\n\n    if found:\n        return found[:count], (\n            "" if len(found) >= count\n            else f"目前取得 {len(found)} 首；可稍後再搜尋補足，或手動新增 BGM。"\n        )\n    return [], last_error or "沒有取得可用配樂。"'
UI_REGION = '    with st.expander("從網路尋找 BGM｜每類至少顯示 10 首", expanded=not bool(local_tracks)):\n        st.caption(\n            "BGM 模組 v4.3.2｜只有按下搜尋按鈕才會連線；"\n            "結果會保留在目前工作階段，切換其他設定不會重複搜尋。"\n        )\n        st.caption(\n            "使用 Openverse 搜尋 CC0、公共領域標記或 CC BY 音樂。"\n            "每次最多取 20 筆並篩選 10 首；CC BY 通常需要署名。"\n        )\n\n        result_key = f"{prefix}_online_results::{category}"\n        error_key = f"{prefix}_online_error::{category}"\n        searched_key = f"{prefix}_online_searched::{category}"\n\n        search_col, clear_col = st.columns([3, 1])\n        with search_col:\n            run_search = st.button(\n                "搜尋／更新這個類別的 10 首網路配樂",\n                key=f"{prefix}_search_v432",\n                type="primary",\n            )\n        with clear_col:\n            clear_results = st.button(\n                "清除結果",\n                key=f"{prefix}_clear_search_v432",\n            )\n\n        if clear_results:\n            st.session_state.pop(result_key, None)\n            st.session_state.pop(error_key, None)\n            st.session_state.pop(searched_key, None)\n            st.rerun()\n\n        if run_search:\n            with st.spinner("正在搜尋配樂；請勿連續重複按搜尋……"):\n                online_results, online_error = search_openverse_bgm(category, 10)\n            st.session_state[result_key] = online_results\n            st.session_state[error_key] = online_error\n            st.session_state[searched_key] = True\n\n        online = list(st.session_state.get(result_key, []))\n        error = str(st.session_state.get(error_key, "") or "")\n        searched = bool(st.session_state.get(searched_key, False))\n\n        if online:\n            online_labels = [\n                f"{index + 1}. {item[\'title\']}｜{item[\'creator\']}｜{item[\'license\']}"\n                for index, item in enumerate(online)\n            ]\n            online_index = st.selectbox(\n                "網路曲庫",\n                list(range(len(online))),\n                format_func=lambda i: online_labels[i],\n                key=f"{prefix}_online_v432",\n            )\n            chosen = online[int(online_index)]\n            detail = (\n                f"授權：{chosen.get(\'license\')} {chosen.get(\'license_version\', \'\')}"\n                f"｜來源：{chosen.get(\'source\', \'Openverse\')}"\n            )\n            st.caption(detail)\n            if chosen.get("download_url"):\n                try:\n                    st.audio(chosen["download_url"])\n                except Exception:\n                    pass\n            if chosen.get("source_url"):\n                st.markdown(f"[查看作品與授權頁]({chosen[\'source_url\']})")\n            if st.button(\n                "下載選取配樂到本機曲庫",\n                key=f"{prefix}_download_online_v432",\n            ):\n                try:\n                    with st.spinner("正在下載並加入本機 BGM 曲庫……"):\n                        saved = download_openverse_bgm(chosen)\n                    st.success(f"已加入：{saved.get(\'title\')}")\n                    st.rerun()\n                except Exception as exc:\n                    st.error(f"下載失敗：{exc}")\n\n            if error:\n                st.info(error)\n        elif searched:\n            if "429" in error:\n                st.warning(error)\n                st.caption(\n                    "先不要連續再按搜尋。可稍後重試，或使用下方「手動新增新的 BGM」。"\n                )\n            else:\n                st.warning("目前沒有取得網路配樂。")\n                if error:\n                    st.caption(f"網路回應：{error}")\n        else:\n            st.info("尚未搜尋。按上方按鈕後才會連線取得配樂。")'


def replace_region(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError(f"找不到更新區段：{start_marker[:60]}")
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def main() -> int:
    if len(sys.argv) < 3:
        return 2

    app_dir = Path(sys.argv[1]).resolve()
    staging = Path(sys.argv[2]).resolve()
    staging.mkdir(parents=True, exist_ok=True)

    app_path = app_dir / "app.py"
    launcher_path = app_dir / "launcher.pyw"
    app = app_path.read_text(encoding="utf-8")
    launcher = launcher_path.read_text(encoding="utf-8")

    app = re.sub(r"Auto Video Editor v4\.3\.\d+", "Auto Video Editor v4.3.2", app)
    app = re.sub(r"v4\.3\.\d+", "v4.3.2", app)
    app = re.sub(
        r'APP_TITLE\s*=\s*"自動短影音剪輯器 v4\.3\.2[^"]*"',
        'APP_TITLE = "自動短影音剪輯器 v4.3.2｜BGM 限流與快取修正版"',
        app,
        count=1,
    )
    app = re.sub(
        r'OPENVERSE_AUDIO_ENDPOINTS\s*=\s*\[[\s\S]*?\]\n',
        'OPENVERSE_AUDIO_ENDPOINTS = ["https://api.openverse.org/v1/audio/"]\n',
        app,
        count=1,
    )

    search_start = "@st.cache_data(ttl=3600, show_spinner=False)\ndef search_openverse_bgm("
    if search_start not in app:
        search_start = "def search_openverse_bgm("
    app = replace_region(
        app,
        search_start,
        "\ndef download_openverse_bgm(",
        SEARCH_REGION,
    )

    app = replace_region(
        app,
        '    with st.expander("從網路尋找 BGM｜每類至少顯示 10 首", expanded=not bool(local_tracks)):\n',
        '\n    with st.expander("手動新增新的 BGM 到曲庫"):\n',
        UI_REGION,
    )

    launcher = re.sub(r'VERSION\s*=\s*"4\.3\.\d+"', 'VERSION = "4.3.2"', launcher, count=1)
    launcher = re.sub(r"v4\.3\.\d+", "v4.3.2", launcher)

    compile(app, "app.py", "exec")
    compile(launcher, "launcher.pyw", "exec")

    (staging / "app.py").write_text(app, encoding="utf-8", newline="\n")
    (staging / "launcher.pyw").write_text(launcher, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
