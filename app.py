from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
from flask import Flask, jsonify
import os
import random
import requests
import threading
import time
from typing import Dict, List, Optional, Tuple

# ============================================================
# 1. ENVIRONMENT VARIABLES & GLOBAL CONFIG
# ============================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
LOTTERY_AUTH = os.environ.get("LOTTERY_AUTH", "")

CONFIG = {
    "api_url": "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList",
    "payout_rate": 0.96,               # 1:1.96 Payout
    "profit_reset_threshold": 100000,  # Target Milestone (+100,000 MMK)
    "poll_interval": 3.0,              # API Polling Interval (seconds)
    "warmup_target": 15,               # Fast Startup Warmup
    "base_unit": 1000,                 # Base bet amount (1,000 MMK)
}


# ============================================================
# 2. EXACT UNBOUNDED FIBONACCI BET SIZING
# ============================================================
def fib(n: int) -> int:
    """1-based Fibonacci calculation: 1, 1, 2, 3, 5, 8, 13, 21, 34..."""
    if n <= 2:
        return 1
    a, b = 1, 1
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b


def get_level_bet(level: int, base_unit: int = CONFIG["base_unit"]) -> Dict[str, int]:
    """သင်၏ မူလ 1:2 Win-Win Ratio Fibonacci Table"""
    f = fib(max(1, level))
    bet1 = base_unit * f
    bet2 = bet1 * 2
    return {"bet1": bet1, "bet2": bet2}


