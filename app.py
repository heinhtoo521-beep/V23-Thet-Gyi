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
    "warmup_target": 25,               # Minimum data rounds before signal
    "base_unit": 1000,                 # Base bet amount (1,000 MMK)
}


# ============================================================
# 2. DYNAMIC FIBONACCI BET SIZING
# ============================================================
def fib(n: int) -> int:
    """1-based Fibonacci calculation: 1, 1, 2, 3, 5, 8, 13, 21..."""
    if n <= 2:
        return 1
    a, b = 1, 1
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b


def get_level_bet(level: int, base_unit: int = CONFIG["base_unit"]) -> Dict[str, int]:
    """1:2 Win-Win Ratio Fibonacci Table"""
    f = fib(max(1, level))
    bet1 = base_unit * f
    bet2 = bet1 * 2
    return {"bet1": bet1, "bet2": bet2}


# ============================================================
# 3. V35 SINGULARITY APEX PREDICTOR ENGINE
# ============================================================
class SingularityApexEngine:
    def __init__(self, history_window: int = 80, health_window: int = 15):
        self.history: List[str] = []
        self.history_window = history_window
        self.health_window = health_window

        self.pattern_health = {
            "TREND": deque(maxlen=health_window),
            "PINGPONG": deque(maxlen=health_window),
            "PAIR": deque(maxlen=health_window),
            "SANDWICH": deque(maxlen=health_window),
            "MARKOV": deque(maxlen=health_window),
        }
        self.active_pattern = "TREND"
        self.locked_step2_pred = "BIG"

    def add(self, outcome: str):
        self.history.append(outcome)
        if len(self.history) > self.history_window:
            self.history.pop(0)

    def update_pattern_health(self, is_win: bool):
        self.pattern_health[self.active_pattern].append(1 if is_win else 0)

    def _get_health_multiplier(self, pattern_name: str) -> float:
        hist = self.pattern_health[pattern_name]
        if len(hist) == 0:
            return 1.0
        win_rate = sum(hist) / len(hist)
        return 0.85 + (win_rate * 0.30)

    def evaluate_market(self, level: int, step: int) -> Tuple[str, str, str]:
        """
        Step 1: Multi-Model Quorum Filter (Level 1: 55%, Level 2: Dual Consensus)
        Step 2: Micro-Entropy Pulse Guard with Vector Lock
        """
        if len(self.history) < CONFIG["warmup_target"]:
            return "SKIP", "BIG", "Warming Up Data"

        h = self.history
        l1 = h[-1]
        l2 = h[-2] if len(h) >= 2 else l1
        l3 = h[-3] if len(h) >= 3 else l2
        l4 = h[-4] if len(h) >= 4 else l3
        l5 = h[-5] if len(h) >= 5 else l4

        # -------------------------------------------------------------
        # STEP 2 CLOSER: Micro-Entropy Pulse Guard
        # -------------------------------------------------------------
        if step == 2:
            # 1. Trend Streak Over-Extension Hazard
            streak_len = 1
            for i in range(len(h) - 2, -1, -1):
                if h[i] == h[-1]:
                    streak_len += 1
                else:
                    break
            if self.active_pattern == "TREND" and streak_len >= 5:
                return "SKIP", "BIG", "Step 2: Trend Shock Guard (Streak >= 5)"

            # 2. Ping-Pong Over-Extension Hazard
            pp_len = 1
            for i in range(len(h) - 1, 0, -1):
                if h[i] != h[i - 1]:
                    pp_len += 1
                else:
                    break
            if self.active_pattern == "PINGPONG" and pp_len >= 5:
                return "SKIP", "BIG", "Step 2: Ping-Pong Shock Guard (PP >= 5)"

            # 3. Micro-Entropy Pulse Check (Abrupt Flip Shock)
            flips = sum(1 for i in range(len(h) - 3, len(h)) if h[i] != h[i - 1])
            if flips >= 3 and self.active_pattern == "TREND":
                return "SKIP", "BIG", "Step 2: Pulse Guard (Abrupt Chaos)"

            return "BET", self.locked_step2_pred, "Step 2: Singularity Closer (WW Hit)"

        # -------------------------------------------------------------
        # STEP 1 ENTRY: Multi-Model Quorum Recognition
        # -------------------------------------------------------------
        agent_votes = {}

        # Agent 1: 2-2 Double Pair (AA-BB -> Flip to A)
        if l3 == l4 and l2 != l3 and l1 == l2:
            p1 = "SMALL" if l1 == "BIG" else "BIG"
            agent_votes["PAIR"] = (p1, 0.88 * self._get_health_multiplier("PAIR"))

        # Agent 2: Pure 4-Step Ping-Pong (A-B-A-B -> Flip)
        if l1 != l2 and l2 != l3 and l3 != l4:
            p1 = "SMALL" if l1 == "BIG" else "BIG"
            agent_votes["PINGPONG"] = (p1, 0.90 * self._get_health_multiplier("PINGPONG"))

        # Agent 3: Dragon Trend Flow (Streak 3+)
        streak_len = 1
        for i in range(len(h) - 2, -1, -1):
            if h[i] == h[-1]:
                streak_len += 1
            else:
                break
        if streak_len >= 3:
            agent_votes["TREND"] = (
                l1,
                min(0.94, 0.76 + (streak_len * 0.04)) * self._get_health_multiplier("TREND"),
            )

        # Agent 4: 1-3 Stick-Sandwich (A-BBB-A -> A)
        if l5 != l4 and l4 == l3 and l3 == l2 and l2 != l1:
            agent_votes["SANDWICH"] = (l1, 0.82 * self._get_health_multiplier("SANDWICH"))

        # Agent 5: Dual-Horizon Markov Memory
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
                conf = (pair_counts[best] / total) * self._get_health_multiplier("MARKOV")
                if conf >= 0.68:
                    agent_votes["MARKOV"] = (best, conf)

        # Level 1 Micro-Transitions
        if level == 1:
            if l1 != l2 and l2 != l3 and "PINGPONG" not in agent_votes:
                agent_votes["PINGPONG_3"] = ("SMALL" if l1 == "BIG" else "BIG", 0.74)
            if l1 == l2 and l3 == l4 and l2 != l3 and "TREND" not in agent_votes:
                agent_votes["EARLY_2"] = (l1, 0.70)

        if not agent_votes:
            return "SKIP", "BIG", "Market Noise (No Concurrence)"

        # Vote Consensus Aggregation
        score_big = sum(conf for p, conf in agent_votes.values() if p == "BIG")
        score_small = sum(conf for p, conf in agent_votes.values() if p == "SMALL")
        best_pred = "BIG" if score_big >= score_small else "SMALL"

        agreeing_agents = [agent for agent, (p, conf) in agent_votes.items() if p == best_pred]
        max_conf = max(conf for p, conf in agent_votes.values() if p == best_pred)

        # LEVEL 1: High Volume Entry (Threshold >= 0.55)
        if level == 1:
            if max_conf >= 0.55:
                self.active_pattern = agreeing_agents[0]
                self.locked_step2_pred = (
                    best_pred
                    if ("TREND" in self.active_pattern or "SANDWICH" in self.active_pattern)
                    else ("SMALL" if best_pred == "BIG" else "BIG")
                )
                return "BET", best_pred, f"Lvl 1: {self.active_pattern} ({max_conf*100:.0f}%)"

        # LEVEL 2: Fortress Quorum (Requires at least 2 Agents consensus)
        elif level == 2:
            if len(agreeing_agents) >= 2 and max_conf >= 0.78:
                self.active_pattern = agreeing_agents[0]
                self.locked_step2_pred = (
                    best_pred
                    if "TREND" in self.active_pattern
                    else ("SMALL" if best_pred == "BIG" else "BIG")
                )
                return "BET", best_pred, f"Lvl 2 Quorum: Consensus ({max_conf*100:.0f}%)"

        # LEVEL 3+: Impervious Multi-Agent Consensus
        else:
            if len(agreeing_agents) >= 2 and max_conf >= 0.90:
                self.active_pattern = agreeing_agents[0]
                self.locked_step2_pred = best_pred
                return "BET", best_pred, f"Lvl 3+ Quorum: Impervious ({max_conf*100:.0f}%)"

        return "SKIP", "BIG", f"Quorum Filter Active (Level {level} Lock)"


