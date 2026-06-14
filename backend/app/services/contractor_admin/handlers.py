"""State handlers for contractor admin WhatsApp flows (FR-001)."""
from __future__ import annotations

import logging
import re

from app.db.enums import AdminFlowType, AdminSessionState
from app.db.models import ContractorAdminSession
from app.services.contractor_admin.keywords import AdminConfirmAction, parse_admin_confirm
from app.services.contractor_admin.prefix import AdminPrefix
from app.services.contractor_admin.session_repo import log_pricing_updated
from app.services.contractor_admin.summary import format_profile_summary, format_rules_summary
from app.services.contractor_admin.types import AdminHandlerDeps, AdminHandlerResult
from app.services.onboarding.service import DuplicateError
from app.services.rate_card.extractor import UnsupportedFormatError, extract_text
from app.services.rate_card.parser import RateCardParser
from app.services.whatsapp.payload import InboundMessage, extract_document_info

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"^[a-z0-9-]{3,64}$")

_MSG_MANAGE_RATES_UNREGISTERED = (
    "manage-rates is for registered contractors only. "
    "Send *onboard* to create a new QuoteWise account."
)
_MSG_ONBOARD_ALREADY_REGISTERED = (
    "This number is already registered. Send *manage-rates* to update your pricing."
)
_MSG_ASK_WORK_TYPE = (
    "Which work type are you updating?\n"
    "Reply with a type (e.g., *painting*, *electrical*, *plumbing*)."
)
_MSG_ASK_CONTENT = (
    "Send your rate card as a message (user paste) or upload a PDF, TXT, or CSV file."
)
_MSG_PARSE_FAILED = "Could not parse that rate card. Please try again or send clearer text."
_MSG_UNSUPPORTED_DOC = "Unsupported file type. Please send PDF, TXT, or CSV."
_MSG_SAVED = "Pricing saved successfully (version {version}). Buyers will get the new rates."
_MSG_CANCELLED = "Update cancelled. Your existing pricing is unchanged."
_MSG_ONBOARD_BUSINESS = "Welcome to QuoteWise setup! What is your business name?"
_MSG_ONBOARD_CITY = "Which city are you based in? (Reply *skip* to leave blank)"
_MSG_ONBOARD_SLUG = (
    "Choose a unique link slug (lowercase letters, numbers, hyphens, 3–64 chars).\n"
    "Example: *sharma-paints*"
)
_MSG_ONBOARD_DONE = (
    "You're live!\n\n"
    "Buyer link: https://wa.me/{bot}?text=quote-{slug}\n\n"
    "Dashboard API key (save this — shown once):\n{api_key}\n\n"
    "Use this key at the web dashboard login."
)


def parse_work_type(text: str) -> str | None:
    normalized = text.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized if normalized else None


def handle_start(
    prefix: AdminPrefix,
    deps: AdminHandlerDeps,
) -> AdminHandlerResult:
    if prefix.flow == AdminFlowType.manage_rates:
        if deps.registered_contractor is None:
            return AdminHandlerResult(
                new_state=AdminSessionState.cancelled,
                outbound_text=_MSG_MANAGE_RATES_UNREGISTERED,
            )
        wt = parse_work_type(prefix.tail) if prefix.tail else None
        if wt:
            return AdminHandlerResult(
                new_state=AdminSessionState.awaiting_content,
                outbound_text=_MSG_ASK_CONTENT,
                work_type=wt,
                contractor_id=deps.registered_contractor.id,
            )
        return AdminHandlerResult(
            new_state=AdminSessionState.awaiting_work_type,
            outbound_text=_MSG_ASK_WORK_TYPE,
            contractor_id=deps.registered_contractor.id,
        )

    if deps.registered_contractor is not None:
        return AdminHandlerResult(
            new_state=AdminSessionState.cancelled,
            outbound_text=_MSG_ONBOARD_ALREADY_REGISTERED,
        )
    return AdminHandlerResult(
        new_state=AdminSessionState.awaiting_business_name,
        outbound_text=_MSG_ONBOARD_BUSINESS,
    )


def handle_message(
    session: ContractorAdminSession,
    inbound: InboundMessage,
    deps: AdminHandlerDeps,
) -> AdminHandlerResult:
    if session.flow_type == AdminFlowType.manage_rates:
        return _handle_manage_rates(session, inbound, deps)
    return _handle_onboard(session, inbound, deps)


