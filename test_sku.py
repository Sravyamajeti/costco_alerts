from seleniumbase import Driver
from bs4 import BeautifulSoup
import time
import re

driver = Driver(uc=True, headless=True)

try:
    print("Navigating to zip...")
    driver.get("https://sameday.costco.com")
    time.sleep(3)
    try:
        zip_input = driver.find_element("css selector", 'input[autocomplete="postal-code"]')
        if zip_input:
            zip_input.send_keys('94536')
            from selenium.webdriver.common.keys import Keys
            zip_input.send_keys(Keys.RETURN)
            time.sleep(4)
    except Exception as e:
        print("Zip bypass err:")

    for sku in ["2619", "4296", "512515"]:
        print(f"\n--- Scraping SKU: {sku} ---")
        driver.get(f"https://sameday.costco.com/store/costco/s?k={sku}")
        time.sleep(4)
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        links = soup.select('a[href*="/products/"]')
        if not links:
            print("No product links found on search page.")
            continue
            
        product_url = "https://sameday.costco.com" + links[0]['href']
        print(f"Found product link: {product_url}")
        
        driver.get(product_url)
        time.sleep(3)
        prod_html = driver.page_source
        if sku in prod_html:
            print(f"SKU {sku} is present in the product page!")
            prod_soup = BeautifulSoup(prod_html, "html.parser")
            elements = prod_soup.find_all(string=re.compile(sku))
            for el in elements:
                # print snippet of text
                print(f"Context: {el.parent.get_text(separator=' ').strip()}")
        else:
            print(f"SKU {sku} is NOT found in the product page.")
finally:
    driver.quit()
