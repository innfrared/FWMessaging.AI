from dataclasses import dataclass


@dataclass(frozen=True)
class QAItem:
    order: int
    question: str
    answer: str

    @staticmethod
    def normalize(order: int, question: str, answer: str) -> "QAItem":
        q = (question or "").strip()
        a = (answer or "").strip()
        return QAItem(order=order, question=q, answer=a)

