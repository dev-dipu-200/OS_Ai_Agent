import asyncio
import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass
class StoredAnalysisRef:
    backend: str
    analysis_id: int
    location: str


def _get_backend() -> str:
    return os.getenv('CALL_ANALYSIS_DB_BACKEND', 'sqlite').strip().lower()


def _sqlite_db_path() -> str:
    default_path = os.path.join(os.getcwd(), 'data', 'call_analysis.db')
    path = os.getenv('CALL_ANALYSIS_SQLITE_PATH', default_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _init_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS call_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_name TEXT NOT NULL,
            participant_identity TEXT,
            participant_kind TEXT,
            started_at REAL NOT NULL,
            ended_at REAL NOT NULL,
            duration_seconds REAL NOT NULL,
            close_reason TEXT NOT NULL,
            overall_match_score REAL NOT NULL,
            total_pairs INTEGER NOT NULL,
            answered_pairs INTEGER NOT NULL,
            unanswered_pairs INTEGER NOT NULL,
            analysis_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS call_conversation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            item_index INTEGER NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at REAL,
            extra_json TEXT,
            FOREIGN KEY (analysis_id) REFERENCES call_analyses(id) ON DELETE CASCADE
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS call_qa_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            pair_index INTEGER NOT NULL,
            question TEXT NOT NULL,
            question_at REAL,
            answer TEXT,
            answer_at REAL,
            score REAL NOT NULL,
            matched_keywords_json TEXT NOT NULL,
            question_keywords_json TEXT NOT NULL,
            answer_keywords_json TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (analysis_id) REFERENCES call_analyses(id) ON DELETE CASCADE
        )
        '''
    )
    conn.commit()


def _store_sqlite(analysis: dict[str, Any]) -> StoredAnalysisRef:
    db_path = _sqlite_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON')
    _init_sqlite(conn)

    cursor = conn.execute(
        '''
        INSERT INTO call_analyses (
            room_name,
            participant_identity,
            participant_kind,
            started_at,
            ended_at,
            duration_seconds,
            close_reason,
            overall_match_score,
            total_pairs,
            answered_pairs,
            unanswered_pairs,
            analysis_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            analysis['room_name'],
            analysis.get('participant_identity'),
            analysis.get('participant_kind'),
            analysis['started_at'],
            analysis['ended_at'],
            analysis['duration_seconds'],
            analysis['close_reason'],
            analysis['overall_match_score'],
            analysis['total_pairs'],
            analysis['answered_pairs'],
            analysis['unanswered_pairs'],
            json.dumps(analysis, ensure_ascii=True),
        ),
    )
    analysis_id = int(cursor.lastrowid)

    conn.executemany(
        '''
        INSERT INTO call_conversation_items (
            analysis_id,
            item_index,
            role,
            text,
            created_at,
            extra_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''',
        [
            (
                analysis_id,
                index,
                item.get('role'),
                item.get('text', ''),
                item.get('created_at'),
                json.dumps(item.get('extra'), ensure_ascii=True) if item.get('extra') is not None else None,
            )
            for index, item in enumerate(analysis.get('conversation', []))
        ],
    )

    conn.executemany(
        '''
        INSERT INTO call_qa_scores (
            analysis_id,
            pair_index,
            question,
            question_at,
            answer,
            answer_at,
            score,
            matched_keywords_json,
            question_keywords_json,
            answer_keywords_json,
            notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        [
            (
                analysis_id,
                index,
                pair.get('question', ''),
                pair.get('question_at'),
                pair.get('answer'),
                pair.get('answer_at'),
                pair.get('score', 0),
                json.dumps(pair.get('matched_keywords', []), ensure_ascii=True),
                json.dumps(pair.get('question_keywords', []), ensure_ascii=True),
                json.dumps(pair.get('answer_keywords', []), ensure_ascii=True),
                pair.get('notes'),
            )
            for index, pair in enumerate(analysis.get('qa_analysis', []))
        ],
    )

    conn.commit()
    conn.close()
    return StoredAnalysisRef(backend='sqlite', analysis_id=analysis_id, location=db_path)


def _fetch_latest_sqlite() -> dict[str, Any] | None:
    db_path = _sqlite_db_path()
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    _init_sqlite(conn)
    cursor = conn.execute('SELECT id, analysis_json FROM call_analyses ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None

    analysis_id, analysis_json = row
    analysis = json.loads(analysis_json)
    analysis['_analysis_id'] = analysis_id
    analysis['_backend'] = 'sqlite'
    analysis['_location'] = db_path
    return analysis


def _fetch_by_id_sqlite(analysis_id: int) -> dict[str, Any] | None:
    db_path = _sqlite_db_path()
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    _init_sqlite(conn)
    cursor = conn.execute('SELECT id, analysis_json FROM call_analyses WHERE id = ?', (analysis_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None

    analysis_id, analysis_json = row
    analysis = json.loads(analysis_json)
    analysis['_analysis_id'] = analysis_id
    analysis['_backend'] = 'sqlite'
    analysis['_location'] = db_path
    return analysis


def _postgres_dsn() -> str:
    dsn = os.getenv('CALL_ANALYSIS_POSTGRES_DSN') or os.getenv('DATABASE_URL')
    if not dsn:
        raise RuntimeError(
            'PostgreSQL backend selected but CALL_ANALYSIS_POSTGRES_DSN or DATABASE_URL is not set.'
        )
    return dsn


def _init_postgres(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS call_analyses (
                id BIGSERIAL PRIMARY KEY,
                room_name TEXT NOT NULL,
                participant_identity TEXT,
                participant_kind TEXT,
                started_at DOUBLE PRECISION NOT NULL,
                ended_at DOUBLE PRECISION NOT NULL,
                duration_seconds DOUBLE PRECISION NOT NULL,
                close_reason TEXT NOT NULL,
                overall_match_score DOUBLE PRECISION NOT NULL,
                total_pairs INTEGER NOT NULL,
                answered_pairs INTEGER NOT NULL,
                unanswered_pairs INTEGER NOT NULL,
                analysis_json JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            '''
        )
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS call_conversation_items (
                id BIGSERIAL PRIMARY KEY,
                analysis_id BIGINT NOT NULL REFERENCES call_analyses(id) ON DELETE CASCADE,
                item_index INTEGER NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at DOUBLE PRECISION,
                extra_json JSONB
            )
            '''
        )
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS call_qa_scores (
                id BIGSERIAL PRIMARY KEY,
                analysis_id BIGINT NOT NULL REFERENCES call_analyses(id) ON DELETE CASCADE,
                pair_index INTEGER NOT NULL,
                question TEXT NOT NULL,
                question_at DOUBLE PRECISION,
                answer TEXT,
                answer_at DOUBLE PRECISION,
                score DOUBLE PRECISION NOT NULL,
                matched_keywords_json JSONB NOT NULL,
                question_keywords_json JSONB NOT NULL,
                answer_keywords_json JSONB NOT NULL,
                notes TEXT
            )
            '''
        )
    conn.commit()


