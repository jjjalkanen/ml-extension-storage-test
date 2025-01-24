import argparse
import hashlib
import os
import random
import shutil
import sys
import tempfile
import time
import unittest
import zipfile

from bs4 import BeautifulSoup
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager

# Custom parameters for this script
import test_config


"""
    The following issue is encountered when running of some of the models:
    https://github.com/huggingface/transformers.js/issues/955
  �[0;93m2025-01-02 12:25:25.385938 [W:onnxruntime:, constant_folding.cc:268 ApplyImpl] Could not find a CPU kernel and hence can't constant fold Exp node '/Exp'�[m
    Hc :100
    <anonymous> line 26 > WebAssembly.instantiate:17014471
    <anonymous> line 26 > WebAssembly.instantiate:2266941
    <anonymous> line 26 > WebAssembly.instantiate:802831
    <anonymous> line 26 > WebAssembly.instantiate:16987174
    <anonymous> line 26 > WebAssembly.instantiate:593201
    <anonymous> line 26 > WebAssembly.instantiate:54812
    <anonymous> line 26 > WebAssembly.instantiate:20680488
    <anonymous> line 26 > WebAssembly.instantiate:88110
    <anonymous> line 26 > WebAssembly.instantiate:8919686
    <anonymous> line 26 > WebAssembly.instantiate:1210123
    <anonymous> line 26 > WebAssembly.instantiate:2921096
    <anonymous> line 26 > WebAssembly.instantiate:2459959
    <anonymous> line 26 > WebAssembly.instantiate:16697504
    <anonymous> line 26 > WebAssembly.instantiate:11495879
    Pd/b[c]< :79
    _OrtCreateSession :111
    createSession chrome://global/content/ml/ort.webgpu-dev.mjs:15480
    createSession2 chrome://global/content/ml/ort.webgpu-dev.mjs:16092
    loadModel chrome://global/content/ml/ort.webgpu-dev.mjs:16206
    createInferenceSessionHandler chrome://global/content/ml/ort.webgpu-dev.mjs:16321
    create chrome://global/content/ml/ort.webgpu-dev.mjs:1179
"""
DEFAULT_MODELS = [
    #    "image-classification",
    # "image-segmentation",
    # "zero-shot-image-classification",
    # "object-detection",
    "zero-shot-object-detection",
    # "depth-estimation",
    # "feature-extraction",
    # "image-feature-extraction",
    # "image-to-text",
    "text-generation",
    # "text-classification",
    # "text2text-generation",
]

unit_test_header = \
"""

Custom parameters may be combined with python unit test parameters:
"""


def zip_folder_flatten(folder_path):
    """
    Compresses the folder at folder_path into a .zip file at output_path,
    *flattening* the structure so all files end up in the root when unzipped.
    """

    # 1. Generate some pseudo-random data (not cryptographically secure).
    #    Using time.time() + random.random() as a simple source of randomness.
    random_data = f"{time.time()}-{random.random()}".encode('utf-8')

    # 2. Create an MD5 digest from the random data.
    hash_str = hashlib.md5(random_data).hexdigest()

    # 3. Construct the filename with .xpi extension.
    file_name = f"{hash_str}.xpi"

    # 4. Build the full path under the OS temporary directory.
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, file_name)

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            for file_name in files:
                absolute_path = os.path.join(root, file_name)

                # By default, os.walk() gives a path like "ext/c.txt" when
                # using os.path.relpath. Here, we only keep the base filename.
                arcname = os.path.basename(file_name)

                zf.write(absolute_path, arcname=arcname)

    return output_path


def get_internal_uuids(driver, extension_ids):
    # Go to the about:debugging page
    about_debugging_url = "about:debugging#/runtime/this-firefox"
    driver.get(about_debugging_url)

    # Give the page some time to render
    time.sleep(3)

    # Get the current page's HTML
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    # Select all <li> items that match the extension pattern
    extension_cards = soup.select(
        'li.card.debug-target-item.qa-debug-target-item')

    uuid_map = dict()
    titles_of_interest = ("Internal UUID", "Extension ID")
    for card in extension_cards:
        # Each extension card can have multiple fieldpairs
        fieldpairs = card.select("div.fieldpair")
        extension_id = None
        internal_uuid = None
        for fieldpair in fieldpairs:
            # Find the title
            dt_elem = fieldpair.find("dt", class_="fieldpair__title")
            if dt_elem:
                elem_title = dt_elem.get_text(strip=True)
                if elem_title in titles_of_interest:
                    # Find the corresponding description
                    dd_elem = fieldpair.find(
                        "dd", class_="fieldpair__description ellipsis-text")
                    if dd_elem:
                        elem_value = dd_elem.get_text(strip=True)
                        if elem_title == "Internal UUID":
                            internal_uuid = elem_value
                        else:
                            assert elem_title == "Extension ID"
                            extension_id = elem_value
                            if extension_id not in extension_ids:
                                break
                        if extension_id is not None and internal_uuid is not None:
                            uuid_map[extension_id] = internal_uuid

    assert set(extension_ids) == set(uuid_map.keys())

    return uuid_map


