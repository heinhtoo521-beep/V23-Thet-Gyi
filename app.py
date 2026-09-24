from __future__ import annotations
from collections import deque
import math
import os
import threading
import time
import hashlib
import json
import random as py_random
from typing import Any, Dict, Optional, Tuple
from flask import Flask, jsonify
import requests

# ============================================================
# 1. ENVIRONMENT VARIABLES & GLOBAL CONFIG
# ============================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
LOTTERY_AUTH = os.environ.get("LOTTERY_AUTH", "")

CONFIG = {
    "api_url": "https://6lotteryapi.com/api/webapi/GetTRXNoaverageEmerdList",  # ⭐ ပြောင်း
    "payout_rate": 0.96,  # 1:1.96 Payout
    "profit_reset_threshold": 100000,  # Target Milestone (+100,000 MMK)
    "poll_interval": 3.0,
    "warmup_target": 15,  # လျင်မြန်စွာ စတင်နိုင်ရန် 15 ကြိမ် အချိန်ယူသည်
    "base_unit": 1000,
}


# ============================================================
# 1.5 SIGNATURE GENERATOR (အသစ် ထည့်) ⭐
# ============================================================
def generate_random() -> str:
    """JavaScript mz() function အတိုင်း UUID v4 format"""
    template = "xxxxxxxxxxxx4xxxyxxxxxxxxxxxxxxx"
    result = ""
    for ch in template:
        if ch == 'x':
            result += format(py_random.randint(0, 15), 'x')
        elif ch == 'y':
            result += format(py_random.randint(8, 11), 'x')
        else:
            result += ch
    return result


def generate_signature(params: dict) -> str:
    """MD5 signature — API အတွက်"""
    data = {k: v for k, v in params.items()
            if k not in ['signature', 'timestamp']}
    sorted_data = dict(sorted(data.items()))
    json_str = json.dumps(sorted_data, separators=(',', ':'), ensure_ascii=False)
    return hashlib.md5(json_str.encode()).hexdigest().upper()


# ============================================================
# 2. EXACT UNBOUNDED FIBONACCI (သင်၏ မူလ Rule အတိုင်း တရားသေ သွားမည်)
# ============================================================
def fib(n: int) -> int:
    """1-based Fibonacci: 1, 1, 2, 3, 5, 8, 13, 21, 34, 55... (Unbounded)"""
    if n <= 2:
        return 1
    a, b = 1, 1
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b


def get_level_bet(level: int, base_unit: int = CONFIG["base_unit"]) -> Dict[str, int]:
    f = fib(max(1, level))
    bet1 = base_unit * f
    bet2 = bet1 * 2
    return {"bet1": bet1, "bet2": bet2}


