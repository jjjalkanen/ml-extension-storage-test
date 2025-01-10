import hashlib
import os
import random
import shutil
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
from webdriver_manager.firefox  import GeckoDriverManager


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


def get_internal_uuids(driver):
    # Go to the about:debugging page
    driver.get("about:debugging#/runtime/this-firefox")
    
    # Give the page some time to render
    time.sleep(3)
    
    # Get the current page's HTML
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    
    # Select all <li> items that match the extension pattern
    extension_cards = soup.select(
        'li.card.debug-target-item.qa-debug-target-item[data-qa-target-type="extension"]'
    )

    for card in extension_cards:
        # Each extension card can have multiple fieldpairs
        fieldpairs = card.select("div.fieldpair")

        for fieldpair in fieldpairs:
            # Find the title
            dt_elem = fieldpair.find("dt", class_="fieldpair__title")
            if dt_elem and dt_elem.get_text(strip=True) == "Internal UUID":
                # Find the corresponding description
                dd_elem = fieldpair.find("dd", class_="fieldpair__description ellipsis-text")
                if dd_elem:
                    uuid_text = dd_elem.get_text(strip=True)
                    return uuid_text

    return None


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
    driver.get("about:addons")

    # 2) Give the page time to load (or use an explicit wait on a specific element)
    time.sleep(2)

    # 3) Use BeautifulSoup to parse, find the "Extensions" category button
    soup = BeautifulSoup(driver.page_source, "html.parser")
    category_button_tag = soup.find(
        "button",
        class_="category",
        attrs={"viewid": "addons://list/extension", "title": "Extensions"}
    )
    if not category_button_tag:
        raise RuntimeError("Could not locate the 'Extensions' category button in about:addons")

    # 4) Use Selenium to locate that same button and click it.
    category_button = driver.find_element(
        By.XPATH,
        '//button[@class="category" and @viewid="addons://list/extension" and @title="Extensions"]'
    )
    category_button.click()

    # 5) Wait until the #main div contains <addon-card addon-id="{extension_id}">
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f'#main addon-card[addon-id="{extension_id}"]'))
    )

    # 6) Click the extension card itself, which should open the detail view
    card = driver.find_element(By.CSS_SELECTOR, f'#main addon-card[addon-id="{extension_id}"]')

    # 7) Inside that card, find a child div of class "card addon" and click it
    child_div = card.find_element(By.CSS_SELECTOR, 'div.card.addon')
    child_div.click()

    # 8) Wait for #main to have current-view="detail"
    WebDriverWait(driver, 10).until(
        attribute_contains((By.CSS_SELECTOR, '#main'), 'current-view', 'detail')
    )

    # 9) Now locate the same addon card in the detail view:
    detail_card = driver.find_element(By.CSS_SELECTOR, f'#main addon-card[addon-id="{extension_id}"]')
    #    and click the button with id="details-deck-button-permissions"
    perm_btn = detail_card.find_element(By.CSS_SELECTOR, '#details-deck-button-permissions')
    perm_btn.click()

    # 10) Wait for the div with class "addon-permissions-optional" to become visible
    optional_perms_div = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.addon-permissions-optional'))
    )

    # Locate the <moz-toggle id="permission-0"> inside that div
    toggle_elem = optional_perms_div.find_element(By.CSS_SELECTOR, 'moz-toggle#permission-0')

    # 11) Click the toggle element
    toggle_elem.click()

    # 12) Wait a few seconds for demonstration/inspection
    time.sleep(3)


def check_preferences(driver):
    # Find the profile directory
    driver.get("about:support")
    profile_dir_span = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.ID, 'profile-dir-box'))
    )
        # Wait until the textContent is not empty
    WebDriverWait(driver, 10).until(
        lambda d: profile_dir_span.get_attribute('innerText').strip() != ""
    )
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
        print("Temp dir ", self.temp_dir)

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
        self.options.binary_location = "D:/mozilla-unified/obj-ff-dbg/dist/bin/firefox.exe"
        self.options.set_preference("browser.ml.enable", True)
        self.options.set_preference("extensions.ml.enabled", True)

        self.options.add_argument("--profile")
        self.options.add_argument(self.temp_dir)

        # self.options.add_argument("--headless")  # Eventually

        self.driver = webdriver.Firefox(options=self.options,
            service=FirefoxService(GeckoDriverManager().install()))

        # Install the extension (assuming you've packaged it as .xpi).
        # If it's just a directory, you may need to zip it or specify the path to the manifest.
        # This returns an extension ID we can use in the moz-extension:// URL.
        extension_path = zip_folder_flatten('ext/')
        self.extension_id = self.driver.install_addon(extension_path, temporary=True)

        self.internal_uuid = None

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

        self.internal_uuid = get_internal_uuids(self.driver)
        self.assertIsNotNone(self.internal_uuid, "Couldn't find the internal UUID")
        
        open_extension_options(self.driver, self.extension_id)

        popup_url = f"moz-extension://{self.internal_uuid}/popup.html"
        self.driver.get(popup_url)

        start_button = self.driver.find_element(By.ID, "startButton")
        start_button.click()

        # Wait for up to 10 seconds for the #status element to be either "success" or "error".
        WebDriverWait(self.driver, 120).until(
            lambda d: d.find_element(By.ID, "status").text in ["success", "error"]
        )

        status_text = self.driver.find_element(By.ID, "status").text
        results_html = self.driver.find_element(By.ID, "results").get_attribute("innerHTML")

        # Now check logic:
        if status_text == "success":
            # Optionally parse with BeautifulSoup, or just read with Selenium
            soup = BeautifulSoup(results_html, "html.parser")
            # We expect a <table><tr><td>1</td><td>2</td><td>3</td></tr></table>
            table_cells = soup.find_all("td")
            results = [cell.get_text() for cell in table_cells]
            for result in results:
                print(result)
        elif status_text == "error":
            soup = BeautifulSoup(results_html, "html.parser")
            # We expect a <div> with "Simulated error occurred" text
            divs = soup.find_all("div")
            # Just check that there's a "Simulated error occurred" in one of them
            errors_found = any("Simulated error occurred" in d.get_text() for d in divs)
            self.assertTrue(errors_found, "Expected 'Simulated error occurred' in the results")

if __name__ == '__main__':
    unittest.main()