class attribute_contains:
    """
    Custom expected condition that checks whether an element's
    given attribute contains the specified text.
    """

    def __init__(self, locator, attribute_name, substring):
        self.locator = locator
        self.attribute_name = attribute_name
        self.substring = substring

    def __call__(self, driver):
        # Try to find the element
        element = driver.find_element(*self.locator)
        if element:
            value = element.get_attribute(self.attribute_name)
            if value and (self.substring in value):
                return element
        return False


def open_extension_options(driver, extension_id):
    """
    Navigates to about:addons, opens the 'Extensions' view, finds the card for the given extension_id,
    clicks on that card to open the detail view, then waits for 'detail' view, 
    clicks 'Permissions', toggles the <button id="input">, then waits.
    
    :param driver: Selenium WebDriver instance
    :param extension_id: The addon-id string from driver.install_addon(...) or known extension ID
    :return: None
    """

    # 1) Go to about:addons
    about_addons_url = "about:addons"
    driver.get(about_addons_url)

    # 2) Give the page time to load (or use an explicit wait on a specific element)
    time.sleep(2)

    # 3) Use BeautifulSoup to parse, find the "Extensions" category button
    soup = BeautifulSoup(driver.page_source, "html.parser")
    category_button_tag = soup.find("button",
                                    class_="category",
                                    attrs={
                                        "viewid": "addons://list/extension",
                                        "title": "Extensions"
                                    })
    if not category_button_tag:
        raise RuntimeError(
            "Could not locate the 'Extensions' category button in about:addons"
        )

    # 4) Use Selenium to locate that same button and click it.
    category_button = driver.find_element(
        By.XPATH,
        '//button[@class="category" and @viewid="addons://list/extension" and @title="Extensions"]'
    )
    category_button.click()

    # 5) Wait until the #main div contains <addon-card addon-id="{extension_id}">
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, f'#main addon-card[addon-id="{extension_id}"]')))

    # 6) Click the extension card itself, which should open the detail view
    card = driver.find_element(By.CSS_SELECTOR,
                               f'#main addon-card[addon-id="{extension_id}"]')

    # 7) Inside that card, find a child div of class "card addon" and click it
    child_div = card.find_element(By.CSS_SELECTOR, 'div.card.addon')
    child_div.click()

    # 8) Wait for #main to have current-view="detail"
    WebDriverWait(driver, 10).until(
        attribute_contains((By.CSS_SELECTOR, '#main'), 'current-view',
                           'detail'))

    # 9) Now locate the same addon card in the detail view:
    detail_card = driver.find_element(
        By.CSS_SELECTOR, f'#main addon-card[addon-id="{extension_id}"]')
    #    and click the button with id="details-deck-button-permissions"
    perm_btn = detail_card.find_element(By.CSS_SELECTOR,
                                        '#details-deck-button-permissions')
    perm_btn.click()

    # 10) Wait for the div with class "addon-permissions-optional" to become visible
    optional_perms_div = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, 'div.addon-permissions-optional')))

    # Locate the <moz-toggle id="permission-0"> inside that div
    toggle_elem = optional_perms_div.find_element(By.CSS_SELECTOR,
                                                  'moz-toggle#permission-0')

    # 11) Click the toggle element
    toggle_elem.click()

    # 12) Wait a few seconds for demonstration/inspection
    time.sleep(3)


def check_preferences(driver):
    # Find the profile directory
    about_support_url = "about:support"
    driver.get(about_support_url)
    profile_dir_span = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.ID, 'profile-dir-box')))
    # Wait until the textContent is not empty
    WebDriverWait(driver, 10).until(
        lambda d: profile_dir_span.get_attribute('innerText').strip() != "")
    profile_dir = profile_dir_span.get_attribute('innerText')

    profile_path = Path(profile_dir)
    for item in profile_path.iterdir():
        print(item)

    # Or user.js
    with open(profile_path / "prefs.js") as prefs_file:
        for line in prefs_file:
            print(line)


