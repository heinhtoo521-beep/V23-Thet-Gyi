"""
V36.0 — APEX-SINGULARITY KERNEL (Render Production Ready)
=========================================================
Strict Rules Preserved:
  ✓ RETAINED: No Level Cap (Unlimited Martingale/Fibonacci)
  ✓ RETAINED: Exact Original Bet Sizing Table & Structure
  ✓ RETAINED: 100% Signal Frequency (Round တိုင်း Signal အမြဲထွက်သည်)
  ✓ FIX: Flask Web Server Bind to 0.0.0.0 for Render Port Health Check
"""

from __future__ import annotations
import math
import time
import os
import requests
import threading
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Optional, Dict, List
from flask import Flask, jsonify

# ══════════════════════════════════════════════════════════
#  CREDENTIALS & CONFIG
# ══════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
LOTTERY_AUTH = os.environ.get("LOTTERY_AUTH", "")

COLOUR_MAP = {
    0: "Violet+Red", 1: "Green", 2: "Red", 3: "Green", 4: "Red",
    5: "Violet+Green", 6: "Red", 7: "Green", 8: "Red", 9: "Green",
}

CONFIG = {
    "api_url": "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList",
    "payout_rate": 0.96,
    "profit_reset_threshold": 100000,
    "poll_interval": 2.0,
    "warmup_target": 15,
}

# မူရင်း Bet Structure အတိုင်း လုံးဝမပြောင်းလဲပါ
LEVEL_TABLE = {
    1:  {"bet1": 1000,  "bet2": 2000},
    2:  {"bet1": 1000,  "bet2": 2000},
    3:  {"bet1": 2000,  "bet2": 4000},
    4:  {"bet1": 2000,  "bet2": 4000},
    5:  {"bet1": 3000,  "bet2": 6000},
    6:  {"bet1": 4000,  "bet2": 8000},
    7:  {"bet1": 6000,  "bet2": 12000},
    8:  {"bet1": 8000,  "bet2": 16000},
    9:  {"bet1": 10000, "bet2": 20000},
    10: {"bet1": 14000, "bet2": 28000},
    11: {"bet1": 19000, "bet2": 38000},
    12: {"bet1": 25000, "bet2": 50000},
    13: {"bet1": 34000, "bet2": 68000},
    14: {"bet1": 46000, "bet2": 92000},
    15: {"bet1": 62000, "bet2": 124000},
}

def get_level_bet(level: int):
    """Fibonacci extension beyond level 15 (Original flow maintained)."""
    if level in LEVEL_TABLE:
        return LEVEL_TABLE[level]
    a = LEVEL_TABLE[14]["bet1"]
    b = LEVEL_TABLE[15]["bet1"]
    for _ in range(level - 15):
        a, b = b, a + b
    return {"bet1": b, "bet2": b * 2}

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(x)))

