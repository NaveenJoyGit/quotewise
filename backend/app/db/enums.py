import enum


class ApprovalMode(str, enum.Enum):
    always_approve = "always_approve"
    auto_approve_above_confidence = "auto_approve_above_confidence"


class SessionSource(str, enum.Enum):
    buyer_direct = "buyer_direct"
    contractor_forward = "contractor_forward"


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


class AdminFlowType(str, enum.Enum):
    manage_rates = "manage_rates"
    onboard = "onboard"


class AdminSessionState(str, enum.Enum):
    awaiting_business_name = "awaiting_business_name"
    awaiting_city = "awaiting_city"
    awaiting_slug = "awaiting_slug"
    awaiting_work_type = "awaiting_work_type"
    awaiting_content = "awaiting_content"
    reviewing = "reviewing"
    creating_account = "creating_account"
    completed = "completed"
    cancelled = "cancelled"
