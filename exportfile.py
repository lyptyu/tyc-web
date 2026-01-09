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


def click_export_button(page):
    """
    Step 2: 找到并点击“基础工商信息导出”按钮。
    """
    btn_selector = "//span[contains(@class, '_c7f86') and contains(@class, '_63015') and contains(text(), '基础工商信息导出')]"
    btn = page.locator(btn_selector)
    btn.wait_for(state="visible")
    btn.click()
    print("已点击“基础工商信息导出”按钮。")


def wait_export_modal(page):
    """
    Step 3: 等待“基础工商信息导出”弹窗出现。
    """
    modal_selector = "//span[contains(@class, '_6e216') and contains(@class, '_cdd93') and contains(., '基础工商信息导出')]"
    page.wait_for_selector(modal_selector, state="visible")
    print("“基础工商信息导出”弹窗已出现。")


def ensure_select_all_fields(page):
    """
    Step 4: 非全选择全选导出字段。
    """
    checkbox_selector = (
        "//i[contains(@class, '_f4eb7') and contains(@class, '_f6a60') "
        "and contains(@class, '_53505') and contains(@class, '_c9c1f')]"
    )
    checkbox = page.locator(checkbox_selector)
    checkbox.wait_for(state="visible")
    class_attr = checkbox.get_attribute("class") or ""
    if "tic-gouxuan" in class_attr:
        print("已经是全选")
    elif "tic-duoxuankuang-banxuan" in class_attr:
        checkbox.click()
        # 轮询检查是否变为选中态
        for _ in range(25):  # ~5秒
            class_attr = checkbox.get_attribute("class") or ""
            if "tic-gouxuan" in class_attr:
                print("点击全选成功")
                break
            time.sleep(0.2)
        else:
            print("点击全选后未检测到已选中状态，请检查页面。")
    else:
        print("未找到可识别的全选复选框状态。")


def read_export_count(page):
    """
    Step 5: 读取 class 为 _b4a3e _ab8c7 的 span 文本，转为数字并输出。
    """
    count_selector = "//span[contains(@class, '_b4a3e') and contains(@class, '_ab8c7')]"
    span = page.locator(count_selector)
    span.wait_for(state="visible")
    raw_text = span.inner_text().strip()
    # 去掉千分位逗号
    digits = raw_text.replace(",", "")
    try:
        value = int(digits)
        print(f"导出数量: {value}")
    except ValueError:
        print(f"无法解析导出数量，原始值: {raw_text}")


def export_file(page):
    # Step 1: wait for batch/search/company/state until matchState==2.
    wait_for_state_done(page)
    # (optional buffer) ensure server-side完成后再继续
    time.sleep(2)
    # Step 2: 点击“基础工商信息导出”按钮
    click_export_button(page)
    # Step 3: 等待“基础工商信息导出”弹窗出现
    wait_export_modal(page)
    # Step 4: 全选导出字段
    ensure_select_all_fields(page)
    # Step 5: 找到总条数： class="_b4a3e _ab8c7" 的 span 元素并输出值
    read_export_count(page)
    input()
