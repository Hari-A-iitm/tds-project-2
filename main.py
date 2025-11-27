import os
import time
import json
import re
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import requests
import pandas as pd

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MY_SECRET = os.getenv("MY_SECRET")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Initialize FastAPI
app = FastAPI()

# Request model
class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

# Root endpoint
@app.get("/")
def root():
    return {"status": "TDS Project 2 API is running", "message": "Send POST to /solve"}

# Main endpoint
@app.post("/solve")
async def solve_quiz(request: QuizRequest, background_tasks: BackgroundTasks):
    if request.secret != MY_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    background_tasks.add_task(solve_quiz_chain, request.email, request.secret, request.url)
    
    return JSONResponse(
        status_code=200,
        content={"status": "accepted", "message": "Quiz is being processed"}
    )

# Main loop
def solve_quiz_chain(email: str, secret: str, start_url: str):
    current_url = start_url
    quiz_count = 0
    max_quizzes = 10
    
    print(f"\n{'='*60}")
    print(f"Starting quiz chain for: {email}")
    print(f"{'='*60}\n")
    
    while current_url and quiz_count < max_quizzes:
        quiz_count += 1
        print(f"\n--- Quiz {quiz_count}: {current_url} ---")
        
        try:
            result = solve_single_quiz(email, secret, current_url)
            
            if result and isinstance(result, dict):
                if result.get('correct'):
                    print(f"✓ Answer was CORRECT!")
                else:
                    print(f"✗ Answer was WRONG: {result.get('reason', 'No reason')}")
                
                next_url = result.get('url')
                if next_url:
                    print(f"→ Next quiz: {next_url}")
                    current_url = next_url
                else:
                    print(f"✓ Quiz chain complete!")
                    break
            else:
                print(f"✗ Invalid response")
                break
                
        except Exception as e:
            print(f"✗ ERROR in quiz {quiz_count}: {str(e)}")
            break
    
    print(f"\n{'='*60}")
    print(f"Completed {quiz_count} quiz(s)")
    print(f"{'='*60}\n")

# Solve single quiz
def solve_single_quiz(email: str, secret: str, quiz_url: str):
    print("1. Fetching quiz page...")
    page_text, page_html = fetch_page_with_playwright(quiz_url)
    print(f"   ✓ Extracted {len(page_text)} chars text, {len(page_html)} chars HTML")
    
    time.sleep(3)
    
    print("2. Analyzing with Gemini...")
    analysis = analyze_quiz_page(page_text)
    print(f"   ✓ Analysis complete")
    print(f"   Submit URL: {analysis.get('submit_url')}")
    question = analysis.get('question', 'N/A')
    print(f"   Question: {question[:100] if question else 'N/A'}...")

    
    time.sleep(3)
    
    print("3. Solving question...")
    answer = solve_question(analysis.get('question', ''), page_text, page_html, quiz_url)
    print(f"   ✓ Answer: {answer}")
    
    print("4. Submitting answer...")
    result = submit_answer(
        submit_url=analysis.get('submit_url'),
        email=email,
        secret=secret,
        quiz_url=quiz_url,
        answer=answer
    )
    print(f"   ✓ Submitted")
    
    return result