# ============================================================
# 3. APEX QUAD-ORACLE PREDICTION ENGINE (PURE SIGNAL POWER)
# ============================================================
class ApexQuadOracleEngine:
    def __init__(self, window: int = 100):
        self.window = window
        self.digits: deque[int] = deque(maxlen=window)
        self.outcomes: deque[str] = deque(maxlen=window)

        # Sub-Oracles အလိုက် Dynamic Real-Time Weights
        self.oracle_weights = [1.25, 1.20, 1.00, 1.05]
        self.last_oracle_preds = [None, None, None, None]

        # Anti-Phase Resynchronization History
        self.recent_predictions: deque[str] = deque(maxlen=6)
        self.recent_actuals: deque[str] = deque(maxlen=6)

    def add_tick(self, digit: int):
        outcome = "BIG" if digit >= 5 else "SMALL"
        self.recent_actuals.append(outcome)

        # 🎯 REAL-TIME HEDGE WEIGHT LEARNING
        for i in range(4):
            pred = self.last_oracle_preds[i]
            if pred is not None:
                if pred == outcome:
                    self.oracle_weights[i] = min(3.5, self.oracle_weights[i] * 1.06)
                else:
                    self.oracle_weights[i] = max(0.2, self.oracle_weights[i] * 0.94)

        self.last_oracle_preds = [None, None, None, None]
        self.digits.append(digit)
        self.outcomes.append(outcome)

    # ---------------------------------------------------------
    # ORACLE 1: Variable Depth Suffix Pattern (Laplace Probability)
    # ---------------------------------------------------------
    def _oracle_suffix_pattern(self) -> Tuple[Optional[str], float]:
        if len(self.outcomes) < 15:
            return None, 0.50
        seq = list(self.outcomes)
        for depth in (4, 3, 2):
            if len(seq) <= depth + 3:
                continue
            pat = tuple(seq[-depth:])
            b_cnt, s_cnt = 0, 0
            for i in range(len(seq) - depth):
                if tuple(seq[i : i + depth]) == pat:
                    if seq[i + depth] == "BIG":
                        b_cnt += 1
                    else:
                        s_cnt += 1
            tot = b_cnt + s_cnt
            if tot >= 2:
                p_b = (b_cnt + 1) / (tot + 2)
                p_s = (s_cnt + 1) / (tot + 2)
                if abs(p_b - p_s) >= 0.12:
                    return ("BIG" if p_b > p_s else "SMALL"), max(p_b, p_s)
        return None, 0.50

    # ---------------------------------------------------------
    # ORACLE 2: Wave & Streak Transition Dynamics
    # ---------------------------------------------------------
    def _oracle_wave_streak(self) -> Tuple[Optional[str], float]:
        if len(self.outcomes) < 6:
            return None, 0.50
        recent = list(self.outcomes)
        streak = 1
        for i in range(len(recent) - 2, -1, -1):
            if recent[i] == recent[-1]:
                streak += 1
            else:
                break
        last = recent[-1]

        # Ping-Pong Check
        if (
            len(recent) >= 4
            and recent[-1] != recent[-2]
            and recent[-2] != recent[-3]
            and recent[-3] != recent[-4]
        ):
            return ("BIG" if last == "SMALL" else "SMALL"), 0.85

        # Dragon Streak
        if streak >= 3:
            return last, min(0.90, 0.72 + streak * 0.03)

        return None, 0.50

    # ---------------------------------------------------------
    # ORACLE 3: Micro-Digit Dual EMA Momentum
    # ---------------------------------------------------------
    def _oracle_digit_ema(self) -> Tuple[Optional[str], float]:
        if len(self.digits) < 12:
            return None, 0.50
        digs = list(self.digits)
        k_f = 2.0 / (3 + 1)
        k_s = 2.0 / (8 + 1)
        ef = digs[-9]
        es = digs[-9]
        for d in digs[-8:]:
            ef = d * k_f + ef * (1 - k_f)
            es = d * k_s + es * (1 - k_s)
        diff = ef - es
        if abs(diff) >= 0.32:
            direction = "BIG" if ef >= 4.5 else "SMALL"
            conf = min(0.84, 0.56 + abs(diff) * 0.12)
            return direction, conf
        return None, 0.50

    # ---------------------------------------------------------
    # ORACLE 4: Transition Phase-Lock Detector
    # ---------------------------------------------------------
    def _oracle_phase_lock(self) -> Tuple[Optional[str], float]:
        if len(self.outcomes) < 8:
            return None, 0.50
        recent = list(self.outcomes)
        trans = sum(
            1 for i in range(len(recent) - 6, len(recent) - 1) if recent[i] != recent[i + 1]
        )
        if trans >= 4:
            return ("BIG" if recent[-1] == "SMALL" else "SMALL"), 0.80
        elif trans <= 1:
            return recent[-1], 0.82
        return None, 0.50

    # ---------------------------------------------------------
    # MASTER EVALUATOR (Signal + Step Hunter)
    # ---------------------------------------------------------
    def evaluate(self, step: int) -> Tuple[str, str, float, str]:
        if len(self.digits) < CONFIG["warmup_target"]:
            return "SKIP", "BIG", 50.0, "Warming Up Engine"

        p1, c1 = self._oracle_suffix_pattern()
        p2, c2 = self._oracle_wave_streak()
        p3, c3 = self._oracle_digit_ema()
        p4, c4 = self._oracle_phase_lock()
        self.last_oracle_preds = [p1, p2, p3, p4]

        # STEP 2 CLOSER HUNTER
        if step == 2:
            if p2:
                chosen, conf, reason = p2, c2, "Step 2: Wave Momentum Closer"
            elif p4:
                chosen, conf, reason = p4, c4, "Step 2: Phase-Lock Closer"
            elif p1:
                chosen, conf, reason = p1, c1, "Step 2: Suffix Closer"
            else:
                chosen, conf, reason = self.outcomes[-1], 0.74, "Step 2: Flow Follow Closer"
            self.recent_predictions.append(chosen)
            return "BET", chosen, conf * 100.0, reason

        # STEP 1: QUAD-ORACLE WEIGHTED AGGREGATION
        b_score, s_score = 0.0, 0.0
        oracles = [(p1, c1, 0), (p2, c2, 1), (p3, c3, 2), (p4, c4, 3)]
        for pred, conf, idx in oracles:
            if pred:
                wt = self.oracle_weights[idx]
                if pred == "BIG":
                    b_score += conf * wt
                else:
                    s_score += conf * wt

        delta = abs(b_score - s_score)
        chosen = "BIG" if b_score >= s_score else "SMALL"

        # 🛡️ ANTI-PHASE RESYNCHRONIZATION
        if len(self.recent_predictions) >= 4 and len(self.recent_actuals) >= 4:
            recent_acc = sum(
                1
                for p, a in zip(list(self.recent_predictions)[-4:], list(self.recent_actuals)[-4:])
                if p == a
            )
            if recent_acc == 0:
                chosen = "SMALL" if chosen == "BIG" else "BIG"
                self.recent_predictions.append(chosen)
                return "BET", chosen, 86.0, "Apex Anti-Phase Resync (Inverted Flow)"

        # 🎯 MINIMAL SKIP
        if delta < 0.12:
            return "SKIP", "BIG", 50.0, "Equilibrium Tie Balance"

        self.recent_predictions.append(chosen)
        conf_pct = min(94.0, 54.0 + delta * 18.0)
        return "BET", chosen, conf_pct, f"Apex Consensus (Power: {conf_pct:.0f}%)"


