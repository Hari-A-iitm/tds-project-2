from playwright.sync_api import sync_playwright
import time
import re

url = "https://tds-llm-analysis.s-anand.net/demo-audio?email=test@example.com&id=3491"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    time.sleep(3)
    
    # Get both visible text and HTML
    visible_text = page.inner_text('body')
    html_content = page.content()
    
    print("="*60)
    print("VISIBLE TEXT:")
    print(visible_text)
    print("\n" + "="*60)
    print("HTML SOURCE:")
    print(html_content)
    print("\n" + "="*60)
    
    # Look for links
    links = page.query_selector_all('a')
    print("LINKS FOUND:")
    for link in links:
        href = link.get_attribute('href')
        text = link.inner_text()
        print(f"  - {text}: {href}")
    
    # Look for any URLs in HTML
    print("\n" + "="*60)
    print("ALL URLS IN HTML:")
    urls = re.findall(r'https?://[^\s<>"]+', html_content)
    for url in urls:
        print(f"  - {url}")
    
    input("\nPress Enter to close...")
    browser.close()
