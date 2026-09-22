"""
V36.0 — APEX-SINGULARITY KERNEL (Custom Telegram Template)
===========================================================
- Strict Rules Maintained (No Level Cap, No Change Bet Size, 100% Signal)
- Telegram Format: Exactly as requested
- LOSS suppression: ရှုံးသည့်အခါ မလိုအပ်သော စာတိုများ မပို့ဘဲ LEVEL UP သာ ပို့ပေးသည်။
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

CONFIG = {
    "api_url": "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList",
    "payout_rate": 0.96,
    "profit_reset_threshold": 100000,
    "poll_interval": 2.0,
    "warmup_target": 15,
}

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
#  BETTING MANAGER
# ══════════════════════════════════════════════════════════
class BettingManager:
    def __init__(self):
        self.reset_all()

    def reset_all(self):
        self.level = 1
        self.level_state = "WAITING_BET1"
        self.bot_step = 1
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
                self.bot_step = 1
                return "BET1_WIN", old_level
            else:
                self.level += 1
                self.level_state = "WAITING_BET1"
                self.bot_step += 1
                self.max_level_reached = max(self.max_level_reached, self.level)
                return "BET1_LOSE", old_level
        else:
            if won:
                self.level = 1
                self.level_state = "WAITING_BET1"
                self.bot_step = 1
                self.cycles_completed += 1
                return "RESET", old_level
            else:
                self.level += 1
                self.level_state = "WAITING_BET1"
                self.bot_step += 1
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

# ══════════════════════════════════════════════════════════
#  APEX-SINGULARITY KERNEL ENGINE
# ══════════════════════════════════════════════════════════
@dataclass
class V36Decision:
    action: str
    signal: str
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
            return V36Decision("BET", side, 0.55, "WARMUP", current_level)

        last = h[-1]
        run_len = self._get_run_length()

        m_stats = self.markov_mem[last]
        p_m = (m_stats[1] + 1.0) / (sum(m_stats) + 2.0)

        key2 = (h[-2], last) if len(h) >= 2 else (0, last)
        p_stats = self.pattern_mem[key2]
        p_pat = (p_stats[1] + 1.0) / (sum(p_stats) + 2.0)

        p_final = clamp(0.52 * p_pat + 0.48 * p_m)
        side = "Big" if p_final >= 0.5 else "Small"
        mode = "STANDARD_FLOW"

        if current_level >= 4:
            mode = f"APEX_INTERCEPT_L{current_level}"
            if run_len >= 2:
                if run_len >= 4:
                    side = "Small" if last == 1 else "Big"
                else:
                    side = "Big" if last == 1 else "Small"
            else:
                side = "Small" if last == 1 else "Big"

        if current_state == "WAITING_BET2":
            mode = "BET2_RAPID_RESET_LOCK"
            if run_len >= 2:
                side = "Big" if last == 1 else "Small"
            else:
                side = "Small" if last == 1 else "Big"

        conf = 0.50 + abs(p_final - 0.5)

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

    def send_telegram(self, message: str):
        if not TELEGRAM_TOKEN or not CHAT_ID:
            print(f"[TG-LOCAL]\n{message}", flush=True)
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

            # 1. Resolve Previous Round
            if self.last_decision and self.last_decision.action == "BET":
                won = (1 if self.last_decision.signal == "Big" else 0) == actual_big
                settle = self.betting.apply_result(won)

                # WIN ဖြစ်ချိန် ပုံစံများ
                if won:
                    if settle['action'] == 'RESET':
                        msg = (
                            f"🔥 WIN ✅ (+{settle['profit']:,.0f})\n"
                            f"🎉 BET2 WIN → Level 1 RESET\n"
                            f"🔄 Level {settle['old_level']} → Level 1\n"
                            f"💵 Profit: {self.betting.current_profit:+,.0f}\n"
                            f"📊 WR: {self.betting.get_wr():.1f}%"
                        )
                        self.send_telegram(msg)
                    else:
                        msg = (
                            f"🔥 WIN ✅ (+{settle['profit']:,.0f})\n"
                            f"🎯 Bet1 Win → Bet2 စောင့်\n"
                            f"🎮 Level: {self.betting.level} | BET2\n"
                            f"💵 Profit: {self.betting.current_profit:+,.0f}\n"
                            f"📊 WR: {self.betting.get_wr():.1f}%"
                        )
                        self.send_telegram(msg)
                else:
                    # ရှုံးသည့်အခါ LOSS စာလုံးမပို့ဘဲ LEVEL UP သာ ပို့သည်
                    next_bet1 = get_level_bet(settle['new_level'])['bet1']
                    msg = (
                        f"📈 LEVEL UP\n"
                        f"🔄 Level {settle['old_level']} → Level {settle['new_level']}\n"
                        f"💰 Next Bet1: {next_bet1:,}"
                    )
                    self.send_telegram(msg)

            # 2. Update Knowledge Base
            self.engine.resolve(actual_big)

            if len(self.engine.history) < CONFIG["warmup_target"]:
                return

            # 3. Next Prediction
            decision = self.engine.predict(current_level=self.betting.level, current_state=self.betting.level_state)
            self.last_decision = decision
            bet_amt, b_type = self.betting.get_current_bet()
            self.betting.total_signals += 1

            # Period အချက်ပြ Signal ပုံစံ
            period_str = str(period)[-3:]
            sig_msg = (
                f"💖 Period {period_str}\n"
                f"🎯 SIGNAL → {decision.signal.upper()}\n"
                f"📊 Conf: {decision.confidence * 100:.1f}%\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🤖 Bot Step: {self.betting.bot_step}x\n"
                f"🎮 Level: {self.betting.level} | {b_type}\n"
                f"💰 Bet: {bet_amt:,}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🏆 Max Level: {self.betting.max_level_reached}\n"
                f"📉 Max DD: {self.betting.max_loss_amount:,.0f}\n"
                f"💵 Profit: {self.betting.current_profit:+,.0f}\n"
                f"📊 WR: {self.betting.get_wr():.1f}%"
            )
            self.send_telegram(sig_msg)

# ══════════════════════════════════════════════════════════
#  TELEGRAM COMMANDS LISTENER
# ══════════════════════════════════════════════════════════
def poll_telegram_commands(bot: V36LiveBot):
    if not TELEGRAM_TOKEN:
        return
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=15"
            res = requests.get(url, timeout=20)
            if res.status_code == 200:
                updates = res.json().get("result", [])
                for upd in updates:
                    offset = upd["update_id"] + 1
                    msg = upd.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "").strip().lower()

                    if chat_id == str(CHAT_ID):
                        b = bot.betting
                        bet_amt, b_type = b.get_current_bet()
                        if text == "/status":
                            bot.send_telegram(
                                f"📊 <b>STATUS UPDATE</b>\n\n"
                                f"• Level: <b>{b.level} ({b.level_state})</b>\n"
                                f"• Bet: <b>{bet_amt:,} ({b_type})</b>\n"
                                f"• Profit: <b>{b.current_profit:+,.0f}</b>\n"
                                f"• Win Rate: <b>{b.get_wr():.1f}%</b>\n"
                                f"• Max Level: <b>{b.max_level_reached}</b>"
                            )
                        elif text == "/reset":
                            b.reset_all()
                            bot.send_telegram("🔄 Level 1 သို့ ပြန်လည် Reset ချပြီးပါပြီ။")
        except Exception:
            time.sleep(2)
        time.sleep(1)

# ══════════════════════════════════════════════════════════
#  API POLLER WORKER
# ══════════════════════════════════════════════════════════
def run_api_poller(bot: V36LiveBot):
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
                                bot.process_round(period, num)
                            else:
                                bot.engine.history.append(1 if num >= 5 else 0)

                    if is_first_poll:
                        is_first_poll = False
        except Exception as e:
            print(f"[POLL ERROR] {e}", flush=True)

        time.sleep(CONFIG["poll_interval"])

# ══════════════════════════════════════════════════════════
#  FLASK SERVER & MAIN
# ══════════════════════════════════════════════════════════
app = Flask(__name__)
GLOBAL_BOT: Optional[V36LiveBot] = None

@app.route("/")
def index():
    return "V36.0 Custom Bot Live!", 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    GLOBAL_BOT = V36LiveBot()
    threading.Thread(target=run_api_poller, args=(GLOBAL_BOT,), daemon=True).start()
    threading.Thread(target=poll_telegram_commands, args=(GLOBAL_BOT,), daemon=True).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