# ============================================================
# 4. BETTING STATE MANAGER (PURE UNBOUNDED FLOW)
# ============================================================
class BettingStateManager:
    def __init__(self):
        self.reset_all()

    def reset_all(self):
        self.level = 1
        self.step = 1
        self.total_signals = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_profit = 0.0
        self.current_profit = 0.0
        self.max_loss_amount = 0.0
        self.max_level_reached = 1
        self.cycles_completed = 0
        self.bot_step = 1

    def reset_milestone(self):
        self.current_profit = 0.0
        self.max_loss_amount = 0.0
        self.level = 1
        self.step = 1
        self.bot_step = 1

    def get_current_bet(self) -> Tuple[int, str]:
        info = get_level_bet(self.level, CONFIG["base_unit"])
        if self.step == 1:
            return info["bet1"], "BET1"
        return info["bet2"], "BET2"

    def get_wr(self) -> float:
        total = self.total_wins + self.total_losses
        return (self.total_wins / total * 100) if total > 0 else 0.0

    def apply_result(self, is_win: bool) -> Dict[str, Any]:
        bet_amount, bet_type = self.get_current_bet()
        old_level = self.level
        old_step = self.step

        if is_win:
            profit = bet_amount * CONFIG["payout_rate"]
            self.total_profit += profit
            self.current_profit += profit
            self.total_wins += 1
            self.bot_step = 1

            if self.step == 1:
                self.step = 2
                action = "WIN_STEP1_TO_STEP2"
            else:
                self.level = 1
                self.step = 1
                self.cycles_completed += 1
                action = f"WIN_WIN_RESET_FROM_LVL_{old_level}"
        else:
            profit = -bet_amount
            self.total_profit += profit
            self.current_profit -= bet_amount
            self.total_losses += 1

            self.level += 1
            self.step = 1
            self.bot_step += 1
            self.max_level_reached = max(self.max_level_reached, self.level)
            action = f"LOSS_LEVEL_UP_TO_{self.level}"

        self.max_loss_amount = min(self.max_loss_amount, self.current_profit)
        target_hit = self.current_profit >= CONFIG["profit_reset_threshold"]

        return {
            "bet_amount": bet_amount,
            "bet_type": bet_type,
            "profit": profit,
            "action": action,
            "old_level": old_level,
            "new_level": self.level,
            "target_hit": target_hit,
        }