# ============================================================
# 3. V68 OMNI-SOVEREIGN PREDICTOR (Zero Exhaustion Traps)
# ============================================================
class OmniSovereignEngineV68:
    def __init__(self, history_window: int = 80):
        self.history: List[str] = []
        self.history_window = history_window

    def add(self, outcome: str):
        self.history.append(outcome)
        if len(self.history) > self.history_window:
            self.history.pop(0)

    def evaluate_market(self, level: int, step: int) -> Tuple[str, str, str]:
        if len(self.history) < CONFIG["warmup_target"]:
            return "SKIP", "BIG", "Warming Up Data"

        h = self.history
        l1 = h[-1]
        l2 = h[-2] if len(h) >= 2 else l1
        l3 = h[-3] if len(h) >= 3 else l2
        l4 = h[-4] if len(h) >= 4 else l3
        l5 = h[-5] if len(h) >= 5 else l4
        l6 = h[-6] if len(h) >= 6 else l5

        # 🎯 BALANCED ASYMMETRIC RECOVERY:
        # Level 1: 0.45 (High Signals) | Level 2: 0.68 (Fast Recovery 1-2 Rounds) | Level 3+: 0.76
        required_conf = 0.45 if level == 1 else (0.68 if level == 2 else 0.76)

        candidate_pred = None
        detected_conf = 0.50
        reason = ""

        # Streak အလျား တွက်ချက်ခြင်း
        streak_len = 1
        for i in range(len(h) - 2, -1, -1):
            if h[i] == h[-1]:
                streak_len += 1
            else:
                break

        # -------------------------------------------------------------
        # STEP 2 CLOSER: Live Rhythm Synchronization (WW Lock)
        # -------------------------------------------------------------
        if step == 2:
            # ၁။ Ping-Pong ဖြစ်နေပါက ပြောင်းပြန် ပိတ်မည်
            if l1 != l2 and l2 != l3:
                p2 = "SMALL" if l1 == "BIG" else "BIG"
                return "BET", p2, "Step 2: Live Ping-Pong Closer (WW Lock)"

            # ၂။ 2-2 Pair အဆုံးသတ်ဖြစ်နေပါက Flip လုပ်မည်
            elif l3 == l4 and l2 == l1 and l2 != l3:
                p2 = "SMALL" if l1 == "BIG" else "BIG"
                return "BET", p2, "Step 2: Live 2-2 Pair Flip Closer (WW Lock)"

            # ၃။ 1-3 Sandwich အဆုံးသတ်ဖြစ်နေပါက Flip လုပ်မည်
            elif l4 == l3 and l3 == l2 and l2 != l1:
                p2 = "SMALL" if l1 == "BIG" else "BIG"
                return "BET", p2, "Step 2: 1-3 Sandwich Return Closer (WW Lock)"

            # ၄။ Trend သွားနေပါက တူရာ လိုက်ပိတ်မည် (Streak >= 5 Hazard Guard ပါဝင်သည်)
            elif streak_len >= 2:
                if streak_len >= 5:
                    return "SKIP", "BIG", "Step 2: Trend Delay Guard (Streak >= 5)"
                return "BET", l1, "Step 2: Live Trend Flow Closer (WW Lock)"

            # Default Live Fallback
            return "BET", l1, "Step 2: Live Momentum Closer (WW Lock)"

        # -------------------------------------------------------------
        # STEP 1 ENTRY: Early-Resonance Multi-Pattern Search
        # -------------------------------------------------------------

        # Pattern 1: Exact 2-2 Double Pair (AA-BB -> Flip to A)
        if l3 == l4 and l2 != l3 and l1 == l2:
            candidate_pred = "SMALL" if l1 == "BIG" else "BIG"
            detected_conf = 0.88
            reason = "Tier-1: Exact 2-2 Double Pair"

        # Pattern 2: Pure 4-Step Ping-Pong (A-B-A-B -> Flip)
        elif l1 != l2 and l2 != l3 and l3 != l4:
            candidate_pred = "SMALL" if l1 == "BIG" else "BIG"
            detected_conf = 0.90
            reason = "Tier-1: Pure 4-Step Ping-Pong"

        # Pattern 3: Dragon Streak Early Flow (Streak 3~4 - အရှိန်ကောင်းချိန် ဝင်သည်)
        elif streak_len in [3, 4]:
            candidate_pred = l1
            detected_conf = 0.85
            reason = f"Tier-1: Early Dragon Streak Flow (Len: {streak_len})"

        # Pattern 4: 1-3 Stick-Sandwich (A-BBB-A -> A)
        elif l5 != l4 and l4 == l3 and l3 == l2 and l2 != l1:
            candidate_pred = l1
            detected_conf = 0.86
            reason = "Tier-1: 1-3 Stick-Sandwich"

        # Pattern 5: 2-1-2 Symmetrical Sandwich (AA-B-AA -> B)
        elif l5 == l4 and l4 != l3 and l3 != l2 and l2 == l1:
            candidate_pred = "SMALL" if l1 == "BIG" else "BIG"
            detected_conf = 0.86
            reason = "Tier-1: 2-1-2 Symmetrical Sandwich"

        # Pattern 6: 3-1 Snapback Rebound (AAA-B -> A)
        elif l4 == l3 and l3 == l2 and l2 != l1:
            candidate_pred = l2
            detected_conf = 0.85
            reason = "Tier-1: 3-1 Snapback Rebound"

        # Pattern 7: 1-2-1 Butterfly Sandwich (A-BB-A -> B)
        elif l4 != l3 and l3 == l2 and l2 != l1:
            candidate_pred = l1
            detected_conf = 0.80
            reason = "1-2-1 Butterfly Sandwich Flow"

        # Pattern 8: 2-1-2-1 Syncopated Wave
        elif l6 == l5 and l5 != l4 and l4 == l3 and l3 == l2 and l2 != l1:
            candidate_pred = "SMALL" if l1 == "BIG" else "BIG"
            detected_conf = 0.82
            reason = "2-1-2-1 Syncopated Wave"

        # Pattern 9: 1-1-2 Rhythm Transition (A-B-A-A -> B)
        elif l4 != l3 and l3 != l2 and l2 == l1:
            candidate_pred = "SMALL" if l1 == "BIG" else "BIG"
            detected_conf = 0.78
            reason = "1-1-2 Rhythm Transition"

        # Pattern 10: Ping-Pong 3-Step (A-B-A -> Flip)
        elif l1 != l2 and l2 != l3:
            candidate_pred = "SMALL" if l1 == "BIG" else "BIG"
            detected_conf = 0.76
            reason = "Ping-Pong 3-Step Momentum"

        # Pattern 11: Early 2-Streak Momentum (AA -> A)
        elif l1 == l2 and l3 == l4 and l2 != l3:
            candidate_pred = l1
            detected_conf = 0.74
            reason = "Early 2-Streak Momentum"

        # Pattern 12: 2-1 Breakout Symmetry (AA-B -> A)
        elif l4 != l3 and l3 == l2 and l2 != l1:
            candidate_pred = "SMALL" if l1 == "BIG" else "BIG"
            detected_conf = 0.72
            reason = "2-1 Breakout Symmetry"

        # Pattern 13: Micro-Chop Vector (A-B -> A)
        elif l1 != l2 and l3 == l2:
            candidate_pred = "SMALL" if l1 == "BIG" else "BIG"
            detected_conf = 0.70
            reason = "Micro-Chop Momentum"

        # Fallback: Dual-Horizon Markov Engine
        else:
            target = tuple(h[-2:])
            pair_counts = defaultdict(int)
            search_h = h[:-2]
            for i in range(len(search_h) - 2):
                if tuple(search_h[i : i + 2]) == target:
                    pair_counts[search_h[i + 2]] += 1
            if pair_counts:
                best = max(pair_counts, key=pair_counts.get)
                total = sum(pair_counts.values())
                if total >= 3:
                    conf = pair_counts[best] / total
                    if conf >= 0.56:
                        candidate_pred = best
                        detected_conf = conf
                        reason = f"Fast Markov Trend ({conf*100:.0f}%, N={total})"

        # LEVEL 2 STABILITY SHIELD
        if level >= 2:
            recent_flips = sum(1 for i in range(len(h) - 4, len(h)) if h[i] != h[i - 1])
            if recent_flips >= 4:
                return "SKIP", "BIG", "Level 2: Chaos Shield Active"

        if candidate_pred and detected_conf >= required_conf:
            return "BET", candidate_pred, f"Step {step}: {reason}"

        return "SKIP", "BIG", f"Market Noise (Conf < {required_conf*100:.0f}%)"


