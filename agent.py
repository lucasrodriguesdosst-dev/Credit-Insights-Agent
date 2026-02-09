"""
Cashflow Category Validator Agent

This agent processes cashflows one by one and validates whether the assigned category
is correct according to the Algoan category taxonomy.

It uses a two-pass approach to minimize web search costs:
  1. A fast triage pass (no web search) where the LLM classifies using its knowledge.
  2. A second pass WITH web search, only when the current or suggested category
     belongs to a set of ambiguous/high-stakes categories that benefit from live data.

If a category is incorrect, the agent proposes a more appropriate one.
"""

import json
import anthropic
from categories import format_taxonomy, ALL_CATEGORIES, get_category_group
from search import extract_entity_query


# Categories that require web search to validate accurately.
# These are specialized, ambiguous, or high-stakes categories where the LLM's
# built-in knowledge is less likely to be sufficient.
WEB_SEARCH_CATEGORIES = {
    "ALLOWANCE",
    "POWER",
    "LOAN_REPAYMENT_REVOLVING",
    "REJECTION_CHECK",
    "FEES_INTERVENTION",
    "ALLOWANCE_FAMILY",
    "FEES_DIRECT_DEBT_RECOVERY",
    "LOAN_REPAYMENT_REAL_ESTATE",
    "GAMBLING",
    "RENTAL_INCOME",
    "GAMBLING_GAIN",
    "RENT",
    "BAILIFF",
    "REFUND_DIRECT_DEBT_RECOVERY_FEES",
    "FEES_OVERDRAFT",
    "FEES_ACCOUNT_SEIZURE",
    "FEES_PREVENTIVE_SEIZURE",
    "RELEASE_ACCOUNT_SEIZURE",
    "FEES_CHECK_REJECTION",
    "LOAN_REPAYMENT_PERSONAL",
    "PERSO_TAX",
    "RELEASE_PREVENTIVE_SEIZURE",
    "WAGE",
    "LOAN_DRAWDOWN_REVOLVING",
    "REFUND_BANK_SERVICE_FEES",
    "LOAN_DRAWDOWN_PERSONAL",
    "PROVISION_PREVENTIVE_SEIZURE",
    "PROVISION_ACCOUNT_SEIZURE",
    "DEFERRED_TOTAL_PAYMENT",
    "REFUND_ACCOUNT_SEIZURE_FEES",
    "FEES_BANK_SERVICE",
    "REFUND_PREVENTIVE_SEIZURE_FEES",
    "LOAN_PREPAYMENT",
    "LOAN_DRAWDOWN_REAL_ESTATE",
    "FEES_INCIDENT",
    "DEBT_COLLECTION",
    "CREDIT_CARD_RESET",
    "RETIREMENT_PENSION",
    "LOAN_DRAWDOWN",
    "REFUND",
    "RELEASE_DIRECT_DEBT_RECOVERY",
    "LOAN_REPAYMENT",
    "FEES_PAYMENT_REJECTION",
    "ALLOWANCE_HEALTH",
    "PROVISION_DIRECT_DEBT_RECOVERY",
    "ALLOWANCE_UNEMPLOYMENT",
    "REJECTION_LOAN_REPAYMENT",
    "SPLIT_PAYMENT",
    "REFUND_BANK_INCIDENT_FEES",
    "REJECTION_PAYMENT",
    "LOAN_REPAYMENT_FAST",
    "LOAN_DRAWDOWN_FAST",
    "LOAN_DRAWDOWN_STUDENT",
}


SYSTEM_PROMPT = """You are a cashflow category validation expert. Your job is to determine whether
the category assigned to a bank cashflow is correct, based on what the entity in the transaction
actually is.

You will be given:
1. A cashflow with its labelRoot, current category, transaction type, and total amount
{search_context}

{taxonomy}

Your task:
1. Identify what the entity in the labelRoot actually does/sells/provides
2. Determine if the currently assigned category is correct given the entity's actual business
3. If incorrect, propose the most appropriate category from the taxonomy above

IMPORTANT RULES:
- Only propose categories that exist in the taxonomy above
- Consider the transaction type (INCOMING vs OUTGOING) when evaluating income vs expense categories
- A CARD transaction at a grocery store should be GROCERY, not SHOPPING
- A transfer labeled as rent should be RENT
- Insurance companies should be INSURANCE (or specific subtypes like INSURANCE_HEALTH, INSURANCE_AUTO, INSURANCE_HOME)
- Telecom operators should be TELECOM
- Online shopping platforms (Amazon, Temu, Vinted, etc.) should be SHOPPING
- Gambling platforms (Winamax, etc.) income should be GAMBLING_GAIN, expenses should be GAMBLING
- Toll road payments (APRR, SAPN, etc.) should be TRANSPORT
- Cashback platforms (iGraal, Poulpeo) income should be OTHER_ENTRY
- Government family allowances (CAF) should be ALLOWANCE_FAMILY
- Catering/restaurant companies should be GROCERY or LEISURE depending on context
- Photo services/shops should be SHOPPING or LEISURE
- Municipal/government wages should be WAGE

Respond in this exact JSON format:
{{
    "entity_description": "Brief description of what the entity is based on your knowledge{and_search}",
    "current_category": "the current category",
    "is_correct": true/false,
    "suggested_category": "the suggested category (same as current if correct)",
    "confidence": "HIGH/MEDIUM/LOW",
    "reasoning": "Brief explanation of why the category is correct or what it should be changed to"
}}
"""


