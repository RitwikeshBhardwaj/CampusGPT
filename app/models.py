from pydantic import BaseModel


class Citation(BaseModel):
    number: int
    doc_name: str
    page: int
    passage: str


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool
    warning: str | None = None
    closest_source: Citation | None = None