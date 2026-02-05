"""
Cashflow Category Validator - Entry Point

Loads cashflow data and runs the category validation agent on each cashflow.
Usage:
    python main.py [path_to_cashflows.json]

If no path is provided, it loads sample_data.json from the current directory.
"""

import json
import sys
import os
from agent import validate_cashflows, generate_report


def main():
    # Determine input file
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = os.path.join(os.path.dirname(__file__), "sample_data.json")

    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        print("Usage: python main.py [path_to_cashflows.json]")
        sys.exit(1)

    # Load cashflow data
    print(f"Loading cashflows from: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support both {"cashFlows": [...]} and direct [...] formats
    if isinstance(data, dict) and "cashFlows" in data:
        cashflows = data["cashFlows"]
    elif isinstance(data, list):
        cashflows = data
    else:
        print("Error: Expected a JSON file with a 'cashFlows' array or a direct array of cashflows.")
        sys.exit(1)

    print(f"Found {len(cashflows)} cashflows to validate.\n")

    # Run the validation agent
    results = validate_cashflows(cashflows)

    # Generate and print report
    report = generate_report(results)
    print(f"\n{report}")

    # Save detailed results
    output_file = input_file.replace(".json", "_validation_results.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to: {output_file}")

    # Save report
    report_file = input_file.replace(".json", "_validation_report.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main()
