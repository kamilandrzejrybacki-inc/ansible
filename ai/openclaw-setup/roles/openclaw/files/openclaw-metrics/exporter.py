import json
import os
import glob
import time
import signal
import threading
import logging
import collections

from prometheus_client import Counter, Histogram, Gauge, start_http_server
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

SESSIONS_DIR = os.environ.get("SESSIONS_DIR", "/data/sessions")
LOGS_DIR = os.environ.get("LOGS_DIR", "/data/logs")
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9101"))

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

tokens_input_total = Counter(
    "openclaw_tokens_input_total",
    "Total input tokens consumed",
    ["provider", "model", "agent"],
)
tokens_output_total = Counter(
    "openclaw_tokens_output_total",
    "Total output tokens consumed",
    ["provider", "model", "agent"],
)
cost_dollars_total = Counter(
    "openclaw_cost_dollars_total",
    "Total cost in dollars",
    ["provider", "model", "agent"],
)
requests_total = Counter(
    "openclaw_requests_total",
    "Total LLM requests",
    ["provider", "model", "agent", "status"],
)
errors_total = Counter(
    "openclaw_errors_total",
    "Total errors by provider and type",
    ["provider", "error_type"],
)
channel_requests_total = Counter(
    "openclaw_channel_requests_total",
    "Total channel requests by agent and channel",
    ["agent", "channel"],
)
tokens_cache_read_total = Counter(
    "openclaw_tokens_cache_read_total",
    "Total cache-read tokens",
    ["provider", "model"],
)
tokens_cache_write_total = Counter(
    "openclaw_tokens_cache_write_total",
    "Total cache-write tokens",
    ["provider", "model"],
)
tokens_estimated_total = Counter(
    "openclaw_tokens_estimated_total",
    "Total tokens that were estimated (not reported by API)",
    ["provider", "model"],
)
telegram_messages_total = Counter(
    "openclaw_telegram_messages_total",
    "Total Telegram messages by direction",
    ["direction"],
)

request_duration_seconds = Histogram(
    "openclaw_request_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model"],
    buckets=[0.5, 1, 5, 10, 30, 60, 120, 300],
)
ollama_inference_seconds = Histogram(
    "openclaw_ollama_inference_seconds",
    "Ollama inference duration in seconds",
    ["model"],
    buckets=[0.5, 1, 5, 10, 30, 60, 120, 300],
)

active_sessions = Gauge(
    "openclaw_active_sessions",
    "Number of active sessions per agent",
    ["agent"],
)
heartbeat_status = Gauge(
    "openclaw_heartbeat_status",
    "1 if the OpenClaw gateway heartbeat has been observed",
)
cost_rate_dollars_per_hour = Gauge(
    "openclaw_cost_rate_dollars_per_hour",
    "Rolling 1-hour cost rate in dollars per hour",
    ["provider"],
)
info_gauge = Gauge(
    "openclaw_info",
    "OpenClaw exporter metadata",
    ["version", "primary_model"],
)

# Shared deque for burn-rate calculation (thread-safe append/popleft)
cost_events: collections.deque = collections.deque(maxlen=3600)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def parse_usage(message: dict, agent: str) -> None:
    inner = message.get("message", {})
    usage = inner.get("usage", {})

    provider = str(inner.get("provider", "unknown") or "unknown")
    model = str(inner.get("model", "unknown") or "unknown")

    input_tokens = int(usage.get("input", 0) or 0)
    output_tokens = int(usage.get("output", 0) or 0)
    cache_read = int(usage.get("cacheRead", 0) or 0)
    cache_write = int(usage.get("cacheWrite", 0) or 0)

    cost_block = usage.get("cost", {}) or {}
    if isinstance(cost_block, dict):
        total_cost = float(cost_block.get("total", 0) or 0)
    else:
        total_cost = float(cost_block or 0)

    # Estimate tokens from content when the API returns zeros
    if input_tokens == 0 and output_tokens == 0:
        content = inner.get("content", "") or ""
        if content:
            estimated = estimate_tokens(str(content))
            input_tokens = estimated
            tokens_estimated_total.labels(provider=provider, model=model).inc(estimated)

    tokens_input_total.labels(provider=provider, model=model, agent=agent).inc(input_tokens)
    tokens_output_total.labels(provider=provider, model=model, agent=agent).inc(output_tokens)

    if cache_read:
        tokens_cache_read_total.labels(provider=provider, model=model).inc(cache_read)
    if cache_write:
        tokens_cache_write_total.labels(provider=provider, model=model).inc(cache_write)

    if total_cost:
        cost_dollars_total.labels(provider=provider, model=model, agent=agent).inc(total_cost)
        cost_events.append({"ts": time.time(), "provider": provider, "cost": total_cost})


def _parse_jsonl_line(line: str, agent: str) -> None:
    line = line.strip()
    if not line:
        return
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        log.warning("Malformed JSON in session file (agent=%s): %s — %s", agent, exc, line[:120])
        return
    parse_usage(obj, agent)


# ---------------------------------------------------------------------------
# Session watcher
# ---------------------------------------------------------------------------

