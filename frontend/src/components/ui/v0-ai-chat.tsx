"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
    AlertTriangle, ListChecks, Database, ShieldAlert, ArrowUpIcon,
    Paperclip, Bot, User, Fingerprint, Zap, DollarSign,
    Activity, CheckCircle2, Link, Terminal, ChevronDown, ChevronUp,
    ChevronRight, X as XIcon,
    Clock, Eye, Skull
} from "lucide-react";

// Single source of truth for the FastAPI backend URL. Override at build time
// with NEXT_PUBLIC_OPENRECALL_API. NEVER put API keys in NEXT_PUBLIC_* —
// only the backend URL belongs here (RULE-UI-05).
const API_BASE =
    (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_OPENRECALL_API) ||
    "http://localhost:8000";

function useAutoResizeTextarea({ minHeight, maxHeight }: { minHeight: number; maxHeight?: number }) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const adjustHeight = useCallback((reset?: boolean) => {
        const ta = textareaRef.current;
        if (!ta) return;
        if (reset) { ta.style.height = `${minHeight}px`; return; }
        ta.style.height = `${minHeight}px`;
        ta.style.height = `${Math.max(minHeight, Math.min(ta.scrollHeight, maxHeight ?? Infinity))}px`;
    }, [minHeight, maxHeight]);
    useEffect(() => { if (textareaRef.current) textareaRef.current.style.height = `${minHeight}px`; }, [minHeight]);
    useEffect(() => {
        const h = () => adjustHeight();
        window.addEventListener("resize", h);
        return () => window.removeEventListener("resize", h);
    }, [adjustHeight]);
    return { textareaRef, adjustHeight };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type TriageData = Record<string, any>;

type Message = {
    id: string;
    role: "user" | "agent";
    content: string;
    rawAlert?: string;
    steps?: string[];
    triageData?: TriageData;
    error?: boolean;
};