# Fetch page
def fetch_page_with_playwright(url: str, retries=3):
    for attempt in range(retries):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(2)
                
                visible_text = page.inner_text('body')
                html_content = page.content()
                browser.close()
                
                return (visible_text, html_content)
        except Exception as e:
            print(f"   ✗ Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                raise

# Analyze page
def analyze_quiz_page(page_text: str) -> dict:
    """Extract submit URL and question - with fallbacks"""
    
    # First, try to extract submit URL directly with regex
    submit_url_match = re.search(r'POST\s+(?:to\s+)?(?:JSON\s+to\s+)?([https://[^\s<>"]+/submit[^\s<>"]*)', page_text, re.IGNORECASE)
    if not submit_url_match:
        submit_url_match = re.search(r'(https://[^\s<>"]+/submit)', page_text, re.IGNORECASE)
    
    if submit_url_match:
        submit_url = submit_url_match.group(1)
        print(f"   → Extracted submit URL directly: {submit_url}")
        return {
            "submit_url": submit_url,
            "question": page_text[:500]
        }
    
    # Fallback: Try Gemini
    try:
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        prompt = f"""
Extract the submit URL from this page.

Page:
---
{page_text}
---

Return ONLY the URL, nothing else.
"""
        
        response = model.generate_content(prompt)
        submit_url_text = response.text.strip()
        
        # Extract URL from response
        url_match = re.search(r'https://[^\s<>"]+', submit_url_text)
        if url_match:
            return {
                "submit_url": url_match.group(0),
                "question": page_text[:500]
            }
    except Exception as e:
        print(f"   ✗ Gemini failed: {e}")
    
    # Final fallback: Look for ANY submit URL
    urls = re.findall(r'https://[^\s<>"]+', page_text)
    submit_url = next((u for u in urls if 'submit' in u.lower()), None)
    
    if not submit_url and urls:
        # Just use the first URL we find
        submit_url = urls[0]
    
    if not submit_url:
        # Hardcode as absolute last resort
        submit_url = "https://tds-llm-analysis.s-anand.net/submit"
    
    print(f"   → Using fallback submit URL: {submit_url}")
    
    return {
        "submit_url": submit_url,
        "question": page_text[:500]
    }

# MAIN SOLVER
def solve_question(question: str, page_text: str, page_html: str, base_url: str):
    model = genai.GenerativeModel('models/gemini-2.5-flash')
    
    # Tool 1: Web Scraping
    scrape_match = re.search(r'Scrape\s+([^\s]+)', question, re.IGNORECASE)
    if scrape_match:
        from urllib.parse import urljoin
        scrape_path = scrape_match.group(1)
        scrape_url = urljoin(base_url, scrape_path)
        
        print(f"   → Scraping: {scrape_url}")
        scraped_text, _ = fetch_page_with_playwright(scrape_url)
        print(f"   → Scraped content: [{scraped_text}]")
        
        # Extract secret code
        code_match = re.search(r'[Ss]ecret\s+code\s+is\s+(\d+)', scraped_text)
        if code_match:
            print(f"   → Found secret code: {code_match.group(1)}")
            return code_match.group(1)
        
        code_match = re.search(r'\b(\d{5,})\b', scraped_text)
        if code_match:
            return code_match.group(1)
        
        return scraped_text.strip()
    
    # Tool 2: CSV Analysis - IMPROVED
    combined_content = page_text + " " + page_html
    
    # Multiple patterns to find CSV URLs
    csv_patterns = [
        r'https?://[^\s<>"\'()]+\.csv',  # Standard URL
        r'href=["\']([^"\']+\.csv)["\']',  # In href attribute
        r'\(([^\)]+\.csv)\)',  # In markdown links like (url)
    ]
    
    csv_url = None
    for pattern in csv_patterns:
        csv_match = re.search(pattern, combined_content, re.IGNORECASE)
        if csv_match:
            csv_url = csv_match.group(1) if csv_match.lastindex else csv_match.group(0)
            # Clean up URL
            csv_url = csv_url.strip('"\'()<>')
            print(f"   → Found CSV URL with pattern: {csv_url}")
            break
    
    if csv_url:
        # Make absolute if relative
        if not csv_url.startswith('http'):
            from urllib.parse import urljoin
            csv_url = urljoin(base_url, csv_url)
        
        print(f"   → Loading CSV: {csv_url}")
        
        try:
            df = pd.read_csv(csv_url, header=None)
            print(f"   → Loaded CSV: {len(df)} rows, columns: {df.columns.tolist()}")
            print(f"   → Sample data:\n{df.head(3)}")
            
            # Extract cutoff
            cutoff_match = re.search(r'[Cc]utoff[:\s]+(\d+)', combined_content)
            if cutoff_match:
                cutoff = int(cutoff_match.group(1))
                print(f"   → Cutoff: {cutoff}")
                
                # Find first numeric column
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    numeric_col = numeric_cols[0]
                    print(f"   → Using column: {numeric_col}")
                    
                    # Filter and sum
                    filtered = df[df[numeric_col] > cutoff]
                    result = filtered[numeric_col].sum()
                    
                    print(f"   → Filtered {len(filtered)} rows where {numeric_col} > {cutoff}")
                    print(f"   → Sum: {result}")
                    
                    return int(result)
                else:
                    print(f"   ✗ No numeric columns found")
            else:
                print(f"   ✗ Cutoff not found in text")
            
        except Exception as e:
            print(f"   ✗ CSV processing failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"   ✗ No CSV URL found")
        print(f"   → HTML sample: {page_html[:500]}")
    
    # Fallback: Gemini
    print(f"   → Using Gemini fallback")
    prompt = f"""
Context:
{page_text[:2000]}

Question: {question}

Answer (just the value):
"""
    
    try:
        response = model.generate_content(prompt)
        answer_text = response.text.strip().replace('`', '').replace('"', '').replace("'", '')
        
        try:
            if '.' in answer_text:
                return float(answer_text)
            return int(answer_text)
        except:
            if answer_text.lower() in ['true', 'yes']:
                return True
            if answer_text.lower() in ['false', 'no']:
                return False
            return answer_text
    except Exception as e:
        print(f"   ✗ Gemini failed: {e}")
        return "error"

# Submit
def submit_answer(submit_url: str, email: str, secret: str, quiz_url: str, answer, retries=3):
    from urllib.parse import urljoin
    
    if not submit_url.startswith('http'):
        submit_url = urljoin(quiz_url, submit_url)
        print(f"   Converted to absolute: {submit_url}")
    
    payload = {
        "email": email,
        "secret": secret,
        "url": quiz_url,
        "answer": answer
    }
    
    print(f"   Submitting to: {submit_url}")
    print(f"   Payload: {payload}")
    
    for attempt in range(retries):
        try:
            response = requests.post(submit_url, json=payload, timeout=60)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"correct": False, "reason": f"HTTP {response.status_code}"}
        except Exception as e:
            print(f"   ✗ Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                return {"correct": False, "reason": str(e)}