# ============================================================
# 4. EXACT UNBOUNDED FIBONACCI STATE MANAGER (Bot Step Fixed)
# ============================================================
class BettingStateManager:
    def __init__(self):
        self.reset_all()

    def reset_all(self):
        self.level = 1
        self.step = 1  # 1: Bet1, 2: Bet2
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

    def apply_result(self, is_win: bool) -> Dict[str, any]:
        bet_amount, bet_type = self.get_current_bet()
        old_level = self.level
        old_step = self.step

        if is_win:
            profit = bet_amount * CONFIG["payout_rate"]
            self.total_profit += profit
            self.current_profit += profit
            self.total_wins += 1

            # 🎯 WIN ဖြစ်သည်နှင့် bot_step သည် ချက်ချင်း 1x သို့ Reset ဆင်းသည်!
            self.bot_step = 1

            if self.step == 1:
                self.step = 2
                action = "WIN_STEP1_TO_STEP2"
            else:
                # 🔥 WIN-WIN HIT! Level 1 သို့ တန်း Reset ဆင်းသည်
                self.level = 1
                self.step = 1
                self.cycles_completed += 1
                action = f"WIN_WIN_RESET_FROM_LVL_{old_level}"
        else:
            profit = -bet_amount
            self.current_profit -= bet_amount
            self.total_losses += 1
            
            # 🎯 UNBOUNDED FIBONACCI: ရှုံးပါက Level + 1 တိုးမည်
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
            "old_step": old_step,
            "new_step": self.step,
            "target_hit": target_hit,
        }


