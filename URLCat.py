import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from urllib.parse import urljoin, urlparse
import re
import time
from collections import defaultdict, Counter
import nltk
from textblob import TextBlob
import json
import base64

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# Page configuration
st.set_page_config(
    page_title="AI Website Analysis Bot",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'analysis_data' not in st.session_state:
    st.session_state.analysis_data = None
if 'crawled_urls' not in st.session_state:
    st.session_state.crawled_urls = []

class WebsiteAnalyzer:
    def __init__(self, base_url, max_pages=50):
        self.base_url = base_url
        self.max_pages = max_pages
        self.crawled_urls = set()
        self.site_data = []
        self.domain = urlparse(base_url).netloc
        
    def is_valid_url(self, url):
        """Check if URL is valid and belongs to the same domain"""
        try:
            parsed = urlparse(url)
            return (parsed.netloc == self.domain or 
                   parsed.netloc == '' or 
                   parsed.netloc.endswith('.' + self.domain))
        except:
            return False
    
    def extract_page_content(self, url):
        """Extract content from a single page"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract basic information
            title = soup.find('title')
            title_text = title.text.strip() if title else 'No Title'
            
            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ''
            
            # Extract headings
            headings = []
            for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if h.text.strip():
                    headings.append(h.text.strip())
            
            # Extract text content
            text_content = soup.get_text()
            text_content = ' '.join(text_content.split())
            
            # Extract links
            links = []
            for link in soup.find_all('a', href=True):
                href = urljoin(url, link['href'])
                if self.is_valid_url(href) and href not in links:
                    links.append(href)
            
            return {
                'url': url,
                'title': title_text,
                'description': description,
                'headings': headings,
                'text_content': text_content[:1000],  # Limit text content
                'word_count': len(text_content.split()),
                'links': links,
                'status': 'success'
            }
            
        except Exception as e:
            return {
                'url': url,
                'title': 'Error',
                'description': '',
                'headings': [],
                'text_content': '',
                'word_count': 0,
                'links': [],
                'status': f'error: {str(e)}'
            }
    
    def classify_content(self, content):
        """Simple content classification based on keywords"""
        text = (content['title'] + ' ' + content['description'] + ' ' + 
                ' '.join(content['headings']) + ' ' + content['text_content']).lower()
        
        categories = {
            'product': ['product', 'buy', 'shop', 'store', 'price', 'cart', 'purchase', 'item', 'catalog'],
            'blog': ['blog', 'post', 'article', 'news', 'story', 'read', 'author', 'published'],
            'about': ['about', 'company', 'team', 'history', 'mission', 'vision', 'who we are'],
            'contact': ['contact', 'phone', 'email', 'address', 'location', 'reach us', 'get in touch'],
            'service': ['service', 'solution', 'consulting', 'support', 'what we do', 'offerings'],
            'help': ['help', 'faq', 'support', 'documentation', 'guide', 'tutorial', 'how to'],
            'legal': ['privacy', 'terms', 'legal', 'policy', 'agreement', 'disclaimer', 'cookies']
        }
        
        scores = {}
        for category, keywords in categories.items():
            scores[category] = sum(1 for keyword in keywords if keyword in text)
        
        return max(scores, key=scores.get) if max(scores.values()) > 0 else 'other'
    
    def analyze_url_hierarchy(self, url):
        """Analyze URL structure and hierarchy"""
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        
        return {
            'depth': len(path_parts),
            'path_parts': path_parts,
            'has_query': bool(parsed.query),
            'file_extension': path_parts[-1].split('.')[-1] if path_parts and '.' in path_parts[-1] else None
        }
    
    def crawl_website(self, progress_callback=None):
        """Main crawling function"""
        to_crawl = [self.base_url]
        crawled = set()
        
        while to_crawl and len(crawled) < self.max_pages:
            current_url = to_crawl.pop(0)
            
            if current_url in crawled:
                continue
                
            crawled.add(current_url)
            
            if progress_callback:
                progress_callback(len(crawled), min(self.max_pages, len(crawled) + len(to_crawl)))
            
            page_data = self.extract_page_content(current_url)
            
            if page_data['status'] == 'success':
                # Classify content
                page_data['category'] = self.classify_content(page_data)
                
                # Analyze URL hierarchy
                page_data['hierarchy'] = self.analyze_url_hierarchy(current_url)
                
                # Extract topic keywords (simple version)
                text = page_data['text_content']
                if text:
                    try:
                        blob = TextBlob(text)
                        words = [word.lower() for word in blob.words if len(word) > 3 and word.isalpha()]
                        page_data['keywords'] = Counter(words).most_common(5)
                    except:
                        page_data['keywords'] = []
                else:
                    page_data['keywords'] = []
                
                self.site_data.append(page_data)
                
                # Add new URLs to crawl queue
                for link in page_data['links']:
                    if link not in crawled and link not in to_crawl:
                        to_crawl.append(link)
            
            time.sleep(0.2)  # Be respectful to the server
        
        return self.site_data

def create_taxonomy_data(site_data):
    """Create taxonomy data for visualization"""
    taxonomy = {
        'categories': Counter([page['category'] for page in site_data]),
        'hierarchy_levels': Counter([page['hierarchy']['depth'] for page in site_data]),
        'file_types': Counter([page['hierarchy']['file_extension'] or 'html' for page in site_data])
    }
    
    # Extract topics from keywords
    all_keywords = []
    for page in site_data:
        all_keywords.extend([kw[0] for kw in page['keywords']])
    taxonomy['topics'] = Counter(all_keywords).most_common(10)
    
    return taxonomy

def create_visualizations(site_data, taxonomy):
    """Create various visualizations"""
    
    # Category distribution pie chart
    if taxonomy['categories']:
        fig_categories = px.pie(
            values=list(taxonomy['categories'].values()),
            names=list(taxonomy['categories'].keys()),
            title="Content Distribution by Category",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_categories.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_categories, use_container_width=True)
    
    # Hierarchy depth bar chart
    if taxonomy['hierarchy_levels']:
        fig_hierarchy = px.bar(
            x=list(taxonomy['hierarchy_levels'].keys()),
            y=list(taxonomy['hierarchy_levels'].values()),
            title="Pages by URL Hierarchy Depth",
            labels={'x': 'Hierarchy Depth', 'y': 'Number of Pages'},
            color=list(taxonomy['hierarchy_levels'].values()),
            color_continuous_scale='Blues'
        )
        fig_hierarchy.update_layout(showlegend=False)
        st.plotly_chart(fig_hierarchy, use_container_width=True)
    
    # Top topics word cloud alternative
    if taxonomy['topics']:
        topics_df = pd.DataFrame(taxonomy['topics'], columns=['Topic', 'Frequency'])
        fig_topics = px.bar(
            topics_df.head(10),
            x='Frequency',
            y='Topic',
            orientation='h',
            title="Top 10 Topics by Frequency",
            color='Frequency',
            color_continuous_scale='Viridis'
        )
        fig_topics.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_topics, use_container_width=True)

def download_csv(data, filename="website_analysis.csv"):
    """Create download link for CSV data"""
    df = pd.DataFrame(data)
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 Download CSV Report</a>'
    return href

def main():
    st.title("🔍 AI Website Analysis Bot")
    st.markdown("**Analyze website structure, content taxonomy, and URL hierarchy with AI-powered insights**")
    
    # Sidebar for configuration
    st.sidebar.header("🛠️ Configuration")
    
    # URL input
    website_url = st.sidebar.text_input(
        "Website URL",
        placeholder="https://example.com",
        help="Enter the website URL you want to analyze"
    )
    
    # Max pages setting
    max_pages = st.sidebar.slider(
        "Maximum Pages to Crawl",
        min_value=5,
        max_value=100,
        value=25,
        help="Limit the number of pages to analyze (recommended: 25-50 for most websites)"
    )
    
    # Analysis button
    if st.sidebar.button("🚀 Start Analysis", type="primary"):
        if website_url:
            try:
                # Validate URL
                if not website_url.startswith(('http://', 'https://')):
                    website_url = 'https://' + website_url
                
                # Initialize analyzer
                analyzer = WebsiteAnalyzer(website_url, max_pages)
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(current, total):
                    progress = current / total if total > 0 else 0
                    progress_bar.progress(min(progress, 1.0))
                    status_text.text(f"🕷️ Analyzing page {current} of {total}")
                
                # Start analysis
                with st.spinner("🔄 Crawling website and analyzing content..."):
                    site_data = analyzer.crawl_website(update_progress)
                
                # Store results in session state
                st.session_state.analysis_data = site_data
                st.session_state.crawled_urls = [page['url'] for page in site_data]
                
                progress_bar.empty()
                status_text.empty()
                
                if site_data:
                    st.success(f"✅ Analysis complete! Successfully analyzed {len(site_data)} pages.")
                else:
                    st.warning("⚠️ No pages were successfully analyzed. Please check the URL and try again.")
                
            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")
                st.info("💡 Try with a different URL or reduce the number of pages to crawl.")
        else:
            st.warning("⚠️ Please enter a website URL to begin analysis")
    
    # Display results if available
    if st.session_state.analysis_data:
        site_data = st.session_state.analysis_data
        
        if not site_data:
            st.warning("No data available to display.")
            return
            
        taxonomy = create_taxonomy_data(site_data)
        
        # Main dashboard tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🏗️ Structure", "📋 URL Listings", "📈 Analytics"])
        
        with tab1:
            st.header("📊 Analysis Overview")
            
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Pages", len(site_data), help="Number of successfully analyzed pages")
            
            with col2:
                st.metric("Categories Found", len(taxonomy['categories']), help="Different content types identified")
            
            with col3:
                max_depth = max(taxonomy['hierarchy_levels'].keys()) if taxonomy['hierarchy_levels'] else 0
                st.metric("Max Hierarchy Depth", max_depth, help="Deepest URL path found")
            
            with col4:
                avg_words = sum(page['word_count'] for page in site_data) / len(site_data) if site_data else 0
                st.metric("Avg Words per Page", f"{avg_words:.0f}", help="Average content length per page")
            
            # Visualizations
            st.subheader("📈 Content Distribution")
            create_visualizations(site_data, taxonomy)
        
        with tab2:
            st.header("🏗️ Website Structure")
            
            # Taxonomy tree (simplified)
            st.subheader("📂 Content Taxonomy")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📁 Categories:**")
                for category, count in taxonomy['categories'].most_common():
                    percentage = (count / len(site_data)) * 100
                    st.write(f"• **{category.title()}**: {count} pages ({percentage:.1f}%)")
            
            with col2:
                st.markdown("**📊 Hierarchy Levels:**")
                for depth, count in sorted(taxonomy['hierarchy_levels'].items()):
                    percentage = (count / len(site_data)) * 100
                    st.write(f"• **Level {depth}**: {count} pages ({percentage:.1f}%)")
            
            # URL patterns analysis
            st.subheader("🔍 URL Pattern Analysis")
            if taxonomy['file_types']:
                st.markdown("**File Types:**")
                for file_type, count in taxonomy['file_types'].most_common(10):
                    st.write(f"• **.{file_type}**: {count} pages")
        
        with tab3:
            st.header("📋 URL Listings")
            
            # Filters
            col1, col2, col3 = st.columns(3)
            
            with col1:
                categories = ['All'] + list(taxonomy['categories'].keys())
                selected_category = st.selectbox("🏷️ Filter by Category", categories)
            
            with col2:
                max_depth = max(taxonomy['hierarchy_levels'].keys()) if taxonomy['hierarchy_levels'] else 5
                selected_depth = st.selectbox("📏 Filter by Hierarchy Depth", 
                                            ['All'] + list(range(1, max_depth + 1)))
            
            with col3:
                # Search functionality
                search_term = st.text_input("🔍 Search in titles/content", placeholder="Enter search term...")
            
            # Filter data
            filtered_data = site_data.copy()
            
            if selected_category != 'All':
                filtered_data = [page for page in filtered_data if page['category'] == selected_category]
            
            if selected_depth != 'All':
                filtered_data = [page for page in filtered_data if page['hierarchy']['depth'] == selected_depth]
            
            if search_term:
                search_term = search_term.lower()
                filtered_data = [page for page in filtered_data 
                               if search_term in page['title'].lower() or 
                                  search_term in page['text_content'].lower()]
            
            # Display filtered results
            st.write(f"**📄 Found {len(filtered_data)} pages matching filters:**")
            
            if filtered_data:
                for i, page in enumerate(filtered_data[:20]):  # Limit display for performance
                    with st.expander(f"📄 {page['title'][:60]}{'...' if len(page['title']) > 60 else ''}", 
                                   expanded=False):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.markdown(f"**🔗 URL:** [{page['url']}]({page['url']})")
                            st.write(f"**🏷️ Category:** {page['category'].title()}")
                            if page['description']:
                                st.write(f"**📝 Description:** {page['description'][:200]}{'...' if len(page['description']) > 200 else ''}")
                            if page['headings']:
                                st.write(f"**📑 Main Headings:** {' | '.join(page['headings'][:3])}")
                        
                        with col2:
                            st.write(f"**📊 Hierarchy Depth:** {page['hierarchy']['depth']}")
                            st.write(f"**📄 Word Count:** {page['word_count']}")
                            if page['keywords']:
                                keywords_str = ', '.join([kw[0] for kw in page['keywords'][:3]])
                                st.write(f"**🔑 Top Keywords:** {keywords_str}")
            else:
                st.info("🔍 No pages match the current filters. Try adjusting your search criteria.")
        
        with tab4:
            st.header("📈 Advanced Analytics")
            
            # Create DataFrame for analysis
            df = pd.DataFrame([
                {
                    'URL': page['url'],
                    'Title': page['title'],
                    'Category': page['category'],
                    'Hierarchy_Depth': page['hierarchy']['depth'],
                    'Word_Count': page['word_count'],
                    'Status': page['status'],
                    'Has_Description': bool(page['description']),
                    'Headings_Count': len(page['headings']),
                    'Links_Count': len(page['links'])
                }
                for page in site_data
            ])
            
            # Display raw data table
            st.subheader("📊 Raw Data Table")
            st.dataframe(df, use_container_width=True, height=400)
            
            # Summary statistics
            st.subheader("📈 Summary Statistics")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Content Statistics:**")
                st.write(f"• Total URLs analyzed: {len(df)}")
                st.write(f"• Average words per page: {df['Word_Count'].mean():.1f}")
                st.write(f"• Pages with descriptions: {df['Has_Description'].sum()}")
                st.write(f"• Average headings per page: {df['Headings_Count'].mean():.1f}")
            
            with col2:
                st.write("**Structure Statistics:**")
                st.write(f"• Maximum depth: {df['Hierarchy_Depth'].max()}")
                st.write(f"• Average depth: {df['Hierarchy_Depth'].mean():.1f}")
                st.write(f"• Pages at root level: {len(df[df['Hierarchy_Depth'] == 0])}")
                
            # Download options
            st.subheader("📥 Export Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📊 Download Full Report (CSV)", type="secondary"):
                    csv_data = download_csv(df.to_dict('records'))
                    st.markdown(csv_data, unsafe_allow_html=True)
                    st.success("✅ CSV download link generated above!")
            
            with col2:
                if st.button("📋 Download URL List (TXT)", type="secondary"):
                    url_list = '\n'.join([page['url'] for page in site_data])
                    b64 = base64.b64encode(url_list.encode()).decode()
                    href = f'<a href="data:text/plain;base64,{b64}" download="url_list.txt">📥 Download URL List</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("✅ URL list download link generated above!")
    
    # Sidebar info
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ About")
    st.sidebar.markdown(
        "This AI-powered bot analyzes website structure and content, "
        "automatically classifying pages by topic, category, and URL hierarchy."
    )
    
    st.sidebar.markdown("### 🛠️ Features")
    st.sidebar.markdown(
        "- **🧠 Smart Content Classification**\n"
        "- **🏗️ URL Hierarchy Analysis**\n"
        "- **🔍 Interactive Filtering**\n"
        "- **📊 Export Capabilities**\n"
        "- **⚡ Real-time Progress Tracking**"
    )
    
    st.sidebar.markdown("### 💡 Tips")
    st.sidebar.markdown(
        "- Start with 15-25 pages for testing\n"
        "- Use simple URLs (avoid complex e-commerce sites)\n"
        "- Check that the website allows crawling\n"
        "- Try news sites or blogs for best results"
    )
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🚀 Built with Streamlit**")

if __name__ == "__main__":
    main()
