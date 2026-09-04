from pydantic import BaseModel


class Message(BaseModel):
    role: str
    content: str | None = None


class ProxyRequest(BaseModel):
    model: str
    messages: list[Message]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False

    agent_id: str | None = None
    session_id: str | None = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Choice(BaseModel):
    index: int = 0
    message: Message
    finish_reason: str | None = None


class StrataMetadata(BaseModel):
    request_id: str
    latency_ms: float
    upstream_model: str


class ProxyResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage | None = None

    strata: StrataMetadata | None = None


class TelemetryEvent(BaseModel):
    request_id: str
    timestamp: str
    agent_id: str | None = None
    session_id: str | None = None
    model: str
    tokens_in: int
    tokens_out: int
    redacted_tokens: int = 0
    latency_ms: float
    status_code: int
    upstream_url: str
    sub_status: str = ""
