from __future__ import annotations

import json
import os
import time
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from .models import AlertFingerprint, MemoryMatch, TriageDecision, utc_now


ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "seed_incidents.json"
LOCAL_MEMORY_PATH = ROOT / "data" / "local_memory.json"


def _run_hindsight_async(coro_factory: Any) -> Any:
    """Run a hindsight-client async call in a way that survives Python 3.14
    + aiohttp's strict task requirement.

    The SDK's aiohttp session is bound to whatever event loop existed when
    ``Hindsight()`` was constructed. Calling ``arecall``/``aretain`` from a
    different loop later (which is what happens once FastAPI starts spinning
    up worker threads) raises
    ``RuntimeError: Timeout context manager should be used inside a task``.

    To sidestep this, every Hindsight call accepts a *factory* callable that
    creates a fresh SDK client AND runs the desired async method, then
    closes the client — all inside a single ``asyncio.run`` event loop.
    The TCP overhead of recreating the client per call is small (Hindsight
    is HTTP-keepalive-irrelevant on a per-request basis).

    ``coro_factory`` is an ``async def`` function (no args) that returns the
    coroutine result. It MUST construct the SDK client itself.
    """
    import asyncio
    import concurrent.futures

    async def _wrap() -> Any:
        return await coro_factory()

    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False

    if not running:
        return asyncio.run(_wrap())

    # An event loop is already running in this thread (e.g., we're being
    # called from inside an async route handler). Hand off to a dedicated
    # worker thread that will create and run its own loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _wrap()).result()


def _build_hindsight_client(base_url: str, api_key: str) -> Any:
    """Return a Hindsight client configured for the given base_url + api_key.

    Probes native ``api_key=`` support on the SDK. If the SDK constructor
    rejects the kwarg with TypeError, fall back to injecting the
    ``Authorization: Bearer ${api_key}`` header into the SDK's underlying
    httpx client. Logs the SDK shape and returns the bare client (no header
    injection) if neither attribute is present, so the caller can still flip
    to fallback mode without crashing.
    """
    from hindsight_client import Hindsight  # type: ignore

    try:
        return Hindsight(base_url=base_url, api_key=api_key)
    except TypeError:
        client = Hindsight(base_url=base_url)
        underlying = getattr(client, "_client", None) or getattr(client, "client", None)
        if underlying is not None and api_key:
            try:
                underlying.headers["Authorization"] = f"Bearer {api_key}"
            except Exception:
                pass
        return client


