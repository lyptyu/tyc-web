import os
import json
import time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError

from exportfile import export_file


class WebAutomation:
    def __init__(self, config_path_or_dict=None, logger=None):
        self.logger = logger
        if not config_path_or_dict:
            config_path_or_dict = r"web_config.json"
        if isinstance(config_path_or_dict, str):
            self.config = self.load_config(config_path_or_dict)
        else:
            self.config = config_path_or_dict

        self.headless = self.config.get("headless", False)

    def log(self, message):
        if self.logger:
            self.logger(message)
        else:
            print(message)

    def load_config(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_latest_file(self, folder):
        if not os.path.exists(folder):
            return None
        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
        ]
        if not files:
            return None
        return max(files, key=os.path.getctime)

    def _parse_cookie_string(self, cookie_string):
        """Parses a raw cookie string into a list of dictionaries."""
        cookies = []

        # Determine domain
        domain = self.config.get("cookie_domain")
        if not domain:
            # Try to infer from import_page_url
            import_url = self.config.get("import_page_url")
            if import_url:
                parsed_url = urlparse(import_url)
                domain = parsed_url.hostname

        if not domain:
            self.log(
                "Warning: Could not determine domain for cookies. Cookies might not be set correctly."
            )

        parts = cookie_string.split(";")
        for part in parts:
            if "=" in part:
                name, value = part.strip().split("=", 1)
                cookie = {
                    "name": name,
                    "value": value,
                    "path": "/",
                    "domain": (
                        domain if domain else ""
                    ),  # Playwright might reject empty domain
                    "httpOnly": False,
                    "secure": False,
                }
                # Clean up domain if it is empty/None to let Playwright handle or fail gracefully
                if not cookie["domain"]:
                    del cookie["domain"]
                    # If no domain, we rely on the browser to set it for the current page context
                    # But add_cookies usually requires it unless url is provided.
                    # Let's try to add 'url' if domain is missing
                    import_url = self.config.get("import_page_url")
                    if import_url:
                        cookie["url"] = import_url

                cookies.append(cookie)
        return cookies

    def run_task(self, import_file):
        """
        Executes the automation task:
        1. Login (using cookies)
        2. Import file
        3. Export/Download result
        Returns:
            str: Path to the downloaded file.
        """
        downloaded_file_path = None
        self.import_file = import_file

        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(
                channel="chrome",
                headless=self.headless,
                ignore_default_args=["--headless"],
            )
            context = browser.new_context()

            # 1. Load Cookies
            cookies_config = self.config.get("login_cookies")
            cookies_to_add = []

            if isinstance(cookies_config, str):
                cookies_to_add = self._parse_cookie_string(cookies_config)
            elif isinstance(cookies_config, list):
                cookies_to_add = cookies_config

            if cookies_to_add:
                try:
                    context.add_cookies(cookies_to_add)
                    self.log(f"Loaded {len(cookies_to_add)} cookies.")
                except Exception as e:
                    self.log(f"Error adding cookies: {e}")
            else:
                self.log("Warning: No login_cookies found or parsed from config.")

            page = context.new_page()

            # 2. Import Process
            try:
                self._process_import(page)
            except Exception as e:
                self.log(f"Error during import process: {e}")
                # Depending on requirements, we might want to stop here
                # but user asked to proceed to step 3?
                # "After the above steps are completed... jump to specified page"
                # If import fails, usually step 3 (downloading result) might not be valid,
                # but the prompt implies sequential execution. I'll re-raise or handle.
                # Assuming if import fails, we can't download the result of that import.
                # However, step 3 says "select latest data", which might be independent.
                # For now, I'll log and continue if possible, or raise.
                # Let's assume we stop on critical failure.
                browser.close()
                raise e

            # 3. Download Process
            # try:
            #     downloaded_file_path = self._process_download(page)
            # except Exception as e:
            #     self.log(f"Error during download process: {e}")
            #     browser.close()
            #     raise e

            browser.close()

        return downloaded_file_path


    def check_login(self, page, trigger=None):
        """
        Listen for the user info API and determine login status.
        Succeeds when the response JSON has state == "ok",
        otherwise logs failure and raises.
        """
        self.log("检查登录状态接口： next/web/getUserInfo...")
        predicate = lambda r: "next/web/getUserInfo" in r.url

        try:
            with page.expect_response(predicate, timeout=10000) as resp_info:
                if trigger:
                    trigger()
            response = resp_info.value
        except TimeoutError:
            self.log("用户登陆失败！请重新设置token")
            raise

        try:
            data = response.json()
        except Exception:
            self.log("用户登陆失败！请重新设置token")
            raise

        if data.get("state") == "ok":
            self.log("登录成功")
            return True
        raise Exception("登录失败: state is not ok")
    def check_vip(self, page, trigger=None):
        """
        Listen for batch/search/import response and ensure state == 'ok'.
        """
        self.log("检查会员接口： batch/search/import ...")
        predicate = lambda r: "batch/search/import" in r.url

        try:
            with page.expect_response(predicate, timeout=15000) as resp_info:
                if trigger:
                    trigger()
            response = resp_info.value
        except TimeoutError:
            self.log("账号会员过期，请重试")
            raise

        try:
            data = response.json()
        except Exception:
            self.log("账号会员过期，请重试")
            raise

        if data.get("state") == "ok":
            self.log("会员检查通过")
            return True

        self.log("账号会员过期，请重试")
        raise Exception("会员检查失败: state is not ok")
    def _process_import(self, page):
        self.check_login(
            page,
            trigger=lambda: (
                page.goto("https://www.tianyancha.com/"),
                page.wait_for_timeout(1500),
            ),
        )
        time.sleep(0.5)
        import_page_url = self.config.get("import_page_url")
        if not import_page_url:
            raise ValueError("Config missing 'import_page_url'")
        
        self.log(f"Navigating to import page: {import_page_url}")
        page.goto(import_page_url)
        # # Prepare file to upload
        # import_folder = self.config.get("import_folder")
        # if not import_folder:
        #     raise ValueError("Config missing 'import_folder'")

        # file_to_upload = self.get_latest_file(import_folder)
        if not self.import_file:
            raise FileNotFoundError(f"No import file specified: {self.import_file}")

        self.log(f"Selected file for import: {self.import_file}")

        # Upload file via input element (supports hidden inputs)
        import_input_selector = self.config.get("import_input_selector")

        if not import_input_selector:
            # Default to generic file input if not specified, as per user's latest request context
            import_input_selector = "input[type='file']"
            self.log(
                f"Config 'import_input_selector' not found, defaulting to: {import_input_selector}"
            )

        self.log(f"Uploading file to input: {import_input_selector}")
        self.check_vip(
            page,
            trigger=lambda: page.set_input_files(import_input_selector, self.import_file),
        )

        time.sleep(2)
        export_file(page)
        return
        parent_btn_selector = self.config.get("export_parent_button_selector")
        if parent_btn_selector:
            self.log(f"Waiting for button: {parent_btn_selector}")
            try:
                # Wait for button to be visible first
                page.wait_for_selector(
                    parent_btn_selector, state="visible", timeout=30000
                )
                self.log("点击“基础工商信息导出”的父按钮...")
                page.click(parent_btn_selector)
                page.wait_for_timeout(1000)
            except TimeoutError:
                self.log(
                    f"Timeout waiting for button: {parent_btn_selector}. Check if selector is correct or button is visible."
                )
                raise
        # 点击全选导出按钮：
        # 查找“导出字段”文本，并点击其相邻的前一个 span 元素（即复选框）
        # HTML结构: <div ...><span class="_3e0af"><i ...></i></span><div ...><span ...>导出字段</span>...</div></div>
        # 策略: 找到包含“导出字段”文本的元素，向上找父级/相邻元素，定位到复选框
        export_checkbox_selector = "//span[contains(text(), '导出字段')]/ancestor::div//span"

        # 如果 config 中指定了特定的 export_data_button_selector，优先使用 config 的（为了兼容性）
        # 但根据用户请求，这里我们构建一个更智能的默认选择器
        config_selector = self.config.get("export_data_button_selector")

        # 如果 config 中的选择器看起来像是旧的或通用的，我们尝试使用新的智能选择器
        # 或者我们直接使用 xpath 定位
        target_selector = (
            config_selector
            if config_selector and "导出字段" not in config_selector
            else export_checkbox_selector
        )

        self.log(f"Waiting for export checkbox: {target_selector}")
        try:
            # Wait for button to be visible first
            page.wait_for_selector(target_selector, state="visible", timeout=30000)
            
            # Check if checkbox is already checked (contains i.tic-gouxuan)
            if page.locator(target_selector).locator("i.tic-gouxuan").count() > 0:
                 self.log("复选框已选中(检测到tic-gouxuan)，跳过点击...")
            else:
                self.log("点击“导出字段”旁的复选框...")
                page.click(target_selector)
                page.wait_for_timeout(1000)

            # 点击全选后，通常需要点击实际的“导出”按钮
            # 检查是否配置了确认导出的按钮选择器
            confirm_export_btn_selector = self.config.get(
                "confirm_export_button_selector"
            )
            if confirm_export_btn_selector:
                self.log(
                    f"Waiting for confirm export button: {confirm_export_btn_selector}"
                )
                page.wait_for_selector(
                    confirm_export_btn_selector, state="visible", timeout=30000
                )
                page.click(confirm_export_btn_selector)
                page.wait_for_timeout(1000)

        except TimeoutError:
            self.log(
                f"Timeout waiting for button: {target_selector}. Check if selector is correct or button is visible."
            )
            raise
        # Wait for automatic page jump (redirect)
        # redirect_route = self.config.get("redirect_route")
        # if redirect_route:
        #     self.log(f"Waiting for redirect to route containing: {redirect_route}")
        #     try:
        #         # Wait until URL contains the redirect route
        #         page.goto(redirect_route)
        #         self.log("Redirect successful.")
        #     except TimeoutError:
        #         raise TimeoutError(
        #             f"Timed out waiting for redirect to {redirect_route}"
        #         )

        # If entered correctly, execute specified button steps to export data
        # Note: User says "export data" here, but step 3 is "download".
        # Maybe this "export" generates the data on server?
        # export_btn_selector = self.config.get("export_data_button_selector")
        # if export_btn_selector:
        #     self.log("Clicking export data button...")
        #     page.click(export_btn_selector)
        #     # Add a small wait for action to register
        #     page.wait_for_timeout(2000)

    def _process_download(self, page):
        download_page_url = self.config.get("redirect_route")
        if not download_page_url:
            raise ValueError("Config missing 'download_page_url'")

        self.log(f"Navigating to download page: {download_page_url}")
        page.goto(download_page_url)

        # 1. Wait for the first row to appear
        self.log("Waiting for data table rows...")
        first_row_selector = "tbody tr:first-child"
        try:
            page.wait_for_selector(first_row_selector, timeout=60000)
        except TimeoutError:
            raise TimeoutError("Timeout waiting for data table to load.")

        # 2. Check status in the 4th column (index 3) until it says "文档生成成功"
        status_cell_selector = f"{first_row_selector} td:nth-child(4)"
        status_text_selector = f"{status_cell_selector} .index_reportStatus__AyXgG"

        self.log("Waiting for document generation to complete...")
        max_retries = 60  # Wait up to 2 minutes
        for i in range(max_retries):
            try:
                # Check if status text exists and is correct
                status_element = page.locator(status_text_selector)
                if status_element.count() > 0:
                    text = status_element.inner_text()
                    if "文档生成成功" in text:
                        self.log("Document generated successfully.")
                        break

                # Fallback check on cell text
                cell_element = page.locator(status_cell_selector)
                if cell_element.count() > 0:
                    text = cell_element.inner_text()
                    if "文档生成成功" in text:
                        self.log("Document generated successfully (found in cell).")
                        break
            except Exception:
                pass

            if i == max_retries - 1:
                raise TimeoutError(
                    "Timed out waiting for document status '文档生成成功'"
                )

            time.sleep(2)
            if i > 0 and i % 5 == 0:
                self.log("Refreshing page to check status...")
                page.reload()
                page.wait_for_selector(first_row_selector, timeout=30000)

        # 3. Click the download button (middle element in last column)
        last_cell_selector = f"{first_row_selector} td:last-child"
        download_btn_selector = f"{last_cell_selector} > div > :nth-child(2)"

        self.log(f"Clicking download button: {download_btn_selector}")

        with page.expect_download() as download_info:
            page.click(download_btn_selector)

        download = download_info.value

        # Determine save path
        export_download_path = self.config.get("export_download_path")
        if not export_download_path:
            export_download_path = os.path.join(os.getcwd(), "downloads")

        if not os.path.exists(export_download_path):
            os.makedirs(export_download_path)

        save_path = os.path.join(export_download_path, download.suggested_filename)
        download.save_as(save_path)

        self.log(f"File downloaded to: {save_path}")
        return save_path


if __name__ == "__main__":
    # Test execution
    # Ensure config.json has the required fields
    config_path = "../dist/config.json"  # Adjust path as needed
    if os.path.exists(config_path):
        automation = WebAutomation(config_path)
        try:
            result = automation.run_task()
            print(f"Task completed. Result: {result}")
        except Exception as e:
            print(f"Task failed: {e}")
    else:
        print("Config file not found for testing.")
