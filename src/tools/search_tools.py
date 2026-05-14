import logging
import warnings

from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


def search_duckduckgo(query: str, max_results: int = 5):
    """
    Search DuckDuckGo for the given query and return a list of results.
    Each result contains 'title', 'href' (link), and 'body' (snippet).
    """
    logger.info(f"Searching DuckDuckGo for: {query}")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return results
    except Exception as e:
        logger.error(f"Error searching DuckDuckGo: {e}")
        return []

if __name__ == "__main__":
    # Test
    test_query = "Specialty Coffee Roastery Dubai Instagram"
    results = search_duckduckgo(test_query)
    for r in results:
        print(f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}\n")