class TestFirefoxExtension(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        print("Profile directory:", self.temp_dir)

        zip_path = Path.cwd() / "assets" / "profile.zip"
        destination_path = Path(self.temp_dir)

        def safe_extract(zip_ref, destination):
            for member in zip_ref.namelist():
                member_path = os.path.join(destination, member)
                abs_destination = os.path.abspath(destination)
                abs_member_path = os.path.abspath(member_path)
                if not abs_member_path.startswith(abs_destination):
                    raise Exception("Attempted Path Traversal in ZIP File")
            zip_ref.extractall(destination)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            safe_extract(zip_ref, destination_path)

        self.options = Options()

        # If binary location is not specified, then use Selenium defaults
        if test_config.binary_location is not None:
            firefox_exe = Path(test_config.binary_location)
            if not firefox_exe.is_file():
                raise Exception("File " + str(firefox_exe) + " does not exist")
            self.options.binary_location = test_config.binary_location
        self.options.set_preference("browser.ml.enable", True)
        self.options.set_preference("extensions.ml.enabled", True)

        self.options.add_argument("--profile")
        self.options.add_argument(self.temp_dir)

        if test_config.headless:
            self.options.add_argument("--headless")

        self.driver = webdriver.Firefox(options=self.options,
                                        service=FirefoxService(
                                            GeckoDriverManager().install()))

        # Install the extension (assuming you've packaged it as .xpi).
        # If it's just a directory, you may need to zip it or specify the path to the manifest.
        # This returns an extension ID we can use in the moz-extension:// URL.
        extension_path = zip_folder_flatten('ext/')

        self.extension_ids = []
        for _ in DEFAULT_MODELS:
            extension_id = self.driver.install_addon(extension_path,
                                                     temporary=True)
            self.extension_ids.append(extension_id)

        self.internal_uuids = []

        self.storage_url = "https://www.example.org"
        self.driver.get(self.storage_url)

        # Store the handle of the storage tab
        self.storage_tab = self.driver.current_window_handle
        self.results_tab = None

    def tearDown(self):
        """
        Close the browser after each test.
        """
        self.driver.quit()
        shutil.rmtree(self.temp_dir)

    def test_async_button(self):
        """
        Tests that clicking the extension button leads to either success or error,
        and verifies the displayed content accordingly.
        """
        # check_preferences(self.driver)

        self.internal_uuids = get_internal_uuids(self.driver,
                                                 self.extension_ids)

        for extension_id in self.extension_ids:
            open_extension_options(self.driver, extension_id)

        new_storage_tab_handle = self.driver.execute_script(
            f"return window.open('{self.storage_url}', '_blank');")
        self.results_tab = [x for x in new_storage_tab_handle.values()][0]

        # popup_handles = []
        print("Extension ids:", self.extension_ids)
        for extension_id, task_name in zip(self.extension_ids, DEFAULT_MODELS):
            self.driver.switch_to.window(self.storage_tab)
            self.driver.implicitly_wait(10)  # seconds

            new_tab_script = f"return window.open(location.href);"
            new_tab_handle = self.driver.execute_script(new_tab_script)
            self.driver.implicitly_wait(10)  # seconds

            print([x for x in new_tab_handle.values()][0])
            tab_handle = [x for x in new_tab_handle.values()][0]
            self.driver.switch_to.window(tab_handle)

            # open_extension_options(self.driver, extension_id)
            internal_uuid = self.internal_uuids[extension_id]

            print(f"Starting {extension_id} for task {task_name}")

            popup_url = f"moz-extension://{internal_uuid}/popup.html?taskName={task_name}"
            self.driver.get(popup_url)
            self.driver.implicitly_wait(10)  # seconds

            start_button = self.driver.find_element(By.ID, "startButton")
            start_button.click()
            self.driver.implicitly_wait(10)  # seconds

            # popup_handle = self.driver.current_window_handle
            # popup_handles.append(popup_handle)

            # status_div = self.driver.find_element(By.ID, "status")
            # status_divs.append(status_div)

        self.driver.switch_to.window(self.results_tab)
        self.driver.implicitly_wait(10)  # seconds

        # results_ = tuple(self.driver.execute_script(
        #     f"return localStorage.getItem('{extension_id}') !== null;")
        #     for extension_id in self.extension_ids)
        # print(results_)
        # print(all(x for x in results_))

        # Wait for up to timeout seconds for the #status element to be either "success" or "error".
        WebDriverWait(self.driver, test_config.timeout).until(lambda d: all(
            self.driver.execute_script(
                f"return localStorage.getItem('{extension_id}') !== null;")
            for extension_id in self.extension_ids))

        results = tuple(
            self.driver.execute_script(
                f"return localStorage.getItem('{extension_id}');")
            for extension_id in self.extension_ids)

        # status_text = status_div.text
        # results_html = self.driver.find_element(By.ID, "results").get_attribute("innerHTML")

        # # Now check logic:
        # soup = BeautifulSoup(results_html, "html.parser")
        # # We expect a table
        # table_cells = soup.find_all("td")
        # results = [cell.get_text() for cell in table_cells]
        for result in results:
            print(result)
        # self.assertEqual(status_text, "success")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Test firefox ml extensions.',
        # Prevent argparse from parsing unknown args to avoid conflicts with unittest
        add_help=False)

    parser.add_argument('-h', '--help', action='store_true')

    parser.add_argument('--binary_location',
                        type=str,
                        default=None,
                        help='Specify /path/to/firefox.exe')
    parser.add_argument('--headless',
                        action='store_true',
                        default=False,
                        help='Run in headless mode')
    parser.add_argument('--timeout',
                        type=int,
                        default=300,
                        help='Time until the test is stopped by force')

    args, remaining_args = parser.parse_known_args()
    if args.help:
        print("Custom parameters:")
        parser.print_help()
        remaining_args.append("--help")
        print(unit_test_header)
    else:
        test_config.binary_location = args.binary_location
        test_config.headless = args.headless
        test_config.timeout = args.timeout

    unittest.main(argv=[sys.argv[0]] + remaining_args)
