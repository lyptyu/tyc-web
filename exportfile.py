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
        return value
    except ValueError:
        print(f"无法解析导出数量，原始值: {raw_text}")
        return None


def perform_export(page, total_count):
    """
    Step 6: 根据数量选择导出方式。
    - 少于 1 万：点击 class="_f64c8 tyc-btn-v2 _53199 _c26a6 _d025c" 的按钮。
    - 大于等于 1 万：使用“自定义范围”分批导出，每批最多 10000。
    """
    if total_count is None:
        print("无法判断总条数，跳过导出点击。")
        return

    if total_count < 10000:
        btn_selector = "//button[contains(@class, '_f64c8') and contains(@class, 'tyc-btn-v2') and contains(@class, '_53199') and contains(@class, '_c26a6') and contains(@class, '_d025c')]"
        btn = page.locator(btn_selector)
        btn.wait_for(state="visible")
        btn.click()
        print("总条数 < 10000，已点击直接导出按钮。")
    else:
        perform_export_custom_ranges(page, total_count)


def perform_export_custom_ranges(page, total_count):
    """
    大于等于 1 万时，使用自定义范围分批导出。
    每批最多导出 10000 条，逐批触发 exportAndFields 接口成功后继续。
    """
    def open_custom_range():
        # 重新打开弹窗
        click_export_button(page)
        wait_export_modal(page)
        ensure_select_all_fields(page)
        # 进入自定义范围
        span_selector = "//span[contains(@class, '_576dc') and contains(text(), '自定义范围：')]"
        span = page.locator(span_selector)
        span.wait_for(state="visible")
        span.click()
        print("已打开弹窗并进入自定义范围。")

    def wait_export_success():
        target = "batch/search/company/exportAndFields"
        deadline = time.time() + 60  # up to 60s per批
        while time.time() < deadline:
            remaining_ms = max(1, int((deadline - time.time()) * 1000))
            try:
                resp = page.context.wait_for_event("response", timeout=remaining_ms)
            except TimeoutError:
                continue
            if target in resp.url:
                try:
                    data = json.loads(resp.text())
                    if data.get("state") == "ok" and data.get("data") == "success":
                        print("本批次导出请求成功。")
                        return True
                except Exception:
                    pass
        print("等待 exportAndFields 成功超时。")
        return False

    def submit_range(start, end):
        inputs = page.locator("//input[contains(@class, '_90acb')]")
        if inputs.count() < 2:
            print("未找到自定义范围输入框。")
            return False
        inputs.nth(0).fill(str(start))
        inputs.nth(1).fill(str(end))
        # 点击导出按钮
        btn_selector = "//button[contains(@class, '_f64c8') and contains(@class, 'tyc-btn-v2') and contains(@class, '_53199') and contains(@class, '_c26a6') and contains(@class, '_d025c')]"
        btn = page.locator(btn_selector)
        btn.wait_for(state="visible")
        btn.click()
        print(f"已提交导出范围：{start}-{end}")
        return wait_export_success()

    start = 1
    batch_size = 10000
    first_batch = True  # 第一次使用已打开的弹窗，后续才重新打开
    while start <= total_count:
        end = min(start + batch_size - 1, total_count)
        if not first_batch:
            open_custom_range()
        ok = submit_range(start, end)
        if not ok:
            print(f"范围 {start}-{end} 导出失败或超时，停止。")
            break
        start = end + 1
        first_batch = False


def basic_export_flow(page):
    """
    Step 1: 点击“基础工商信息导出”按钮
    Step 2: 等待弹窗出现
    Step 3: 全选导出字段
    Step 4: 获取总条数
    Step 5: 按数量执行导出（含分批）
    """
    click_export_button(page)
    wait_export_modal(page)
    ensure_select_all_fields(page)
    total_count = read_export_count(page)
    perform_export(page, total_count)


def export_file(page):
    # Step 1: 等待 batch/search/company/state 直到 matchState==2.
    wait_for_state_done(page)
    # (optional buffer) ensure server-side完成后再继续
    time.sleep(2)
    # 基础工商信息导出流程
    basic_export_flow(page)
    input()
