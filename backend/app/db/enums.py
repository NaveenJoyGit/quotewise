import enum


class WorkType(str, enum.Enum):
    painting = "painting"
    false_ceiling = "false_ceiling"


class ApprovalMode(str, enum.Enum):
    always_approve = "always_approve"
    auto_approve_above_confidence = "auto_approve_above_confidence"


class SessionState(str, enum.Enum):
    greeting = "greeting"
    identifying_scope = "identifying_scope"
    collecting_inputs = "collecting_inputs"
    clarifying = "clarifying"
    ready_to_quote = "ready_to_quote"
    awaiting_approval = "awaiting_approval"
    quote_delivered = "quote_delivered"
    closed = "closed"


class MessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class MessageType(str, enum.Enum):
    text = "text"
    voice = "voice"
    image = "image"
    document = "document"


class QuoteStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    sent = "sent"
    expired = "expired"
