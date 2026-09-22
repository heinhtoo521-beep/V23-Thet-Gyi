"""
V52.1 — APEX-CHRONO QUANTUM SINGULARITY (Strict Message Sequence Edition)
=========================================================================
- Fixed Message Ordering: WIN message is GUARANTEED to appear BEFORE next Signal.
- Removed background race conditions using a Synchronous Serial Queue.
- Signal Period is ALWAYS API Issue Number + 1.
- LEVEL UP messages completely removed (Silent on loss).
- Flow: Period 015 Signal -> Period 015 WIN -> Period 016 Signal.
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
    "warmup_target": 12,
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
        self.cooldown_rounds = 0

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
                self.cooldown_rounds = 1 if self.level >= 3 else 0
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
                self.cooldown_rounds = 1 if self.level >= 3 else 0
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
#  PENTA-BAND NEXUS PREDICTION ENGINE
# ══════════════════════════════════════════════════════════
@dataclass
class V36Decision:
    action: str
    signal: str
    confidence: float
    tactical_mode: str
    level: int

class PredictionEngineV36:
    def __init__(self, max_history: int = 150):
        self.history = deque(maxlen=max_history)

    def resolve(self, actual_big: int):
        self.history.append(actual_big)

    def _get_streaks(self) -> Tuple[int, int]:
        h = list(self.history)
        if not h:
            return 0, -1
        last = h[-1]
        run = 0
        for x in reversed(h):
            if x == last:
                run += 1
            else:
                break
        return run, last

    def _get_alternations(self) -> int:
        h = list(self.history)
        if len(h) < 2:
            return 0
        alt = 1
        for i in range(len(h) - 1, 0, -1):
            if h[i] != h[i - 1]:
                alt += 1
            else:
                break
        return alt

    def predict(self, current_level: int, current_state: str, cooldown: int) -> V36Decision:
        h = list(self.history)
        if len(h) < CONFIG["warmup_target"]:
            side = "Big" if sum(h[-5:]) >= 3 else "Small"
            return V36Decision("BET", side, 0.55, "WARMUP", current_level)

        last = h[-1]
        run_len, run_val = self._get_streaks()
        alt_len = self._get_alternations()

        recent_6 = h[-6:]
        decay_sum, weight_sum = 0.0, 0.0
        n = len(recent_6)
        for idx, val in enumerate(recent_6):
            w = math.exp((idx - n) / 2.8)
            decay_sum += val * w
            weight_sum += w
        p_band_a = decay_sum / weight_sum if weight_sum > 0 else 0.5

        k2_count = [0, 0]
        if len(h) >= 3:
            k2 = (h[-2], last)
            for i in range(len(h) - 2):
                if (h[i], h[i+1]) == k2:
                    k2_count[h[i+2]] += 1
        p_band_b = (k2_count[1] + 1.0) / (sum(k2_count) + 2.0)

        recent_12 = sum(h[-12:]) / 12.0
        p_band_c = 1.0 - recent_12

        is_alternating = (len(h) >= 2 and h[-1] != h[-2])
        p_band_d = (1.0 - last) if is_alternating else last

        recent_4 = h[-4:]
        diff = sum(recent_4) / 4.0
        p_band_e = 0.70 if diff >= 0.75 else (0.30 if diff <= 0.25 else 0.50)

        golden_override = False
        if cooldown > 0:
            if run_len >= 2 or alt_len >= 2:
                golden_override = True
            else:
                return V36Decision("WAIT", "Big", 0.50, f"COOLDOWN_{cooldown}", current_level)

        if current_state == "WAITING_BET2":
            if run_len >= 2:
                side = "Big" if run_val == 1 else "Small"
                mode = f"BET2_CHRONO_DRAGON_S{run_len}"
                conf = min(0.98, 0.91 + (run_len * 0.03))
                return V36Decision("BET", side, conf, mode, current_level)
            elif alt_len >= 2:
                side = "Small" if last == 1 else "Big"
                mode = f"BET2_CHRONO_CHOP_A{alt_len}"
                conf = min(0.96, 0.89 + (alt_len * 0.03))
                return V36Decision("BET", side, conf, mode, current_level)
            else:
                p_comb = (0.35 * p_band_a) + (0.30 * p_band_b) + (0.15 * p_band_c) + (0.10 * p_band_d) + (0.10 * p_band_e)
                side = "Big" if p_comb >= 0.50 else "Small"
                mode = "BET2_CHRONO_FORCE"
                conf = 0.91
                return V36Decision("BET", side, conf, mode, current_level)

        p_final = (0.35 * p_band_a) + (0.30 * p_band_b) + (0.15 * p_band_c) + (0.10 * p_band_d) + (0.10 * p_band_e)
        side = "Big" if p_final >= 0.50 else "Small"
        deviation = abs(p_final - 0.50)

        if current_level >= 3:
            votes_big = sum([
                1 if p_band_a >= 0.5 else 0,
                1 if p_band_b >= 0.5 else 0,
                1 if p_band_c >= 0.5 else 0,
                1 if p_band_d >= 0.5 else 0,
                1 if p_band_e >= 0.5 else 0,
            ])
            has_super_majority = (votes_big >= 4) if side == "Big" else (votes_big <= 1)

            if not has_super_majority and not golden_override:
                return V36Decision("WAIT", side, 0.50, f"LOCKDOWN_SKIP_L{current_level}", current_level)

            required_conf = 0.74
            mode = f"CHRONO_LOCKDOWN_L{current_level}"
            conf = 0.78 + (deviation * 1.8)
        else:
            required_conf = 0.56 if current_level == 1 else 0.62
            if run_len >= 2:
                side = "Big" if run_val == 1 else "Small"
                mode = f"CHRONO_STREAK_S{run_len}"
                conf = min(0.95, 0.76 + (run_len * 0.04))
            elif alt_len >= 2:
                side = "Small" if last == 1 else "Big"
                mode = f"CHRONO_CHOP_A{alt_len}"
                conf = min(0.94, 0.75 + (alt_len * 0.04))
            else:
                mode = "CHRONO_FLOW"
                conf = 0.62 + (deviation * 1.6)

        if conf < required_conf and not golden_override:
            return V36Decision("WAIT", side, conf, f"NOISE_FILTER_L{current_level}", current_level)

        conf = clamp(conf, 0.62, 0.98)
        return V36Decision("BET", side, conf, mode, current_level)

# ══════════════════════════════════════════════════════════
#  LIVE BOT & SYNCHRONOUS TELEGRAM SENDER
# ══════════════════════════════════════════════════════════
class V36LiveBot:
    def __init__(self):
        self.lock = threading.Lock()
        self.engine = PredictionEngineV36()
        self.betting = BettingManager()
        self.last_decision: Optional[V36Decision] = None

    def send_telegram_sync(self, message: str):
        """အစီအစဉ်မလွဲချော်စေရန် တိုက်ရိုက်ပို့ဆောင်သော Synchronous Method"""
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

            # ══════════════════════════════════════════════════════════
            # 1. RESOLVE PREVIOUS ROUND (WIN MESSAGE ကို အရင်ပို့ခြင်း)
            # ══════════════════════════════════════════════════════════
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
                    # Win message ကို အရင် ရောက်အောင်ပို့ပြီး အနည်းငယ် စောင့်သည်
                    self.send_telegram_sync(win_msg)
                    time.sleep(0.3)
                else:
                    # Loss ဖြစ်ပါက တိတ်ဆိတ်စွာ ကျော်သည်
                    pass

            # ══════════════════════════════════════════════════════════
            # 2. UPDATE KNOWLEDGE BASE
            # ══════════════════════════════════════════════════════════
            self.engine.resolve(actual_big)

            if len(self.engine.history) < CONFIG["warmup_target"]:
                return

            # ══════════════════════════════════════════════════════════
            # 3. NEXT PREDICTION & SIGNAL SENDING
            # ══════════════════════════════════════════════════════════
            decision = self.engine.predict(
                current_level=self.betting.level,
                current_state=self.betting.level_state,
                cooldown=self.betting.cooldown_rounds
            )
            self.last_decision = decision

            if self.betting.cooldown_rounds > 0 and decision.action != "WAIT":
                self.betting.cooldown_rounds = max(0, self.betting.cooldown_rounds - 1)
            elif self.betting.cooldown_rounds > 0:
                self.betting.cooldown_rounds -= 1

            if decision.action == "WAIT":
                return

            bet_amt, b_type = self.betting.get_current_bet()
            self.betting.total_signals += 1

            # API Period + 1 Logic
            try:
                current_num = int(period)
                next_period_num = current_num + 1
                period_str = str(next_period_num)[-3:]
            except Exception:
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
            # အရင်ပွဲ၏ WIN Message ရောက်ပြီးမှသာ Signal Message အသစ်ကို ပို့ဆောင်သည်
            self.send_telegram_sync(sig_msg)

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
                            bot.send_telegram_sync(
                                f"📊 <b>STATUS UPDATE</b>\n\n"
                                f"• Level: <b>{b.level} ({b.level_state})</b>\n"
                                f"• Bet: <b>{bet_amt:,} ({b_type})</b>\n"
                                f"• Profit: <b>{b.current_profit:+,.0f}</b>\n"
                                f"• Win Rate: <b>{b.get_wr():.1f}%</b>\n"
                                f"• Max Level: <b>{b.max_level_reached}</b>"
                            )
                        elif text == "/reset":
                            b.reset_all()
                            bot.send_telegram_sync("🔄 Level 1 သို့ ပြန်လည် Reset ချပြီးပါပြီ။")
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
    return "V52.1 APEX-CHRONO Strict Sequence Live!", 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    GLOBAL_BOT = V36LiveBot()
    threading.Thread(target=run_api_poller, args=(GLOBAL_BOT,), daemon=True).start()
    threading.Thread(target=poll_telegram_commands, args=(GLOBAL_BOT,), daemon=True).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
