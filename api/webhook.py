import sys
import os

# API ফোল্ডারকে সার্চ পাথে যোগ করা
# Vercel-এ root ডিরেক্টরি /var/task থেকে শুরু হয়।
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.dirname(__file__)) # এই লাইনটি api ফোল্ডারকে যোগ করে।

import json
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, Application

# এখানে শুধু মডিউলের নাম ব্যবহার করুন, কারণ sys.path-এ api ফোল্ডার যুক্ত করা হয়েছে।
# কিন্তু ModuleNotFoundError এড়াতে আমরা try-except ব্লক ব্যবহার করব:

try:
    from bot_core import app 
except ModuleNotFoundError:
    # যদি আগের ইম্পোর্ট কাজ না করে, তবে ফোল্ডারের নাম যোগ করে চেষ্টা করা হবে
    from api.bot_core import app 

# Vercel Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8028816575:AAGhh5zxgLM2vVczlhqq6K0I-n7tMtnJprs")
# 
# বাকি সব একই থাকবে, শুধু লগিং লেভেল INFO তে সেট করা হলো যাতে ডিবাগিং সহজ হয়।
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Vercel-এর জন্য মূল হ্যান্ডলার ফাংশন
def handler(event, context):
    try:
        # Vercel ইভেন্ট থেকে HTTP বডি পাওয়া
        body = json.loads(event['body'])
        
        # টেলিগ্রামের জন্য আপডেট অবজেক্ট তৈরি করা
        update = Update.de_json(body, app.bot)
        
        # Application.update_queue-তে আপডেট যোগ করা
        app.update_queue.put(update)

        return {
            'statusCode': 200,
            'body': 'ok'
        }

    except Exception as e:
        logging.error(f"Error processing update: {e}", exc_info=True)
        # 500 এরর যাতে না আসে, তাই 200 (ok) পাঠানো হচ্ছে।
        return {
            'statusCode': 200,
            'body': json.dumps({'error': str(e)})
        }
