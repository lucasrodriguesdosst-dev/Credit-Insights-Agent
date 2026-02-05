"""
Algoan Category Taxonomy

Complete category taxonomy sourced from the Algoan REST SDK.
Reference: https://docs.algoan.com/developer-doc/category-taxonomy
"""

# Income categories
INCOME_CATEGORIES = [
    "ALLOWANCE",
    "ALLOWANCE_FAMILY",
    "ALLOWANCE_HOUSING",
    "ALLOWANCE_UNEMPLOYMENT",
    "ALLOWANCE_HEALTH",
    "ALLOWANCE_INCOME_SUPPORT",
    "ALLOWANCE_INCOME",
    "STATE_SUBSIDY",
    "GAMBLING_GAIN",
    "RENTAL_INCOME",
    "RECEIVED_ALIMONY",
    "PAID_ALIMONY",
    "WAGE",
    "WAGE_BONUS",
    "WAGE_SALARY_ADVANCE",
    "WAGE_ADVANCE_PAYMENT",
    "RETIREMENT_PENSION",
    "REVERSIONARY_PENSION",
    "DISSAVING",
    "OTHER_ENTRY",
]

# Expense categories
EXPENSE_CATEGORIES = [
    "INSURANCE",
    "INSURANCE_HEALTH",
    "INSURANCE_AUTO",
    "INSURANCE_HOME",
    "TRANSPORT",
    "POWER",
    "RENT",
    "TELECOM",
    "HEALTH",
    "GROCERY",
    "TOBACCO",
    "GAMBLING",
    "LEISURE",
    "SHOPPING",
    "DEFERRED_TOTAL_PAYMENT",
    "MULTIMEDIA",
    "SPORT",
    "OTHER_EXPENSE",
]

# Credit categories
CREDIT_CATEGORIES = [
    "LOAN_DRAWDOWN",
    "LOAN_DRAWDOWN_REAL_ESTATE",
    "LOAN_DRAWDOWN_PERSONAL",
    "LOAN_DRAWDOWN_REVOLVING",
    "LOAN_REPAYMENT",
    "LOAN_REPAYMENT_REAL_ESTATE",
    "LOAN_REPAYMENT_PERSONAL",
    "LOAN_REPAYMENT_REVOLVING",
    "LOAN_PREPAYMENT",
    "SPLIT_PAYMENT",
    "DEBT_RECOVERY",
    "DEBT_COLLECTION",
    "BAILIFF",
    "LEASING",
]

# Saving categories
SAVING_CATEGORIES = [
    "INTEREST",
    "SAVING",
    "BANKBOOK_SAVING",
    "SHARE_SAVING",
]

# Bank operation categories
BANK_OPERATION_CATEGORIES = [
    "REJECTION_PAYMENT",
    "REJECTION_LOAN_REPAYMENT",
    "REJECTION_CHECK",
    "FEES_BANK_SERVICE",
    "FEES_OVERDRAFT",
    "FEES_CHECK_REJECTION",
    "FEES_PAYMENT_REJECTION",
    "FEES_INTERVENTION",
    "FEES_INCIDENT",
    "FEES_DIRECT_DEBT_RECOVERY",
    "FEES_ACCOUNT_SEIZURE",
    "FEES_PREVENTIVE_SEIZURE",
    "REFUND_DIRECT_DEBT_RECOVERY_FEES",
    "REFUND_ACCOUNT_SEIZURE_FEES",
    "REFUND_PREVENTIVE_SEIZURE_FEES",
    "REFUND_BANK_INCIDENT_FEES",
    "REFUND_BANK_SERVICE_FEES",
    "RELEASE_DIRECT_DEBT_RECOVERY",
    "RELEASE_ACCOUNT_SEIZURE",
    "RELEASE_PREVENTIVE_SEIZURE",
    "PROVISION_DIRECT_DEBT_RECOVERY",
    "PROVISION_ACCOUNT_SEIZURE",
    "PROVISION_PREVENTIVE_SEIZURE",
    "CREDIT_CARD_RESET",
]

# Refund categories
REFUND_CATEGORIES = [
    "REFUND",
    "REFUND_INSURANCE",
    "REFUND_EXPENSE_REPORT",
]

# Tax categories
TAX_CATEGORIES = [
    "PRO_TAX",
    "PRO_TAX_REFUND",
    "PERSO_TAX",
    "INCOME_TAX",
    "HOUSING_TAX",
    "PROPERTY_TAX",
    "PERSO_TAX_CREDIT",
    "PERSO_TAX_REFUND",
]

# Transaction types
TRANSACTION_TYPES = [
    "CASH_DEPOSIT",
    "CASH_WITHDRAWAL",
    "CHECK_DEPOSIT",
    "CHECK",
    "INCOMING_TRANSFER",
    "INCOMING_INTERNAL_TRANSFER",
    "OUTGOING_TRANSFER",
    "OUTGOING_INTERNAL_TRANSFER",
    "CARD",
    "CARD_REFUND",
    "DIRECT_DEBIT",
    "INCOMING_CARD",
    "CREDIT",
    "DEBIT",
]

# All categories combined
ALL_CATEGORIES = (
    INCOME_CATEGORIES
    + EXPENSE_CATEGORIES
    + CREDIT_CATEGORIES
    + SAVING_CATEGORIES
    + BANK_OPERATION_CATEGORIES
    + REFUND_CATEGORIES
    + TAX_CATEGORIES
)

# Category groups for reference
CATEGORY_GROUPS = {
    "INCOME": INCOME_CATEGORIES,
    "EXPENSE": EXPENSE_CATEGORIES,
    "CREDIT": CREDIT_CATEGORIES,
    "SAVING": SAVING_CATEGORIES,
    "BANK_OPERATION": BANK_OPERATION_CATEGORIES,
    "REFUND": REFUND_CATEGORIES,
    "TAX": TAX_CATEGORIES,
}


def get_category_group(category: str) -> str | None:
    """Return the group name for a given category."""
    for group_name, categories in CATEGORY_GROUPS.items():
        if category in categories:
            return group_name
    return None


def is_valid_category(category: str) -> bool:
    """Check if a category is valid in the Algoan taxonomy."""
    return category in ALL_CATEGORIES


def format_taxonomy() -> str:
    """Return a formatted string of the complete taxonomy for use in prompts."""
    lines = ["Algoan Category Taxonomy:\n"]
    for group_name, categories in CATEGORY_GROUPS.items():
        lines.append(f"  {group_name}:")
        for cat in categories:
            lines.append(f"    - {cat}")
        lines.append("")
    return "\n".join(lines)
