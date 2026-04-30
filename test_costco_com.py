from seleniumbase import Driver
import time
from bs4 import BeautifulSoup

driver = Driver(uc=True, headless=True)
try:
    driver.get("https://www.costco.com/CatalogSearch?keyword=2619")
    time.sleep(5)
    print("Title:", driver.title)
    html = driver.page_source
    if "2619" in html:
        print("SKU 2619 is present on costco.com!")
    else:
        print("SKU 2619 not found.")
finally:
    driver.quit()