def _handle_manage_rates(
    session: ContractorAdminSession,
    inbound: InboundMessage,
    deps: AdminHandlerDeps,
) -> AdminHandlerResult:
    if session.state == AdminSessionState.awaiting_work_type:
        wt = parse_work_type(inbound.text or "")
        if wt is None:
            return AdminHandlerResult(
                new_state=AdminSessionState.awaiting_work_type,
                outbound_text=_MSG_ASK_WORK_TYPE,
            )
        return AdminHandlerResult(
            new_state=AdminSessionState.awaiting_content,
            outbound_text=_MSG_ASK_CONTENT,
            work_type=wt,
        )

    if session.state == AdminSessionState.awaiting_content:
        return _parse_rate_content(session, inbound, deps)

    if session.state == AdminSessionState.reviewing:
        return _handle_review(session, inbound, deps)

    return AdminHandlerResult(
        new_state=session.state,
        outbound_text="Send *manage-rates* to start a pricing update.",
    )


def _handle_onboard(
    session: ContractorAdminSession,
    inbound: InboundMessage,
    deps: AdminHandlerDeps,
) -> AdminHandlerResult:
    text = (inbound.text or "").strip()
    profile = dict(session.draft_profile or {})

    if session.state == AdminSessionState.awaiting_business_name:
        if len(text) < 2:
            return AdminHandlerResult(
                new_state=AdminSessionState.awaiting_business_name,
                outbound_text="Please enter a business name (at least 2 characters).",
            )
        profile["business_name"] = text
        return AdminHandlerResult(
            new_state=AdminSessionState.awaiting_city,
            outbound_text=_MSG_ONBOARD_CITY,
            draft_profile=profile,
        )

    if session.state == AdminSessionState.awaiting_city:
        profile["city"] = None if text.lower() == "skip" else text
        return AdminHandlerResult(
            new_state=AdminSessionState.awaiting_slug,
            outbound_text=_MSG_ONBOARD_SLUG,
            draft_profile=profile,
        )

    if session.state == AdminSessionState.awaiting_slug:
        slug = text.lower().strip()
        if not _SLUG_RE.match(slug):
            return AdminHandlerResult(
                new_state=AdminSessionState.awaiting_slug,
                outbound_text="Invalid slug. Use 3–64 lowercase letters, numbers, or hyphens.",
            )
        profile["whatsapp_link_slug"] = slug
        return AdminHandlerResult(
            new_state=AdminSessionState.awaiting_work_type,
            outbound_text=_MSG_ASK_WORK_TYPE,
            draft_profile=profile,
        )

    if session.state == AdminSessionState.awaiting_work_type:
        wt = parse_work_type(text)
        if wt is None:
            return AdminHandlerResult(
                new_state=AdminSessionState.awaiting_work_type,
                outbound_text=_MSG_ASK_WORK_TYPE,
            )
        return AdminHandlerResult(
            new_state=AdminSessionState.awaiting_content,
            outbound_text=_MSG_ASK_CONTENT,
            work_type=wt,
            draft_profile=profile,
        )

    if session.state == AdminSessionState.awaiting_content:
        result = _parse_rate_content(session, inbound, deps)
        if result.draft_profile is None:
            result = AdminHandlerResult(
                new_state=result.new_state,
                outbound_text=result.outbound_text,
                work_type=result.work_type,
                draft_rules=result.draft_rules,
                draft_profile=profile,
                parse_notes=result.parse_notes,
                validation_errors=result.validation_errors,
            )
        return result

    if session.state == AdminSessionState.reviewing:
        action = parse_admin_confirm(text)
        if action == AdminConfirmAction.cancel:
            return AdminHandlerResult(
                new_state=AdminSessionState.cancelled,
                outbound_text=_MSG_CANCELLED,
            )
        if action != AdminConfirmAction.save:
            return AdminHandlerResult(
                new_state=AdminSessionState.reviewing,
                outbound_text=format_profile_summary(profile, session.draft_rules or {}),
            )
        return _create_onboard_account(session, deps, profile)

    return AdminHandlerResult(
        new_state=session.state,
        outbound_text="Send *onboard* to start setup.",
    )