# ============================================================
# 5. LIVE BOT CONTROLLER (API + TELEGRAM + STATE)
# ============================================================
class LiveSignalBot:
    def __init__(self):
        self.lock = threading.Lock()
        self.engine = OmniSovereignEngineV68()
        self.betting = BettingStateManager()
        self.last_signal_info: Optional[Dict[str, any]] = None
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
            # -------------------------------------------------------------
            # PERIOD နံပါတ် တိကျစွာ တွက်ချက်ခြင်း (...576 -> Signal: ...577)
            # -------------------------------------------------------------
            try:
                raw_int_period = int(period)
                current_period_str = str(raw_int_period)[-3:]
                next_period_str = str(raw_int_period + 1)[-3:]
            except Exception:
                current_period_str = str(period)[-3:]
                next_period_str = "NXT"

            actual_outcome = "BIG" if digit >= 5 else "SMALL"

            # -------------------------------------------------------------
            # ၁။ WARMUP PHASE
            # -------------------------------------------------------------
            if len(self.engine.history) < CONFIG["warmup_target"]:
                self.engine.add(actual_outcome)
                current_count = len(self.engine.history)
                self.send_telegram(
                    f"📊 <b>Data Warming up... [ {current_count} / {CONFIG['warmup_target']} ]</b>\n"
                    f"Period {current_period_str} → {actual_outcome} ({digit})"
                )
                return

            # -------------------------------------------------------------
            # ၂။ SETTLE PREVIOUS BET (If previous round had a BET signal)
            # -------------------------------------------------------------
            if self.last_signal_info and self.last_signal_info["action"] == "BET":
                pred = self.last_signal_info["prediction"]
                is_win = (actual_outcome == pred)
                settle = self.betting.apply_result(is_win)

                if is_win:
                    if "WIN_WIN_RESET" in settle["action"]:
                        win_msg = (
                            f"🔥 <b>WIN</b> ✅ (+{settle['profit']:,.0f} MMK)\n"
                            f"🎉 <b>BET2 WIN → Level 1 RESET</b>\n"
                            f"🔄 Level {settle['old_level']} → Level 1"
                        )
                    else:
                        win_msg = (
                            f"🔥 <b>WIN</b> ✅ (+{settle['profit']:,.0f} MMK)\n"
                            f"🎯 <b>Bet 1 WON → Hunting Bet 2</b>"
                        )
                    self.send_telegram(win_msg)

                    # 🏆 Milestone Check (+100,000 MMK Target)
                    if settle.get("target_hit", False):
                        milestone_msg = (
                            f"🏆🏆🏆🏆 <b>TARGET +100,000 GOD-TIER MILESTONE!</b> 🏆🏆🏆🏆\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📉 Max Drawdown: {self.betting.max_loss_amount:+,.0f} MMK\n"
                            f"📈 Max Level Reached: Level {self.betting.max_level_reached}\n"
                            f"💵 Milestone Profit: +100,000 MMK Locked"
                        )
                        self.send_telegram(milestone_msg)
                        self.betting.reset_milestone()

            # Update Engine with the newly finished round result
            self.engine.add(actual_outcome)

            # -------------------------------------------------------------
            # ၃။ EVALUATE SIGNAL FOR NEXT PERIOD (ဥပမာ ...577 အတွက်)
            # -------------------------------------------------------------
            action, pred, reason = self.engine.evaluate_market(
                self.betting.level, self.betting.step
            )

            if action == "SKIP":
                self.last_signal_info = {"action": "SKIP"}
                skip_msg = f"💖 Period {next_period_str} SKIP ⏭️"
                self.send_telegram(skip_msg)
                return

            # BET SIGNAL GENERATION
            bet_amt, b_type = self.betting.get_current_bet()
            self.betting.total_signals += 1

            self.last_signal_info = {
                "action": "BET",
                "prediction": pred,
                "bet_amount": bet_amt,
                "reason": reason,
            }

            # 🎯 သင်သတ်မှတ်ပေးထားသော အတိအကျ Signal Message Format
            msg = (
                f"💖 Period {next_period_str}\n"
                f"🎯 SIGNAL → <b>{pred.upper()}</b> 🔥\n"
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

    # -------------------------------------------------------------
    # ၄။ API POLLING WORKER
    # -------------------------------------------------------------
    def start_polling_loop(self):
        def worker():
            print("[LiveSignalBot V68] Starting 6lottery API Poller...", flush=True)
            headers = {
                "accept": "application/json, text/plain, */*",
                "authorization": (
                    f"Bearer {LOTTERY_AUTH}"
                    if not LOTTERY_AUTH.startswith("Bearer")
                    else LOTTERY_AUTH
                ),
                "content-type": "application/json;charset=UTF-8",
                "origin": "https://6win598.com",
                "referer": "https://6win598.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            while True:
                try:
                    payload = {
                        "pageSize": 10,
                        "pageNo": 1,
                        "typeId": 30,
                        "language": 7,
                        "random": "036263f367384d418be07465793c8da8",
                        "signature": "55F4FD150F15F090B943374F3C9BE78B",
                        "timestamp": int(time.time()),
                    }
                    res = requests.post(
                        CONFIG["api_url"], json=payload, headers=headers, timeout=5
                    )
                    if res.status_code == 200:
                        data = res.json()
                        list_data = data.get("data", {}).get("list", [])
                        if list_data:
                            latest = list_data[0]
                            period = str(latest.get("issueNumber"))
                            digit = int(latest.get("number"))

                            if period != self.last_processed_period:
                                self.last_processed_period = period
                                print(f"[Round Received] Period: {period}, Digit: {digit}", flush=True)
                                self.process_round(period, digit)
                                time.sleep(1.0)
                    else:
                        print(f"[API Non-200] Status: {res.status_code}", flush=True)
                except Exception as e:
                    print(f"[Polling Error] {e}", flush=True)

                time.sleep(CONFIG["poll_interval"])

        t = threading.Thread(target=worker, daemon=True)
        t.start()


# ============================================================
# 6. FLASK WEB SERVER & FAST BOOT FOR RENDER
# ============================================================
app = Flask(__name__)

GLOBAL_BOT = LiveSignalBot()
GLOBAL_BOT.start_polling_loop()

@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "engine": "V68 Omni-Sovereign Balanced Active Flow",
        "current_level": GLOBAL_BOT.betting.level,
        "max_level_reached": GLOBAL_BOT.betting.max_level_reached,
        "total_profit": GLOBAL_BOT.betting.total_profit,
        "win_rate": f"{GLOBAL_BOT.betting.get_wr():.1f}%",
        "total_signals": GLOBAL_BOT.betting.total_signals
    }), 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "uptime_check": "ok"}), 200


# ============================================================
# 7. MAIN ENTRY POINT
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