def _store_postgres(analysis: dict[str, Any]) -> StoredAnalysisRef:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            'PostgreSQL backend selected but psycopg is not installed. Install requirements and retry.'
        ) from exc

    dsn = _postgres_dsn()
    with psycopg.connect(dsn) as conn:
        _init_postgres(conn)
        with conn.cursor() as cur:
            cur.execute(
                '''
                INSERT INTO call_analyses (
                    room_name,
                    participant_identity,
                    participant_kind,
                    started_at,
                    ended_at,
                    duration_seconds,
                    close_reason,
                    overall_match_score,
                    total_pairs,
                    answered_pairs,
                    unanswered_pairs,
                    analysis_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                ''',
                (
                    analysis['room_name'],
                    analysis.get('participant_identity'),
                    analysis.get('participant_kind'),
                    analysis['started_at'],
                    analysis['ended_at'],
                    analysis['duration_seconds'],
                    analysis['close_reason'],
                    analysis['overall_match_score'],
                    analysis['total_pairs'],
                    analysis['answered_pairs'],
                    analysis['unanswered_pairs'],
                    json.dumps(analysis, ensure_ascii=True),
                ),
            )
            analysis_id = int(cur.fetchone()[0])

            for index, item in enumerate(analysis.get('conversation', [])):
                cur.execute(
                    '''
                    INSERT INTO call_conversation_items (
                        analysis_id,
                        item_index,
                        role,
                        text,
                        created_at,
                        extra_json
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ''',
                    (
                        analysis_id,
                        index,
                        item.get('role'),
                        item.get('text', ''),
                        item.get('created_at'),
                        json.dumps(item.get('extra'), ensure_ascii=True) if item.get('extra') is not None else None,
                    ),
                )

            for index, pair in enumerate(analysis.get('qa_analysis', [])):
                cur.execute(
                    '''
                    INSERT INTO call_qa_scores (
                        analysis_id,
                        pair_index,
                        question,
                        question_at,
                        answer,
                        answer_at,
                        score,
                        matched_keywords_json,
                        question_keywords_json,
                        answer_keywords_json,
                        notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                    ''',
                    (
                        analysis_id,
                        index,
                        pair.get('question', ''),
                        pair.get('question_at'),
                        pair.get('answer'),
                        pair.get('answer_at'),
                        pair.get('score', 0),
                        json.dumps(pair.get('matched_keywords', []), ensure_ascii=True),
                        json.dumps(pair.get('question_keywords', []), ensure_ascii=True),
                        json.dumps(pair.get('answer_keywords', []), ensure_ascii=True),
                        pair.get('notes'),
                    ),
                )
        conn.commit()
    return StoredAnalysisRef(backend='postgres', analysis_id=analysis_id, location='call_analyses')


