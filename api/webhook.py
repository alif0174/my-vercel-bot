import sys
# এই লাইনটি বর্তমান ডিরেক্টরি (api ফোল্ডার) কে সার্চ পাথে যোগ করবে
sys.path.append('.') 

import os
import json
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, Application
from bot_core import app # <--- এখন bot_core থেকে 'app' খুঁজে পাবে

# Vercel Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8028816575:AAGhh5zxgLM2vVczlhqq6K0I-n7tMtnJprs")

# Vercel-এর জন্য মূল হ্যান্ডলার ফাংশন
def handler(event, context):
    try:
        # Vercel ইভেন্ট থেকে HTTP বডি পাওয়া
        body = json.loads(event['body'])
        
        # টেলিগ্রামের জন্য আপডেট অবজেক্ট তৈরি করা
        update = Update.de_json(body, app.bot)
        
        # Application.update_queue-তে আপডেট যোগ করা (এটি অ্যাপ্লিকেশনকে মেসেজ প্রক্রিয়া করতে সাহায্য করে)
        app.update_queue.put(update)

        # মেসেজ প্রসেস করা 
        # Application.process_update(update) ব্যবহার করা এখন আর প্রয়োজন নেই, 
        # কারণ ApplicationBuilder().build()-এর পরিবর্তে Application.builder().updater().build() 
        # ব্যবহার না করলে এটি স্বয়ংক্রিয়ভাবে কাজ করে না। 
        # Vercel এ এটিই সবচেয়ে সহজ तरीका।

        return {
            'statusCode': 200,
            'body': 'ok'
        }

    except Exception as e:
        # কোনো এরর হলে সেটি লগ করা 
        logging.error(f"Error processing update: {e}", exc_info=True)
        # 500 এরর যাতে না আসে, তাই 200 (ok) পাঠানো হচ্ছে, কিন্তু Vercel লগ দেখাবে।
        return {
            'statusCode': 200,
            'body': json.dumps({'error': str(e)})
        }

