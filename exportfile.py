import json
import time
from playwright.sync_api import TimeoutError


def wait_for_state_done(page, timeout_sec=20):
    """
    等待 batch/search/company/state 响应，直到 matchState==2 即视为完成。
    返回 True 表示已检测到 matchState==2，否则 False。
    """
    target = "batch/search/company/state"
    state = {"done": False}
    seen = set()

    def _log_response(response):
        if state["done"]:
            return
        if target not in response.url:
            return

        resp_id = id(response)
        if resp_id in seen:
            return
        seen.add(resp_id)

        match_state = None
        try:
            data = json.loads(response.text())
            match_state = data.get("data", {}).get("matchState")
        except Exception:
            match_state = None
        if match_state == 2 and not state["done"]:
            state["done"] = True
            print("上传结束")

    page.on("response", _log_response)

    # 由于该接口一定会出现，仅等待直到匹配到 matchState==2 或超时。
    deadline = time.time() + timeout_sec
    while time.time() < deadline and not state["done"]:
        remaining_ms = max(1, int((deadline - time.time()) * 1000))
        try:
            resp = page.context.wait_for_event("response", timeout=remaining_ms)
        except TimeoutError:
            continue
        if target in resp.url:
            _log_response(resp)
            if state["done"]:
                break
    if not state["done"]:
        print("在规定时间内未检测到 matchState==2。")

    try:
        page.off("response", _log_response)
    except Exception:
        pass

    return state["done"]


def export_file(page):
    # Step 1: wait for batch/search/company/state until matchState==2.
    wait_for_state_done(page)
    time.sleep(2)
	# Step 2: 
    input()
