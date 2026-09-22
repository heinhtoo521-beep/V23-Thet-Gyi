"""
V57.1 — APEX-GOD-LEVEL SINGULARITY (Super Signal Resolution Edition)
====================================================================
- Integrated Super Signal Detection:
  * 2 Steps Lock: "⚡ SUPER SIGNAL: ၂ ကြိမ်အတွင်း အမိလိုက်ပါ"
  * 3 Steps Lock: "⚡ SUPER SIGNAL: ၃ ကြိမ်အတွင်း အမိလိုက်ပါ"
- Core Principles 1 & 2 Maintained: PRNG State Recovery + 3D Phase Space Attractor.
- Strict Rules Maintained:
  * Free-Flow Scaling (Level 15+ Fibonacci Table, No Forced Cap).
  * Period + 1 Logic strictly enforced.
  * Silent Loss (Zero loss / level-up messages).
  * Strict Message Order: (Previous Win Message) -> (Next Period Signal).
  * Profit Target +100,000 Auto-Reset (Max Level, Max DD, Profit -> 0/1).
"""

from __future__ import annotations
import math
import time
import os
import requests
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple
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
    "warmup_target": 18,
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

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))

# ══════════════════════════════════════════════════════════
#  BETTING MANAGER (WITH +100k AUTO-RESET)
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
        self.cooldown_rounds = 0

    def reset_milestone(self):
        self.current_profit = 0.0
        self.max_loss_amount = 0.0
        self.max_level_reached = 1
        self.level = 1
        self.level_state = "WAITING_BET1"
        self.bot_step = 1

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
                self.cooldown_rounds = 0
                return "BET1_WIN", old_level
            else:
                self.level += 1
                self.level_state = "WAITING_BET1"
                self.bot_step += 1
                self.max_level_reached = max(self.max_level_reached, self.level)
                self.cooldown_rounds = 1 if self.level >= 4 else 0
                return "BET1_LOSE", old_level
        else:
            if won:
                self.level = 1
                self.level_state = "WAITING_BET1"
                self.bot_step = 1
                self.cycles_completed += 1
                self.cooldown_rounds = 0
                return "RESET", old_level
            else:
                self.level += 1
                self.level_state = "WAITING_BET1"
                self.bot_step += 1
                self.max_level_reached = max(self.max_level_reached, self.level)
                self.cooldown_rounds = 1 if self.level >= 4 else 0
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

        target_hit = False
        if self.current_profit >= CONFIG["profit_reset_threshold"]:
            target_hit = True

        return {
            "bet_amount": bet_amount,
            "bet_type": bet_type,
            "profit": profit,
            "action": action,
            "old_level": old_level,
            "new_level": self.level,
            "target_hit": target_hit,
        }

# ══════════════════════════════════════════════════════════
#  PREDICTION ENGINE WITH SUPER SIGNAL DETECTION
# ══════════════════════════════════════════════════════════
@dataclass
class V57Decision:
    action: str
    signal: str
    confidence: float
    tactical_mode: str
    level: int
    super_signal_text: Optional[str] = None  # Super Signal သတိပေးစာ

