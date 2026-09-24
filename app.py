from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
from flask import Flask, jsonify
import math
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
    "warmup_target": 20,               # Warmup Chart Data (20 Candlesticks)
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
# 3. V72 QUANT APEX MASTER PREDICTOR ENGINE (O(1) Architecture)
# ============================================================
class QuantApexMasterEngineV72:
    def __init__(self, chart_window: int = 100):
        self.chart_window = chart_window
        self.prices: deque[float] = deque(maxlen=chart_window)
        self.outcomes: deque[str] = deque(maxlen=chart_window)
        self.digits: deque[int] = deque(maxlen=chart_window)
        self.cumulative_price: float = 1000.0
        self.step1_trade_mode: str = "TREND"

    def add_tick(self, digit: int):
        """0-9 ဂဏန်းအား O(1) Fast Deque ထဲသို့ တိုက်ရိုက် ထည့်သွင်းခြင်း"""
        outcome = "BIG" if digit >= 5 else "SMALL"
        price_delta = float(digit - 4.5)
        self.cumulative_price += price_delta

        self.prices.append(self.cumulative_price)
        self.outcomes.append(outcome)
        self.digits.append(digit)

    # ---------------------------------------------------------
    # TECHNICAL QUANT INDICATORS
    # ---------------------------------------------------------
    def _calculate_ema(self, period: int) -> float:
        if len(self.prices) < period:
            return self.prices[-1] if self.prices else 1000.0
        k = 2.0 / (period + 1.0)
        sub_series = list(self.prices)[-period:]
        ema = sub_series[0]
        for price in sub_series[1:]:
            ema = (price * k) + (ema * (1.0 - k))
        return ema

    def _calculate_rsi(self, period: int = 10) -> float:
        if len(self.prices) < period + 1:
            return 50.0
        sub_series = list(self.prices)[-(period + 1) :]
        gains, losses = 0.0, 0.0
        for i in range(1, len(sub_series)):
            diff = sub_series[i] - sub_series[i - 1]
            if diff >= 0:
                gains += diff
            else:
                losses += abs(diff)
        if losses == 0.0:
            return 100.0
        rs = (gains / period) / (losses / period)
        return 100.0 - (100.0 / (1.0 + rs))

    def _calculate_volatility(self, period: int = 10) -> float:
        if len(self.prices) < period:
            return 1.0
        sub_series = list(self.prices)[-period:]
        mean = sum(sub_series) / period
        variance = sum((x - mean) ** 2 for x in sub_series) / period
        return math.sqrt(variance)

    def _calculate_instant_derivative(self) -> float:
        """3-Tick Directional Check (9-0-9 လှိုင်းမှား ဖယ်ထုတ်ခြင်း)"""
        if len(self.prices) < 4:
            return 0.0
        p = list(self.prices)
        d1 = p[-1] - p[-2]
        d2 = p[-2] - p[-3]
        if (d1 > 0 and d2 > 0) or (d1 < 0 and d2 < 0):
            return p[-1] - p[-3]
        return 0.0

    # ---------------------------------------------------------
    # QUANT MARKET EVALUATION (Signal ⟷ Level ⟷ Step)
    # ---------------------------------------------------------
    def evaluate_market(self, level: int, step: int) -> Tuple[str, str, str]:
        if len(self.prices) < CONFIG["warmup_target"]:
            return "SKIP", "BIG", "Warming Up Market Candlesticks"

        ema_fast = self._calculate_ema(period=5)
        ema_slow = self._calculate_ema(period=14)
        rsi = self._calculate_rsi(period=10)
        volatility = self._calculate_volatility(period=10)
        derivative = self._calculate_instant_derivative()

        trend_bias = "BIG" if ema_fast >= ema_slow else "SMALL"
        trend_strength = abs(ema_fast - ema_slow)

        # -------------------------------------------------------------
        # STEP 2 CLOSER: RSI Exhaustion Priority Gate
        # -------------------------------------------------------------
        if step == 2:
            # Squeeze Guard
            if volatility < 0.35 and 48.0 <= rsi <= 52.0:
                return (
                    "SKIP",
                    "BIG",
                    "Step 2: Sideways Squeeze Guard (Waiting Liquidity)",
                )

            # Priority 1: Step 1 Reversion Memory Follow-Through
            if self.step1_trade_mode == "REVERSION_BEAR":
                return (
                    "BET",
                    "SMALL",
                    "Step 2: Bearish Reversion Follow-Through (WW Hit)",
                )
            elif self.step1_trade_mode == "REVERSION_BULL":
                return (
                    "BET",
                    "BIG",
                    "Step 2: Bullish Reversion Follow-Through (WW Hit)",
                )

            # Priority 2: RSI Exhaustion Check (Overbought/Oversold Priority)
            if rsi >= 78.0:
                return (
                    "BET",
                    "SMALL",
                    "Step 2: RSI Overbought Exhaustion Closer (WW Hit)",
                )
            elif rsi <= 22.0:
                return (
                    "BET",
                    "BIG",
                    "Step 2: RSI Oversold Exhaustion Closer (WW Hit)",
                )

            # Priority 3: Derivative Momentum Flow
            if abs(derivative) >= 5.0:
                shock_direction = "BIG" if derivative > 0 else "SMALL"
                return (
                    "BET",
                    shock_direction,
                    f"Step 2: Instant Velocity Alignment ({shock_direction})",
                )

            # Priority 4: Live Trend Continuation Closer
            return (
                "BET",
                trend_bias,
                f"Step 2: Quant {trend_bias} Flow Closer (WW Hit)",
            )

        # -------------------------------------------------------------
        # STEP 1 ENTRY: Multi-Indicator Concurrence Matrix
        # -------------------------------------------------------------
        signal = None
        confidence = 0.50
        reason = ""
        trade_mode = "TREND"

        # Strategy 1: RSI Extreme Mean-Reversion Snap
        if rsi >= 75.0:
            signal = "SMALL"
            confidence = 0.90
            trade_mode = "REVERSION_BEAR"
            reason = f"Quant: RSI Overbought Snap (RSI: {rsi:.1f})"
        elif rsi <= 25.0:
            signal = "BIG"
            confidence = 0.90
            trade_mode = "REVERSION_BULL"
            reason = f"Quant: RSI Oversold Snap (RSI: {rsi:.1f})"

        # Strategy 2: Filtered Derivative Surge
        elif abs(derivative) >= 6.0:
            signal = "BIG" if derivative > 0 else "SMALL"
            confidence = 0.88
            trade_mode = "TREND"
            reason = f"Quant: Verified Derivative Surge ({signal})"

        # Strategy 3: Strong Trend Breakout
        elif trend_strength >= 1.5 and (
            (trend_bias == "BIG" and rsi >= 55.0)
            or (trend_bias == "SMALL" and rsi <= 45.0)
        ):
            signal = trend_bias
            confidence = 0.86
            trade_mode = "TREND"
            reason = f"Quant: Strong EMA Breakout ({trend_bias})"

        # Strategy 4: Standard Trend Wave Following
        elif trend_strength >= 0.4:
            signal = trend_bias
            confidence = 0.76
            trade_mode = "TREND"
            reason = f"Quant: {trend_bias} Wave Flow"

        # Strategy 5: Micro-Price Impulse Flow
        else:
            p_list = list(self.prices)
            recent_delta = p_list[-1] - p_list[-4]
            if abs(recent_delta) >= 2.0:
                signal = "BIG" if recent_delta > 0 else "SMALL"
                confidence = 0.65
                trade_mode = "TREND"
                reason = f"Quant: Micro-Price Impulse ({signal})"

        # 🎯 ASYMMETRIC TIERED SHIELD: Level 1: 0.48 (90% Signals) | Level 2+: 0.80 Fortress
        required_conf = 0.48 if level == 1 else (0.80 if level == 2 else 0.88)

        if signal and confidence >= required_conf:
            self.step1_trade_mode = trade_mode
            return "BET", signal, reason

        return (
            "SKIP",
            "BIG",
            f"Market Squeeze Filter (Conf: {confidence*100:.0f}%)",
        )


# ============================================================
# 4. EXACT UNBOUNDED FIBONACCI STATE MANAGER
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
        self.engine = QuantApexMasterEngineV72()
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
            if len(self.engine.prices) < CONFIG["warmup_target"]:
                self.engine.add_tick(digit)
                current_count = len(self.engine.prices)
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

            # Update Engine with the newly finished round tick
            self.engine.add_tick(digit)

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
            print("[LiveSignalBot V72] Starting 6lottery API Poller...", flush=True)
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

# 🎯 FAST-BOOT: Gunicorn နှင့် Render အတွက် Module Level တွင် တိုက်ရိုက် စတင်သည်
GLOBAL_BOT = LiveSignalBot()
GLOBAL_BOT.start_polling_loop()

@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "engine": "V72 Quant Apex Master 90% Active Flow",
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