# ══════════════════════════════════════════════════════════
#  BETTING MANAGER (ORIGINAL RULES PRESERVED - NO CAP)
# ══════════════════════════════════════════════════════════
class BettingManager:
    def __init__(self):
        self.reset_all()

    def reset_all(self):
        self.level = 1
        self.level_state = "WAITING_BET1"
        self.total_signals = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_profit = 0.0
        self.total_loss_amount = 0.0
        self.current_profit = 0.0
        self.max_loss_amount = 0.0
        self.max_level_reached = 1
        self.cycles_completed = 0
        self.profit_resets = 0

    def get_current_bet(self):
        info = get_level_bet(self.level)
        if self.level_state == "WAITING_BET1":
            return info["bet1"], "BET1"
        return info["bet2"], "BET2"

    def get_wr(self):
        total = self.total_wins + self.total_losses
        return (self.total_wins / total * 100) if total > 0 else 0.0

    def on_result(self, won: bool):
        old_level = self.level
        if self.level_state == "WAITING_BET1":
            if won:
                self.level_state = "WAITING_BET2"
                return "BET1_WIN", old_level
            else:
                self.level += 1
                self.level_state = "WAITING_BET1"
                self.max_level_reached = max(self.max_level_reached, self.level)
                return "BET1_LOSE", old_level
        else:
            if won:
                self.level = 1
                self.level_state = "WAITING_BET1"
                self.cycles_completed += 1
                return "RESET", old_level
            else:
                self.level += 1
                self.level_state = "WAITING_BET1"
                self.max_level_reached = max(self.max_level_reached, self.level)
                return "BET2_LOSE", old_level

    def apply_result(self, won: bool):
        bet_amount, bet_type = self.get_current_bet()
        if won:
            profit = bet_amount * CONFIG["payout_rate"]
            self.total_profit += profit
            self.current_profit += profit
            self.total_wins += 1
        else:
            profit = -bet_amount
            self.total_loss_amount += bet_amount
            self.current_profit -= bet_amount
            self.total_losses += 1

        self.max_loss_amount = min(self.max_loss_amount, self.current_profit)
        action, old_level = self.on_result(won)

        return {
            "bet_amount": bet_amount,
            "bet_type": bet_type,
            "profit": profit,
            "action": action,
            "old_level": old_level,
            "new_level": self.level,
        }

    def check_profit_reset(self):
        if self.current_profit >= CONFIG["profit_reset_threshold"]:
            report = {
                "net_profit": self.current_profit,
                "max_level": self.max_level_reached,
            }
            self.total_profit = 0.0
            self.total_loss_amount = 0.0
            self.current_profit = 0.0
            self.max_loss_amount = 0.0
            self.level = 1
            self.level_state = "WAITING_BET1"
            self.max_level_reached = 1
            self.profit_resets += 1
            return report
        return None

# ══════════════════════════════════════════════════════════
#  APEX-SINGULARITY KERNEL ENGINE
# ══════════════════════════════════════════════════════════
@dataclass
class V36Decision:
    action: str          # "BET" (100% High Frequency)
    signal: str          # "Big" or "Small"
    confidence: float
    tactical_mode: str
    level: int

class PredictionEngineV36:
    def __init__(self, max_history=3000):
        self.history = deque(maxlen=max_history)
        self.markov_mem = defaultdict(lambda: [1.0, 1.0])
        self.pattern_mem = defaultdict(lambda: [1.0, 1.0])

    def resolve(self, actual_big: int):
        h = list(self.history)
        if len(h) >= 2:
            self.markov_mem[h[-1]][actual_big] += 1.0
        if len(h) >= 3:
            key2 = (h[-2], h[-1])
            self.pattern_mem[key2][actual_big] += 1.0
        self.history.append(actual_big)

    def _get_run_length(self) -> int:
        h = list(self.history)
        if not h:
            return 0
        last = h[-1]
        run = 0
        for x in reversed(h):
            if x == last:
                run += 1
            else:
                break
        return run

    def predict(self, current_level: int, current_state: str) -> V36Decision:
        h = list(self.history)
        if len(h) < CONFIG["warmup_target"]:
            side = "Big" if sum(h[-5:]) >= 3 else "Small"
            return V36Decision("BET", side, 0.50, "WARMUP", current_level)

        last = h[-1]
        run_len = self._get_run_length()

        # 1. Base Markov
        m_stats = self.markov_mem[last]
        p_m = (m_stats[1] + 1.0) / (sum(m_stats) + 2.0)

        # 2. 2-Order Pattern Matcher
        key2 = (h[-2], last) if len(h) >= 2 else (0, last)
        p_stats = self.pattern_mem[key2]
        p_pat = (p_stats[1] + 1.0) / (sum(p_stats) + 2.0)

        p_final = clamp(0.52 * p_pat + 0.48 * p_m)
        side = "Big" if p_final >= 0.5 else "Small"
        mode = "STANDARD_FLOW"

        # 3. CRITICAL CYCLE-BREAKER POLICY (Level 4+ Interception)
        if current_level >= 4:
            mode = f"APEX_INTERCEPT_L{current_level}"
            if run_len >= 2:
                if run_len >= 4:
                    side = "Small" if last == 1 else "Big"
                else:
                    side = "Big" if last == 1 else "Small"
            else:
                side = "Small" if last == 1 else "Big"

        # 4. BET 2 RAPID RESET LOCK (Focuses on Instant Reset to Level 1)
        if current_state == "WAITING_BET2":
            mode = "BET2_RAPID_RESET_LOCK"
            if run_len >= 2:
                side = "Big" if last == 1 else "Small"
            else:
                side = "Small" if last == 1 else "Big"

        conf = abs(p_final - 0.5) * 2.0

        return V36Decision(
            action="BET",
            signal=side,
            confidence=conf,
            tactical_mode=mode,
            level=current_level
        )

