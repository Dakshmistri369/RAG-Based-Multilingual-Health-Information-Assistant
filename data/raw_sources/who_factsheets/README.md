# WHO Fact Sheets — Source PDFs

## What to add here

Place WHO (World Health Organization) disease fact sheet PDFs in this folder.

### Recommended fact sheets to download:

| Disease/Topic | URL |
|---|---|
| Dengue and severe dengue | https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue |
| Malaria | https://www.who.int/news-room/fact-sheets/detail/malaria |
| Tuberculosis (TB) | https://www.who.int/news-room/fact-sheets/detail/tuberculosis |
| Diabetes | https://www.who.int/news-room/fact-sheets/detail/diabetes |
| Hypertension | https://www.who.int/news-room/fact-sheets/detail/hypertension |
| COVID-19 | https://www.who.int/news-room/fact-sheets/detail/coronavirus-disease-(covid-19) |
| Cholera | https://www.who.int/news-room/fact-sheets/detail/cholera |
| Pneumonia | https://www.who.int/news-room/fact-sheets/detail/pneumonia |
| Diarrhoeal diseases | https://www.who.int/news-room/fact-sheets/detail/diarrhoeal-disease |
| Anaemia | https://www.who.int/news-room/fact-sheets/detail/anaemia |
| Mental health (overview) | https://www.who.int/news-room/fact-sheets/detail/mental-disorders |
| Typhoid | https://www.who.int/news-room/fact-sheets/detail/typhoid |
| Japanese encephalitis | https://www.who.int/news-room/fact-sheets/detail/japanese-encephalitis |

### How to download PDFs

Most WHO fact sheets can be printed to PDF from your browser, or downloaded
from the WHO website. When saving, use descriptive filenames like:
- `who_dengue_factsheet.pdf`
- `who_malaria_factsheet.pdf`
- `who_tuberculosis_factsheet.pdf`

### Important notes

- These PDFs are publicly available and free to use for educational purposes.
- Content is typically in English — the RAG system uses multilingual embeddings
  (BAAI/bge-m3) that allow Hindi/Tamil/Bengali queries to match English documents.
- After adding PDFs, run `python backend/ingest.py` to process them.
