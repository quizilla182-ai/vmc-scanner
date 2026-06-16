import os
import re
import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]

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
    oversold = wt2 < 100
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

def get_news_summary(symbol):
    try:
        keyword = symbol.replace("USDT", "")
        rss_url = f"https://news.google.com/rss/search?q={keyword}&hl=th&gl=TH&ceid=TH:th"
        r = requests.get(rss_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        titles = re.findall(r'<title>(.*?)</title>', r.text)[2:6]
        headlines = [re.sub(r'<[^>]+>', '', t) for t in titles]
        if not headlines:
            return "ไม่พบข่าวล่าสุด"
        news_text = "\n".join(headlines)
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        prompt = f"""สรุปข่าวต่อไปนี้เกี่ยวกับ {keyword} เป็นภาษาไทย 2-3 ประโยคสั้นๆ เข้าใจง่าย บอกสาเหตุที่ราคาขึ้นหรือลง:

{news_text}

ตอบเป็นภาษาไทยเท่านั้น ไม่ต้องมีหัวข้อ ตอบสั้นๆ กระชับ"""
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        g = requests.post(gemini_url, json=payload, timeout=15)
        result = g.json()
        return result['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"❌ ดึงข่าวไม่ได้: {e}")
        return "ไม่สามารถดึงข่าวได้ในขณะนี้"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("✅ ส่ง Telegram สำเร็จ")
    except Exception as e:
        print(f"❌ ส่งไม่ได้: {e}")

def format_message(symbol, asset_type, wt1_val, wt2_val, close_price, tf="Daily (1D)"):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    emoji = "🪙" if asset_type == "CRYPTO" else "📈"
    news = get_news_summary(symbol)
    return (f"🟢 <b>VMC Cipher B — Green Circle (BUY)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} <b>Symbol :</b> {symbol}\n"
            f"📊 <b>Type   :</b> {asset_type}\n"
            f"⏱️ <b>TF     :</b> {tf}\n"
            f"💰 <b>ราคา   :</b> {close_price:,.4f}\n"
            f"〰️ <b>WT1    :</b> {wt1_val:.2f}\n"
            f"〰️ <b>WT2    :</b> {wt2_val:.2f}\n"
            f"🕐 <b>เวลา   :</b> {now}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📰 <b>สรุปข่าว:</b>\n{news}\n"
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
            send_telegram(format_message("BTCUSDT", "CRYPTO", wt1.iloc[-2], wt2.iloc[-2], df['close'].iloc[-2], "4H"))
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
