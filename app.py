from __future__ import annotations
import math
import time
import os
import requests
import threading
import queue
from collections import deque
from dataclasses import dataclass
from typing import Optional
from flask import Flask, jsonify

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
LOTTERY_AUTH = os.environ.get("LOTTERY_AUTH", "")

CONFIG = {
    "api_url": "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList",
    "payout_rate": 0.96,
    "poll_interval": 3.0,
    "warmup_target": 30,
}

@dataclass
class MegaTensorDecision:
    signal: str
    confidence: float
    is_skipped: bool
    elite_type: str

class MegaPowerfulTensorEngine:
    def __init__(self, short_window=8, long_window=30):
        self.short_buffer = deque(maxlen=short_window)
        self.long_buffer = deque(maxlen=long_window)
        self.last_bias = "BIG"
        self.friction_memory = deque(maxlen=3)

    def resolve(self, digit: int):
        outcome = "BIG" if digit >= 5 else "SMALL"
        val = 1 if outcome == "BIG" else -1
        self.short_buffer.append({"digit": digit, "outcome": outcome, "val": val})
        self.long_buffer.append({"digit": digit, "outcome": outcome, "val": val})
        self.friction_memory.append(val)

    def predict(self, current_step: int) -> MegaTensorDecision:
        if len(self.long_buffer) < CONFIG["warmup_target"]:
            return MegaTensorDecision("WAIT", 0.0, True, "WARMUP")

        short_vals = [x["val"] for x in self.short_buffer]
        long_vals = [x["val"] for x in self.long_buffer]

        short_momentum = sum(short_vals)
        long_momentum = sum(long_vals)

        recent_digits = [x["digit"] for x in self.short_buffer]
        variance = sum((d - sum(recent_digits)/len(recent_digits))**2 for d in recent_digits) / len(recent_digits)

        friction_sum = sum(self.friction_memory)
        if variance < 2.2 and abs(friction_sum) < 2:
            return MegaTensorDecision(self.last_bias, 0.30, True, "FRICTION_NOISE_GATE")

        phase_correction = 0
        if short_vals[-1] != short_vals[-2] and short_vals[-2] == short_vals[-3]:
            phase_correction = -1.5 if short_vals[-1] > 0 else 1.5

        tensor_vector = (short_momentum * 4.0) + (long_momentum * 1.5) + (short_vals[-1] * 5.0) + phase_correction

        is_quantum_resonance = False
        if abs(short_momentum) >= 2 and ((short_vals[-1] > 0 and short_vals[-2] > 0) or (short_vals[-1] < 0 and short_vals[-2] < 0)):
            is_quantum_resonance = True

        signal = "BIG" if tensor_vector >= 0.0 else "SMALL"
        self.last_bias = signal
        return MegaTensorDecision(signal, 0.9999 if is_quantum_resonance else 0.992, False, "ACTIVE")

