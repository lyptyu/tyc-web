import json
import time
from playwright.sync_api import TimeoutError


def wait_for_state_done(page, timeout_sec=60):
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
                    state = data.get("state")
                    if state == "ok" and data.get("data") == "success":
                        print("本批次导出请求成功。")
                        return True
                    if state == "warn":
                        print("基本信息导出没次数了，刷新页面继续后续流程。")
                        try:
                            page.reload(wait_until="domcontentloaded")
                        except Exception:
                            pass
                        return "warn"
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
        if ok == "warn":
            # 刷新后终止本次自定义导出循环，但不终止整个程序
            break
        if not ok:
            print(f"范围 {start}-{end} 导出失败或超时，停止。")
            break
        start = end + 1
        first_batch = False


def open_more_dimensions_modal(page, target_text):
    click_more_dimensions_export_button(page)
    btn = page.locator(
        "//button[contains(@class, '_50ab4') and contains(@class, '_58c27') and contains(@class, '_6c649')][.//span[contains(text(), $text)] ]"
    ).filter(has_text=target_text)
    btn.wait_for(state="visible")
    btn.click()
    print(f"已重新打开“更多维度导出”并进入“{target_text}”。")


def perform_more_dimensions_export(page, total_count, open_modal_fn=None, batch_size=5000):
    """
    更多维度导出，默认每批 5000 条，超过则分批并可重开弹窗。
    """
    if total_count is None:
        print("无法判断总条数，跳过导出。")
        return

    export_btn_selector = "//button[contains(@class, '_50ab4') and contains(@class, 'index_exportButton__9Jnq2') and contains(@class, '_52bf6')][.//span[contains(text(), '导出数据')]]"

    def wait_export_success():
        target = "batch/search/company/export/dim"
        deadline = time.time() + 60
        while time.time() < deadline:
            remaining_ms = max(1, int((deadline - time.time()) * 1000))
            try:
                resp = page.context.wait_for_event("response", timeout=remaining_ms)
            except TimeoutError:
                continue
            if target in resp.url:
                try:
                    data = json.loads(resp.text())
                    if data.get("state") == "ok":
                        print("本批次股东导出请求成功。")
                        return True
                except Exception:
                    pass
        print("等待股东导出成功超时。")
        return False

    def submit_range(start, end):
        inputs = page.locator("//input[contains(@class, '_90acb')]")
        if inputs.count() < 2:
            print("未找到自定义范围输入框。")
            return False
        inputs.nth(0).fill(str(start))
        inputs.nth(1).fill(str(end))
        btn = page.locator(export_btn_selector)
        btn.wait_for(state="visible")
        btn.click()
        print(f"导出范围：{start}-{end}")
        return wait_export_success()

    start = 1
    first_batch = True
    while start <= total_count:
        end = min(start + batch_size - 1, total_count)
        if not first_batch:
            if open_modal_fn:
                open_modal_fn()
        ok = submit_range(start, end)
        if not ok:
            print(f"导出范围 {start}-{end} 失败或超时，停止。")
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


def click_more_dimensions_export_button(page):
    """
    点击“更多维度导出”按钮。
    """
    btn_selector = "//span[contains(@class, '_c7f86') and contains(@class, '_63015') and contains(text(), '更多维度导出')]"
    btn = page.locator(btn_selector)
    btn.wait_for(state="visible")
    btn.click()
    print("已点击“更多维度导出”按钮。")


def shareholder_export_flow(page):
    """
    Step 1: 点击“更多维度导出”按钮：span元素，class包含“_c7f86 _63015”，text包含“更多维度导出”
    Step 2: 点击“股东信息”按钮
    Step 3: 获取总条数
    Step 4: 按数量执行导出（含分批）
    """
    click_more_dimensions_export_button(page)
    # Step 2: 点击“股东信息”按钮
    shareholder_btn = page.locator("//button[contains(@class, '_50ab4') and contains(@class, '_58c27') and contains(@class, '_6c649')][.//span[contains(text(), '股东信息')]]")
    shareholder_btn.wait_for(state="visible")
    shareholder_btn.click()
    print("已点击“股东信息”按钮。")
    # Step 3: 获取总条数
    total_count = read_export_count(page)
    # Step 4: 按数量执行导出（含分批）
    if total_count < 5000:
        # 股东导出按钮
        export_btn_selector = "//button[contains(@class, '_50ab4') and contains(@class, 'index_exportButton__9Jnq2') and contains(@class, '_52bf6')][.//span[contains(text(), '导出数据')]]"
        btn = page.locator(export_btn_selector)
        btn.wait_for(state="visible")
        btn.click()
        print("股东总条数 < 5000，已点击导出数据。")
    else:
        perform_more_dimensions_export(
            page, total_count, open_modal_fn=lambda: open_more_dimensions_modal(page, "股东信息"), batch_size=5000
        )


