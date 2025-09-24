# Multi-Session Breakout Alert Bot – Python

This bot monitors almost 500 Binance Futures coins across Asian, London, and New York trading sessions. It tracks session highs and lows and sends real-time alerts to Telegram whenever a price breaks one of these key levels.  

*Key Features:*
- Monitors multiple trading sessions (Asia → London → New York) automatically
- Sends instant Telegram notifications when a breakout happens
- Avoids duplicate alerts – if a level was already broken before the bot starts, it will send the alert once but won’t repeat it
- Helps traders spot potential opportunities without constantly watching the screen
- Built in Python using Pandas for data handling and Requests for API calls

*How it works:*
- Collects 15-minute candle data for each coin
- Calculates session highs and lows
- Sends alerts only when a new breakout occurs, so you won’t get spammed

*Why it’s useful:*
- Makes it easier to stay disciplined and follow a data-driven trading approach
- Lets you monitor hundreds of coins at the same time
- Can be extended to additional strategies like liquidity sweeps or moving averages

*Setup Instructions 

# 1. Install required libraries:
pip install requests pandas pytz


# 2. Add your Telegram API key and chat ID in a config.py file (do NOT upload real keys to GitHub)
echo "TELEGRAM_TOKEN = 'YOUR_API_KEY_HERE'" > config.py
echo "CHAT_ID = 'YOUR_CHAT_ID_HERE'" >> config.py


# 3. Run the bot
python Session_Breakout.py

