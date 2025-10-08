# api/webhook.py এর সম্পূর্ণ কোডটি (আগের কমেন্ট থেকে কপি করা):
import sys
import os

# API ফোল্ডারকে সার্চ পাথে যোগ করা
sys.path.append(os.path.dirname(__file__))

import json
import logging
from telegram import Update
# bot_core থেকে শুধু ফাংশনটি ইম্পোর্ট করা হলো
from bot_core import create_application 

# Application অবজেক্টটি শুধু একবার তৈরি করা হবে
app = create_application()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Vercel-এর জন্য মূল হ্যান্ডলার ফাংশন
def handler(request):
    try:
        # Vercel request object এর মাধ্যমে বডি পাওয়া
        if request.get('body'):
            body = json.loads(request['body'])
        else:
            return {'statusCode': 400, 'body': 'No body provided'}

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
        # 500 এরর এড়াতে 200 (ok) পাঠানো হচ্ছে
        return {
            'statusCode': 200,
            'body': json.dumps({'error': str(e)})
        }
