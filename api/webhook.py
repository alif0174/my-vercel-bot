import sys
import os

# API ফোল্ডারকে সার্চ পাথে যোগ করা
# এটি ModuleNotFoundError এর সমস্যা সমাধান করবে
sys.path.append(os.path.dirname(__file__))

import json
import logging
from telegram import Update

# ERROR: issubclass() এড়াতে telegram.ext থেকে ApplicationBuilder বা Application ইম্পোর্ট করা হচ্ছে না 
# কারণ Vercel শুধু handler ফাংশন এক্সপেক্ট করে।

# Vercel Environment Variables
# bot_core থেকে 'app' ভেরিয়েবল ইম্পোর্ট করা হলো।
# যদি ইম্পোর্টে এরর আসে, তবে Vercel রানটাইম লগ দেখাবে।
from bot_core import app 


# Vercel-এর জন্য মূল হ্যান্ডলার ফাংশন (এই ফাংশনটি Vercel নিজে খুঁজে নেয়)
# এটিই একমাত্র গ্লোবাল ভেরিয়েবল যা Vercel আশা করে না যে এটি কোনো ক্লাস হবে।
def handler(request):
    try:
        # অনুরোধের (request) body থেকে JSON ডেটা পাওয়া
        # Vercel request object ব্যবহার করা হচ্ছে, তাই event['body'] এর পরিবর্তে সরাসরি request.json() ব্যবহার করুন।
        
        # NOTE: Vercel এর সার্ভারলেস Python হ্যান্ডলারটি সাধারণত 
        # (event, context) ডিকশনারি গ্রহণ করে, কিন্তু কিছু ক্ষেত্রে request অবজেক্ট ব্যবহার করা যেতে পারে।
        
        # আমরা (event, context) মডেলটিকেই ব্যবহার করব, যা আগের কোডে ছিল,
        # যাতে নিশ্চিত হয় এটি Vercel এর স্ট্যান্ডার্ড অনুযায়ী চলে।

        # তাই, আমরা ধরে নিচ্ছি Vercel আপনার কোডটিকে আগের মতোই (event, context) মডেল দিয়ে কল করবে।

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
        # কোনো এরর হলে সেটি লগ করা
        logging.basicConfig(level=logging.ERROR)
        logging.error(f"Error processing update: {e}", exc_info=True)
        # 500 এরর এড়াতে 200 (ok) পাঠানো হচ্ছে, যাতে টেলিগ্রাম চেষ্টা বন্ধ না করে।
        return {
            'statusCode': 200,
            'body': json.dumps({'error': str(e)})
        }