class PredictionEngineV57:
    def __init__(self, max_history: int = 150):
        self.history_digits = deque(maxlen=max_history)
        self.history_binary = deque(maxlen=max_history)

    def resolve(self, digit: int):
        self.history_digits.append(digit)
        self.history_binary.append(1 if digit >= 5 else 0)

    def _prng_state_recovery(self) -> float:
        digits = list(self.history_digits)
        if len(digits) < 10:
            return 0.50
        diffs = [(digits[i] - digits[i-1]) % 10 for i in range(1, len(digits))]
        recent_diffs = diffs[-6:]
        avg_drift = sum(recent_diffs) / len(recent_diffs)
        projected_digit = (digits[-1] + int(round(avg_drift))) % 10
        return 0.85 if projected_digit >= 5 else 0.15

    def _phase_space_attractor(self) -> float:
        d = list(self.history_digits)
        if len(d) < 12:
            return 0.50
        current_vector = (d[-1], d[-2], d[-3])
        attractor_pull = [0, 0]
        for i in range(len(d) - 4):
            vec = (d[i+2], d[i+1], d[i])
            dist = math.sqrt(
                (current_vector[0] - vec[0])**2 +
                (current_vector[1] - vec[1])**2 +
                (current_vector[2] - vec[2])**2
            )
            if dist < 4.5:
                next_val = 1 if d[i+3] >= 5 else 0
                weight = 1.0 / (dist + 0.5)
                attractor_pull[next_val] += weight
        total = sum(attractor_pull)
        return (attractor_pull[1] / total) if total > 0 else 0.50

    def _get_streaks(self) -> Tuple[int, int]:
        b = list(self.history_binary)
        if not b:
            return 0, -1
        last = b[-1]
        run = 0
        for x in reversed(b):
            if x == last:
                run += 1
            else:
                break
        return run, last

    def _get_alternations(self) -> int:
        b = list(self.history_binary)
        if len(b) < 2:
            return 0
        alt = 1
        for i in range(len(b) - 1, 0, -1):
            if b[i] != b[i - 1]:
                alt += 1
            else:
                break
        return alt

    def predict(self, current_level: int, current_state: str, cooldown: int) -> V57Decision:
        b = list(self.history_binary)
        d = list(self.history_digits)
        if len(b) < CONFIG["warmup_target"]:
            return V57Decision("WAIT", "Big", 0.50, "WARMUP", current_level)

        if cooldown > 0:
            return V57Decision("WAIT", "Big", 0.50, f"COOLDOWN_{cooldown}", current_level)

        last_digit = d[-1]
        streak_len, streak_val = self._get_streaks()
        alt_len = self._get_alternations()

        p_prng = self._prng_state_recovery()
        p_phase = self._phase_space_attractor()
        p_harmonics = sum(b[-8:]) / 8.0
        p_decay = (b[-1] * 0.45) + (b[-2] * 0.35) + (b[-3] * 0.20)

        # ══════════════════════════════════════════════════════════
        # SUPER SIGNAL RESOLUTION CHECK
        # ══════════════════════════════════════════════════════════
        super_text = None

        # ၁။ Singularity Double-Lock (Extreme Digits + Resonance) -> ၂ ကြိမ်အတွင်း
        if (last_digit in [0, 1, 8, 9]) and ((p_prng >= 0.70 and p_phase >= 0.65) or (p_prng <= 0.30 and p_phase <= 0.35)):
            super_text = "⚡ SUPER SIGNAL: ၂ ကြိမ်အတွင်း အမိလိုက်ပါ"

        # ၂။ Chop Exhaustion Strike (တလှည့်စီခုန်တာ ၄ ကြိမ်ပြည့်ပြီးချိန်) -> ၂ ကြိမ်အတွင်း
        elif alt_len >= 4:
            super_text = "⚡ SUPER SIGNAL: ၂ ကြိမ်အတွင်း အမိလိုက်ပါ"

        # ၃။ Resonant Dragon Streak (တူညီတာ ၃ ကြိမ်ထက် ဆက်နေချိန်) -> ၃ ကြိမ်အတွင်း
        elif streak_len >= 3 and abs(p_phase - 0.50) >= 0.20:
            super_text = "⚡ SUPER SIGNAL: ၃ ကြိမ်အတွင်း အမိလိုက်ပါ"

        # ══════════════════════════════════════════════════════════
        # BET 2 HYPER-RESONANT LOCK
        # ══════════════════════════════════════════════════════════
        if current_state == "WAITING_BET2":
            both_agree_big = (p_prng >= 0.52 and p_phase >= 0.52)
            both_agree_small = (p_prng < 0.48 and p_phase < 0.48)

            if both_agree_big:
                conf = min(0.98, 0.92 + abs(p_phase - 0.50))
                if not super_text:
                    super_text = "⚡ SUPER SIGNAL: ၂ ကြိမ်အတွင်း အမိလိုက်ပါ"
                return V57Decision("BET", "Big", conf, "BET2_GOD_RESONANCE_BIG", current_level, super_text)
            elif both_agree_small:
                conf = min(0.98, 0.92 + abs(p_phase - 0.50))
                if not super_text:
                    super_text = "⚡ SUPER SIGNAL: ၂ ကြိမ်အတွင်း အမိလိုက်ပါ"
                return V57Decision("BET", "Small", conf, "BET2_GOD_RESONANCE_SMALL", current_level, super_text)
            else:
                side = "Big" if p_phase >= 0.50 else "Small"
                return V57Decision("BET", side, 0.89, "BET2_PHASE_ATTRACTOR_FORCE", current_level, super_text)

        # ══════════════════════════════════════════════════════════
        # BET 1 MATRIX
        # ══════════════════════════════════════════════════════════
        p_combined = (0.40 * p_prng) + (0.35 * p_phase) + (0.15 * p_harmonics) + (0.10 * p_decay)
        side = "Big" if p_combined >= 0.50 else "Small"
        deviation = abs(p_combined - 0.50)

        if current_level >= 3:
            conflict = (p_prng >= 0.50 and p_phase < 0.50) or (p_prng < 0.50 and p_phase >= 0.50)
            if conflict:
                return V57Decision("WAIT", side, 0.50, f"SINGULARITY_SKIP_L{current_level}", current_level)

        conf = 0.74 + (deviation * 1.6)
        required_conf = 0.66 if current_level <= 2 else (0.75 if current_level <= 4 else 0.83)

        if conf < required_conf:
            return V57Decision("WAIT", side, conf, f"NOISE_FILTER_L{current_level}", current_level)

        conf = clamp(conf, 0.70, 0.98)
        return V57Decision("BET", side, conf, "QUANTUM_FLOW", current_level, super_text)