class SessionWatcher(FileSystemEventHandler):
    def __init__(self, sessions_dir: str) -> None:
        super().__init__()
        self.sessions_dir = sessions_dir
        self.file_positions: dict[str, int] = {}

    def _agent_from_path(self, path: str) -> str:
        # Expected layout: <sessions_dir>/agents/<agent_name>/sessions/<file>.jsonl
        try:
            rel = os.path.relpath(path, self.sessions_dir)
            parts = rel.split(os.sep)
            if len(parts) >= 3 and parts[0] == "agents":
                return parts[1]
        except ValueError:
            pass
        return "unknown"

    def _read_new_lines(self, path: str) -> None:
        agent = self._agent_from_path(path)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(self.file_positions.get(path, 0))
                for line in fh:
                    _parse_jsonl_line(line, agent)
                self.file_positions[path] = fh.tell()
        except OSError as exc:
            log.warning("Could not read session file %s: %s", path, exc)

    def scan_existing(self) -> None:
        pattern = os.path.join(self.sessions_dir, "agents", "*", "sessions", "*.jsonl")
        files = glob.glob(pattern, recursive=False)
        log.info("Scanning %d existing session file(s) in %s", len(files), self.sessions_dir)
        # Track unique agents for active_sessions gauge
        agents_seen: set[str] = set()
        for path in files:
            agent = self._agent_from_path(path)
            agents_seen.add(agent)
            self._read_new_lines(path)
        for agent in agents_seen:
            active_sessions.labels(agent=agent).set(
                sum(1 for p in files if self._agent_from_path(p) == agent)
            )

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        if event.src_path.endswith(".jsonl"):
            self._read_new_lines(event.src_path)

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        if event.src_path.endswith(".jsonl"):
            agent = self._agent_from_path(event.src_path)
            # Initialise position at 0 so the whole file is read
            self.file_positions.setdefault(event.src_path, 0)
            self._read_new_lines(event.src_path)
            active_sessions.labels(agent=agent).inc()


# ---------------------------------------------------------------------------
# Log tailer
# ---------------------------------------------------------------------------

class LogTailer(threading.Thread):
    daemon = True

    def __init__(self, logs_dir: str) -> None:
        super().__init__(name="LogTailer")
        self.logs_dir = logs_dir

    def _latest_log(self) -> str | None:
        pattern = os.path.join(self.logs_dir, "openclaw-*.log")
        files = glob.glob(pattern)
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def _parse_log_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            log.warning("Malformed JSON in log file: %s — %s", exc, line[:120])
            return

        entry_str = str(entry)

        if "embedded_run_agent_end" in entry_str:
            data = entry.get("1", {}) or {}
            model = str(data.get("model", "unknown") or "unknown")
            provider = str(data.get("provider", "unknown") or "unknown")
            agent = str(data.get("agent", "unknown") or "unknown")
            is_error = bool(data.get("isError", False))
            status = "error" if is_error else "success"
            requests_total.labels(provider=provider, model=model, agent=agent, status=status).inc()
            if is_error:
                error_type = str(data.get("error", "unknown") or "unknown")
                errors_total.labels(provider=provider, error_type=error_type).inc()

        if "telegram" in entry_str and "sendMessage" in entry_str:
            telegram_messages_total.labels(direction="out").inc()

        if "heartbeat" in entry_str and "started" in entry_str:
            heartbeat_status.set(1)

    def run(self) -> None:
        current_log: str | None = None
        position: int = 0
        last_rotation_check: float = 0.0

        while True:
            now = time.time()

            # Detect log rotation (or initial discovery) every 60 s
            if now - last_rotation_check >= 60 or current_log is None:
                latest = self._latest_log()
                if latest and latest != current_log:
                    log.info("LogTailer switching to %s", latest)
                    current_log = latest
                    position = 0
                last_rotation_check = now

            if current_log is None:
                log.debug("No openclaw-*.log found in %s; will retry in 10s", self.logs_dir)
                time.sleep(10)
                continue

            try:
                with open(current_log, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(position)
                    for line in fh:
                        self._parse_log_line(line)
                    position = fh.tell()
            except OSError as exc:
                log.warning("Could not read log file %s: %s", current_log, exc)

            time.sleep(1)


# ---------------------------------------------------------------------------
# Burn-rate calculator
# ---------------------------------------------------------------------------

class BurnRateCalculator(threading.Thread):
    daemon = True

    def __init__(self) -> None:
        super().__init__(name="BurnRateCalculator")

    def run(self) -> None:
        while True:
            time.sleep(60)
            now = time.time()
            cutoff = now - 3600
            # Aggregate cost per provider over the last hour
            provider_costs: dict[str, float] = collections.defaultdict(float)
            for event in list(cost_events):
                if event["ts"] >= cutoff:
                    provider_costs[event["provider"]] += event["cost"]
            for provider, total in provider_costs.items():
                cost_rate_dollars_per_hour.labels(provider=provider).set(total)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    log.info(
        "Starting OpenClaw metrics exporter (port=%d, sessions=%s, logs=%s)",
        METRICS_PORT,
        SESSIONS_DIR,
        LOGS_DIR,
    )

    watcher = SessionWatcher(SESSIONS_DIR)
    watcher.scan_existing()

    observer = Observer()
    observer.schedule(watcher, path=SESSIONS_DIR, recursive=True)
    observer.start()
    log.info("Watchdog observer started for %s", SESSIONS_DIR)

    log_tailer = LogTailer(LOGS_DIR)
    log_tailer.start()
    log.info("LogTailer started for %s", LOGS_DIR)

    burn_calc = BurnRateCalculator()
    burn_calc.start()
    log.info("BurnRateCalculator started")

    info_gauge.labels(version="1.0.0", primary_model="unknown").set(1)

    start_http_server(METRICS_PORT)
    log.info("Prometheus HTTP server listening on :%d", METRICS_PORT)

    signal.pause()


if __name__ == "__main__":
    main()
