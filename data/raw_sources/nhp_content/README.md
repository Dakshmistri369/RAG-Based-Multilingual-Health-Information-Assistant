# NHP India Content — Source PDFs

## What to add here

Place content from the National Health Portal India (NHP) in this folder.
NHP content is ideal because it is already written for Indian citizens, in
simple language, and is available in Hindi and other regional languages.

### Recommended NHP content (save as PDFs):

| Topic | URL |
|---|---|
| Health A-Z disease information | https://www.nhp.gov.in/healthlyliving/health-a-z |
| Common diseases guide | https://www.nhp.gov.in/disease |
| First aid guide | https://www.nhp.gov.in/healthlyliving/first-aid |
| Women's health | https://www.nhp.gov.in/women-health |
| Child health | https://www.nhp.gov.in/child-health |
| Mental health | https://www.nhp.gov.in/mental-health |
| Yoga and wellness | https://www.nhp.gov.in/yoga |

### How to get NHP content as PDFs

**Option 1: Print to PDF from browser**
  - Visit the NHP page
  - Press Ctrl+P (or Cmd+P on Mac)
  - Select "Save as PDF"

**Option 2: Use a web scraper (with NHP's permission)**
  - NHP content is publicly available under Government Open Data License
  - Respect robots.txt and rate-limit your scraper

### Hindi content note

NHP has content in Hindi at https://www.nhp.gov.in/hi
These Hindi PDFs are especially valuable because the BAAI/bge-m3 embedding
model can match both Hindi queries and Hindi documents natively.

After adding PDFs, run `python backend/ingest.py` to process them.
