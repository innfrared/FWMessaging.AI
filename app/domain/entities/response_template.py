from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseTemplate:
    text: str
    required_substrings: list[str]
