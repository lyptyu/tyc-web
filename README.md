# WebFrame Automation

This module implements the Playwright automation for file import and download.

## Installation

Ensure `playwright` is installed:
```bash
pip install playwright
playwright install chromium
```

## Usage

### Configuration

You need to add the following fields to your `config.json` (or pass a dictionary with these keys):

- `login_cookies`: Can be a list of cookie objects OR a raw cookie string (e.g., `"key1=val1; key2=val2"`).
- `cookie_domain`: (Required if `login_cookies` is a string) The domain to apply the cookies to (e.g., "example.com"). If omitted, the script tries to infer it from `import_page_url`.
- `import_page_url`: URL of the page where import happens.
- `import_folder`: Local folder containing files to import (the script picks the latest file).
- `import_input_selector`: CSS selector for the file input element (e.g., `input[type='file']`).
- `redirect_route`: Part of the URL to wait for after import (to verify success).
- `export_data_button_selector`: CSS selector for the button to click after successful import.
- `download_page_url`: URL of the page to download files.
- `latest_data_selector`: CSS selector to select the latest data row (optional, if selection is needed).
- `download_button_selector`: CSS selector for the download button.
- `export_download_path`: Local folder where downloaded files will be saved.
- `headless`: Boolean (true/false) to run browser in headless mode.

### Example Code

```python
from webframe.automation import WebAutomation

# Initialize with config file path
automation = WebAutomation("../dist/config.json")

# Or initialize with dictionary
# automation = WebAutomation(config_dict)

try:
    # Run the task
    downloaded_file = automation.run_task()
    print(f"File downloaded to: {downloaded_file}")
except Exception as e:
    print(f"Error: {e}")
```
