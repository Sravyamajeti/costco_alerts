import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import re
import time

options = uc.ChromeOptions()
options.headless = True
driver = uc.Chrome(options=options)

driver.get("https://sameday.costco.com/store/costco/s?k=1794528")
time.sleep(5)

soup = BeautifulSoup(driver.page_source, "html.parser")
card = soup.find(attrs={"aria-label": "product card"})
if card:
    a_tag = card.find("a", href=True)
    if a_tag:
        href = a_tag["href"]
        print("Found product link:", href)
        driver.get("https://sameday.costco.com" + href)
        time.sleep(4)
        prod_soup = BeautifulSoup(driver.page_source, "html.parser")
        # Try to find 'Ends'
        ends_span = prod_soup.find(text=re.compile(r'Ends\s+[a-zA-Z]{3}\s+\d+'))
        if ends_span:
            print("Found date string:", ends_span)
        else:
            print("Date string not found on product page")
    else:
        print("No a tag on card")
else:
    print("No product card found")

driver.quit()