# ══════════════════════════════════════════════════════════
#  LIVE BOT & TELEGRAM DISPATCHER
# ══════════════════════════════════════════════════════════
class V36LiveBot:
    def __init__(self):
        self.lock = threading.Lock()
        self.engine = PredictionEngineV36()
        self.betting = BettingManager()
        self.last_decision: Optional[V36Decision] = None
        self.is_warmup = True

    def send_telegram(self, message: str):
        if not TELEGRAM_TOKEN or not CHAT_ID:
            print(f"[TG-LOG] {message[:100]}...", flush=True)
            return

        def _send():
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
            for _ in range(3):
                try:
                    res = requests.post(url, json=payload, timeout=8)
                    if res.status_code == 200:
                        break
                except Exception:
                    time.sleep(1)

        threading.Thread(target=_send, daemon=True).start()

    def process_round(self, period: str, digit: int):
        with self.lock:
            actual_big = 1 if digit >= 5 else 0
            actual_text = "Big" if actual_big == 1 else "Small"

            # 1. Resolve Previous Bet
            if self.last_decision and self.last_decision.action == "BET":
                won = (1 if self.last_decision.signal == "Big" else 0) == actual_big
                settle = self.betting.apply_result(won)

                if won:
                    if settle['action'] == 'RESET':
                        self.send_telegram(
                            f"✅ <b>WIN (+{settle['profit']:,.0f})</b>\n"
                            f"🎉 <b>BET2 WIN ➔ LEVEL 1 RESET!</b>\n"
                            f"Level: {settle['old_level']} ➔ 1\n"
                            f"Profit: <b>{self.betting.current_profit:+,.0f}</b>\n"
                            f"WR: {self.betting.get_wr():.1f}%"
                        )
                    else:
                        self.send_telegram(
                            f"✅ <b>WIN (+{settle['profit']:,.0f})</b>\n"
                            f"➡️ <b>BET1 WIN ➔ PROCEED TO BET2</b>\n"
                            f"Level: {self.betting.level} | Next: BET2\n"
                            f"Profit: <b>{self.betting.current_profit:+,.0f}</b>"
                        )
                else:
                    self.send_telegram(
                        f"❌ <b>LOSS ({settle['profit']:,.0f})</b>\n"
                        f"⚠️ Level: {settle['old_level']} ➔ {settle['new_level']}\n"
                        f"Profit: <b>{self.betting.current_profit:+,.0f}</b>"
                    )

                reset = self.betting.check_profit_reset()
                if reset:
                    self.send_telegram(
                        f"🏆 <b>PROFIT RESET TARGET HIT!</b>\n"
                        f"Net Banked: <b>+{reset['net_profit']:,.0f}</b>\n"
                        f"Max Level: {reset['max_level']}\n"
                        f"Resetting back to Level 1..."
                    )

            # 2. Update Engine Knowledge
            self.engine.resolve(actual_big)

            # 3. Check Warmup
            if len(self.engine.history) < CONFIG["warmup_target"]:
                print(f"[WARMUP] Collected {len(self.engine.history)}/{CONFIG['warmup_target']} rounds.", flush=True)
                return

            # 4. Generate Next Prediction
            decision = self.engine.predict(current_level=self.betting.level, current_state=self.betting.level_state)
            self.last_decision = decision
            bet_amt, b_type = self.betting.get_current_bet()
            self.betting.total_signals += 1

            # Dispatch Signal to Telegram
            self.send_telegram(
                f"🚨 <b>PERIOD {str(period)[-4:]} SIGNAL</b>\n"
                f"🎯 TARGET: <b>{decision.signal.upper()}</b>\n"
                f"📊 Conf: {decision.confidence:.1%} | Mode: <code>{decision.tactical_mode}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 Level: <b>{self.betting.level}</b> ({b_type})\n"
                f"💵 Bet: <b>{bet_amt:,}</b>\n"
                f"📈 Net Profit: <b>{self.betting.current_profit:+,.0f}</b> | WR: {self.betting.get_wr():.1f}%\n"
                f"🎲 Last: {digit} ({actual_text})"
            )

