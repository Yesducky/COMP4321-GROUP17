# COMP4321 Search Engine Project

## Setup Instructions

1. **Create Virtual Environment**
```bash
python -m venv venv
```

2. **Activate & Install Dependencies**
```bash
source venv/bin/activate
chmod +x setup.sh
./setup.sh
```

3. **Initialize Database**
```bash
flask init-db
```

4. **Start Development Server**
```bash
python app.py
```

## Accessing the Web Interface
- The search engine interface will be available at: http://localhost:5000
- Click "Clear All" to clear all indexed pages
- Click "Start Crawl" to begin indexing pages

## Important Notes
- Ensure `stopwords.txt` exists in project root
- Server may take several minutes to index pages after starting crawl
- Use Chrome/Firefox for best compatibility
- Monitor terminal output for crawl progress