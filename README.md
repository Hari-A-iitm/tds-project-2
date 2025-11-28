---
title: TDS Project 2 Quiz Solver
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# TDS Project 2: LLM Analysis Quiz Solver

Automated quiz-solving system using LLMs, web scraping, and data analysis.

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