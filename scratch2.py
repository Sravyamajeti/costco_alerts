import time
from src.price_check import _make_browser

context, sb, driver = _make_browser()
try:
    driver.get("https://sameday.costco.com")
    time.sleep(5)
    
    inputs = driver.find_elements("css selector", "input")
    for i in inputs:
        print(f"INPUT attrs: placeholder={i.get_attribute('placeholder')} id={i.get_attribute('id')} name={i.get_attribute('name')} autocomplete={i.get_attribute('autocomplete')}")
        
    buttons = driver.find_elements("css selector", "button")
    for b in buttons:
        if b.text.strip():
            print(f"BUTTON: {b.text.strip()}")
            
finally:
    context.__exit__(None, None, None)
