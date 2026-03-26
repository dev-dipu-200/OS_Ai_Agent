import re
from collections.abc import Sequence
from typing import Any

from call_analysis_store import (
    StoredAnalysisRef,
    analysis_db_health_async,
    fetch_analysis_by_id_async,
    fetch_latest_analysis_async,
    store_call_analysis as store_call_analysis_record,
)

_STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'can', 'for', 'from', 'how', 'i',
    'in', 'is', 'it', 'me', 'my', 'of', 'on', 'or', 'our', 'please', 'the', 'this',
    'to', 'we', 'what', 'when', 'where', 'which', 'who', 'why', 'with', 'you', 'your'
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9']+", text.lower())


def _keywords(text: str) -> set[str]:
    return {token for token in _tokenize(text) if len(token) > 2 and token not in _STOP_WORDS}


def _score_answer(question: str, answer: str) -> dict[str, Any]:
    answer = answer.strip()
    if not answer:
        return {
            'score': 0,
            'matched_keywords': [],
            'question_keywords': [],
            'answer_keywords': [],
            'notes': 'No user answer captured for this prompt.',
        }

    question_keywords = _keywords(question)
    answer_keywords = _keywords(answer)
    matched_keywords = sorted(question_keywords & answer_keywords)

    base_score = 30
    overlap_score = 0
    if question_keywords:
        overlap_ratio = len(matched_keywords) / len(question_keywords)
        overlap_score = round(overlap_ratio * 40)

    length_score = min(len(answer.split()) * 3, 30)
    score = min(base_score + overlap_score + length_score, 100)

    notes = 'Answer captured.'
    if question_keywords and not matched_keywords:
        notes = 'Answer captured, but keyword overlap with the prompt is low.'

    return {
        'score': score,
        'matched_keywords': matched_keywords,
        'question_keywords': sorted(question_keywords),
        'answer_keywords': sorted(answer_keywords),
        'notes': notes,
    }


def build_call_analysis(
    *,
    room_name: str,
    participant_identity: str | None,
    participant_kind: str | None,
    started_at: float,
    ended_at: float,
    close_reason: str,
    conversation: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    qa_pairs: list[dict[str, Any]] = []
    pending_question: dict[str, Any] | None = None

    for entry in conversation:
        role = entry.get('role')
        text = (entry.get('text') or '').strip()
        if not text:
            continue

        if role == 'assistant':
            if pending_question is not None:
                qa_pairs.append(
                    {
                        'question': pending_question['text'],
                        'question_at': pending_question['created_at'],
                        'answer': '',
                        'answer_at': None,
                        **_score_answer(pending_question['text'], ''),
                    }
                )
            pending_question = entry
            continue

        if role == 'user' and pending_question is not None:
            qa_pairs.append(
                {
                    'question': pending_question['text'],
                    'question_at': pending_question['created_at'],
                    'answer': text,
                    'answer_at': entry.get('created_at'),
                    **_score_answer(pending_question['text'], text),
                }
            )
            pending_question = None

    if pending_question is not None:
        qa_pairs.append(
            {
                'question': pending_question['text'],
                'question_at': pending_question['created_at'],
                'answer': '',
                'answer_at': None,
                **_score_answer(pending_question['text'], ''),
            }
        )

    overall_score = round(
        sum(pair['score'] for pair in qa_pairs) / len(qa_pairs), 2
    ) if qa_pairs else 0.0

    answered_pairs = sum(1 for pair in qa_pairs if pair['answer'])
    unanswered_pairs = len(qa_pairs) - answered_pairs

    return {
        'room_name': room_name,
        'participant_identity': participant_identity,
        'participant_kind': participant_kind,
        'started_at': started_at,
        'ended_at': ended_at,
        'duration_seconds': round(max(ended_at - started_at, 0), 2),
        'close_reason': close_reason,
        'overall_match_score': overall_score,
        'total_pairs': len(qa_pairs),
        'answered_pairs': answered_pairs,
        'unanswered_pairs': unanswered_pairs,
        'conversation': list(conversation),
        'qa_analysis': qa_pairs,
    }


def store_call_analysis(analysis: dict[str, Any]) -> StoredAnalysisRef:
    return store_call_analysis_record(analysis)


async def fetch_latest_analysis() -> dict[str, Any] | None:
    return await fetch_latest_analysis_async()


async def fetch_analysis_by_id(analysis_id: int) -> dict[str, Any] | None:
    return await fetch_analysis_by_id_async(analysis_id)


async def analysis_db_health() -> dict[str, Any]:
    return await analysis_db_health_async()
