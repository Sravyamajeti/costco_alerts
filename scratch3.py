import time
from selenium.webdriver.common.by import By
from src.price_check import _make_browser

context, sb, driver = _make_browser()
try:
    driver.get("https://sameday.costco.com")
    time.sleep(5)
    
    zip_input = driver.find_element(By.CSS_SELECTOR, 'input[autocomplete="postal-code"]')
    if zip_input:
        zip_input.send_keys("94536")
        time.sleep(1)
        
        # Click "Start Shopping" instead of Keys.RETURN
        btn = driver.find_element(By.XPATH, "//button[contains(., 'Start Shopping')]")
        btn.click()
        time.sleep(5)
        
        # Go to a product page
        print("Zip code submitted, going to product page...")
        driver.get("https://sameday.costco.com/store/costco/s?k=2619")
        time.sleep(5)
        
        print("Page loaded, dumping cards...")
        from bs4 import BeautifulSoup
        import re
        soup = BeautifulSoup(driver.page_source, "html.parser")
        headings = soup.find_all(attrs={"role": "heading"})
        for h in headings:
             print("FOUND HEADING:", h.text)
        
finally:
    context.__exit__(None, None, None)