class IncidentMemory:
    """Hindsight Cloud-first memory adapter with deterministic local JSON fallback."""

    def __init__(self) -> None:
        self.base_url = os.getenv(
            "HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"
        )
        self.bank_id = os.getenv("HINDSIGHT_BANK_ID", "openrecall")
        self.api_key: str = ""
        self.client: Any | None = None
        self.status = "local fallback: Hindsight client unavailable"
        self.fallback_mode = True
        self._dedupe_index: set[tuple[str, str, str]] = set()
        self._init_hindsight()

    def _init_hindsight(self) -> None:
        self.api_key = os.getenv("HINDSIGHT_API_KEY", "").strip()
        if not self.api_key:
            self.client = None
            self.fallback_mode = True
            self.status = "fallback mode: HINDSIGHT_API_KEY unset"
            return

        try:
            import httpx

            # Health probe; treat 401/403 as host-up (key issue is separate).
            response = httpx.head(
                self.base_url,
                timeout=2,
                headers={"Authorization": f"Bearer {self.api_key}"},
                follow_redirects=True,
            )
            if response.status_code >= 500:
                raise RuntimeError(
                    f"Hindsight health check returned {response.status_code}"
                )
            self.client = _build_hindsight_client(self.base_url, self.api_key)
            self.fallback_mode = False
            self.status = (
                f"connected to Hindsight Cloud at {self.base_url} / bank {self.bank_id}"
            )
        except Exception as exc:
            self.client = None
            self.fallback_mode = True
            self.status = (
                f"fallback mode: Hindsight Cloud unreachable ({exc.__class__.__name__})"
            )

    def close(self) -> None:
        if self.client is None:
            return
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    def _flip_to_fallback(self, exc: Exception, where: str) -> None:
        """Switch to fallback mode for the remainder of the session.

        Per R11.3: when any Hindsight Cloud request fails, the adapter SHALL
        switch to the Local_Fallback_Store for the remainder of the session.
        Calling close() on the SDK client and dropping the reference prevents
        further calls from re-attempting Hindsight; subsequent calls take the
        local-fallback branch in recall/retain.

        Logs the full traceback to stderr so operators can diagnose Hindsight
        Cloud issues without having to re-attach a debugger.
        """
        import sys
        import traceback

        self.fallback_mode = True
        self.status = (
            f"fallback mode: Hindsight {where} failed "
            f"({exc.__class__.__name__}: {exc!s})"
        )
        print(
            f"[OpenRecall] {self.status}",
            file=sys.stderr,
        )
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        if self.client is not None:
            close = getattr(self.client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
            self.client = None

    def recall(self, query: str, limit: int = 5) -> list[MemoryMatch]:
        if self.client is not None:
            try:
                async def _do_recall() -> Any:
                    fresh = _build_hindsight_client(self.base_url, self.api_key)
                    try:
                        return await fresh.arecall(
                            bank_id=self.bank_id, query=query
                        )
                    finally:
                        aclose = getattr(fresh, "aclose", None)
                        if callable(aclose):
                            try:
                                await aclose()
                            except Exception:
                                pass

                raw = _run_hindsight_async(_do_recall)
                matches = self._normalize_hindsight_results(raw)[:limit]
                if matches:
                    return matches
            except Exception as exc:
                self._flip_to_fallback(exc, "recall")
        return self._local_recall(query, limit)

    def recall_by_fingerprint(
        self, fingerprint: AlertFingerprint, limit: int = 5
    ) -> list[MemoryMatch]:
        """Recall memories ranked by fingerprint overlap.

        Tries Hindsight Cloud first when the client is initialized. On any
        exception OR an empty cloud result, falls back to the local store.
        The local-recall query is built from the canonical fingerprint string
        plus all six field values concatenated so the existing keyword-overlap
        scorer has terms to match against.
        """
        from .fingerprint import format_fingerprint  # local import avoids cycle

        canonical = format_fingerprint(fingerprint)

        if self.client is not None:
            try:
                async def _do_recall() -> Any:
                    fresh = _build_hindsight_client(self.base_url, self.api_key)
                    try:
                        return await fresh.arecall(
                            bank_id=self.bank_id, query=canonical
                        )
                    finally:
                        aclose = getattr(fresh, "aclose", None)
                        if callable(aclose):
                            try:
                                await aclose()
                            except Exception:
                                pass

                raw = _run_hindsight_async(_do_recall)
                matches = self._normalize_hindsight_results(raw)[:limit]
                if matches:
                    return matches
            except Exception as exc:
                self._flip_to_fallback(exc, "recall")

        # Local fallback: build a richer query string so the keyword scorer fires.
        parts = [
            fingerprint.error_class,
            fingerprint.service_role,
            fingerprint.dependency_pattern,
            fingerprint.signal_shape,
            fingerprint.attack_pattern,
            fingerprint.environment,
        ]
        local_query = " ".join(p for p in parts if p)
        return self._local_recall(local_query, limit)

    def recall_by_decision(
        self,
        fingerprint: AlertFingerprint,
        decision: TriageDecision,
        limit: int = 5,
    ) -> list[MemoryMatch]:
        """Recall memories matching the fingerprint AND filtered to one TriageDecision.

        Over-fetches then post-filters so the result respects ``limit`` even when
        Hindsight returns mixed-decision matches.
        """
        matches = self.recall_by_fingerprint(
            fingerprint, limit=max(limit * 2, limit + 5)
        )
        filtered = [
            m for m in matches if m.metadata.get("triage_decision") == decision
        ]
        return filtered[:limit]

    def retain(
        self,
        content: str,
        context: str = "incident memory",
        metadata: dict[str, Any] | None = None,
        *,
        fingerprint: AlertFingerprint | None = None,
        decision: TriageDecision | None = None,
        dead_ends: list[str] | None = None,
        analyst_id: str | None = None,
        business_impact_minutes: int | None = None,
    ) -> str:
        from .fingerprint import format_fingerprint  # local import avoids cycle

        canonical = format_fingerprint(fingerprint) if fingerprint is not None else ""
        decision_key = decision or ""
        content_hash = sha256(content.encode("utf-8")).hexdigest()
        dedupe_key = (canonical, decision_key, content_hash)

        if dedupe_key in self._dedupe_index:
            return "skipped duplicate"
        self._dedupe_index.add(dedupe_key)

        # Build the metadata block. New keyword-only fields take precedence on key
        # clash so existing call sites keep their original behavior unless they
        # pass the new kwargs.
        new_metadata: dict[str, Any] = {
            "fingerprint_canonical": canonical,
            "triage_decision": decision,
            "dead_ends": list(dead_ends) if dead_ends else [],
            "analyst_id": analyst_id,
            "business_impact_minutes": business_impact_minutes,
        }
        if metadata is None:
            merged_metadata: dict[str, Any] = new_metadata
        else:
            merged_metadata = {**metadata, **new_metadata}

        # Hindsight Cloud's SDK validates metadata as dict[str, str]: drop None
        # values entirely and coerce lists / ints / bools to JSON / decimal
        # strings so the call doesn't trip a Pydantic ValidationError on the
        # client side. The richer Python-typed metadata is preserved for the
        # local fallback record so MemoryMatch.metadata still surfaces lists.
        def _coerce_for_cloud(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, str):
                return value
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, (list, tuple, set, dict)):
                return json.dumps(list(value) if isinstance(value, set) else value, sort_keys=True)
            return str(value)

        cloud_metadata: dict[str, str] = {}
        for k, v in merged_metadata.items():
            coerced = _coerce_for_cloud(v)
            if coerced is not None and coerced != "":
                cloud_metadata[str(k)] = coerced

        if self.client is not None:
            try:
                async def _do_retain_with_metadata() -> Any:
                    fresh = _build_hindsight_client(self.base_url, self.api_key)
                    try:
                        return await fresh.aretain(
                            bank_id=self.bank_id,
                            content=content,
                            context=context,
                            timestamp=utc_now(),
                            metadata=cloud_metadata,
                        )
                    finally:
                        aclose = getattr(fresh, "aclose", None)
                        if callable(aclose):
                            try:
                                await aclose()
                            except Exception:
                                pass

                async def _do_retain_no_metadata() -> Any:
                    fresh = _build_hindsight_client(self.base_url, self.api_key)
                    try:
                        return await fresh.aretain(
                            bank_id=self.bank_id,
                            content=content,
                            context=context,
                            timestamp=utc_now(),
                        )
                    finally:
                        aclose = getattr(fresh, "aclose", None)
                        if callable(aclose):
                            try:
                                await aclose()
                            except Exception:
                                pass

                try:
                    _run_hindsight_async(_do_retain_with_metadata)
                except TypeError:
                    # SDK does not accept metadata=; retry without it. The
                    # in-process dedupe index still tracks the metadata key.
                    _run_hindsight_async(_do_retain_no_metadata)
                return "retained in Hindsight"
            except Exception as exc:
                self._flip_to_fallback(exc, "retain")

        # Local JSON fallback path. Re-check the on-disk file because
        # local_memory.json may persist across processes.
        item = {
            "title": context,
            "content": content,
            "metadata": merged_metadata,
            "timestamp": utc_now(),
        }
        memories = self._load_local_retained_memory()
        for existing in memories:
            if _match_local_dedupe(existing, dedupe_key):
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
                async def _do_reflect() -> Any:
                    fresh = _build_hindsight_client(self.base_url, self.api_key)
                    try:
                        return await fresh.areflect(
                            bank_id=self.bank_id, query=query
                        )
                    finally:
                        aclose = getattr(fresh, "aclose", None)
                        if callable(aclose):
                            try:
                                await aclose()
                            except Exception:
                                pass

                reflection = _run_hindsight_async(_do_reflect)
                return str(reflection)
            except Exception as exc:
                self._flip_to_fallback(exc, "reflect")
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
        cloud_retained = fallback_retained = skipped = errored = 0
        for item in incidents:
            content = format_seed_memory(item)
            try:
                status = self.retain(
                    content,
                    context=f"seed incident: {item['service']} {item['error_type']}",
                    metadata=item,
                )
            except Exception:
                errored += 1
                continue
            if "retained in Hindsight" in status:
                cloud_retained += 1
            elif "skipped duplicate" in status or "already had this memory" in status:
                skipped += 1
            else:
                fallback_retained += 1
            if delay_seconds > 0:
                time.sleep(delay_seconds)
        return (
            f"seed: cloud={cloud_retained} fallback={fallback_retained} "
            f"skipped={skipped} errored={errored} of {len(incidents)} total"
        )

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

        # Hindsight Cloud splits a single retained memory into multiple
        # result rows by ``type``: usually ``observation`` (auto-extracted
        # summary, no metadata), ``world`` (the original retain content,
        # carries our metadata), and ``experience`` (analyst takeaway,
        # carries our metadata too). Naive iteration drops the metadata
        # for any document where the observation row outranks the
        # world/experience rows. To preserve our analyst-confirmed
        # ``triage_decision``/``dead_ends``/``fingerprint_canonical`` we:
        #   1. Parse every row.
        #   2. Group rows by ``document_id`` so siblings can share metadata.
        #   3. For each row, attach the richest metadata from its document
        #      group.
        #   4. Decode JSON-stringified list values back to Python lists.
        TYPE_RANK = {"experience": 3, "world": 2, "observation": 1}

        # Pass 1: extract minimal record per row.
        rows: list[dict[str, Any]] = []
        for idx, item in enumerate(candidates):
            doc_id: str | None = None
            kind: str = ""
            score_default = max(0.4, 0.85 - idx * 0.08)
            if isinstance(item, str):
                content = item
                title = title_from_content(item, idx)
                score = 0.75
                metadata: dict[str, Any] = {}
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
                    or score_default
                )
                metadata = (
                    dict(item.get("metadata"))
                    if isinstance(item.get("metadata"), dict)
                    else {}
                )
                doc_id = item.get("document_id")
                kind = str(item.get("type") or "")
            elif hasattr(item, "text"):
                content = str(getattr(item, "text"))
                title = (
                    str(getattr(item, "context", "") or "")
                    or title_from_content(content, idx)
                )
                score = float(
                    getattr(item, "score", None)
                    or getattr(item, "similarity", None)
                    or score_default
                )
                # IMPORTANT: read the SDK's metadata attribute; previously
                # the code dropped this and only stored hindsight_id/type.
                raw_meta = getattr(item, "metadata", None)
                metadata = dict(raw_meta) if isinstance(raw_meta, dict) else {}
                metadata.setdefault("hindsight_id", str(getattr(item, "id", "")))
                kind = str(getattr(item, "type", "") or "")
                metadata["hindsight_type"] = kind
                doc_id = getattr(item, "document_id", None)
            else:
                content = str(item)
                title = title_from_content(content, idx)
                score = 0.6
                metadata = {}

            # Decode JSON-stringified list/dict fields we coerced on the way
            # IN so analysts see proper Python lists on the way OUT. Cf.
            # ``_coerce_for_cloud`` in retain().
            for k, v in list(metadata.items()):
                if isinstance(v, str) and v and v[0] in "[{":
                    try:
                        decoded = json.loads(v)
                        metadata[k] = decoded
                    except (ValueError, TypeError):
                        pass

            rows.append(
                {
                    "title": title,
                    "content": content,
                    "score": score,
                    "metadata": metadata,
                    "doc_id": doc_id,
                    "kind": kind,
                    "idx": idx,
                }
            )

        # Pass 2: per document_id, find the metadata-rich representative.
        # A row "carries our metadata" if it has triage_decision OR
        # fingerprint_canonical set.
        def _carries_metadata(meta: dict[str, Any]) -> bool:
            return bool(meta.get("triage_decision") or meta.get("fingerprint_canonical"))

        doc_meta: dict[str, dict[str, Any]] = {}
        for row in rows:
            did = row["doc_id"]
            if not did or not _carries_metadata(row["metadata"]):
                continue
            existing = doc_meta.get(did)
            if existing is None or TYPE_RANK.get(row["kind"], 0) > TYPE_RANK.get(
                existing.get("hindsight_type", ""), 0
            ):
                doc_meta[did] = row["metadata"]

        # Pass 3: collapse to one MemoryMatch per document_id (or per row if
        # it has no document_id). Prefer the row with richer metadata + the
        # higher result-type rank within the same document group.
        seen_docs: set[str] = set()
        matches: list[MemoryMatch] = []
        for row in rows:
            did = row["doc_id"]
            if did and did in seen_docs:
                continue
            if did:
                seen_docs.add(did)

            # Inherit the document group's metadata if this row's own
            # metadata is empty.
            metadata = dict(row["metadata"])
            if did and did in doc_meta:
                for k, v in doc_meta[did].items():
                    metadata.setdefault(k, v)

            matches.append(
                MemoryMatch(
                    title=row["title"],
                    content=row["content"],
                    score=min(row["score"], 1.0),
                    source="hindsight",
                    metadata=cast(dict[str, Any], metadata),
                )
            )

        # Pass 4: re-score client-side (RULE-MEMORY-04). Hindsight Cloud does
        # not return relevance scores; the position-based defaults above are
        # arbitrary. Matches that carry our triage_decision metadata are the
        # ones the triage engine can actually use, so they must rank highest.
        # Within each tier, preserve the original Hindsight ordering.
        def _score_key(m: MemoryMatch) -> tuple[int, float]:
            has_decision = 1 if m.metadata.get("triage_decision") else 0
            return (has_decision, m.score)

        ranked = sorted(dedupe_matches(matches), key=_score_key, reverse=True)
        # Re-assign position-based scores. Metadata-rich matches get a
        # gentler decay (0.02/pos) so up to 5 can qualify as Strong_Matches
        # (score >= 0.85). Matches without triage_decision get steeper decay.
        for i, m in enumerate(ranked):
            if m.metadata.get("triage_decision"):
                m.score = min(1.0, max(0.4, 0.95 - i * 0.02))
            else:
                m.score = min(1.0, max(0.4, 0.70 - i * 0.05))
        return ranked

    def _load_seed_memory(self) -> list[dict[str, Any]]:
        memories: list[dict[str, Any]] = []
        if SEED_PATH.exists():
            for item in json.loads(SEED_PATH.read_text(encoding="utf-8")):
                # Forward-compatible: triage_decision/dead_ends are added in Task 11
                # but we read them now with safe defaults so future seed records
                # surface their metadata through recall_by_fingerprint /
                # recall_by_decision without a memory.py change.
                metadata = dict(item)
                metadata.setdefault("triage_decision", item.get("triage_decision"))
                metadata.setdefault("dead_ends", item.get("dead_ends", []))
                memories.append(
                    {
                        "title": item["title"],
                        "content": format_seed_memory(item),
                        "metadata": metadata,
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
            # Surface the OpenRecall metadata block on the MemoryMatch so the
            # downstream UI, audit recorder, and recall_by_decision filter all
            # see the new fields. Defaults are forward-compatible — missing
            # keys read as None / [].
            surfaced_metadata: dict[str, Any] = dict(local_metadata)
            surfaced_metadata.setdefault(
                "triage_decision", local_metadata.get("triage_decision")
            )
            surfaced_metadata.setdefault(
                "dead_ends", local_metadata.get("dead_ends", []) or []
            )
            surfaced_metadata.setdefault(
                "fingerprint_canonical",
                local_metadata.get("fingerprint_canonical"),
            )
            surfaced_metadata.setdefault(
                "analyst_id", local_metadata.get("analyst_id")
            )
            surfaced_metadata.setdefault(
                "business_impact_minutes",
                local_metadata.get("business_impact_minutes"),
            )
            scored.append(
                MemoryMatch(
                    title=str(item.get("title", "local memory")),
                    content=str(item.get("content", "")),
                    score=score,
                    source="local-json",
                    metadata=surfaced_metadata,
                )
            )
        return dedupe_matches(
            sorted(
                scored,
                key=lambda match: (
                    match.score,
                    1 if match.metadata.get("triage_decision") else 0,
                ),
                reverse=True,
            )
        )[:limit]


def format_seed_memory(item: dict[str, Any]) -> str:
    # Seed format is intentionally stable: triage_decision and dead_ends ride
    # in metadata, not in the rendered content string.
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


def _match_local_dedupe(
    existing: dict[str, Any], dedupe_key: tuple[str, str, str]
) -> bool:
    """Return True when an on-disk record matches the in-process dedupe key."""
    md = existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}
    md_dict = cast(dict[str, Any], md)
    existing_canonical = str(md_dict.get("fingerprint_canonical", "") or "")
    existing_decision = str(md_dict.get("triage_decision") or "")
    existing_hash = sha256(
        str(existing.get("content", "")).encode("utf-8")
    ).hexdigest()
    return (existing_canonical, existing_decision, existing_hash) == dedupe_key


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