# ══════════════════════════════════════════════════════════
#  API POLLER WORKER
# ══════════════════════════════════════════════════════════
def run_api_poller(bot: V36LiveBot):
    print("🚀 V36.0 Live Poller Loop Started...", flush=True)
    seen_periods = set()
    seen_order = deque(maxlen=1000)
    is_first_poll = True

    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": f"Bearer {LOTTERY_AUTH}",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://6win598.com",
        "referer": "https://6win598.com/",
        "user-agent": "Mozilla/5.0",
    }

    while True:
        try:
            payload = {
                "pageSize": 10, "pageNo": 1, "typeId": 30, "language": 7,
                "random": "036263f367384d418be07465793c8da8",
                "signature": "55F4FD150F15F090B943374F3C9BE78B",
                "timestamp": int(time.time()),
            }
            res = requests.post(CONFIG["api_url"], headers=headers, json=payload, timeout=5)
            if res.status_code == 200:
                data = res.json().get("data", {}).get("list", [])
                if data:
                    sorted_data = sorted(data, key=lambda x: int(x.get("issueNumber", 0)))
                    for item in sorted_data:
                        period = str(item.get("issueNumber"))
                        num = int(item.get("number"))
                        if period not in seen_periods:
                            seen_periods.add(period)
                            seen_order.append(period)
                            if len(seen_periods) > 1000:
                                oldest = seen_order.popleft()
                                seen_periods.discard(oldest)

                            if not is_first_poll:
                                print(f"[ROUND] {period} -> Number: {num}", flush=True)
                                bot.process_round(period, num)
                            else:
                                bot.engine.history.append(1 if num >= 5 else 0)

                    if is_first_poll:
                        is_first_poll = False
                        print(f"✅ Initialized with {len(bot.engine.history)} historical rounds.", flush=True)
        except Exception as e:
            print(f"[POLL ERROR] {e}", flush=True)

        time.sleep(CONFIG["poll_interval"])

# ══════════════════════════════════════════════════════════
#  FLASK WEB SERVER (PREVENTS RENDER EXIT EARLY)
# ══════════════════════════════════════════════════════════
app = Flask(__name__)
GLOBAL_BOT: Optional[V36LiveBot] = None

@app.route("/")
def index():
    if not GLOBAL_BOT:
        return "Bot Initializing...", 200
    b = GLOBAL_BOT.betting
    return f"""
    <h2>V36.0 APEX-SINGULARITY BOT RUNNING</h2>
    <p><b>Status:</b> Active (100% Signal Frequency)</p>
    <p><b>Current Level:</b> {b.level} ({b.level_state})</p>
    <p><b>Net Profit:</b> {b.current_profit:+,.0f}</p>
    <p><b>Win Rate:</b> {b.get_wr():.1f}%</p>
    <p><b>Max Level Seen:</b> {b.max_level_reached}</p>
    <p><b>Profit Resets Completed:</b> {b.profit_resets}</p>
    """, 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "V36-APEX-BOT"}), 200

# ══════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🌟 Starting V36.0 Apex-Singularity Bot Service...", flush=True)
    GLOBAL_BOT = V36LiveBot()

    # Background Thread အဖြစ် Poller စတင်ခြင်း
    poller_thread = threading.Thread(target=run_api_poller, args=(GLOBAL_BOT,), daemon=True)
    poller_thread.start()

    # Render Service မပိတ်သွားစေရန် Flask Server ကို 0.0.0.0 တွင် Listen လုပ်ခြင်း
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
