import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
from urllib.parse import urljoin, urlparse
import re
import time
from collections import Counter
import nltk
from textblob import TextBlob
import base64

# Download required NLTK data (silent)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# Page configuration
st.set_page_config(
    page_title="AI Website Analysis Bot + GSC",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'analysis_data' not in st.session_state:
    st.session_state.analysis_data = None
if 'crawled_urls' not in st.session_state:
    st.session_state.crawled_urls = []
if 'gsc_data' not in st.session_state:
    st.session_state.gsc_data = None

class WebsiteAnalyzer:
    def __init__(self, base_url, max_pages=50):
        self.base_url = base_url.rstrip('/')
        self.max_pages = max_pages
        self.domain = urlparse(base_url).netloc
        self.site_data = []

    def is_valid_url(self, url):
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ("http", "https") and
                (parsed.netloc == self.domain or parsed.netloc.endswith('.' + self.domain) or parsed.netloc == '')
            )
        except:
            return False

    def extract_page_content(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            title = soup.title.string.strip() if soup.title else "No Title"
            meta_desc = soup.find("meta", attrs={"name": "description"})
            description = meta_desc.get("content", "").strip() if meta_desc else ""
            headings = [h.get_text().strip() for h in soup.find_all(re.compile('^h[1-6]$'))]
            text_content = ' '.join(soup.get_text().split())[:1000]
            links = []
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"]).split('#')[0]
                if self.is_valid_url(href):
                    links.append(href)
            links = list(dict.fromkeys(links))
            return {
                "url": url,
                "title": title,
                "description": description,
                "headings": headings,
                "text_content": text_content,
                "word_count": len(text_content.split()),
                "links": links,
                "status": "success",
            }
        except Exception as e:
            return {
                "url": url,
                "title": "Error",
                "description": "",
                "headings": [],
                "text_content": "",
                "word_count": 0,
                "links": [],
                "status": f"error: {e}",
            }

    _CATEGORY_KEYWORDS = {
        "product": ["product", "buy", "shop", "price", "cart"],
        "blog": ["blog", "post", "article", "news"],
        "about": ["about", "company", "team", "history"],
        "contact": ["contact", "phone", "email", "address"],
        "service": ["service", "solution", "support"],
        "help": ["help", "faq", "guide", "tutorial"],
        "legal": ["privacy", "terms", "policy", "legal"],
    }

    def classify_content(self, page):
        text = " ".join([
            page["title"], page["description"],
            " ".join(page["headings"]), page["text_content"]
        ]).lower()
        scores = {cat: sum(k in text for k in kws) for cat, kws in self._CATEGORY_KEYWORDS.items()}
        return max(scores, key=scores.get) if max(scores.values()) > 0 else "other"

    def hierarchy_info(self, url):
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        return {
            "depth": len(parts),
            "file_ext": parts[-1].split(".")[-1] if parts and "." in parts[-1] else "html"
        }

    def crawl(self, callback=None):
        todo, done = [self.base_url], set()
        while todo and len(done) < self.max_pages:
            current = todo.pop(0)
            if current in done: continue
            done.add(current)
            if callback: callback(len(done), min(self.max_pages, len(done)+len(todo)))
            page = self.extract_page_content(current)
            if page["status"] == "success":
                page["category"] = self.classify_content(page)
                page["hierarchy"] = self.hierarchy_info(current)
                blob = TextBlob(page["text_content"])
                words = [w.lower() for w in blob.words if w.isalpha() and len(w)>3]
                page["keywords"] = Counter(words).most_common(5)
                self.site_data.append(page)
                for link in page["links"]:
                    if link not in done and link not in todo and len(done)+len(todo)<self.max_pages:
                        todo.append(link)
            time.sleep(0.15)
        return self.site_data

def build_taxonomy(data):
    return {
        "categories": Counter(d["category"] for d in data),
        "depth": Counter(d["hierarchy"]["depth"] for d in data),
        "file_types": Counter(d["hierarchy"]["file_ext"] for d in data)
    }

def csv_download_link(df, label, filename):
    csv = df.to_csv(index=False)
    b64 = base
