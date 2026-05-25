"""Format pricing drafts for WhatsApp review messages (FR-001)."""
from __future__ import annotations


def format_rules_summary(
    rules: dict,
    notes: list[str],
    validation_errors: list[str],
) -> str:
    lines = ["*Rate table preview*"]
    for row in rules.get("rate_table", []):
        cond = ", ".join(f"{k}={v}" for k, v in row.get("conditions", {}).items())
        rate = row.get("rate_per_sqft", "?")
        lines.append(f"• {cond or '(default)'}: Rs. {rate}/sqft")

    if validation_errors:
        lines.append("\n*Schema warnings* (fix before buyers quote):")
        for err in validation_errors[:5]:
            lines.append(f"• {err}")
        if len(validation_errors) > 5:
            lines.append(f"• …and {len(validation_errors) - 5} more")

    if notes:
        lines.append("\n*AI notes*:")
        for note in notes[:3]:
            lines.append(f"• {note}")

    lines.append('\nReply *yes* to save or *cancel* to discard.')
    return "\n".join(lines)


def format_profile_summary(profile: dict, rules: dict) -> str:
    lines = [
        "*Profile*",
        f"Business: {profile.get('business_name', '?')}",
        f"City: {profile.get('city') or '(not set)'}",
        f"Slug: {profile.get('whatsapp_link_slug', '?')}",
        "",
        format_rules_summary(rules, [], []),
    ]
    return "\n".join(lines)