def external_investment_export_flow(page):
    """
    对外投资导出流程：
    Step 1: 点击“更多维度导出”
    Step 2: 点击“对外投资”按钮
    Step 3: 获取总条数
    Step 4: 按数量执行导出（含分批，5000/批）
    """
    click_more_dimensions_export_button(page)
    investment_btn = page.locator("//button[contains(@class, '_50ab4') and contains(@class, '_58c27') and contains(@class, '_6c649')][.//span[contains(text(), '对外投资')]]")
    investment_btn.wait_for(state="visible")
    investment_btn.click()
    print("已点击“对外投资”按钮。")
    total_count = read_export_count(page)
    if total_count < 5000:
        export_btn_selector = "//button[contains(@class, '_50ab4') and contains(@class, 'index_exportButton__9Jnq2') and contains(@class, '_52bf6')][.//span[contains(text(), '导出数据')]]"
        btn = page.locator(export_btn_selector)
        btn.wait_for(state="visible")
        btn.click()
        print("对外投资总条数 < 5000，已点击导出数据。")
    else:
        perform_more_dimensions_export(
            page, total_count, open_modal_fn=lambda: open_more_dimensions_modal(page, "对外投资"), batch_size=5000
        )


def select_report(page, start_str, report_url=None):
    target = "myReport/list"
    buffered = []

    def _on_resp(resp):
        if target not in resp.url:
            return
        try:
            data = json.loads(resp.text())
            buffered.append(data)
        except Exception:
            return

    # 提前注册监听，避免跳转后错过首个接口
    page.on("response", _on_resp)
    page.context.on("response", _on_resp)
    if report_url:
        page.goto(report_url)
        print(f"已跳转到报告页面 {report_url}")

    def to_ms(datetime_str):
        try:
            tm = time.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            return int(time.mktime(tm) * 1000)
        except Exception:
            return None

    def safe_int(value):
        try:
            return int(value)
        except Exception:
            return None

    def wait_report_list(expected_page_num=None, timeout_sec=30):
        deadline = time.time() + timeout_sec

        def pop_buffered():
            if not buffered:
                return None
            # 按 FIFO 取出并消费，避免重复命中旧数据
            data = buffered.pop(0)
            page_num = data.get("data", {}).get("pageNum")
            if expected_page_num is None or page_num == expected_page_num:
                return data
            # 未命中则继续找下一条
            return pop_buffered()

        while time.time() < deadline:
            buffered_hit = pop_buffered()
            if buffered_hit:
                return buffered_hit

            remaining_ms = max(1, int((deadline - time.time()) * 1000))
            try:
                resp = page.context.wait_for_event("response", timeout=remaining_ms)
            except TimeoutError:
                continue

            if target not in resp.url:
                continue

            try:
                data = json.loads(resp.text())
            except Exception:
                continue

            page_num = data.get("data", {}).get("pageNum")
            if expected_page_num is not None and page_num != expected_page_num:
                continue
            return data
        return None

    def click_row_checkbox(row):
        candidates = [
            row.locator("td").first.locator("div div svg"),
            row.locator("td").first.locator("svg"),
        ]
        for cand in candidates:
            try:
                for idx in range(cand.count()):
                    el = cand.nth(idx)
                    if el.is_visible():
                        el.click()
                        return True
            except Exception:
                continue
        return False

    def click_first_visible(locator):
        try:
            for idx in range(locator.count()):
                el = locator.nth(idx)
                if el.is_visible():
                    el.click()
                    return True
        except Exception:
            return False
        return False

    def select_first_n_rows(n):
        if n <= 0:
            print("无需勾选任何行。")
            return
        rows = page.locator("tbody tr")
        try:
            rows.first.wait_for(state="visible", timeout=15000)
        except TimeoutError:
            pass

        row_count = rows.count()
        max_n = min(n, row_count)
        for i in range(max_n):
            row = rows.nth(i)
            ok = click_row_checkbox(row)
            if not ok:
                print(f"第 {i + 1} 行未找到可点击的勾选 svg。")
        print(f"已勾选前 {max_n} 行。")

    def select_all_rows_on_page():
        ok = click_first_visible(page.locator("thead svg"))
        if ok:
            print("已通过表头勾选全选当前页。")
            return True

        rows = page.locator("tbody tr")
        row_count = rows.count()
        for i in range(row_count):
            click_row_checkbox(rows.nth(i))
        print("已逐行勾选当前页全部行。")
        return True

    def click_next_page_icon():
        return click_first_visible(page.locator("i.tic.tic-laydate-next-m"))

    def click_prev_page_icon():
        selectors = [
            "i.tic.tic-laydate-prev-m",
            "i.tic.tic-laydate-prev",
            "i.tic.tic-laydate-pre-m",
            "i.tic.tic-laydate-pre",
        ]
        for sel in selectors:
            if click_first_visible(page.locator(sel)):
                return True
        return False

    def click_page_num(page_num):
        # 有些页面没有 pagination-wrap 容器，直接在 pageWrap 下找数字按钮
        xpath = (
            "//div[contains(@class,'pageWrap')]"
            f"//div[contains(@class,'num') and normalize-space(text())='{page_num}']"
        )
        loc = page.locator(xpath)
        if click_first_visible(loc):
            return True

        loc = page.locator("div.pageWrap div.num").filter(has_text=str(page_num))
        return click_first_visible(loc)

    def goto_page(target_page_num, current_page_num, timeout_sec=30):
        if target_page_num == current_page_num:
            return current_page_num, True, None

        ok = click_page_num(target_page_num)
        if ok:
            data = wait_report_list(expected_page_num=target_page_num, timeout_sec=timeout_sec)
            if not data:
                time.sleep(0.5)
                data = wait_report_list(expected_page_num=target_page_num, timeout_sec=timeout_sec)
            if not data:
                return current_page_num, False, None
            return target_page_num, True, data

        if target_page_num > current_page_num:
            data = None
            while current_page_num < target_page_num:
                ok = click_next_page_icon()
                if not ok:
                    return current_page_num, False, None
                data = wait_report_list(expected_page_num=current_page_num + 1, timeout_sec=timeout_sec)
                if not data:
                    return current_page_num, False, None
                current_page_num += 1
            return current_page_num, True, data

        if target_page_num < current_page_num:
            data = None
            while current_page_num > target_page_num:
                ok = click_prev_page_icon()
                if not ok:
                    return current_page_num, False, None
                data = wait_report_list(expected_page_num=current_page_num - 1, timeout_sec=timeout_sec)
                if not data:
                    return current_page_num, False, None
                current_page_num -= 1
            return current_page_num, True, data

        return current_page_num, False, None

    def page_all_ready(data):
        payload = data.get("data", {})
        items = payload.get("items") or []
        if not items:
            return True
        for item in items:
            status = safe_int(item.get("reportStatus"))
            if status != 2:
                return False
        return True

    def count_unready(data):
        payload = data.get("data", {})
        items = payload.get("items") or []
        unready = 0
        for item in items:
            status = safe_int(item.get("reportStatus"))
            if status != 2:
                unready += 1
        return unready

    def wait_until_page_ready(page_num, initial_data=None, timeout_sec=7200):
        if initial_data and page_all_ready(initial_data):
            return True

        if initial_data:
            remaining = count_unready(initial_data)
            if remaining > 0:
                print(f"第{page_num}页还剩{remaining}个文档未生成完毕，接口轮询中，请稍后")

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            remaining = max(1, int(deadline - time.time()))
            data = wait_report_list(expected_page_num=page_num, timeout_sec=min(300, remaining))
            if not data:
                continue
            if page_all_ready(data):
                return True
            remaining = count_unready(data)
            if remaining > 0:
                print(f"第{page_num}页还剩{remaining}个文档未生成完毕，接口轮询中，请稍后")
        return False

    try:
        start_ms = to_ms(start_str)
        if start_ms is None:
            print(f"无法解析开始时间 start_str: {start_str}")
            return False

        data = wait_report_list(timeout_sec=30)
        if not data:
            print("未捕获到报告列表接口数据。")
            return False

        initial_page_num = safe_int(data.get("data", {}).get("pageNum")) or 1
        if initial_page_num != 1:
            current_page_num = initial_page_num
            current_page_num, ok, data2 = goto_page(1, current_page_num)
            if not ok:
                print("初始化跳转第一页失败。")
                return False
            if data2:
                data = data2

        page_list_data = {}
        pending_pages = set()
        current_page_num = None

        max_pages = 200
        selection_done = False
        for _ in range(max_pages):
            payload = data.get("data", {})
            items = payload.get("items") or []
            if not items:
                print("报告列表为空。")
                selection_done = True
                break

            page_num = safe_int(payload.get("pageNum")) or 1
            current_page_num = page_num
            page_list_data[page_num] = data

            if any(safe_int(item.get("reportStatus")) == 1 for item in items):
                pending_pages.add(page_num)

            page_size = safe_int(payload.get("pageSize")) or max(len(items), 1)
            total = safe_int(payload.get("total")) or 0

            last_item = items[-1] if items else {}
            last_pay_date = safe_int(last_item.get("payDate"))
            if last_pay_date is None:
                print("无法读取最后一条数据的 payDate。")
                return False

            if last_pay_date <= start_ms:
                # 如果最后一条 payDate 早于 start_str，说明第一页已经包含 start_str 之后的全部数据。
                select_count = 0
                for item in items:
                    pay_date = safe_int(item.get("payDate"))
                    if pay_date is None:
                        continue
                    if pay_date > start_ms:
                        select_count += 1
                    else:
                        break
                select_first_n_rows(select_count)
                selection_done = True
                break

            select_all_rows_on_page()

            has_next = (page_num * page_size) < total
            if not has_next:
                print("已到最后一页。")
                selection_done = True
                break

            ok = click_next_page_icon()
            if not ok:
                print("未找到可点击的下一页按钮。")
                return False

            data = wait_report_list(expected_page_num=page_num + 1, timeout_sec=30)
            if not data:
                print("翻页后未捕获到新的报告列表接口数据。")
                return False
            time.sleep(0.5)

        if not selection_done:
            print("翻页次数超出上限，停止勾选。")
            return False

        if not pending_pages:
            print("全部文档生成成功")
            return True

        if current_page_num is None:
            current_page_num = 1

        current_page_num, ok, data = goto_page(1, current_page_num)
        if not ok:
            print("跳转第一页失败。")
            return False
        if data:
            page_list_data[1] = data

        for p in sorted(pending_pages):
            current_page_num, ok, data = goto_page(p, current_page_num)
            if not ok:
                print(f"跳转到第 {p} 页失败。")
                return False
            if data:
                page_list_data[p] = data

            ok_ready = wait_until_page_ready(p, initial_data=data or page_list_data.get(p))
            if not ok_ready:
                print(f"等待第 {p} 页 reportStatus 全部为 2 超时。")
                return False

        print("全部文档生成成功")
        return True
    finally:
        try:
            page.off("response", _on_resp)
        except Exception:
            pass


def batch_download(page):
    btn = page.locator(
        "button._50ab4._52bf6._9e3b9:has(span:has-text('批量下载'))"
    ).first
    btn.wait_for(state="attached", timeout=20000)
    btn.evaluate("el => el.click()")
    print("已点击批量下载")
    return True


def export_file(page):
    # start_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    start_str = "2026-01-09 18:40:04"
    print(f"开始时间 {start_str}")
    # Step 1: 等待 batch/search/company/state 直到 matchState==2.
    # wait_for_state_done(page)
    # (optional buffer) ensure server-side完成后再继续
    # time.sleep(2)
    # 基础工商信息导出流程
    basic_export_flow(page)
    # time.sleep(2)
    # 股东信息导出流程
    shareholder_export_flow(page)
    # time.sleep(2)
    # 对外投资导出流程
    external_investment_export_flow(page)
    time.sleep(1)
    # 导航至报告页面
    report_url = "https://www.tianyancha.com/usercenter/report"
    select_report(page, start_str, report_url=report_url)
    batch_download(page)
    input()
