from automation import WebAutomation

# 初始化自动化实例
automation = WebAutomation()

# 执行任务并获取下载文件路径
try:
    import_file = r"C:\Users\linyipeng\Desktop\基协数据修复.xls"
    downloaded_file_path = automation.run_task(import_file)
    print(f"文件已下载至: {downloaded_file_path}")
except Exception as e:
    print(f"任务执行失败: {e}")
