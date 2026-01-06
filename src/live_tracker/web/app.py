"""
Flask Web Application for Live Tracker Dashboard.

Professional trading dashboard with real-time signals and analysis.
"""

import json
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request

from live_tracker.data.fetcher import MarketDataFetcher
from live_tracker.signals.engine import SignalEngine
from live_tracker.config import DEFAULT_WATCHLISTS

logger = logging.getLogger(__name__)

# Global instances
fetcher = MarketDataFetcher()
engine = SignalEngine()

def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    app.config["JSON_SORT_KEYS"] = False

    @app.route("/")
    def index():
        """Main dashboard page."""
        return render_template("dashboard.html", watchlists=DEFAULT_WATCHLISTS)

    @app.route("/api/scan", methods=["POST"])
    def api_scan():
        """Scan symbols and return signals."""
        data = request.get_json() or {}
        symbols = data.get("symbols", ["SPY", "QQQ", "AAPL", "NVDA"])

        if isinstance(symbols, str):
            symbols = [s.strip().upper() for s in symbols.split(",")]

        results = []
        for symbol in symbols:
            try:
                df = fetcher.get_data_with_indicators(symbol, period="3mo", interval="1d")
                if not df.empty:
                    signal = engine.analyze(df, symbol)

                    # Get price history for sparkline
                    price_history = df["close"].tail(30).tolist()

                    results.append({
                        "symbol": signal.symbol,
                        "price": round(signal.price, 2),
                        "signal": signal.signal_type.value,
                        "strength": signal.strength.value,
                        "score": round(signal.score, 1),
                        "stop_loss": round(signal.stop_loss, 2) if signal.stop_loss else None,
                        "take_profit": round(signal.take_profit, 2) if signal.take_profit else None,
                        "risk_reward": signal.risk_reward,
                        "price_history": price_history,
                        "indicators": signal.indicators,
                        "timestamp": signal.timestamp.isoformat(),
                    })
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                results.append({
                    "symbol": symbol,
                    "error": str(e)
                })

        return jsonify({
            "success": True,
            "count": len(results),
            "timestamp": datetime.now().isoformat(),
            "results": results
        })

    @app.route("/api/analyze/<symbol>")
    def api_analyze(symbol):
        """Get detailed analysis for a single symbol."""
        symbol = symbol.upper()

        try:
            df = fetcher.get_data_with_indicators(symbol, period="6mo", interval="1d")

            if df.empty:
                return jsonify({"success": False, "error": f"No data for {symbol}"}), 404

            signal = engine.analyze(df, symbol)
            info = fetcher.get_info(symbol)

            # Price history for chart
            price_data = []
            for idx, row in df.tail(90).iterrows():
                price_data.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(row["open"], 2),
                    "high": round(row["high"], 2),
                    "low": round(row["low"], 2),
                    "close": round(row["close"], 2),
                    "volume": int(row["volume"])
                })

            return jsonify({
                "success": True,
                "symbol": symbol,
                "signal": {
                    "type": signal.signal_type.value,
                    "strength": signal.strength.value,
                    "score": round(signal.score, 1),
                    "stop_loss": round(signal.stop_loss, 2) if signal.stop_loss else None,
                    "take_profit": round(signal.take_profit, 2) if signal.take_profit else None,
                    "risk_reward": signal.risk_reward,
                },
                "price": round(signal.price, 2),
                "indicators": signal.indicators,
                "info": info,
                "price_history": price_data,
                "timestamp": datetime.now().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/watchlists")
    def api_watchlists():
        """Get available watchlists."""
        return jsonify({
            "success": True,
            "watchlists": DEFAULT_WATCHLISTS
        })

    @app.route("/api/quote/<symbol>")
    def api_quote(symbol):
        """Get current quote for a symbol."""
        symbol = symbol.upper()

        try:
            quote = fetcher.get_quote(symbol)
            return jsonify({
                "success": True,
                "quote": quote
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    return app


def run_server(host="127.0.0.1", port=5000, debug=False):
    """Run the Flask development server."""
    app = create_app()
    print(f"\n{'='*50}")
    print(f"🚀 Live Tracker Dashboard")
    print(f"{'='*50}")
    print(f"\nOpen your browser to: http://{host}:{port}")
    print(f"\nPress Ctrl+C to stop\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)
