import requests
from bs4 import BeautifulSoup
from typing import Dict, Tuple
import os
from urllib.parse import urlparse

def fetch_web_content(url: str) -> Tuple[str, str]:
    """
    Fetch content from a web page.
    
    Args:
        url (str): URL of the webpage to fetch
        
    Returns:
        Tuple[str, str]: A tuple containing (text_content, page_title)
        
    Raises:
        ValueError: If the URL is invalid
        ConnectionError: If there's an error connecting to the website
        Exception: For other errors
    """
    try:
        # Validate URL format
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError(f"Invalid URL format: {url}")
        
        # Add scheme if missing
        if not parsed_url.scheme:
            url = f"https://{url}"
        
        # Send request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract page title
        page_title = soup.title.string if soup.title else urlparse(url).netloc
        
        # Extract text content
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
            
        # Get text content
        text = soup.get_text(separator=' ', strip=True)
        
        # Handle whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text, page_title
        
    except requests.exceptions.MissingSchema:
        raise ValueError(f"Invalid URL. Make sure it starts with http:// or https://: {url}")
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Failed to connect to {url}. Check your internet connection and the URL.")
    except requests.exceptions.Timeout:
        raise ConnectionError(f"Connection to {url} timed out. The server may be down or unresponsive.")
    except requests.exceptions.HTTPError as e:
        raise ConnectionError(f"HTTP Error: {str(e)}")
    except Exception as e:
        raise Exception(f"An error occurred while fetching the web page: {str(e)}")