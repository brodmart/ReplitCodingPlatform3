import trafilatura
import json
from urllib.parse import urlparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_site(url):
    """Analyze a website's CodeMirror implementation"""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            # Get main content
            text_content = trafilatura.extract(downloaded)
            
            # Look for CodeMirror specific patterns
            codemirror_patterns = {
                'version': r'codemirror[/-](\d+\.\d+\.\d+)',
                'themes': r'theme[/-]([\w-]+)\.css',
                'modes': r'mode[/-]([\w-]+)\.js'
            }
            
            return {
                'url': url,
                'implementation_details': text_content
            }
    except Exception as e:
        logger.error(f"Error analyzing {url}: {str(e)}")
        return None

def main():
    # List of major sites using CodeMirror
    sites = [
        'https://www.w3schools.com/tryit/tryit.asp?filename=tryhtml_hello',
        'https://codepen.io/pen/',
        'https://jsfiddle.net/',
        'https://codesandbox.io/',
    ]
    
    results = {}
    for site in sites:
        logger.info(f"Analyzing {site}...")
        result = analyze_site(site)
        if result:
            domain = urlparse(site).netloc
            results[domain] = result
    
    # Save results
    with open('codemirror_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
        
    logger.info("Analysis complete. Results saved to codemirror_analysis.json")

if __name__ == "__main__":
    main()
