from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, cast

from .models import MemoryMatch, utc_now


ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "seed_incidents.json"
LOCAL_MEMORY_PATH = ROOT / "data" / "local_memory.json"


class IncidentMemory:
    """Hindsight-first memory adapter with deterministic local JSON fallback."""

    def __init__(self) -> None:
        self.base_url = os.getenv("HINDSIGHT_BASE_URL", "http://localhost:8888")
        self.bank_id = os.getenv("HINDSIGHT_BANK_ID", "incident-memory-agent")
        self.client: Any | None = None
        self.status = "local fallback: Hindsight client unavailable"
        self.fallback_mode = True
        self._init_hindsight()

    def _init_hindsight(self) -> None:
        try:
            import httpx
            from hindsight_client import Hindsight  # type: ignore

            response = httpx.get(self.base_url, timeout=2)
            if response.status_code >= 500:
                raise RuntimeError(
                    f"Hindsight health check returned {response.status_code}"
                )
            self.client = Hindsight(base_url=self.base_url)
            self.status = f"connected to open-source Hindsight at {self.base_url} / bank {self.bank_id}"
            self.fallback_mode = False
        except Exception as exc:
            self.client = None
            self.status = (
                f"fallback mode: Hindsight not reachable ({exc.__class__.__name__})"
            )
            self.fallback_mode = True

    def close(self) -> None:
        if self.client is None:
            return
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    def recall(self, query: str, limit: int = 5) -> list[MemoryMatch]:
        if self.client is not None:
            try:
                raw = self.client.recall(bank_id=self.bank_id, query=query)
                matches = self._normalize_hindsight_results(raw)[:limit]
                if matches:
                    return matches
            except Exception as exc:
                self.status = (
                    f"fallback mode: Hindsight recall failed ({exc.__class__.__name__})"
                )
                self.fallback_mode = True
        return self._local_recall(query, limit)

    def retain(
        self,
        content: str,
        context: str = "incident memory",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if self.client is not None:
            try:
                self.client.retain(
                    bank_id=self.bank_id,
                    content=content,
                    context=context,
                    timestamp=utc_now(),
                )
                return "retained in Hindsight"
            except Exception as exc:
                self.status = (
                    f"fallback mode: Hindsight retain failed ({exc.__class__.__name__})"
                )
                self.fallback_mode = True
        item = {
            "title": context,
            "content": content,
            "metadata": metadata or {},
            "timestamp": utc_now(),
        }
        memories = self._load_local_retained_memory()
        if any(
            existing.get("title") == item["title"]
            and existing.get("content") == item["content"]
            for existing in memories
        ):
            return "local JSON fallback already had this memory"
        memories.append(item)
        LOCAL_MEMORY_PATH.write_text(json.dumps(memories, indent=2), encoding="utf-8")
        return "retained in local JSON fallback"

    def reflect(self, query: str, matches: list[MemoryMatch]) -> str:
        use_live_reflect = (
            os.getenv("HINDSIGHT_ENABLE_REFLECT_API", "false").lower() == "true"
        )
        if self.client is not None and use_live_reflect:
            try:
                reflection = self.client.reflect(bank_id=self.bank_id, query=query)
                return str(reflection)
            except Exception as exc:
                self.status = f"fallback mode: Hindsight reflect failed ({exc.__class__.__name__})"
                self.fallback_mode = True
        if not matches:
            return "No prior memory was strong enough to form a reflection; retain the final RCA after resolution."
        top = matches[0]
        return (
            f"Reflection from prior incidents: closest memory is '{top.title}' with score {top.score:.2f}. "
            "Use it to bias verification toward repeated root causes, but confirm with current evidence before remediation."
        )

    def seed(self) -> str:
        incidents = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        limit = int(os.getenv("HINDSIGHT_SEED_LIMIT", "0"))
        if limit > 0:
            incidents = incidents[:limit]
        if self.client is None:
            return (
                f"fallback mode: {len(incidents)} seed memories are available from "
                "data/seed_incidents.json; start Hindsight to retain them in a live bank"
            )
        delay_seconds = float(os.getenv("HINDSIGHT_SEED_DELAY_SECONDS", "0"))
        retained = 0
        for item in incidents:
            content = format_seed_memory(item)
            self.retain(
                content,
                context=f"seed incident: {item['service']} {item['error_type']}",
                metadata=item,
            )
            retained += 1
            if delay_seconds > 0 and retained < len(incidents):
                time.sleep(delay_seconds)
        return f"seeded {retained} incident memories"

    def _normalize_hindsight_results(self, raw: Any) -> list[MemoryMatch]:
        if raw is None:
            return []
        if isinstance(raw, list):
            candidates = raw
        elif isinstance(raw, dict):
            candidates = raw.get("results", raw.get("memories", []))
        elif hasattr(raw, "results"):
            candidates = getattr(raw, "results")
        else:
            candidates = [raw]
        matches: list[MemoryMatch] = []
        for idx, item in enumerate(candidates):
            if isinstance(item, str):
                content, title, score, metadata = (
                    item,
                    title_from_content(item, idx),
                    0.75,
                    {},
                )
            elif isinstance(item, dict):
                content = str(
                    item.get("content")
                    or item.get("text")
                    or item.get("memory")
                    or item
                )
                title = str(
                    item.get("title")
                    or item.get("context")
                    or title_from_content(content, idx)
                )
                score = float(
                    item.get("score")
                    or item.get("similarity")
                    or item.get("relevance")
                    or max(0.4, 0.85 - idx * 0.08)
                )
                metadata = (
                    item.get("metadata")
                    if isinstance(item.get("metadata"), dict)
                    else {}
                )
            elif hasattr(item, "text"):
                content = str(getattr(item, "text"))
                title = title_from_content(content, idx)
                score = float(
                    getattr(item, "score", None)
                    or getattr(item, "similarity", None)
                    or max(0.4, 0.85 - idx * 0.08)
                )
                metadata = {
                    "hindsight_id": str(getattr(item, "id", "")),
                    "hindsight_type": str(getattr(item, "type", "")),
                }
            else:
                content, title, score, metadata = (
                    str(item),
                    title_from_content(str(item), idx),
                    0.6,
                    {},
                )
            matches.append(
                MemoryMatch(
                    title=title,
                    content=content,
                    score=min(score, 1.0),
                    source="hindsight",
                    metadata=cast(dict[str, Any], metadata),
                )
            )
        return dedupe_matches(matches)

    def _load_seed_memory(self) -> list[dict[str, Any]]:
        memories: list[dict[str, Any]] = []
        if SEED_PATH.exists():
            for item in json.loads(SEED_PATH.read_text(encoding="utf-8")):
                memories.append(
                    {
                        "title": item["title"],
                        "content": format_seed_memory(item),
                        "metadata": item,
                    }
                )
        return memories

    def _load_local_retained_memory(self) -> list[dict[str, Any]]:
        if not LOCAL_MEMORY_PATH.exists():
            return []
        raw = json.loads(LOCAL_MEMORY_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []

    def _load_local_memory(self) -> list[dict[str, Any]]:
        memories = self._load_seed_memory()
        seen = {memory_key(item) for item in memories}
        retained: list[dict[str, Any]] = []
        changed = False
        for item in self._load_local_retained_memory():
            key = memory_key(item)
            if key in seen:
                changed = True
                continue
            seen.add(key)
            retained.append(item)
        if changed:
            LOCAL_MEMORY_PATH.write_text(
                json.dumps(retained, indent=2), encoding="utf-8"
            )
        memories.extend(retained)
        return memories

    def _local_recall(self, query: str, limit: int) -> list[MemoryMatch]:
        terms = {
            token.strip(".,:;()[]{}\"'").lower()
            for token in query.split()
            if len(token) > 2 and token.lower() not in STOPWORDS
        }
        scored: list[MemoryMatch] = []
        for item in self._load_local_memory():
            blob = f"{item.get('title', '')} {item.get('content', '')}".lower()
            overlap = sum(1 for term in terms if term in blob)
            if overlap < 2:
                continue
            score = min(0.95, 0.25 + overlap / max(len(terms), 1))
            if score < MIN_LOCAL_RECALL_SCORE:
                continue
            local_metadata = (
                item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            )
            scored.append(
                MemoryMatch(
                    title=str(item.get("title", "local memory")),
                    content=str(item.get("content", "")),
                    score=score,
                    source="local-json",
                    metadata=cast(dict[str, Any], local_metadata),
                )
            )
        return dedupe_matches(
            sorted(scored, key=lambda match: match.score, reverse=True)
        )[:limit]


def format_seed_memory(item: dict[str, Any]) -> str:
    return (
        f"Incident: {item['title']}\n"
        f"Service: {item['service']} in {item['environment']} | Severity: {item['severity']} | Type: {item['type']}\n"
        f"Symptoms: {item['symptoms']}\n"
        f"Root cause: {item['root_cause']}\n"
        f"Verification commands: {'; '.join(item['verification_commands'])}\n"
        f"Resolution: {item['resolution']}\n"
        f"Lessons learned: {item['lessons_learned']}"
    )


def memory_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("title", "")), str(item.get("content", "")))


def dedupe_matches(matches: list[MemoryMatch]) -> list[MemoryMatch]:
    unique: list[MemoryMatch] = []
    seen: set[tuple[str, str]] = set()
    for match in matches:
        key = (match.title, match.content)
        if key in seen:
            continue
        seen.add(key)
        unique.append(match)
    return unique


def title_from_content(content: str, idx: int) -> str:
    compact = " ".join(content.split())
    if not compact:
        return f"Hindsight memory {idx + 1}"
    return compact[:84] + ("..." if len(compact) > 84 else "")


STOPWORDS = {
    "after",
    "alert",
    "api",
    "app",
    "and",
    "are",
    "but",
    "can",
    "for",
    "from",
    "high",
    "low",
    "medium",
    "not",
    "prod",
    "production",
    "service",
    "sev",
    "the",
    "this",
    "with",
}

MIN_LOCAL_RECALL_SCORE = 0.5
