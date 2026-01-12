import os
import traceback

from automation import WebAutomation


def _read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _append_log(text):
    with open("file_cookie_log.txt", "a", encoding="utf-8") as f:
        f.write(text)


SEPARATOR = "-" * 70 + "\n"


def run_sequential(cookie_dir="cookie", file_dir="file"):
    i = 1
    while True:
        cookie_name = f"cookie{i}.txt"
        file_name = f"file{i}.txt"

        cookie_path = os.path.join(cookie_dir, cookie_name)
        import_file_path_file = os.path.join(file_dir, file_name)

        if not os.path.exists(cookie_path) or not os.path.exists(import_file_path_file):
            break

        cookie_string = _read_text(cookie_path)
        import_file = _read_text(import_file_path_file)

        if not os.path.exists(import_file):
            _append_log(f"{i} {cookie_name}-{file_name}-失败\n")
            _append_log(f"import_file not found: {import_file}\n\n")
            _append_log(SEPARATOR)
            i += 1
            continue

        log_lines = []
        automation = WebAutomation(logger=lambda m: log_lines.append(str(m)))

        try:
            downloaded_file_path = automation.run_task(
                import_file=import_file,
                cookie_string=cookie_string,
            )
            _append_log(f"{i} {cookie_name}-{file_name}-成功\n")
            if downloaded_file_path:
                print(f"文件已下载至: {downloaded_file_path}")
            else:
                print("执行完成，但未返回下载路径")
        except Exception:
            _append_log(f"{i} {cookie_name}-{file_name}-失败\n")
            _append_log("\n".join(log_lines) + "\n")
            _append_log(traceback.format_exc() + "\n")

        _append_log("\n")
        _append_log(SEPARATOR)

        i += 1


if __name__ == "__main__":
    run_sequential()