def _needs_web_search(current_category: str, triage_result: dict | None) -> bool:
    """
    Determine if a web search is needed based on the current category
    and the triage result from the first pass.

    Returns True if either the current category or the suggested category
    belongs to the WEB_SEARCH_CATEGORIES set.
    """
    if current_category in WEB_SEARCH_CATEGORIES:
        return True
    if triage_result:
        suggested = triage_result.get("suggested_category", "")
        if suggested in WEB_SEARCH_CATEGORIES:
            return True
    return False


def _parse_llm_response(response_text: str, category: str) -> dict:
    """Parse JSON from the LLM response text, handling markdown code blocks."""
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        return json.loads(response_text.strip())
    except (json.JSONDecodeError, IndexError):
        return {
            "entity_description": "Failed to parse response",
            "current_category": category,
            "is_correct": None,
            "suggested_category": category,
            "confidence": "LOW",
            "reasoning": f"Raw response: {response_text[:500]}",
        }


def _build_cashflow_prompt(cashflow: dict, with_search: bool) -> str:
    """Build the user prompt for a cashflow validation."""
    label_root = cashflow.get("labelRoot", "")
    category = cashflow.get("category", "")
    cf_type = cashflow.get("type", "")
    total_amount = cashflow.get("totalAmount", 0)

    prompt = (
        f"Cashflow details:\n"
        f"  - labelRoot: {label_root}\n"
        f"  - Current category: {category}\n"
        f"  - Transaction type: {cf_type}\n"
        f"  - Total amount: {total_amount}\n"
    )

    if with_search:
        query_hint = extract_entity_query(label_root)
        prompt += (
            f"\nPlease search the web for \"{query_hint}\" to identify what this entity is, "
            f"then validate whether the current category is correct."
        )
    else:
        prompt += (
            f"\nUsing your existing knowledge, identify what this entity likely is "
            f"and validate whether the current category is correct."
        )

    return prompt


def _call_llm(client: anthropic.Anthropic, system: str, user_prompt: str,
              with_search: bool) -> tuple[str, str]:
    """
    Call the Anthropic API with or without the web search tool.

    Returns:
        A tuple of (response_text, search_results_summary).
    """
    kwargs = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    if with_search:
        kwargs["tools"] = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 1,
        }]

    response = client.messages.create(**kwargs)

    # Handle pause_turn for long-running web searches
    if with_search:
        messages = [{"role": "user", "content": user_prompt}]
        while response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            kwargs["messages"] = messages
            response = client.messages.create(**kwargs)

    # Extract text and search result titles.
    # With web search + citations, Claude returns multiple text blocks;
    # concatenate them all so the JSON parser can find the full response.
    text_parts = []
    search_results_summary = ""
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "web_search_tool_result":
            titles = []
            for item in (block.content if isinstance(block.content, list) else []):
                if hasattr(item, "title"):
                    titles.append(item.title)
            if titles:
                search_results_summary = "; ".join(titles)

    response_text = "".join(text_parts)
    return response_text, search_results_summary


