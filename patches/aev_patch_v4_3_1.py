from pathlib import Path
import re
import sys


def replace_region(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("找不到需要更新的 BGM 搜尋程式區段")
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
    app = app.replace("Auto Video Editor v4.3.0", "Auto Video Editor v4.3.1")
    app = app.replace("v4.3.0", "v4.3.1")
    app = app.replace(
        'APP_TITLE = "自動短影音剪輯器 v4.3.1｜素材池 AI 剪輯導演＋網路 BGM 曲庫"',
        'APP_TITLE = "自動短影音剪輯器 v4.3.1｜網路 BGM 搜尋修正版"',
    )

    start_marker = "@st.cache_data(ttl=3600, show_spinner=False)\ndef search_openverse_bgm("
    end_marker = "\ndef download_openverse_bgm("

    replacement = r'''@st.cache_data(ttl=3600, show_spinner=False)
def search_openverse_bgm(category: str, count: int = 10) -> Tuple[List[dict], str]:
    queries = BGM_CATEGORIES.get(category, [category])
    found: List[dict] = []
    seen = set()
    last_error = ""
    headers = {
        "User-Agent": "AutoVideoEditor/4.3.1 (local desktop app)",
        "Accept": "application/json",
    }
    page_size = 20

    for query in queries:
        for page in range(1, 4):
            payload = None
            for endpoint in OPENVERSE_AUDIO_ENDPOINTS:
                try:
                    response = requests.get(
                        endpoint,
                        params={
                            "q": query,
                            "page_size": page_size,
                            "page": page,
                            "license": "cc0,pdm,by",
                        },
                        headers=headers,
                        timeout=25,
                    )
                    if response.status_code >= 400:
                        try:
                            detail = str(response.json().get("detail") or "").strip()
                        except Exception:
                            detail = ""
                        if detail:
                            raise RuntimeError(detail)
                    response.raise_for_status()
                    payload = response.json()
                    break
                except Exception as exc:
                    last_error = str(exc)

            if not isinstance(payload, dict):
                continue
            results = payload.get("results", [])
            if not isinstance(results, list) or not results:
                break

            for raw in results:
                license_code = str(raw.get("license", "")).lower().strip()
                if license_code not in BGM_ALLOWED_LICENSES:
                    continue
                media_url = str(raw.get("url") or raw.get("audio_url") or "").strip()
                if not media_url.startswith(("http://", "https://")):
                    continue
                identity = str(raw.get("id") or media_url)
                if identity in seen:
                    continue
                seen.add(identity)
                found.append({
                    "id": identity,
                    "title": str(raw.get("title") or "未命名配樂").strip(),
                    "creator": str(raw.get("creator") or "未知創作者").strip(),
                    "license": license_code.upper(),
                    "license_version": str(raw.get("license_version") or "").strip(),
                    "category": category,
                    "duration": raw.get("duration"),
                    "source": str(raw.get("source") or raw.get("provider") or "Openverse"),
                    "source_url": str(raw.get("foreign_landing_url") or raw.get("detail_url") or "").strip(),
                    "download_url": media_url,
                    "attribution": str(raw.get("attribution") or "").strip(),
                })
                if len(found) >= count:
                    return found[:count], ""
    return found[:count], last_error
'''

    app = replace_region(app, start_marker, end_marker, replacement)
    app = app.replace(
        'st.caption("使用 Openverse 搜尋可商用的 CC0、公共領域標記或 CC BY 音樂。下載前請查看作品頁；CC BY 作品通常需要署名。")',
        'st.caption("使用 Openverse 搜尋 CC0、公共領域標記或 CC BY 音樂。匿名搜尋每頁最多 20 筆，程式會自動分頁取得至少 10 首；CC BY 通常需要署名。")',
    )

    launcher = launcher_path.read_text(encoding="utf-8")
    launcher = launcher.replace('VERSION = "4.3.0"', 'VERSION = "4.3.1"')
    launcher = launcher.replace("v4.3.0", "v4.3.1")

    compile(app, "app.py", "exec")
    compile(launcher, "launcher.pyw", "exec")

    (staging / "app.py").write_text(app, encoding="utf-8", newline="\n")
    (staging / "launcher.pyw").write_text(launcher, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
