import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz

# Configuration
TELEGRAM_TOKEN = "YOUR_API_KEY_HERE"
CHAT_ID = "YOUR_CHAT_ID_HERE"

# Session times in UTC-4 (as per your requirement)
SESSION_TIMES = {
    'asia': {'start': 19, 'end': 4},    # 19:00-04:00 UTC-4
    'london': {'start': 3, 'end': 12},  # 03:00-12:00 UTC-4
    'new_york': {'start': 9.5, 'end': 16}  # 09:30-16:00 UTC-4 (4:00 PM)
}

# Global variables to store session data
session_data = {}
alerted_levels = set()

def get_top_futures_symbols(limit=500):
    """Get top Binance futures symbols by volume using public API"""
    try:
        response = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr")
        tickers = response.json()
        
        # Filter USDT pairs and sort by quoteVolume
        usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
        
        return [pair['symbol'] for pair in sorted_pairs[:limit]]
    except Exception as e:
        print(f"Error getting futures symbols: {e}")
        return []

def get_current_session():
    """Determine the current trading session based on UTC-4 time"""
    now = datetime.now(pytz.timezone('America/New_York'))  # UTC-4
    current_hour = now.hour + now.minute/60
    
    if SESSION_TIMES['asia']['start'] <= current_hour < 24 or 0 <= current_hour < SESSION_TIMES['asia']['end']:
        return 'asia'
    elif SESSION_TIMES['london']['start'] <= current_hour < SESSION_TIMES['london']['end']:
        return 'london'
    elif SESSION_TIMES['new_york']['start'] <= current_hour < SESSION_TIMES['new_york']['end']:
        return 'new_york'
    else:
        return None  # Outside trading hours

def get_15m_candles(symbol, limit=96):
    """Get 15m candles using public API"""
    try:
        response = requests.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={
                'symbol': symbol,
                'interval': '15m',
                'limit': limit
            }
        )
        return response.json()
    except Exception as e:
        print(f"Error getting candles for {symbol}: {e}")
        return []

def get_current_price(symbol):
    """Get current price using public API"""
    try:
        response = requests.get(
            "https://fapi.binance.com/fapi/v1/ticker/price",
            params={'symbol': symbol}
        )
        return float(response.json()['price'])
    except Exception as e:
        print(f"Error getting price for {symbol}: {e}")
        return None

def get_session_high_low(symbol, session, candles):
    """Calculate session high and low from 15m candles"""
    if not candles:
        return None, None
    
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                       'close_time', 'quote_asset_volume', 'trades', 
                                       'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    
    session_high = df['high'].max()
    session_low = df['low'].min()
    
    return session_high, session_low

def send_telegram_alert(message):
    """Send alert via Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, params=params)
        if response.status_code != 200:
            print(f"Telegram API error: {response.text}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def monitor_symbol(symbol):
    """Monitor a single symbol for session level breaks"""
    global session_data, alerted_levels
    
    current_session = get_current_session()
    if not current_session:
        return
    
    try:
        # Get 15m candles (last 24 hours)
        candles = get_15m_candles(symbol, 96)
        
        # Get current price
        current_price = get_current_price(symbol)
        if current_price is None:
            return
        
        # Process each session
        for session in ['asia', 'london', 'new_york']:
            # Filter candles for this session
            session_candles = []
            for candle in candles:
                candle_time = datetime.fromtimestamp(candle[0]/1000, pytz.timezone('America/New_York'))
                hour = candle_time.hour + candle_time.minute/60
                
                if session == 'asia':
                    if (SESSION_TIMES['asia']['start'] <= hour < 24) or (0 <= hour < SESSION_TIMES['asia']['end']):
                        session_candles.append(candle)
                else:
                    if SESSION_TIMES[session]['start'] <= hour < SESSION_TIMES[session]['end']:
                        session_candles.append(candle)
            
            # Calculate session high/low if not already done
            if symbol not in session_data:
                session_data[symbol] = {}
            
            if session not in session_data[symbol] and session_candles:
                high, low = get_session_high_low(symbol, session, session_candles)
                if high and low:
                    session_data[symbol][session] = {'high': high, 'low': low}
                    print(f"{symbol} {session} session - High: {high}, Low: {low}")
        
        # Check for level breaks in current session
        if current_session == 'london':
            # Check against Asia session levels
            if 'asia' in session_data.get(symbol, {}):
                asia_high = session_data[symbol]['asia']['high']
                asia_low = session_data[symbol]['asia']['low']
                
                # Generate unique keys for these levels
                high_key = f"{symbol}_asia_high"
                low_key = f"{symbol}_asia_low"
                
                if current_price >= asia_high and high_key not in alerted_levels:
                    message = f"🚨 {symbol} touched ASIA session HIGH ({asia_high}) in LONDON session at {current_price}"
                    send_telegram_alert(message)
                    alerted_levels.add(high_key)
                
                if current_price <= asia_low and low_key not in alerted_levels:
                    message = f"🚨 {symbol} touched ASIA session LOW ({asia_low}) in LONDON session at {current_price}"
                    send_telegram_alert(message)
                    alerted_levels.add(low_key)
        
        elif current_session == 'new_york':
            # Check against both Asia and London sessions
            for check_session in ['asia', 'london']:
                if check_session in session_data.get(symbol, {}):
                    check_high = session_data[symbol][check_session]['high']
                    check_low = session_data[symbol][check_session]['low']
                    
                    high_key = f"{symbol}_{check_session}_high"
                    low_key = f"{symbol}_{check_session}_low"
                    
                    if current_price >= check_high and high_key not in alerted_levels:
                        message = f"🚨 {symbol} touched {check_session.upper()} session HIGH ({check_high}) in NEW YORK session at {current_price}"
                        send_telegram_alert(message)
                        alerted_levels.add(high_key)
                    
                    if current_price <= check_low and low_key not in alerted_levels:
                        message = f"🚨 {symbol} touched {check_session.upper()} session LOW ({check_low}) in NEW YORK session at {current_price}"
                        send_telegram_alert(message)
                        alerted_levels.add(low_key)
    
    except Exception as e:
        print(f"Error processing {symbol}: {e}")

def main():
    print("Starting Session High/Low Alert Bot...")
    
    # Get top 500 futures symbols
    symbols = get_top_futures_symbols(500)
    if not symbols:
        print("No symbols found. Exiting.")
        return
    
    print(f"Monitoring {len(symbols)} symbols...")
    
    # Main loop
    while True:
        current_session = get_current_session()
        if current_session:
            print(f"\nCurrent session: {current_session.upper()} - {datetime.now(pytz.timezone('America/New_York'))}")
            
            # Process each symbol
            for symbol in symbols:
                monitor_symbol(symbol)
                time.sleep(0.1)  # Rate limiting
            
            # Clear alerted levels at session change
            if 'last_session' in globals() and current_session != last_session:
                alerted_levels.clear()
                print(f"Session changed from {last_session} to {current_session}. Cleared alerted levels.")
            
            last_session = current_session
        else:
            print("Outside trading hours. Waiting...")
        
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