def _parse_rate_content(
    session: ContractorAdminSession,
    inbound: InboundMessage,
    deps: AdminHandlerDeps,
) -> AdminHandlerResult:
    content_text: str | None = None

    if inbound.message_type == "text" and inbound.text:
        content_text = inbound.text
    elif inbound.message_type == "document":
        doc = extract_document_info(inbound.raw)
        if doc is None:
            return AdminHandlerResult(
                new_state=AdminSessionState.awaiting_content,
                outbound_text=_MSG_UNSUPPORTED_DOC,
            )
        try:
            file_bytes, _ = deps.wa.download_media(doc.media_id)
            content_text = extract_text(file_bytes, doc.filename)
        except UnsupportedFormatError:
            return AdminHandlerResult(
                new_state=AdminSessionState.awaiting_content,
                outbound_text=_MSG_UNSUPPORTED_DOC,
            )
        except Exception as exc:
            logger.error("admin.document_download_failed", exc_info=True)
            return AdminHandlerResult(
                new_state=AdminSessionState.awaiting_content,
                outbound_text=f"Could not download file: {exc}",
            )
    else:
        return AdminHandlerResult(
            new_state=AdminSessionState.awaiting_content,
            outbound_text=_MSG_ASK_CONTENT,
        )

    work_type = session.work_type or WorkType.painting
    try:
        parsed = RateCardParser(deps.llm).parse(
            content_text,
            work_type_hint=work_type.value,
        )
    except Exception:
        logger.error("admin.rate_parse_failed", exc_info=True)
        return AdminHandlerResult(
            new_state=AdminSessionState.awaiting_content,
            outbound_text=_MSG_PARSE_FAILED,
        )

    if session.flow_type == AdminFlowType.onboard:
        summary = format_profile_summary(session.draft_profile or {}, parsed.rules)
    else:
        summary = format_rules_summary(
            parsed.rules, parsed.notes, parsed.validation_errors
        )

    return AdminHandlerResult(
        new_state=AdminSessionState.reviewing,
        outbound_text=summary,
        draft_rules=parsed.rules,
        parse_notes=parsed.notes,
        validation_errors=parsed.validation_errors,
    )


def _handle_review(
    session: ContractorAdminSession,
    inbound: InboundMessage,
    deps: AdminHandlerDeps,
) -> AdminHandlerResult:
    action = parse_admin_confirm(inbound.text or "")
    if action == AdminConfirmAction.cancel:
        return AdminHandlerResult(
            new_state=AdminSessionState.cancelled,
            outbound_text=_MSG_CANCELLED,
        )
    if action != AdminConfirmAction.save:
        return AdminHandlerResult(
            new_state=AdminSessionState.reviewing,
            outbound_text=format_rules_summary(
                session.draft_rules or {},
                session.parse_notes or [],
                session.validation_errors or [],
            ),
        )

    contractor_id = session.contractor_id
    if contractor_id is None and deps.registered_contractor:
        contractor_id = deps.registered_contractor.id
    if contractor_id is None or session.draft_rules is None or session.work_type is None:
        return AdminHandlerResult(
            new_state=AdminSessionState.cancelled,
            outbound_text="Missing data to save. Send *manage-rates* to try again.",
        )

    try:
        config = deps.onboarding.save_pricing_config(
            contractor_id=contractor_id,
            work_type=session.work_type,
            rules=session.draft_rules,
        )
        log_pricing_updated(deps.db, contractor_id, session.work_type, config.version)
    except Exception as exc:
        logger.error("admin.save_pricing_failed", exc_info=True)
        return AdminHandlerResult(
            new_state=AdminSessionState.reviewing,
            outbound_text=f"Could not save pricing: {exc}",
        )

    return AdminHandlerResult(
        new_state=AdminSessionState.completed,
        outbound_text=_MSG_SAVED.format(version=config.version),
    )


def _create_onboard_account(
    session: ContractorAdminSession,
    deps: AdminHandlerDeps,
    profile: dict,
) -> AdminHandlerResult:
    from app.services.whatsapp.phone import normalize_phone_e164

    phone = normalize_phone_e164(session.admin_phone)
    try:
        contractor = deps.onboarding.create_contractor(
            business_name=profile["business_name"],
            phone=phone,
            city=profile.get("city"),
            whatsapp_link_slug=profile["whatsapp_link_slug"],
            wa_phone_number_id=deps.tenant_contractor.wa_phone_number_id,
        )
        version = 1
        if session.draft_rules and session.work_type:
            config = deps.onboarding.save_pricing_config(
                contractor_id=contractor.id,
                work_type=session.work_type,
                rules=session.draft_rules,
            )
            version = config.version
            log_pricing_updated(
                deps.db,
                contractor.id,
                session.work_type,
                version,
            )
    except DuplicateError as exc:
        return AdminHandlerResult(
            new_state=AdminSessionState.awaiting_slug,
            outbound_text=f"{exc} Please send a different slug.",
        )
    except Exception as exc:
        logger.error("admin.create_contractor_failed", exc_info=True)
        return AdminHandlerResult(
            new_state=AdminSessionState.reviewing,
            outbound_text=f"Could not create account: {exc}",
        )

    bot = deps.tenant_contractor.wa_phone_number_id or "BOT_NUMBER"
    return AdminHandlerResult(
        new_state=AdminSessionState.completed,
        outbound_text=_MSG_ONBOARD_DONE.format(
            bot=bot,
            slug=contractor.whatsapp_link_slug,
            api_key=contractor.api_key,
        ),
        contractor_id=contractor.id,
    )