function DecisionBadge({ decision, confidence }: { decision: string; confidence: number }) {
    const fp = decision === "False Positive" || decision === "Known Benign" || decision === "Duplicate";
    const color = fp ? "text-green-400 border-green-700 bg-green-950" : decision === "Escalated" ? "text-red-400 border-red-700 bg-red-950" : "text-amber-400 border-amber-700 bg-amber-950";
    return (
        <div className={cn("flex items-center gap-2 px-3 py-2 rounded-lg border font-semibold text-sm", color)}>
            {fp ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
            {decision} <span className="opacity-60 font-normal text-xs">({confidence}%)</span>
        </div>
    );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
    const [open, setOpen] = useState(true);
    return (
        <div className="border border-border rounded-lg overflow-hidden">
            <button onClick={() => setOpen(o => !o)} className="flex items-center justify-between w-full px-3 py-2 bg-muted/30 hover:bg-muted/50 transition-colors text-left">
                <span className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">{icon}{title}</span>
                {open ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
            </button>
            {open && <div className="px-3 py-3 space-y-1.5 text-sm">{children}</div>}
        </div>
    );
}

function CodeLine({ text }: { text: string }) {
    return <div className="font-mono text-xs bg-black/40 text-green-400 px-2 py-1 rounded border border-border/50 select-all">{text}</div>;
}

function TriageCard({ d, rawAlert }: { d: TriageData; rawAlert: string }) {
    const fp: Record<string, string> = d.fingerprint || {};

    return (
        <div className="space-y-3 w-full max-w-2xl">
            {/* Top summary card */}
            <div className="bg-card border border-border rounded-xl p-4 space-y-3">
                {/* Header row: meta tags + decision badge */}
                <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="flex flex-col gap-1.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                            <span className="font-mono text-[11px] font-bold bg-red-950 text-red-400 border border-red-800 px-2 py-0.5 rounded">{d.severity}</span>
                            <span className="text-[11px] font-semibold text-foreground">{d.service}</span>
                            <span className="text-[11px] px-2 py-0.5 rounded bg-secondary text-secondary-foreground capitalize">{d.environment}</span>
                            <span className="text-[11px] px-2 py-0.5 rounded bg-secondary text-secondary-foreground">{d.incident_type}</span>
                        </div>
                        <div className="text-xs text-amber-400 font-medium">{d.impact_level}</div>
                        <div className="text-xs text-muted-foreground">{d.blast_radius}</div>
                    </div>
                    <DecisionBadge decision={d.decision} confidence={d.confidence} />
                </div>

                {/* Human approval banner — inside card so it's always visible */}
                {d.requires_human_approval && (
                    <div className="flex items-start gap-2 text-xs text-amber-300 border border-amber-800 bg-amber-950/40 rounded-lg px-3 py-2">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                        <span><strong>Human approval required</strong> before any remediation. {d.escalation_reason && <span className="opacity-70">Reason: {d.escalation_reason}</span>}</span>
                    </div>
                )}

                {/* Alert DNA Fingerprint */}
                {Object.keys(fp).length > 0 && (
                    <div className="border-t border-border pt-3">
                        <div className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                            <Fingerprint className="w-3 h-3" />Alert DNA Fingerprint
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                            {Object.entries(fp).map(([k, v]) => (
                                <span key={k} className="text-[10px] px-2 py-0.5 rounded-full bg-secondary text-secondary-foreground border border-border">
                                    <span className="opacity-40">{k.replace(/_/g, " ")}: </span>{String(v)}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Cost / Router / Latency row */}
                <div className="border-t border-border pt-3 grid grid-cols-3 gap-3">
                    <div>
                        <div className="text-[10px] text-muted-foreground flex items-center gap-1 mb-1"><Database className="w-3 h-3" />Router</div>
                        <div className="text-xs font-medium truncate">{d.memory_bypassed ? "Hindsight memory" : d.router_model}</div>
                    </div>
                    <div>
                        <div className="text-[10px] text-muted-foreground flex items-center gap-1 mb-1"><DollarSign className="w-3 h-3" />Cost</div>
                        <div className={cn("text-xs font-medium", d.memory_bypassed ? "text-green-400" : "text-amber-400")}>${d.cost_usd?.toFixed(6) ?? "0.000000"}</div>
                    </div>
                    <div>
                        <div className="text-[10px] text-muted-foreground flex items-center gap-1 mb-1"><Zap className="w-3 h-3" />Latency</div>
                        <div className="text-xs font-medium">{d.latency_ms}ms</div>
                    </div>
                </div>
            </div>

            {/* Root Causes */}
            {d.root_causes?.length > 0 && (
                <Section title="Root Cause Analysis" icon={<AlertTriangle className="w-3.5 h-3.5" />}>
                    {d.root_causes.map((rc: TriageData, i: number) => (
                        <div key={i} className="space-y-1">
                            <div className="font-medium text-foreground">{rc.cause}</div>
                            <div className="text-muted-foreground text-xs">{rc.evidence}</div>
                            <div className="text-xs">Confidence: <span className="text-primary font-medium">{typeof rc.confidence === "number" ? `${(rc.confidence * 100).toFixed(0)}%` : rc.confidence}</span></div>
                        </div>
                    ))}
                </Section>
            )}

            {/* Prior Incidents from Memory */}
            {d.prior_incidents?.length > 0 && (
                <Section title={`Prior Incidents in Memory (${d.memory_hit_count} hits)`} icon={<Clock className="w-3.5 h-3.5" />}>
                    {d.prior_incidents.map((p: TriageData, i: number) => (
                        <div key={i} className="flex items-center justify-between gap-2">
                            <span className="text-foreground">{p.title}</span>
                            <div className="flex items-center gap-1.5 shrink-0">
                                <span className="text-xs text-muted-foreground">score {p.score?.toFixed(2)}</span>
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground">{p.decision}</span>
                            </div>
                        </div>
                    ))}
                    {d.memory_reflection && <p className="text-xs text-muted-foreground border-t border-border pt-2 mt-1">{d.memory_reflection}</p>}
                </Section>
            )}

            {/* Dead Ends */}
            {d.dead_ends?.length > 0 && (
                <Section title="Dead Ends (Skip These)" icon={<Skull className="w-3.5 h-3.5" />}>
                    {d.dead_ends.map((de: string, i: number) => (
                        <div key={i} className="text-red-400 flex items-start gap-1.5"><XIcon className="w-3 h-3 shrink-0 mt-0.5" />{de}</div>
                    ))}
                </Section>
            )}

            {/* Verification Commands */}
            {d.verification_commands?.length > 0 && (
                <Section title="Verification Commands" icon={<Terminal className="w-3.5 h-3.5" />}>
                    {d.verification_commands.map((cmd: string, i: number) => <CodeLine key={i} text={cmd} />)}
                </Section>
            )}

            {/* Containment */}
            {d.containment_notes?.length > 0 && (
                <Section title="Containment Steps" icon={<ShieldAlert className="w-3.5 h-3.5" />}>
                    {d.containment_notes.map((n: string, i: number) => (
                        <div key={i} className="flex items-start gap-2 text-foreground"><ChevronRight className="w-3 h-3 shrink-0 mt-0.5 text-amber-400" />{n}</div>
                    ))}
                </Section>
            )}

            {/* Remediation */}
            {d.remediation_suggestions?.length > 0 && (
                <Section title="Remediation" icon={<CheckCircle2 className="w-3.5 h-3.5" />}>
                    {d.remediation_suggestions.map((s: string, i: number) => (
                        <div key={i} className="flex items-start gap-2 text-foreground"><CheckCircle2 className="w-3 h-3 shrink-0 mt-0.5 text-green-400" />{s}</div>
                    ))}
                </Section>
            )}

            {/* Evidence to Preserve */}
            {d.evidence_to_preserve?.length > 0 && (
                <Section title="Evidence to Preserve" icon={<Eye className="w-3.5 h-3.5" />}>
                    {d.evidence_to_preserve.map((e: string, i: number) => (
                        <div key={i} className="flex gap-2 text-foreground"><span className="text-blue-400 shrink-0">·</span>{e}</div>
                    ))}
                </Section>
            )}

            {/* Postmortem */}
            {d.postmortem_action_items?.length > 0 && (
                <Section title="Postmortem Action Items" icon={<ListChecks className="w-3.5 h-3.5" />}>
                    {d.postmortem_action_items.map((a: string, i: number) => (
                        <div key={i} className="flex gap-2 text-foreground"><span className="text-muted-foreground shrink-0">{i + 1}.</span>{a}</div>
                    ))}
                </Section>
            )}

            {/* Audit trace — every RouteTrace step + matching AuditTraceEntry (P15) */}
            {Array.isArray(d.audit_trace) && d.audit_trace.length > 0 && (
                <Section title={`Audit Trace (${d.audit_trace.length} step${d.audit_trace.length !== 1 ? "s" : ""})`} icon={<Activity className="w-3.5 h-3.5" />}>
                    {d.audit_trace.map((e: TriageData, i: number) => {
                        const skipped = e.llm_skipped || e.model === "memory-bypass";
                        return (
                            <div key={i} className="border border-border/50 rounded-lg px-2.5 py-2 bg-black/20 space-y-1">
                                <div className="flex items-center justify-between gap-2 flex-wrap">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground">{i + 1}</span>
                                        <span className="text-xs font-semibold text-foreground">{e.step}</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        {skipped ? (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-950 text-green-400 border border-green-800">memory-bypass</span>
                                        ) : e.live_model_call ? (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800">live</span>
                                        ) : (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">deterministic</span>
                                        )}
                                        <span className="text-[10px] font-mono text-muted-foreground">{e.model}</span>
                                    </div>
                                </div>
                                {e.route_reason && (
                                    <div className="text-[11px] text-muted-foreground italic">{e.route_reason}</div>
                                )}
                                <div className="grid grid-cols-4 gap-2 text-[10px] pt-0.5">
                                    <div>
                                        <span className="text-muted-foreground">cost</span>{" "}
                                        <span className={cn("font-mono", skipped ? "text-green-400" : "text-amber-400")}>${(e.cost_usd ?? 0).toFixed(6)}</span>
                                    </div>
                                    <div>
                                        <span className="text-muted-foreground">baseline</span>{" "}
                                        <span className="font-mono text-muted-foreground">${(e.baseline_cost_usd ?? 0).toFixed(6)}</span>
                                    </div>
                                    <div>
                                        <span className="text-muted-foreground">savings</span>{" "}
                                        <span className="font-mono text-green-400">${(e.savings_usd ?? 0).toFixed(6)}</span>
                                    </div>
                                    <div>
                                        <span className="text-muted-foreground">latency</span>{" "}
                                        <span className="font-mono text-muted-foreground">{(e.latency_ms ?? 0).toFixed(0)}ms</span>
                                    </div>
                                </div>
                                {e.proposed_decision && (
                                    <div className="text-[10px] text-muted-foreground">
                                        proposed decision: <span className="text-foreground capitalize">{String(e.proposed_decision).replace(/_/g, " ")}</span>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </Section>
            )}

            {/* Override & Retain — closes the learning loop */}
            <RetainPanel d={d} rawAlert={rawAlert} onRetained={() => {}} />

        </div>
    );
}

const DECISIONS = ["false_positive", "duplicate", "known_benign", "real", "escalated"] as const;

function RetainPanel({ d, rawAlert, onRetained }: { d: TriageData; rawAlert: string; onRetained: () => void }) {
    const [open, setOpen] = useState(false);
    // Default to 'real' — NOT the routing decision ('escalated').
    // Choosing 'real' here means the next identical alert is served from memory, bypassing the LLM.
    const agentDecision = d.decision?.toLowerCase().replace(/\s+/g, "_") || "real";
    const [decision, setDecision] = useState(agentDecision === "escalated" ? "real" : agentDecision);
    const [deadEnds, setDeadEnds] = useState(d.dead_ends?.join("\n") || "");
    const [note, setNote] = useState("");
    const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");

    const handleRetain = async () => {
        setStatus("loading");
        try {
            const res = await fetch(`${API_BASE}/retain`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    raw_alert: rawAlert,
                    service: d.service,
                    decision,
                    dead_ends: deadEnds.split("\n").map((s: string) => s.trim()).filter(Boolean),
                    analyst_note: note || undefined,
                    fingerprint: d.fingerprint || undefined,
                }),
            });
            if (!res.ok) throw new Error("Retain failed");
            setStatus("done");
            onRetained();
        } catch {
            setStatus("error");
        }
    };

    if (status === "done") {
        return (
            <div className="flex items-center gap-2 text-xs text-green-400 border border-green-800 bg-green-950/30 rounded-lg px-3 py-2">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                Retained to memory. <strong className="text-green-300">The next analyst will inherit this decision and the dead ends you recorded.</strong>
            </div>
        );
    }

    return (
        <div className="border border-border rounded-xl overflow-hidden">
            <button
                onClick={() => setOpen(o => !o)}
                className="flex items-center justify-between w-full px-4 py-2.5 bg-primary/10 hover:bg-primary/20 transition-colors text-left"
            >
                <span className="flex items-center gap-2 text-xs font-semibold text-primary">
                    <Database className="w-3.5 h-3.5" />
                    Override Decision & Retain to Memory
                </span>
                {open ? <ChevronUp className="w-3.5 h-3.5 text-primary" /> : <ChevronDown className="w-3.5 h-3.5 text-primary" />}
            </button>

            {open && (
                <div className="px-4 py-3 space-y-3 bg-card">
                    <div>
                        <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1.5">Final Decision</label>
                        <div className="flex flex-wrap gap-1.5">
                            {DECISIONS.map(d => (
                                <button
                                    key={d}
                                    onClick={() => setDecision(d)}
                                    className={cn(
                                        "text-[11px] px-3 py-1 rounded-full border transition-colors capitalize",
                                        decision === d
                                            ? "bg-primary text-primary-foreground border-primary"
                                            : "bg-secondary text-secondary-foreground border-border hover:border-primary/50"
                                    )}
                                >
                                    {d.replace("_", " ")}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1.5">
                            Dead Ends to Record <span className="font-normal normal-case opacity-60">(one per line — future analysts will skip these)</span>
                        </label>
                        <textarea
                            value={deadEnds}
                            onChange={e => setDeadEnds(e.target.value)}
                            rows={3}
                            placeholder={"Restarted pods — did not fix it\nRolled back image — config drift persisted"}
                            className="w-full text-xs bg-background border border-border rounded-lg px-3 py-2 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:border-primary/50"
                        />
                    </div>

                    <div>
                        <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1.5">Analyst Note <span className="font-normal normal-case opacity-60">(optional)</span></label>
                        <input
                            value={note}
                            onChange={e => setNote(e.target.value)}
                            placeholder="Root cause confirmed: missing PAYMENT_PROVIDER_URL in ConfigMap after cleanup"
                            className="w-full text-xs bg-background border border-border rounded-lg px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
                        />
                    </div>

                    {status === "error" && (
                        <p className="text-xs text-destructive">Failed to retain — check the backend is running.</p>
                    )}

                    <button
                        onClick={handleRetain}
                        disabled={status === "loading"}
                        className="w-full py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50"
                    >
                        {status === "loading" ? "Retaining…" : "Save & retain to Hindsight"}
                    </button>
                </div>
            )}
        </div>
    );
}

export function VercelV0Chat() {
    const [activeTab, setActiveTab] = useState<"triage" | "calibration" | "soar" | "tenants">("triage");
    const [value, setValue] = useState("");
    const [messages, setMessages] = useState<Message[]>([]);
    const [isTyping, setIsTyping] = useState(false);
    const [totalAlerts, setTotalAlerts] = useState(0);
    const [moneySaved, setMoneySaved] = useState(0);
    const [pctSaved, setPctSaved] = useState(0);
    const [hindsightOk, setHindsightOk] = useState(false);
    const [groqLive, setGroqLive] = useState(false);
    const [costPoints, setCostPoints] = useState<{index:number;cost:number;baseline:number}[]>([]);
    const [seeding, setSeeding] = useState(false);
    const [seedDone, setSeedDone] = useState(false);

    const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 60, maxHeight: 200 });
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const refreshStats = async () => {
        try {
            const [s, c] = await Promise.all([
                fetch(`${API_BASE}/stats`).then(r => r.json()),
                fetch(`${API_BASE}/cost-curve`).then(r => r.json()),
            ]);
            setTotalAlerts(s.total_alerts ?? 0);
            setMoneySaved(s.total_savings_usd ?? 0);
            setPctSaved(s.pct_saved ?? 0);
            setHindsightOk(s.hindsight_connected ?? false);
            setGroqLive(s.groq_live ?? false);
            setCostPoints(c.points ?? []);
        } catch { /* backend not up yet */ }
    };

    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional fetch-on-mount; refresh is debounced by user-triggered re-fetches downstream.
    useEffect(() => { refreshStats(); }, []);
    useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isTyping]);

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const fr = new FileReader();
        fr.onload = (ev) => { setValue(ev.target?.result as string ?? ""); adjustHeight(); };
        fr.readAsText(file);
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    const handleSeed = async () => {
        setSeeding(true);
        try {
            const res = await fetch(`${API_BASE}/seed`, { method: "POST" });
            const data = await res.json();
            setSeedDone(true);
            setMessages(p => [...p, { id: Date.now().toString(), role: "agent", content: data.message ?? "Seed complete." }]);
        } catch {
            setMessages(p => [...p, { id: Date.now().toString(), role: "agent", error: true, content: "Seed failed. Confirm the backend is running on the configured port." }]);
        } finally { setSeeding(false); }
    };

    const callBackend = async (alertText: string) => {
        setIsTyping(true);
        try {
            const res = await fetch(`${API_BASE}/analyze`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ alert: alertText }),
            });
            if (!res.ok) throw new Error(`Backend returned ${res.status}`);
            const data = await res.json();
            const steps: string[] = data.steps ?? [];
            const msgId = Date.now().toString();

            // Add the message skeleton first with no steps
            setMessages(prev => [...prev, {
                id: msgId, role: "agent",
                rawAlert: alertText,
                content: "",
                steps: [],
                triageData: undefined,
            }]);
            setIsTyping(false);

            // Animate steps in one by one
            for (let i = 0; i < steps.length; i++) {
                await new Promise(r => setTimeout(r, 380));
                setMessages(prev => prev.map(m =>
                    m.id === msgId ? { ...m, steps: steps.slice(0, i + 1) } : m
                ));
            }

            // After all steps, attach the full triage card
            await new Promise(r => setTimeout(r, 400));
            const hits = data.memory_hit_count ?? 0;
            setMessages(prev => prev.map(m =>
                m.id === msgId ? {
                    ...m,
                    content: data.memory_bypassed
                        ? `Memory hit. Strong LLM bypassed. ${hits} prior decision${hits !== 1 ? "s" : ""} from Hindsight.`
                        : `Routed to ${data.router_model ?? "model"}. ${hits > 0 ? `${hits} prior match${hits !== 1 ? "es" : ""} — but consistency below threshold.` : "Novel fingerprint — no prior memory."}`,
                    triageData: data,
                } : m
            ));
            refreshStats();
        } catch {
            setIsTyping(false);
            setMessages(prev => [...prev, {
                id: Date.now().toString(), role: "agent", error: true,
                content: "Could not reach the OpenRecall backend. Confirm `uvicorn api:app --port 8000` is running.",
            }]);
        }
    };

    const send = () => {
        if (!value.trim() || isTyping) return;
        setMessages(p => [...p, { id: Date.now().toString(), role: "user", content: value.trim() }]);
        callBackend(value.trim());
        setValue(""); adjustHeight(true);
    };

    const quickSend = (text: string) => {
        setMessages(p => [...p, { id: Date.now().toString(), role: "user", content: text }]);
        callBackend(text);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    };

    const handleSiemClick = () => setMessages(p => [...p, {
        id: Date.now().toString(), role: "agent",
        content: "SIEM integration (Splunk, Datadog, Elastic SIEM) is on the roadmap.",
    }]);

    return (
        <div className="flex flex-col h-[calc(100vh-2rem)] w-full max-w-4xl mx-auto rounded-2xl overflow-hidden border border-border bg-background shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-card shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                        <Activity className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                        <h1 className="text-base font-bold text-foreground leading-tight">OpenRecall Triage Copilot</h1>
                        <div className="flex items-center gap-2 mt-0.5">
                            <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full", hindsightOk ? "bg-green-950 text-green-400" : "bg-yellow-950 text-yellow-400")}>
                                {hindsightOk ? "● Hindsight" : "○ Fallback"}
                            </span>
                            <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full", groqLive ? "bg-blue-950 text-blue-400" : "bg-secondary text-muted-foreground")}>
                                {groqLive ? "● Groq Live" : "○ Deterministic"}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="hidden sm:flex items-center gap-4">
                    <div className="flex flex-col items-end">
                        <span className="text-[10px] text-muted-foreground">Alerts Processed</span>
                        <span className="text-sm font-semibold text-foreground">{totalAlerts.toLocaleString()}</span>
                    </div>
                    <div className="flex flex-col items-end">
                        <span className="text-[10px] text-muted-foreground">LLM Cost Saved</span>
                        <span className="text-sm font-semibold text-green-400">${moneySaved.toFixed(4)}</span>
                    </div>
                    {pctSaved > 0 && (
                        <div className="flex flex-col items-end">
                            <span className="text-[10px] text-muted-foreground">Savings Rate</span>
                            <span className="text-sm font-semibold text-green-400">{pctSaved.toFixed(1)}%</span>
                        </div>
                    )}
                    {/* Mini cost curve chart */}
                    {costPoints.length > 1 && (
                        <MiniCostChart points={costPoints} />
                    )}
                </div>
            </div>

            {/* Tab navigation */}
            <div className="flex items-center gap-0 border-b border-border bg-card/50 px-2 shrink-0">
                {([
                    ["triage", "Triage"],
                    ["calibration", "Calibration"],
                    ["soar", "SOAR Webhooks"],
                    ["tenants", "Tenants & Users"],
                ] as const).map(([key, label]) => (
                    <button key={key} onClick={() => setActiveTab(key)}
                        className={cn("px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-px",
                            activeTab === key
                                ? "border-primary text-primary"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        )}>{label}</button>
                ))}
            </div>

            {/* Tab content */}
            {activeTab === "triage" ? (<>
            {/* Messages — scrollable area */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-3 text-muted-foreground opacity-60 mt-10">
                        <ShieldAlert className="w-14 h-14" />
                        <h2 className="text-xl font-semibold text-foreground">Paste an alert or upload a log to begin.</h2>
                        <p className="text-sm max-w-sm">I will fingerprint it, check Hindsight memory, and surface root causes, commands, and remediation steps — not just a label.</p>
                    </div>
                )}

                {messages.map((msg) => (
                    <div key={msg.id} className={cn("flex w-full", msg.role === "user" ? "justify-end" : "justify-start")}>
                        <div className={cn("flex gap-3 max-w-[90%]", msg.role === "user" ? "flex-row-reverse" : "flex-row")}>
                            <div className={cn("flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5",
                                msg.role === "user" ? "bg-secondary text-secondary-foreground" : "bg-primary text-primary-foreground")}>
                                {msg.role === "user" ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                            </div>
                            <div className={cn("flex flex-col gap-3", msg.role === "user" ? "items-end" : "items-start")}>
                                {msg.role === "user" ? (
                                    <div className="bg-secondary text-secondary-foreground px-4 py-2.5 rounded-2xl rounded-tr-sm text-sm whitespace-pre-wrap max-w-lg">{msg.content}</div>
                                ) : (
                                    <>
                                        {/* Animated agent steps */}
                                        {msg.steps && msg.steps.length > 0 && (
                                            <div className="space-y-1.5 mb-2">
                                                {msg.steps.map((step, i) => (
                                                    <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground animate-in fade-in slide-in-from-left-2 duration-300">
                                                        <span className="shrink-0 mt-0.5">›</span>
                                                        <span>{step.split(/\*\*(.+?)\*\*/).map((part, j) =>
                                                            j % 2 === 1
                                                                ? <strong key={j} className="text-foreground font-semibold">{part}</strong>
                                                                : part
                                                        )}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                        {msg.content && <div className={cn("text-sm px-1 leading-relaxed", msg.error ? "text-destructive" : "text-muted-foreground")}>{msg.content}</div>}
                                        {msg.triageData && <TriageCard d={msg.triageData} rawAlert={msg.rawAlert ?? ""} />}
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                ))}

                {isTyping && (
                    <div className="flex gap-3">
                        <div className="w-7 h-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center shrink-0 mt-0.5">
                            <Bot className="w-3.5 h-3.5" />
                        </div>
                        <div className="bg-card border border-border px-4 py-3 rounded-2xl rounded-tl-sm flex gap-1 items-center h-10">
                            {[0, 200, 400].map(d => <span key={d} className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: `${d}ms` }} />)}
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>
            {/* Input footer — fixed at bottom, not overlapping */}
            <div className="shrink-0 border-t border-border bg-background px-4 py-3 space-y-2">

                {/* Scenario quick-send pills — only on empty state */}
                {messages.length === 0 && (
                    <div className="flex flex-wrap gap-1.5 justify-center">
                        <ActionButton icon={<AlertTriangle className="w-3.5 h-3.5" />} label="CrashLoopBackOff" onClick={() => quickSend("SEV-2 prod checkout-service CrashLoopBackOff after deploy 2026.05.16. Pods restart every 40s. Last log: KeyError PAYMENT_PROVIDER_URL. Recent ConfigMap cleanup removed env var. 5xx on checkout started at 14:07 UTC.")} />
                        <ActionButton icon={<Database className="w-3.5 h-3.5" />} label="DB Pool Exhaustion" onClick={() => quickSend("P2 production payments-api p95 latency 8s and intermittent 503. Logs show timeout waiting for database connection from pool. Deploy happened yesterday, traffic normal, no obvious error owner.")} />
                        <ActionButton icon={<ShieldAlert className="w-3.5 h-3.5" />} label="WAF SQL Injection" onClick={() => quickSend("HIGH prod waf SQL injection alert grouped 63 requests against api-gateway /search?q=' OR 1=1--. Source ASN repeated across 12 IPs. Some 500s observed. Preserve request IDs and app logs.")} />
                    </div>
                )}

                {/* Textarea card */}
                <div className="bg-card rounded-xl border border-border shadow-sm">
                    <Textarea
                        ref={textareaRef}
                        value={value}
                        onChange={(e) => { setValue(e.target.value); adjustHeight(); }}
                        onKeyDown={handleKeyDown}
                        placeholder="Paste raw alert JSON, upload a log file, or describe an incident… (Enter to send, Shift+Enter for newline)"
                        className={cn("w-full px-4 py-3 resize-none bg-transparent border-none text-foreground text-sm",
                            "focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0",
                            "placeholder:text-muted-foreground placeholder:text-sm min-h-[60px]")}
                        style={{ overflow: "hidden" }}
                    />
                    <div className="flex items-center justify-between px-3 pb-2 border-t border-border/40 pt-2">
                        <div className="flex items-center gap-1">
                            <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" accept=".txt,.json,.log" />
                            <button onClick={() => fileInputRef.current?.click()} title="Upload log / alert file" className="p-1.5 hover:bg-muted rounded-md transition-colors text-muted-foreground hover:text-foreground">
                                <Paperclip className="w-4 h-4" />
                            </button>
                            {/* Utility buttons inline in toolbar */}
                            <button onClick={handleSiemClick} title="Connect SIEM" className="p-1.5 hover:bg-muted rounded-md transition-colors text-muted-foreground hover:text-foreground">
                                <Link className="w-4 h-4" />
                            </button>
                            <button
                                onClick={!seeding && !seedDone ? handleSeed : undefined}
                                title={seedDone ? "Memory already seeded" : "Seed Hindsight Memory"}
                                className={cn("p-1.5 rounded-md transition-colors",
                                    seedDone ? "text-green-500" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                                )}
                            >
                                <Database className="w-4 h-4" />
                            </button>
                            {seeding && <span className="text-[10px] text-muted-foreground animate-pulse">Seeding…</span>}
                        </div>
                        <button onClick={send} disabled={!value.trim() || isTyping}
                            className={cn("px-2 py-1.5 rounded-md border flex items-center gap-1 transition-colors",
                                value.trim() && !isTyping ? "bg-primary text-primary-foreground border-primary hover:bg-primary/90" : "bg-muted border-transparent text-muted-foreground opacity-50 cursor-not-allowed")}>
                            <ArrowUpIcon className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
            </>) : activeTab === "calibration" ? (
                <CalibrationPanel />
            ) : activeTab === "soar" ? (
                <SOARPanel />
            ) : (
                <TenantsPanel />
            )}
        </div>
    );
}

function CalibrationPanel() {
    const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${API_BASE}/calibration`).then(r => r.json()).then(setMetrics).catch(() => setMetrics(null)).finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">Loading calibration data…</div>;
    if (!metrics) return <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">Could not load calibration data.</div>;

    const total = (metrics.total_decisions as number) ?? 0;
    const accuracy = (metrics.accuracy_pct as number) ?? 0;
    const overrideRate = (metrics.override_rate_pct as number) ?? 0;
    const eligible = (metrics.auto_close_eligible as boolean) ?? false;
    const reason = (metrics.auto_close_reason as string) ?? "";
    const perDecision = (metrics.per_decision as Record<string, Record<string, number>>) ?? {};
    const buckets = (metrics.confidence_buckets as Array<Record<string, unknown>>) ?? [];

    return (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div>
                <h2 className="text-lg font-bold text-foreground mb-1">Confidence Calibration</h2>
                <p className="text-xs text-muted-foreground">Track proposed vs actual decisions to measure auto-triage accuracy over time.</p>
            </div>

            {/* Summary cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <StatCard label="Total Decisions" value={total.toString()} />
                <StatCard label="Accuracy" value={`${accuracy}%`} color={accuracy >= 90 ? "text-green-400" : accuracy >= 70 ? "text-amber-400" : "text-red-400"} />
                <StatCard label="Override Rate" value={`${overrideRate}%`} color={overrideRate <= 10 ? "text-green-400" : "text-amber-400"} />
                <StatCard label="Auto-Close" value={eligible ? "Eligible" : "Not Yet"} color={eligible ? "text-green-400" : "text-muted-foreground"} />
            </div>

            {/* Auto-close status */}
            <div className={cn("px-4 py-3 rounded-lg border text-sm", eligible ? "border-green-700 bg-green-950/50 text-green-300" : "border-border bg-muted/30 text-muted-foreground")}>
                {eligible ? "✓ " : "○ "}{reason}
            </div>

            {/* Per-decision breakdown */}
            {Object.keys(perDecision).length > 0 && (
                <Section title="Per-Decision Breakdown" icon={<ListChecks className="w-3.5 h-3.5" />}>
                    <div className="space-y-2">
                        {Object.entries(perDecision).map(([decision, stats]) => (
                            <div key={decision} className="flex items-center justify-between text-xs">
                                <span className="font-medium capitalize">{decision.replace("_", " ")}</span>
                                <span className="text-muted-foreground">
                                    {stats.correct ?? 0} correct / {stats.overridden ?? 0} overridden of {stats.proposed ?? 0}
                                </span>
                            </div>
                        ))}
                    </div>
                </Section>
            )}

            {/* Confidence buckets */}
            {buckets.length > 0 && (
                <Section title="Confidence Calibration Curve" icon={<Activity className="w-3.5 h-3.5" />}>
                    <div className="space-y-2">
                        {buckets.map((b, i) => (
                            <div key={i} className="flex items-center gap-3 text-xs">
                                <span className="w-16 text-muted-foreground">{b.range as string}</span>
                                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                    <div className="h-full bg-primary rounded-full" style={{ width: `${b.accuracy_pct as number}%` }} />
                                </div>
                                <span className="w-12 text-right">{b.accuracy_pct as number}%</span>
                                <span className="w-8 text-right text-muted-foreground">n={b.count as number}</span>
                            </div>
                        ))}
                    </div>
                </Section>
            )}

            {total === 0 && (
                <div className="text-center text-muted-foreground text-sm py-8">
                    No decisions tracked yet. Submit alerts via the Triage tab or SOAR webhooks to start building calibration data.
                </div>
            )}
        </div>
    );
}

function SOARPanel() {
    const [platform, setPlatform] = useState<"splunk" | "sentinel" | "generic">("generic");
    const [payload, setPayload] = useState('{"alert_text": "SEV-2 prod checkout-service CrashLoopBackOff", "severity": "SEV-2", "source": "splunk"}');
    const [result, setResult] = useState<Record<string, unknown> | null>(null);
    const [loading, setLoading] = useState(false);

    const testWebhook = async () => {
        setLoading(true);
        setResult(null);
        try {
            const res = await fetch(`${API_BASE}/webhook/${platform}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: payload,
            });
            setResult(await res.json());
        } catch { setResult({ status: "error", escalation_reason: "Could not reach backend" }); }
        finally { setLoading(false); }
    };

    const templates: Record<string, string> = {
        splunk: JSON.stringify({ container_id: 12345, container_name: "CrashLoop Alert", severity: "high", description: "SEV-2 prod checkout-service CrashLoopBackOff after deploy. KeyError PAYMENT_PROVIDER_URL.", label: "sre" }, null, 2),
        sentinel: JSON.stringify({ incident_id: "INC-001", title: "SQL Injection on api-gateway", description: "HIGH prod waf SQL injection 63 requests against /search", severity: "High", tactics: ["InitialAccess"] }, null, 2),
        generic: JSON.stringify({ alert_text: "SEV-2 prod checkout-service CrashLoopBackOff. KeyError PAYMENT_PROVIDER_URL.", severity: "SEV-2", source: "datadog" }, null, 2),
    };

    return (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div>
                <h2 className="text-lg font-bold text-foreground mb-1">SOAR Webhook Tester</h2>
                <p className="text-xs text-muted-foreground">Test enrichment webhooks for Splunk SOAR, Microsoft Sentinel, or any generic SIEM.</p>
            </div>

            {/* Platform selector */}
            <div className="flex gap-2">
                {(["splunk", "sentinel", "generic"] as const).map(p => (
                    <button key={p} onClick={() => { setPlatform(p); setPayload(templates[p]); setResult(null); }}
                        className={cn("px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                            platform === p ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground"
                        )}>{p === "splunk" ? "Splunk SOAR" : p === "sentinel" ? "Sentinel" : "Generic"}</button>
                ))}
            </div>

            {/* Endpoint info */}
            <div className="text-xs text-muted-foreground bg-muted/30 px-3 py-2 rounded-lg border border-border font-mono">
                POST {API_BASE}/webhook/{platform}
            </div>

            {/* Payload editor */}
            <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Request Payload</label>
                <textarea value={payload} onChange={e => setPayload(e.target.value)}
                    className="w-full h-40 bg-black/40 text-green-400 font-mono text-xs p-3 rounded-lg border border-border resize-none focus:outline-none focus:border-primary" />
            </div>

            <button onClick={testWebhook} disabled={loading}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
                {loading ? "Sending…" : "Send Test Webhook"}
            </button>

            {/* Result */}
            {result && (
                <Section title="Enrichment Response" icon={<Zap className="w-3.5 h-3.5" />}>
                    <div className="space-y-2">
                        <div className="flex items-center gap-3">
                            <span className={cn("px-2 py-0.5 rounded text-xs font-semibold",
                                result.status === "enriched" ? "bg-green-950 text-green-400" : "bg-red-950 text-red-400"
                            )}>{String(result.status)}</span>
                            {result.proposed_decision ? (
                                <span className="text-xs font-medium capitalize">{String(result.proposed_decision).replace("_", " ")}</span>
                            ) : null}
                            {result.confidence !== undefined ? (
                                <span className="text-xs text-muted-foreground">({(Number(result.confidence) * 100).toFixed(1)}%)</span>
                            ) : null}
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                            <div><span className="text-muted-foreground">Action:</span> <span className="font-medium">{String(result.recommended_action)}</span></div>
                            <div><span className="text-muted-foreground">Auto-closeable:</span> <span className="font-medium">{result.auto_closeable ? "Yes" : "No"}</span></div>
                            <div><span className="text-muted-foreground">Memory bypassed:</span> <span className="font-medium">{result.memory_bypassed ? "Yes" : "No"}</span></div>
                            <div><span className="text-muted-foreground">Cost:</span> <span className="font-medium">${String(result.cost_usd)}</span></div>
                            <div><span className="text-muted-foreground">Latency:</span> <span className="font-medium">{String(result.latency_ms)}ms</span></div>
                            <div><span className="text-muted-foreground">Matches:</span> <span className="font-medium">{String(result.memory_match_count)}</span></div>
                        </div>
                        {Array.isArray(result.dead_ends) && result.dead_ends.length > 0 ? (
                            <div className="text-xs"><span className="text-muted-foreground">Dead ends:</span> {(result.dead_ends as string[]).join("; ")}</div>
                        ) : null}
                        {result.escalation_reason ? (
                            <div className="text-xs text-amber-400">{String(result.escalation_reason)}</div>
                        ) : null}
                    </div>
                </Section>
            )}
        </div>
    );
}

function TenantsPanel() {
    const [tenants, setTenants] = useState<Array<Record<string, unknown>>>([]);
    const [newName, setNewName] = useState("");
    const [newBankId, setNewBankId] = useState("");
    const [userForm, setUserForm] = useState({ tenantId: "default", email: "", name: "", role: "analyst" });
    const [createdUser, setCreatedUser] = useState<Record<string, unknown> | null>(null);
    const [loading, setLoading] = useState(true);

    const refresh = () => {
        fetch(`${API_BASE}/tenants`).then(r => r.json()).then(d => setTenants(d.tenants ?? [])).catch(() => {}).finally(() => setLoading(false));
    };
    useEffect(() => { refresh(); }, []);

    const createTenant = async () => {
        if (!newName.trim()) return;
        const params = new URLSearchParams({ name: newName });
        if (newBankId.trim()) params.set("bank_id", newBankId);
        await fetch(`${API_BASE}/tenants?${params}`, { method: "POST" });
        setNewName(""); setNewBankId("");
        refresh();
    };

    const createUser = async () => {
        if (!userForm.email.trim() || !userForm.name.trim()) return;
        const params = new URLSearchParams({ email: userForm.email, display_name: userForm.name, role: userForm.role });
        const res = await fetch(`${API_BASE}/tenants/${userForm.tenantId}/users?${params}`, { method: "POST" });
        const data = await res.json();
        setCreatedUser(data);
        setUserForm({ ...userForm, email: "", name: "" });
    };

    if (loading) return <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">Loading…</div>;

    return (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div>
                <h2 className="text-lg font-bold text-foreground mb-1">Tenants & Users</h2>
                <p className="text-xs text-muted-foreground">Manage teams with isolated memory banks and role-based access.</p>
            </div>

            {/* Existing tenants */}
            <Section title={`Tenants (${tenants.length})`} icon={<Database className="w-3.5 h-3.5" />}>
                <div className="space-y-2">
                    {tenants.map((t, i) => (
                        <div key={i} className="flex items-center justify-between text-xs bg-muted/30 px-3 py-2 rounded-lg">
                            <div>
                                <span className="font-medium text-foreground">{t.name as string}</span>
                                <span className="text-muted-foreground ml-2">({t.tenant_id as string})</span>
                            </div>
                            <span className="font-mono text-muted-foreground text-[10px]">bank: {t.memory_bank_id as string}</span>
                        </div>
                    ))}
                </div>
            </Section>

            {/* Create tenant */}
            <Section title="Create Tenant" icon={<Zap className="w-3.5 h-3.5" />}>
                <div className="flex gap-2">
                    <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Team name"
                        className="flex-1 px-3 py-1.5 bg-black/40 border border-border rounded-lg text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary" />
                    <input value={newBankId} onChange={e => setNewBankId(e.target.value)} placeholder="Bank ID (optional)"
                        className="flex-1 px-3 py-1.5 bg-black/40 border border-border rounded-lg text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary" />
                    <button onClick={createTenant} className="px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90">Create</button>
                </div>
            </Section>

            {/* Create user */}
            <Section title="Create User" icon={<User className="w-3.5 h-3.5" />}>
                <div className="space-y-2">
                    <div className="flex gap-2">
                        <select value={userForm.tenantId} onChange={e => setUserForm({ ...userForm, tenantId: e.target.value })}
                            className="px-3 py-1.5 bg-black/40 border border-border rounded-lg text-xs text-foreground focus:outline-none focus:border-primary">
                            {tenants.map((t, i) => <option key={i} value={t.tenant_id as string}>{t.name as string}</option>)}
                        </select>
                        <select value={userForm.role} onChange={e => setUserForm({ ...userForm, role: e.target.value })}
                            className="px-3 py-1.5 bg-black/40 border border-border rounded-lg text-xs text-foreground focus:outline-none focus:border-primary">
                            <option value="analyst">Analyst</option>
                            <option value="senior">Senior Analyst</option>
                            <option value="soc_lead">SOC Lead</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>
                    <div className="flex gap-2">
                        <input value={userForm.email} onChange={e => setUserForm({ ...userForm, email: e.target.value })} placeholder="Email"
                            className="flex-1 px-3 py-1.5 bg-black/40 border border-border rounded-lg text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary" />
                        <input value={userForm.name} onChange={e => setUserForm({ ...userForm, name: e.target.value })} placeholder="Display name"
                            className="flex-1 px-3 py-1.5 bg-black/40 border border-border rounded-lg text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary" />
                        <button onClick={createUser} className="px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90">Create</button>
                    </div>
                </div>
            </Section>

            {/* Created user result */}
            {createdUser && (
                <div className="bg-green-950/50 border border-green-700 rounded-lg px-4 py-3 text-xs space-y-1">
                    <div className="text-green-400 font-medium">User created successfully</div>
                    <div className="text-green-300">Name: {(createdUser.user as Record<string, unknown>)?.display_name as string}</div>
                    <div className="text-green-300">Role: {(createdUser.user as Record<string, unknown>)?.role as string}</div>
                    <div className="font-mono text-green-400 bg-black/40 px-2 py-1 rounded mt-1">API Key: {createdUser.api_key as string}</div>
                    <div className="text-muted-foreground mt-1">Save this key — it won&apos;t be shown again.</div>
                </div>
            )}
        </div>
    );
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
    return (
        <div className="bg-card border border-border rounded-lg px-3 py-2">
            <div className="text-[10px] text-muted-foreground">{label}</div>
            <div className={cn("text-lg font-bold", color ?? "text-foreground")}>{value}</div>
        </div>
    );
}

function MiniCostChart({ points }: { points: { index: number; cost: number; baseline: number }[] }) {
    const W = 120, H = 40, pad = 4;
    const maxB = Math.max(...points.map(p => p.baseline), 0.0001);
    const toX = (i: number) => pad + (i / Math.max(points.length - 1, 1)) * (W - pad * 2);
    const toY = (v: number) => H - pad - (v / maxB) * (H - pad * 2);
    const pathFor = (key: "cost" | "baseline") =>
        points.map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p[key]).toFixed(1)}`).join(" ");
    return (
        <div className="flex flex-col items-end gap-0.5">
            <span className="text-[10px] text-muted-foreground">Cost Curve</span>
            <svg width={W} height={H} className="rounded overflow-hidden bg-black/20">
                {/* Savings area fill */}
                <path
                    d={`${pathFor("cost")} L${toX(points.length - 1).toFixed(1)},${toY(points[points.length - 1].baseline).toFixed(1)} ${points.slice().reverse().map((p, i) => `L${toX(points.length - 1 - i).toFixed(1)},${toY(p.baseline).toFixed(1)}`).join(" ")} Z`}
                    fill="rgba(34,197,94,0.15)"
                />
                {/* Baseline (red) */}
                <path d={pathFor("baseline")} fill="none" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="3 2" />
                {/* Actual cost (green) */}
                <path d={pathFor("cost")} fill="none" stroke="#22c55e" strokeWidth="1.5" />
            </svg>
            <div className="flex items-center gap-2 text-[9px] text-muted-foreground">
                <span className="flex items-center gap-0.5"><span className="inline-block w-2 h-0.5 bg-green-500 rounded" />actual</span>
                <span className="flex items-center gap-0.5"><span className="inline-block w-2 h-0.5 bg-red-500 rounded" />baseline</span>
            </div>
        </div>
    );
}

function ActionButton({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick?: () => void }) {
    return (
        <button type="button" onClick={onClick}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-card hover:bg-muted rounded-full border border-border text-muted-foreground hover:text-foreground transition-colors text-[11px] font-medium shadow-sm">
            {icon}{label}
        </button>
    );
}
