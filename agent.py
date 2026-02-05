"""
Cashflow Category Validator Agent

This agent processes cashflows one by one, searches online for the entities
referenced in the labelRoot field, and validates whether the assigned category
is correct according to the Algoan category taxonomy.

If a category is incorrect, the agent proposes a more appropriate one.
"""

import json
import anthropic
from categories import format_taxonomy, ALL_CATEGORIES, get_category_group
from search import search_entity


SYSTEM_PROMPT = """You are a cashflow category validation expert. Your job is to determine whether
the category assigned to a bank cashflow is correct, based on what the entity in the transaction
actually is.

You will be given:
1. A cashflow with its labelRoot, current category, transaction type, and total amount
2. Web search results about the entity referenced in the labelRoot

{taxonomy}

Your task:
1. Analyze the web search results to understand what the entity in the labelRoot actually does/sells/provides
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
    "entity_description": "Brief description of what the entity is based on search results",
    "current_category": "the current category",
    "is_correct": true/false,
    "suggested_category": "the suggested category (same as current if correct)",
    "confidence": "HIGH/MEDIUM/LOW",
    "reasoning": "Brief explanation of why the category is correct or what it should be changed to"
}}
"""


def validate_cashflow(client: anthropic.Anthropic, cashflow: dict) -> dict:
    """
    Validate a single cashflow's category by searching for the entity
    and using Claude to assess correctness.

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

    # Search for the entity online
    search_results = search_entity(label_root)

    # Build the prompt for Claude
    cashflow_info = (
        f"Cashflow details:\n"
        f"  - labelRoot: {label_root}\n"
        f"  - Current category: {category}\n"
        f"  - Transaction type: {cf_type}\n"
        f"  - Total amount: {total_amount}\n"
        f"\nWeb search results about this entity:\n{search_results}"
    )

    system = SYSTEM_PROMPT.format(taxonomy=format_taxonomy())

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": cashflow_info}],
    )

    # Parse the response
    response_text = response.content[0].text

    try:
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        result = json.loads(response_text.strip())
    except (json.JSONDecodeError, IndexError):
        result = {
            "entity_description": "Failed to parse response",
            "current_category": category,
            "is_correct": None,
            "suggested_category": category,
            "confidence": "LOW",
            "reasoning": f"Raw response: {response_text[:500]}",
        }

    # Add metadata
    result["labelRoot"] = label_root
    result["type"] = cf_type
    result["totalAmount"] = total_amount
    result["search_results"] = search_results

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

    for i, cashflow in enumerate(cashflows):
        label_root = cashflow.get("labelRoot", "N/A")
        print(f"[{i + 1}/{len(cashflows)}] Validating: {label_root}")

        try:
            result = validate_cashflow(client, cashflow)
            results.append(result)

            status = "CORRECT" if result.get("is_correct") else "INCORRECT"
            if not result.get("is_correct"):
                suggested = result.get("suggested_category", "?")
                current = result.get("current_category", "?")
                print(f"  -> {status}: {current} -> {suggested}")
                print(f"     Reason: {result.get('reasoning', 'N/A')}")
            else:
                print(f"  -> {status}: {result.get('current_category', '?')}")

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
