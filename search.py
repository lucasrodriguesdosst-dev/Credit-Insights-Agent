"""
Web search utility for looking up entities from cashflow labelRoot fields.
Uses DuckDuckGo search to find information about transaction entities.
"""

from duckduckgo_search import DDGS


def search_entity(label_root: str, max_results: int = 3) -> str:
    """
    Search the web for information about an entity found in a cashflow labelRoot.

    Args:
        label_root: The labelRoot value from the cashflow (e.g., "INST WINAMAX RETRAIT")
        max_results: Maximum number of search results to return

    Returns:
        A formatted string with search results describing the entity.
    """
    # Clean and extract the meaningful entity name from the labelRoot
    query = _extract_entity_query(label_root)
    if not query:
        return f"Could not extract a meaningful entity name from: {label_root}"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"No search results found for: {query}"

        formatted = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            formatted.append(f"- {title}: {body}")

        return f"Search results for '{query}':\n" + "\n".join(formatted)

    except Exception as e:
        return f"Search failed for '{query}': {str(e)}"


def _extract_entity_query(label_root: str) -> str:
    """
    Extract a meaningful search query from a labelRoot value.
    Removes common banking prefixes/suffixes and noise words.
    """
    # Common noise words in French banking labels
    noise_words = {
        "INST", "RETRAIT", "PAIEMENT", "VIR", "VIREMENT", "PRELEVEMENT",
        "CB", "CARTE", "CHQ", "CHEQUE", "RET", "ECH", "ECHEANCE",
        "MR", "MME", "M.", "MLLE", "MR OU MME", "MONSIEUR", "MADAME",
        "FRE", "FR", "FRAIS", "COTIS", "COTISATION",
        "SAS", "SARL", "SA", "SCI", "EURL", "B.V.", "BV",
        "N/REF", "REF", "REMISE",
    }

    # Split and filter
    parts = label_root.upper().split()
    filtered = [p for p in parts if p not in noise_words and len(p) > 1]

    if not filtered:
        # Fallback to original if everything was filtered
        return label_root.strip()

    query = " ".join(filtered)

    # Add context for better search results
    return f"{query} company France"