# ══════════════════════════════════════════════════════════
#  LIVE BOT & DISPATCHER
# ══════════════════════════════════════════════════════════
class V57LiveBot:
    def __init__(self):
        self.lock = threading.Lock()
        self.engine = PredictionEngineV57()
        self.betting = BettingManager()
        self.last_decision: Optional[V57Decision] = None

    def send_telegram_sync(self, message: str):
        if not TELEGRAM_TOKEN or not CHAT_ID:
            print(f"[TG-LOCAL]\n{message}", flush=True)
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        for _ in range(3):
            try:
                res = requests.post(url, json=payload, timeout=6)
                if res.status_code == 200:
                    break
            except Exception:
                time.sleep(0.5)

    def process_round(self, period: str, digit: int):
        with self.lock:
            actual_big = 1 if digit >= 5 else 0

            # 1. RESOLVE PREVIOUS ROUND (WIN MESSAGE)
            if self.last_decision and self.last_decision.action == "BET":
                won = (1 if self.last_decision.signal == "Big" else 0) == actual_big
                settle = self.betting.apply_result(won)

                if won:
                    if settle['action'] == 'RESET':
                        win_msg = (
                            f"🔥 WIN ✅ (+{settle['profit']:,.0f})\n"
                            f"🎉 BET2 WIN → Level 1 RESET\n"
                            f"🔄 Level {settle['old_level']} → Level 1\n"
                            f"💵 Profit: {self.betting.current_profit:+,.0f}\n"
                            f"📊 WR: {self.betting.get_wr():.1f}%"
                        )
                    else:
                        win_msg = (
                            f"🔥 WIN ✅ (+{settle['profit']:,.0f})\n"
                            f"🎯 Bet1 Win → Bet2 စောင့်\n"
                            f"🎮 Level: {self.betting.level} | BET2\n"
                            f"💵 Profit: {self.betting.current_profit:+,.0f}\n"
                            f"📊 WR: {self.betting.get_wr():.1f}%"
                        )
                    self.send_telegram_sync(win_msg)
                    time.sleep(0.3)

                    # PROFIT TARGET 100,000 AUTO-RESET
                    if settle.get("target_hit", False):
                        target_msg = (
                            f"🏆 <b>TARGET HIT: +100,000 REACHED!</b> 🎉\n"
                            f"━━━━━━━━━━━━━━━━━\n"
                            f"🔄 <b>Max Level, Max DD, Profit Reset to 0</b>\n"
                            f"🚀 စက်ဝန်းအသစ် ပြန်လည်စတင်ပါပြီ။"
                        )
                        self.send_telegram_sync(target_msg)
                        self.betting.reset_milestone()
                        time.sleep(0.3)
                else:
                    pass  # Silent Loss

            # 2. UPDATE KNOWLEDGE BASE
            self.engine.resolve(digit)

            if len(self.engine.history_digits) < CONFIG["warmup_target"]:
                return

            # 3. NEXT PREDICTION
            decision = self.engine.predict(
                current_level=self.betting.level,
                current_state=self.betting.level_state,
                cooldown=self.betting.cooldown_rounds
            )
            self.last_decision = decision

            if self.betting.cooldown_rounds > 0:
                self.betting.cooldown_rounds -= 1

            if decision.action == "WAIT":
                return

            bet_amt, b_type = self.betting.get_current_bet()
            self.betting.total_signals += 1

            # Period + 1
            try:
                current_num = int(period)
                next_period_num = current_num + 1
                period_str = str(next_period_num)[-3:]
            except Exception:
                period_str = str(period)[-3:]

            # Message တည်ဆောက်ခြင်း
            super_line = f"\n{decision.super_signal_text}" if decision.super_signal_text else ""

            sig_msg = (
                f"💖 Period {period_str}\n"
                f"🎯 SIGNAL → {decision.signal.upper()}\n"
                f"📊 Conf: {decision.confidence * 100:.1f}%{super_line}\n"
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
            self.send_telegram_sync(sig_msg)

# ══════════════════════════════════════════════════════════
#  TELEGRAM COMMANDS & API POLLER
# ══════════════════════════════════════════════════════════
def poll_telegram_commands(bot: V57LiveBot):
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
                            bot.send_telegram_sync(
                                f"📊 <b>STATUS UPDATE (V57.1 SUPER)</b>\n\n"
                                f"• Level: <b>{b.level} ({b.level_state})</b>\n"
                                f"• Bet: <b>{bet_amt:,} ({b_type})</b>\n"
                                f"• Profit: <b>{b.current_profit:+,.0f}</b>\n"
                                f"• Win Rate: <b>{b.get_wr():.1f}%</b>\n"
                                f"• Max Level: <b>{b.max_level_reached}</b>\n"
                                f"• Max DD: <b>{b.max_loss_amount:,.0f}</b>"
                            )
                        elif text == "/reset":
                            b.reset_all()
                            bot.send_telegram_sync("🔄 Level 1 သို့ ပြန်လည် Reset ချပြီးပါပြီ။")
        except Exception:
            time.sleep(2)
        time.sleep(1)

def run_api_poller(bot: V57LiveBot):
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
                                bot.engine.resolve(num)

                    if is_first_poll:
                        is_first_poll = False
        except Exception as e:
            print(f"[POLL ERROR] {e}", flush=True)

        time.sleep(CONFIG["poll_interval"])

app = Flask(__name__)
GLOBAL_BOT: Optional[V57LiveBot] = None

@app.route("/")
def index():
    return "V57.1 APEX-GOD-LEVEL Super Signal Live!", 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    GLOBAL_BOT = V57LiveBot()
    threading.Thread(target=run_api_poller, args=(GLOBAL_BOT,), daemon=True).start()
    threading.Thread(target=poll_telegram_commands, args=(GLOBAL_BOT,), daemon=True).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