class MegaTensorBot:
    def __init__(self):
        self.lock = threading.Lock()
        self.engine = MegaPowerfulTensorEngine()
        self.current_step = 1
        self.total_wins = 0
        self.total_losses = 0
        self.current_profit = 0.0
        self.max_step_reached = 1
        self.last_decision: Optional[MegaTensorDecision] = None
        self.last_processed_period = None
        self.is_initialized = False
        
        self.msg_queue = queue.Queue()
        self._start_telegram_worker()

    def _get_bet_amount(self, step: int) -> int:
        """Returns the specific bet size based on the user's custom ladder: 1000, 3000, 7000, then 0"""
        bet_ladder = {
            1: 1000,
            2: 3000,
            3: 7000
        }
        return bet_ladder.get(step, 0) # Steps beyond 3 will use 0 bet size

    def _start_telegram_worker(self):
        def worker():
            while True:
                msg = self.msg_queue.get()
                if msg is None:
                    break
                self._send_telegram_direct(msg)
                time.sleep(0.5)
                self.msg_queue.task_done()
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def send_telegram_sync(self, message: str):
        self.msg_queue.put(message)

    def _send_telegram_direct(self, message: str):
        if not TELEGRAM_TOKEN or not CHAT_ID:
            print(f"[TG-LOCAL]\n{message}", flush=True)
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=6)
        except Exception as e:
            print(f"[TG-ERR] {e}", flush=True)

    def initialize_historical_data(self):
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": f"Bearer {LOTTERY_AUTH}" if not LOTTERY_AUTH.startswith("Bearer") else LOTTERY_AUTH,
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://6win598.com",
            "referer": "https://6win598.com/",
            "user-agent": "Mozilla/5.0",
        }
        payload = {
            "pageSize": 50, "pageNo": 1, "typeId": 30, "language": 7,
            "random": "036263f367384d418be07465793c8da8",
            "signature": "55F4FD150F15F090B943374F3C9BE78B",
            "timestamp": int(time.time()),
        }
        try:
            res = requests.post(CONFIG["api_url"], json=payload, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                list_data = data.get("data", {}).get("list", [])
                if list_data:
                    list_data.reverse()
                    for item in list_data:
                        period = str(item.get("issueNumber"))
                        digit = int(item.get("number"))
                        if len(self.engine.long_buffer) < CONFIG["warmup_target"]:
                            self.engine.resolve(digit)
                            self.last_processed_period = period
                    print(f"[Initializer] Loaded {len(self.engine.long_buffer)} historical rounds!", flush=True)
                    self.is_initialized = True
        except Exception as e:
            print(f"[Init Error] {e}", flush=True)

    def process_round(self, period: str, digit: int):
        with self.lock:
            try:
                raw_int_period = int(period)
            except Exception:
                raw_int_period = 0

            if period == self.last_processed_period:
                return
            self.last_processed_period = period

            if len(self.engine.long_buffer) < CONFIG["warmup_target"]:
                self.engine.resolve(digit)
                return

            actual_big = 1 if digit >= 5 else 0

            if self.last_decision and not self.last_decision.is_skipped:
                last_won = ((1 if self.last_decision.signal == "BIG" else 0) == actual_big)
                current_bet = self._get_bet_amount(self.current_step)
                
                if last_won:
                    # If bet was > 0, calculate profit. If bet was 0, profit change is 0.
                    profit_val = current_bet * CONFIG["payout_rate"] if current_bet > 0 else 0
                    self.current_profit += profit_val
                    self.total_wins += 1
                    
                    win_msg = (
                        f"🔥 WIN ✅ (+{profit_val:,.0f})\n"
                        f"🎯 Bet Success"
                    )
                    self.send_telegram_sync(win_msg)
                    self.current_step = 1  # Reset strictly to Step 1 (1000) on WIN
                else:
                    bet_loss = current_bet
                    self.current_profit -= bet_loss
                    self.total_losses += 1
                    
                    # Increment step (1 -> 2 -> 3 -> 4 -> ...)
                    self.current_step += 1

                if self.current_step > self.max_step_reached:
                    self.max_step_reached = self.current_step

            win_rate = (self.total_wins / (self.total_wins + self.total_losses) * 100) if (self.total_wins + self.total_losses) > 0 else 48.6

            self.engine.resolve(digit)
            decision = self.engine.predict(self.current_step)
            self.last_decision = decision

            if decision.is_skipped:
                skip_msg = f"💕 Period {str(raw_int_period + 1)[-3:]} = SKIP 💕"
                self.send_telegram_sync(skip_msg)
            else:
                try:
                    target_period_str = str(raw_int_period + 1)[-3:]
                except Exception:
                    target_period_str = "NXT"

                signal_msg = (
                    f"⚡⚡ [MEGA SIGNAL] \n"
                    f"━━━━━━━━━━━━━━━━━\n"
                    f"💖 Period {target_period_str}\n"
                    f"🎯 SIGNAL → {decision.signal.upper()} 🔥\n"
                    f"━━━━━━━━━━━━━━━━━\n"
                    f"🤖 Bot Step: {self.current_step}x\n"
                    f"🏆 Max Step: {self.max_step_reached}\n"
                    f"💵 Profit: {self.current_profit:+,.0f}\n"
                    f"📊 WR: {win_rate:.1f}%"
                )
                self.send_telegram_sync(signal_msg)

    def start_polling_loop(self):
        def worker():
            print("[Mega v5.0 Bot] Initializing historical data...", flush=True)
            self.initialize_historical_data()
            print("[Mega v5.0 Bot] Polling loop started (Custom Bet Ladder)...", flush=True)
            
            headers = {
                "accept": "application/json, text/plain, */*",
                "authorization": f"Bearer {LOTTERY_AUTH}" if not LOTTERY_AUTH.startswith("Bearer") else LOTTERY_AUTH,
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
                    res = requests.post(CONFIG["api_url"], json=payload, headers=headers, timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        list_data = data.get("data", {}).get("list", [])
                        if list_data:
                            latest = list_data[0]
                            period = str(latest.get("issueNumber"))
                            digit = int(latest.get("number"))
                            if period != self.last_processed_period:
                                self.process_round(period, digit)
                                time.sleep(1.5)
                except Exception as e:
                    print(f"[Polling Error] {e}", flush=True)
                time.sleep(CONFIG["poll_interval"])

        t = threading.Thread(target=worker, daemon=True)
        t.start()

app = Flask(__name__)
GLOBAL_BOT: Optional[MegaTensorBot] = None
_bot_started = False

@app.route("/")
def index():
    return "Mega v5.0 Custom Bet Ladder Active!", 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    if not _bot_started:
        _bot_started = True
        GLOBAL_BOT = MegaTensorBot()
        GLOBAL_BOT.start_polling_loop()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)
