# TDS Project 2: LLM Analysis Quiz Solver

Automated quiz-solving system using LLMs, web scraping, and data analysis.

## Features

-  Automated quiz solving using Gemini 2.5 Flash
-  Web scraping with Playwright
-  CSV data analysis with Pandas
-  Handles quiz chains automatically
-  FastAPI backend with background tasks

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Install Playwright browsers: `playwright install`
4. Create `.env` file with your API keys:
   GEMINI_API_KEY=your_key_here
   MY_SECRET=your_secret_here

5. Run: `uvicorn main:app --reload`

## API Endpoint

POST to `/solve` with:
{
"email": "your@email.com",
"secret": "your_secret",
"url": "https://quiz-url.com"
}

## Tech Stack

- FastAPI
- Google Gemini AI
- Playwright
- Pandas
- Python 3.11+

## License

MIT License