# ============================================================
# 4. ADAPTIVE BETTING & STATE MANAGER
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

            if self.step == 1:
                self.step = 2
                self.bot_step += 1
                action = "WIN_STEP1_TO_STEP2"
            else:
                # 🔥 WIN-WIN HIT! Full Instant Reset to Level 1
                self.level = 1
                self.step = 1
                self.bot_step = 1
                self.cycles_completed += 1
                action = f"WIN_WIN_RESET_FROM_LVL_{old_level}"
        else:
            profit = -bet_amount
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
        self.engine = SingularityApexEngine()
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
                self.engine.update_pattern_health(is_win)
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
                else:
                    # Loss alert is kept silent
                    pass

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

            # 🎯 သင်သတ်မှတ်ပေးထားသော Format အတိုင်း တိကျစွာ ပြင်ဆင်ထားသော Message
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
            print("[LiveSignalBot] Starting 6lottery API Poller...", flush=True)
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
# 6. FLASK WEB SERVER FOR RENDER DEPLOYMENT
# ============================================================
app = Flask(__name__)
GLOBAL_BOT: Optional[LiveSignalBot] = None

@app.route("/")
def index():
    if not GLOBAL_BOT:
        return "Bot is initializing...", 200
    return jsonify({
        "status": "online",
        "engine": "V35 Singularity Apex Active",
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
    GLOBAL_BOT = LiveSignalBot()
    GLOBAL_BOT.start_polling_loop()
    
    # Render provides PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
