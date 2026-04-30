from bs4 import BeautifulSoup
import re

with open("dump_2619.html", "r") as f:
    html = f.read()
    
soup = BeautifulSoup(html, "html.parser")
card = soup.find(attrs={"aria-label": "product card"})
search_context = card if card else soup

# Try finding h2
h2 = search_context.find('h2')
print("h2 text:", h2.get_text(strip=True) if h2 else "None")

# Try finding image alt
img = search_context.find('img', alt=True)
print("img alt:", img['alt'] if img else "None")

# Try all spans inside card
if card:
    for span in card.find_all('span'):
        text = span.get_text(strip=True)
        if len(text) > 10 and not any(char.isdigit() for char in text):
            print("Possible title span:", text)
