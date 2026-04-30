import time
from src.price_check import _make_browser

context, sb, driver = _make_browser()
driver.get("https://sameday.costco.com")
time.sleep(5)

btns = driver.find_elements("css selector", "button")
print([b.text for b in btns if b.text.strip()])

context.__exit__(None, None, None)
