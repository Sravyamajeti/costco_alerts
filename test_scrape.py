import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

options = uc.ChromeOptions()
options.headless = True
driver = uc.Chrome(options=options)

print("Bypassing zip...")
driver.get("https://sameday.costco.com")
time.sleep(3)
try:
    zip_input = driver.find_element(By.CSS_SELECTOR, 'input[autocomplete="postal-code"]')
    if zip_input:
        zip_input.send_keys('94536')
        zip_input.send_keys(Keys.RETURN)
        time.sleep(3)
except Exception as e:
    print("Zip bypass err:", e)

driver.get("https://sameday.costco.com/store/costco/s?k=2619")
time.sleep(4)
with open("dump_2619.html", "w") as f:
    f.write(driver.page_source)

driver.quit()
print("Saved dump_2619.html")