# ============================================================
# 5. LIVE BOT CONTROLLER
# ============================================================
class LiveSignalBot:
    def __init__(self):
        self.lock = threading.Lock()
        self.engine = ApexQuadOracleEngine()
        self.betting = BettingStateManager()
        self.last_signal_info: Optional[Dict[str, Any]] = None
        self.last_processed_period: Optional[str] = None

    def send_telegram(self, message: str):
        if not TELEGRAM_TOKEN or not CHAT_ID:
            print(f"[TG-LOCAL]\n{message}\n", flush=True)
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=6)
        except Exception as e:
            print(f"[TG-ERR] {e}", flush=True)

    def process_round(self, period: str, digit: int):
        with self.lock:
            try:
                raw_int = int(period)
                current_period_str = str(raw_int)[-3:]
                next_period_str = str(raw_int + 1)[-3:]
            except Exception:
                current_period_str = str(period)[-3:]
                next_period_str = "NXT"

            actual_outcome = "BIG" if digit >= 5 else "SMALL"

            # 1. Warmup
            if len(self.engine.digits) < CONFIG["warmup_target"]:
                self.engine.add_tick(digit)
                self.send_telegram(
                    f"⚡ <b>Apex Engine Warming... [ {len(self.engine.digits)} / {CONFIG['warmup_target']} ]</b>\n"
                    f"Period {current_period_str} → {actual_outcome} ({digit})"
                )
                return

            # 2. Settle Previous Bet
            if self.last_signal_info and self.last_signal_info["action"] == "BET":
                pred = self.last_signal_info["prediction"]
                is_win = actual_outcome == pred
                settle = self.betting.apply_result(is_win)

                if is_win:
                    if "WIN_WIN_RESET" in settle["action"]:
                        self.send_telegram(
                            f"🔥 <b>WIN</b> ✅ (+{settle['profit']:,.0f} MMK)\n"
                            f"🎉 <b>Step 2 WON → Level 1 RESET</b>\n"
                            f"🔄 Level {settle['old_level']} → Level 1"
                        )
                    else:
                        self.send_telegram(
                            f"🔥 <b>WIN</b> ✅ (+{settle['profit']:,.0f} MMK)\n"
                            f"🎯 <b>Bet 1 WON → Hunting Step 2 Closer</b>"
                        )

                    if settle.get("target_hit", False):
                        self.send_telegram(
                            f"🏆🏆🏆 <b>TARGET +100,000 MMK REACHED!</b> 🏆🏆🏆\n"
                            f"📉 Max Drawdown: {self.betting.max_loss_amount:+,.0f} MMK\n"
                            f"📈 Max Level Reached: Level {self.betting.max_level_reached}"
                        )
                        self.betting.reset_milestone()

            # Update Engine
            self.engine.add_tick(digit)

            # 3. Deliberate Next Round
            action, pred, conf, reason = self.engine.evaluate(self.betting.step)

            if action == "SKIP":
                self.last_signal_info = {"action": "SKIP"}
                self.send_telegram(f"💖 Period {next_period_str} <b>SKIP ⏭️</b>")
                return

            bet_amt, b_type = self.betting.get_current_bet()
            self.betting.total_signals += 1

            self.last_signal_info = {
                "action": "BET",
                "prediction": pred,
                "bet_amount": bet_amt,
                "reason": reason,
            }

            msg = (
                f"💖 Period {next_period_str}\n"
                f"🎯 SIGNAL → <b>{pred.upper()}</b> 🔥\n"
                f"💡 Edge: <i>{reason}</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 Bot Step: {self.betting.bot_step}x\n"
                f"🎮 Level: {self.betting.level} | {b_type}\n"
                f"💰 Bet: {bet_amt:,} MMK\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏆 Max Level: Level {self.betting.max_level_reached}\n"
                f"📉 Max DD: {self.betting.max_loss_amount:+,.0f} MMK\n"
                f"💵 Current Profit: {self.betting.current_profit:+,.0f} MMK\n"
                f"📊 Win Rate: {self.betting.get_wr():.1f}%"
            )
            self.send_telegram(msg)

    def start_polling_loop(self):
        def worker():
            print("[Apex Live Bot] Starting 6lottery TRX API Stream...", flush=True)
            # ⭐ Headers — သင့် curl အတိုင်း ပြောင်း
            headers = {
                "authority": "6lotteryapi.com",
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-MM,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                "ar-origin": "https://6windk5.com",
                "authorization": (
                    f"Bearer {LOTTERY_AUTH}"
                    if not LOTTERY_AUTH.startswith("Bearer")
                    else LOTTERY_AUTH
                ),
                "content-type": "application/json;charset=UTF-8",
                "origin": "https://6windk5.com",
                "referer": "https://6windk5.com/",
                "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
            }
            while True:
                try:
                    # ⭐ Payload — signature auto-generate
                    params = {
                        "pageSize": 10,
                        "pageNo": 1,
                        "typeId": 13,
                        "language": 7,
                        "random": generate_random(),
                    }
                    payload = {
                        **params,
                        "signature": generate_signature(params),
                        "timestamp": int(time.time()),
                    }
                    res = requests.post(
                        CONFIG["api_url"], json=payload, headers=headers, timeout=5
                    )
                    if res.status_code == 200:
                        data = res.json()
                        # ⭐ Data path ပြောင်း (data.data.gameslist)
                        list_data = data.get("data", {}).get("data", {}).get("gameslist", [])
                        if list_data:
                            latest = list_data[0]
                            period = str(latest.get("issueNumber"))
                            digit = int(latest.get("number"))

                            if period != self.last_processed_period:
                                self.last_processed_period = period
                                self.process_round(period, digit)
                                time.sleep(1.0)
                    else:
                        print(f"[API Error] {res.status_code}: {res.text[:200]}", flush=True)
                except Exception as e:
                    print(f"[Polling Error] {e}", flush=True)

                time.sleep(CONFIG["poll_interval"])

        t = threading.Thread(target=worker, daemon=True)
        t.start()


# ============================================================
# 6. FLASK WEB SERVER FOR RENDER
# ============================================================
app = Flask(__name__)
GLOBAL_BOT = LiveSignalBot()
GLOBAL_BOT.start_polling_loop()


@app.route("/")
def index():
    return (
        jsonify({
            "status": "online",
            "engine": "Apex Quad-Oracle Pure Signal Engine",
            "current_level": GLOBAL_BOT.betting.level,
            "max_level_reached": GLOBAL_BOT.betting.max_level_reached,
            "total_profit": GLOBAL_BOT.betting.total_profit,
            "win_rate": f"{GLOBAL_BOT.betting.get_wr():.1f}%",
            "total_signals": GLOBAL_BOT.betting.total_signals,
        }),
        200,
    )


@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
