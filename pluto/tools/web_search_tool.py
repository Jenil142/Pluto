import os
import sys
from ddgs import DDGS
from google.genai import types


def search_web(query, max_results=5, **kwargs):
    """Searches the web using DuckDuckGo and returns formatted results."""

    try:
        # ddgs v9 prints noisy debug output to stdout (response URLs, engine errors).
        # We suppress it by temporarily redirecting stdout to /dev/null during the search.
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

        try:
            results = DDGS().text(query, max_results=max_results)
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout

    except Exception as e:
        return f"Search failed: {e}"

    if not results:
        return "No results found."

    formatted = f"Web search results for: '{query}'\n\n"

    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("href", "")
        snippet = result.get("body", "No description")

        formatted += f"{i}. {title}\n"
        formatted += f"   URL: {url}\n"
        formatted += f"   {snippet}\n\n"

    return formatted


# --- Gemini Tool Declaration ---

search_web_declaration = types.FunctionDeclaration(
    name="search_web",
    description="Searches the internet using DuckDuckGo. Use this tool when the user asks about current events, weather, news, real-time information, or anything you don't know the answer to.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "query": types.Schema(
                type="STRING",
                description="The search query to look up on the web."
            ),
            "max_results": types.Schema(
                type="INTEGER",
                description="The number of search results to return. Defaults to 5."
            )
        },
        required=["query"]
    )
)