def _fetch_latest_postgres() -> dict[str, Any] | None:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            'PostgreSQL backend selected but psycopg is not installed. Install requirements and retry.'
        ) from exc

    dsn = _postgres_dsn()
    with psycopg.connect(dsn) as conn:
        _init_postgres(conn)
        with conn.cursor() as cur:
            cur.execute('SELECT id, analysis_json FROM call_analyses ORDER BY id DESC LIMIT 1')
            row = cur.fetchone()
    if not row:
        return None

    analysis_id, analysis_json = row
    analysis = json.loads(analysis_json)
    analysis['_analysis_id'] = analysis_id
    analysis['_backend'] = 'postgres'
    analysis['_location'] = 'call_analyses'
    return analysis


def _fetch_by_id_postgres(analysis_id: int) -> dict[str, Any] | None:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            'PostgreSQL backend selected but psycopg is not installed. Install requirements and retry.'
        ) from exc

    dsn = _postgres_dsn()
    with psycopg.connect(dsn) as conn:
        _init_postgres(conn)
        with conn.cursor() as cur:
            cur.execute('SELECT id, analysis_json FROM call_analyses WHERE id = %s', (analysis_id,))
            row = cur.fetchone()
    if not row:
        return None

    analysis_id, analysis_json = row
    analysis = json.loads(analysis_json)
    analysis['_analysis_id'] = analysis_id
    analysis['_backend'] = 'postgres'
    analysis['_location'] = 'call_analyses'
    return analysis


def store_call_analysis(analysis: dict[str, Any]) -> StoredAnalysisRef:
    backend = _get_backend()
    if backend == 'postgres':
        return _store_postgres(analysis)
    if backend != 'sqlite':
        raise RuntimeError("Unsupported CALL_ANALYSIS_DB_BACKEND. Use 'sqlite' or 'postgres'.")
    return _store_sqlite(analysis)


def fetch_latest_analysis() -> dict[str, Any] | None:
    backend = _get_backend()
    if backend == 'postgres':
        return _fetch_latest_postgres()
    if backend != 'sqlite':
        raise RuntimeError("Unsupported CALL_ANALYSIS_DB_BACKEND. Use 'sqlite' or 'postgres'.")
    return _fetch_latest_sqlite()


def fetch_analysis_by_id(analysis_id: int) -> dict[str, Any] | None:
    backend = _get_backend()
    if backend == 'postgres':
        return _fetch_by_id_postgres(analysis_id)
    if backend != 'sqlite':
        raise RuntimeError("Unsupported CALL_ANALYSIS_DB_BACKEND. Use 'sqlite' or 'postgres'.")
    return _fetch_by_id_sqlite(analysis_id)


def _test_postgres_connection_sync() -> None:
    import psycopg

    dsn = _postgres_dsn()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()


def test_postgres_connection() -> None:
    try:
        import psycopg  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            'PostgreSQL backend selected but psycopg is not installed. Install requirements and retry.'
        ) from exc
    _test_postgres_connection_sync()


def test_postgres_connection_async() -> asyncio.Future:
    return asyncio.to_thread(_test_postgres_connection_sync)


def fetch_latest_analysis_async() -> asyncio.Future:
    return asyncio.to_thread(fetch_latest_analysis)


def fetch_analysis_by_id_async(analysis_id: int) -> asyncio.Future:
    return asyncio.to_thread(fetch_analysis_by_id, analysis_id)


def analysis_db_health() -> dict[str, Any]:
    backend = _get_backend()
    try:
        if backend == 'postgres':
            test_postgres_connection()
            return {'backend': backend, 'ok': True}
        if backend != 'sqlite':
            return {'backend': backend, 'ok': False, 'error': 'Unsupported backend'}
        db_path = _sqlite_db_path()
        conn = sqlite3.connect(db_path)
        _init_sqlite(conn)
        conn.execute('SELECT 1')
        conn.close()
        return {'backend': backend, 'ok': True, 'path': db_path}
    except Exception as exc:
        return {'backend': backend, 'ok': False, 'error': str(exc)}


def analysis_db_health_async() -> asyncio.Future:
    return asyncio.to_thread(analysis_db_health)
