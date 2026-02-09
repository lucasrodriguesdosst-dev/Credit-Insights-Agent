"""
Web search utility for looking up entities from cashflow labelRoot fields.
Provides query extraction logic used by the agent's Anthropic web search tool.
"""


def extract_entity_query(label_root: str) -> str:
    """
    Extract a meaningful search query from a labelRoot value.
    Removes common banking prefixes/suffixes and noise words.

    Args:
        label_root: The labelRoot value from the cashflow

    Returns:
        A cleaned search query string.
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
