import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime

TELEGRAM_BOT_TOKEN = "8820625591:AAHAbkptEQEeC0Z10s14YepK0x1qvYqn2aM"
TELEGRAM_CHAT_ID   = "961895833"

CRYPTO_SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT"]
STOCK_SYMBOLS  = ["KTOS","AEHR","AMSC","IPWR"]

def calculate_wavetrend(df, channel_len=9, avg_len=12):
    src = (df['high'] + df['low'] + df['close']) / 3
    esa = src.ewm(span=channel_len, adjust=False).mean()
    d   = (src - esa).abs().ewm(span=channel_len, adjust=False).mean()
    ci  = (src - esa) / (0.015 * d)
    tci = ci.ewm(span=avg_len, adjust=False).mean()
    wt1 = tci
    wt2 = wt1.rolling(4).mean()
    return wt1, wt2

def detect_green_circle(df):
    wt1, wt2 = calculate_wavetrend(df)
    cross_up = (wt1.shift(1) < wt2.shift(1)) & (wt1 > wt2)
    oversold = wt2 < -60
    return cross_up & oversold, wt1, wt2

def get_crypto_data(symbol, limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": "1d", "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        df = pd.DataFrame(data, columns=['time','open','high','low','close','volume','close_time','quote_vol','trades','taker_buy_base','taker_buy_quote','ignore'])
        for col in ['open','high','low','close']:
            df[col] = df[col].astype(float)
        return df
    except:
        return None

def get_stock_data(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "6mo", "interval": "1d"}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        quotes = data['chart']['result'][0]
        ohlcv = quotes['indicators']['quote'][0]
        df = pd.DataFrame({'time': quotes['timestamp'], 'open': ohlcv['open'], 'high': ohlcv['high'], 'low': ohlcv['low'], 'close': ohlcv['close']}).dropna()
        return df
    except:
        return None

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("✅ ส่ง Telegram สำเร็จ")
    except Exception as e:
        print(f"❌ ส่งไม่ได้: {e}")

def format_message(symbol, asset_type, wt1_val, wt2_val, close_price):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    emoji = "🪙" if asset_type == "CRYPTO" else "📈"
    return (f"🟢 <b>VMC Cipher B — Green Circle (BUY)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} <b>Symbol :</b> {symbol}\n"
            f"📊 <b>Type   :</b> {asset_type}\n"
            f"⏱️ <b>TF     :</b> Daily (1D)\n"
            f"💰 <b>ราคา   :</b> {close_price:,.4f}\n"
            f"〰️ <b>WT1    :</b> {wt1_val:.2f}\n"
            f"〰️ <b>WT2    :</b> {wt2_val:.2f}\n"
            f"🕐 <b>เวลา   :</b> {now}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <i>วิเคราะห์เพิ่มเติมก่อนตัดสินใจ</i>")
def scan_btc_4h():
    print("🔍 Scan BTC 4H...")
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 100}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        df = pd.DataFrame(data, columns=['time','open','high','low','close','volume','close_time','quote_vol','trades','taker_buy_base','taker_buy_quote','ignore'])
        for col in ['open','high','low','close']:
            df[col] = df[col].astype(float)
        green, wt1, wt2 = detect_green_circle(df)
        if green.iloc[-2]:
            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            msg = (f"🟢 <b>VMC Cipher B — Green Circle (BUY)</b>\n"
                   f"━━━━━━━━━━━━━━━━━━━\n"
                   f"🪙 <b>Symbol :</b> BTCUSDT\n"
                   f"📊 <b>Type   :</b> CRYPTO\n"
                   f"⏱️ <b>TF     :</b> 4H\n"
                   f"💰 <b>ราคา   :</b> {df['close'].iloc[-2]:,.4f}\n"
                   f"〰️ <b>WT1    :</b> {wt1.iloc[-2]:.2f}\n"
                   f"〰️ <b>WT2    :</b> {wt2.iloc[-2]:.2f}\n"
                   f"🕐 <b>เวลา   :</b> {now}\n"
                   f"━━━━━━━━━━━━━━━━━━━\n"
                   f"⚠️ <i>วิเคราะห์เพิ่มเติมก่อนตัดสินใจ</i>")
            send_telegram(msg)
            print("🟢 พบสัญญาณ BTC 4H!")
        else:
            print(f"⬜ ไม่มีสัญญาณ BTC 4H  WT2={wt2.iloc[-2]:.1f}")
    except Exception as e:
        print(f"❌ Error BTC 4H: {e}")

def scan_all():
    print(f"🔍 เริ่ม scan {datetime.now()}")
    signals_found = 0
    for symbol in CRYPTO_SYMBOLS:
        df = get_crypto_data(symbol)
        if df is None or len(df) < 30: continue
        green, wt1, wt2 = detect_green_circle(df)
        if green.iloc[-2]:
            send_telegram(format_message(symbol, "CRYPTO", wt1.iloc[-2], wt2.iloc[-2], df['close'].iloc[-2]))
            signals_found += 1
        time.sleep(0.3)
    for symbol in STOCK_SYMBOLS:
        df = get_stock_data(symbol)
        if df is None or len(df) < 30: continue
        green, wt1, wt2 = detect_green_circle(df)
        if green.iloc[-2]:
            send_telegram(format_message(symbol, "STOCK US", wt1.iloc[-2], wt2.iloc[-2], df['close'].iloc[-2]))
            signals_found += 1
        time.sleep(0.3)
    if signals_found == 0:
        send_telegram(f"📋 <b>สรุปผล Scan รายวัน</b>\n🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}\nℹ️ ไม่พบสัญญาณ Green Circle วันนี้")
    print(f"✅ เสร็จ พบ {signals_found} สัญญาณ")

scan_all()
scan_btc_4h()

