import os
import sqlite3
import time
import threading

from flask import Flask, request, jsonify

DB_PATH = os.path.join(os.path.dirname(__file__), "antibomb.db")

# --- защита: token bucket + cooldown + allowlist ---

ALLOWLIST = set()          # пусто = разрешены любые номера (в рамках лимитов)
DENYLIST = {"9000000000"}  # пример заблокированного номера

BUCKET_CAPACITY = 3        # макс. «бакет» запросов на номер
REFILL_PER_MIN = 1         # сколько токенов возвращается в минуту
COOLDOWN_SEC = 60          # минимальная пауза между запросами с одного IP

_lock = threading.Lock()
_buckets = {}   # phone -> (tokens, last_ts)
_last_ip = {}   # ip -> last_ts
_log = []       # журнал попыток


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS attempts ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts REAL, phone TEXT, ip TEXT, ok INTEGER, reason TEXT)"
    )
    conn.commit()
    return conn


def check_request(phone: str, ip: str):
    """Возвращает (ok, reason). Применяет все правила защиты."""
    now = time.time()
    with _lock:
        if phone in DENYLIST:
            return False, "phone blocked"
        if ALLOWLIST and phone not in ALLOWLIST:
            return False, "phone not in allowlist"

        last_ip_ts = _last_ip.get(ip, 0)
        if now - last_ip_ts < COOLDOWN_SEC:
            return False, f"ip cooldown {int(COOLDOWN_SEC - (now - last_ip_ts))}s"

        tokens, last_ts = _buckets.get(phone, (BUCKET_CAPACITY, now))
        tokens = min(BUCKET_CAPACITY, tokens + (now - last_ts) / 60 * REFILL_PER_MIN)
        if tokens < 1:
            _buckets[phone] = (tokens, now)
            return False, "rate limit (token bucket empty)"
        _buckets[phone] = (tokens - 1, now)
        _last_ip[ip] = now

        conn = _db()
        conn.execute(
            "INSERT INTO attempts (ts, phone, ip, ok, reason) VALUES (?,?,?,?,?)",
            (now, phone, ip, 1, "ok"),
        )
        conn.commit()
        conn.close()
        return True, "ok"


def log_denied(phone: str, ip: str, reason: str):
    with _lock:
        _log.append((time.time(), phone, ip, reason))
        conn = _db()
        conn.execute(
            "INSERT INTO attempts (ts, phone, ip, ok, reason) VALUES (?,?,?,?,?)",
            (time.time(), phone, ip, 0, reason),
        )
        conn.commit()
        conn.close()


def spike_alert(threshold=10, window=60):
    """True, если за последние window секунд было >= threshold отказов —
    сюда в реальном боте вешается уведомление в Telegram."""
    cutoff = time.time() - window
    recent = [e for e in _log if e[0] >= cutoff and e[3] != "ok"]
    return len(recent) >= threshold, len(recent)


app = Flask(__name__)


@app.route("/sms/request", methods=["POST"])
def sms_request():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", ""))
    if not phone.isdigit() or len(phone) < 10:
        return jsonify(error="invalid phone"), 400
    ok, reason = check_request(phone, request.remote_addr or "?")
    if not ok:
        log_denied(phone, request.remote_addr or "?", reason)
        return jsonify(error="rejected", reason=reason), 429
    # реальной отправки нет — это эмулятор шлюза
    return jsonify(status="queued", phone=phone, note="emulated, nothing sent")


@app.route("/call/request", methods=["POST"])
def call_request():
    return sms_request()  # та же логика защиты


@app.route("/stats", methods=["GET"])
def stats():
    conn = _db()
    rows = conn.execute(
        "SELECT ok, COUNT(*) FROM attempts GROUP BY ok"
    ).fetchall()
    conn.close()
    return jsonify(stats={str(ok): n for ok, n in rows})


def main():
    port = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", "20129")))
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