def validate_cashflow(client: anthropic.Anthropic, cashflow: dict) -> dict:
    """
    Validate a single cashflow's category using a two-pass approach:

    Pass 1 (triage): Fast classification without web search.
    Pass 2 (search): Only if the current or suggested category is in
                     WEB_SEARCH_CATEGORIES, re-validate with web search.

    Args:
        client: Anthropic API client
        cashflow: A cashflow dict with at least labelRoot, category, type

    Returns:
        A dict with the validation result
    """
    label_root = cashflow.get("labelRoot", "")
    category = cashflow.get("category", "")
    cf_type = cashflow.get("type", "")
    total_amount = cashflow.get("totalAmount", 0)

    taxonomy = format_taxonomy()
    used_search = False

    # --- Pass 1: Triage (no web search) ---
    system_triage = SYSTEM_PROMPT.format(
        taxonomy=taxonomy,
        search_context="",
        and_search="",
    )
    user_prompt = _build_cashflow_prompt(cashflow, with_search=False)
    response_text, _ = _call_llm(client, system_triage, user_prompt, with_search=False)
    triage_result = _parse_llm_response(response_text, category)

    # --- Pass 2: Web search only if needed ---
    if _needs_web_search(category, triage_result):
        used_search = True
        system_search = SYSTEM_PROMPT.format(
            taxonomy=taxonomy,
            search_context="2. Web search results about the entity referenced in the labelRoot",
            and_search=" and search results",
        )
        user_prompt = _build_cashflow_prompt(cashflow, with_search=True)
        response_text, search_summary = _call_llm(
            client, system_search, user_prompt, with_search=True
        )
        result = _parse_llm_response(response_text, category)
        result["search_results"] = search_summary or "Web search via Anthropic API"
    else:
        result = triage_result
        result["search_results"] = "No web search needed"

    # Add metadata
    result["labelRoot"] = label_root
    result["type"] = cf_type
    result["totalAmount"] = total_amount
    result["used_web_search"] = used_search

    return result


def validate_cashflows(cashflows: list[dict], anthropic_api_key: str | None = None) -> list[dict]:
    """
    Validate categories for a list of cashflows.

    Args:
        cashflows: List of cashflow dicts
        anthropic_api_key: Optional API key (uses ANTHROPIC_API_KEY env var if not provided)

    Returns:
        List of validation results
    """
    kwargs = {}
    if anthropic_api_key:
        kwargs["api_key"] = anthropic_api_key

    client = anthropic.Anthropic(**kwargs)
    results = []

    search_count = 0

    for i, cashflow in enumerate(cashflows):
        label_root = cashflow.get("labelRoot", "N/A")
        print(f"[{i + 1}/{len(cashflows)}] Validating: {label_root}")

        try:
            result = validate_cashflow(client, cashflow)
            results.append(result)

            if result.get("used_web_search"):
                search_count += 1

            search_tag = " [searched]" if result.get("used_web_search") else ""
            status = "CORRECT" if result.get("is_correct") else "INCORRECT"
            if not result.get("is_correct"):
                suggested = result.get("suggested_category", "?")
                current = result.get("current_category", "?")
                print(f"  -> {status}: {current} -> {suggested}{search_tag}")
                print(f"     Reason: {result.get('reasoning', 'N/A')}")
            else:
                print(f"  -> {status}: {result.get('current_category', '?')}{search_tag}")

        except Exception as e:
            print(f"  -> ERROR: {str(e)}")
            results.append({
                "labelRoot": label_root,
                "type": cashflow.get("type", ""),
                "current_category": cashflow.get("category", ""),
                "is_correct": None,
                "suggested_category": cashflow.get("category", ""),
                "confidence": "LOW",
                "reasoning": f"Error: {str(e)}",
                "error": str(e),
            })

    print(f"\nWeb searches performed: {search_count}/{len(cashflows)} cashflows")
    return results


def generate_report(results: list[dict]) -> str:
    """Generate a summary report from validation results."""
    total = len(results)
    correct = sum(1 for r in results if r.get("is_correct") is True)
    incorrect = sum(1 for r in results if r.get("is_correct") is False)
    errors = sum(1 for r in results if r.get("is_correct") is None)

    lines = [
        "=" * 70,
        "CASHFLOW CATEGORY VALIDATION REPORT",
        "=" * 70,
        f"Total cashflows analyzed: {total}",
        f"Correctly categorized:    {correct} ({correct/total*100:.1f}%)" if total > 0 else "",
        f"Incorrectly categorized:  {incorrect} ({incorrect/total*100:.1f}%)" if total > 0 else "",
        f"Errors:                   {errors}" if errors > 0 else "",
        "",
    ]

    if incorrect > 0:
        lines.append("-" * 70)
        lines.append("SUGGESTED CORRECTIONS:")
        lines.append("-" * 70)

        for r in results:
            if r.get("is_correct") is False:
                lines.append(
                    f"\n  labelRoot:  {r.get('labelRoot', 'N/A')}"
                )
                lines.append(
                    f"  Entity:     {r.get('entity_description', 'N/A')}"
                )
                lines.append(
                    f"  Current:    {r.get('current_category', 'N/A')}"
                )
                lines.append(
                    f"  Suggested:  {r.get('suggested_category', 'N/A')}"
                )
                lines.append(
                    f"  Confidence: {r.get('confidence', 'N/A')}"
                )
                lines.append(
                    f"  Reasoning:  {r.get('reasoning', 'N/A')}"
                )

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
