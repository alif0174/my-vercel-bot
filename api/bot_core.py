import json
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os
import datetime
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---
# সাধারণ সেটিংস
# ---
daily_pwd = f"JWKzRqgz{datetime.datetime.now().day}"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8028816575:AAGhh5zxgLM2vVczlhqq6K0I-n7tMtnJprs")
ADMIN_IDS = [1712462578, 5019082603]
DATA_FILE = 'bot_data.json'
MIN_WITHDRAW_AMOUNT = 100
# পরিবর্তন: উইথড্র ফি ফিক্সড ৬ টাকা
WITHDRAWAL_FIXED_FEE = 6

# প্রতিটি টাস্কের জন্য নির্ধারিত পুরস্কার
TASK_REWARDS = {
    'gmail': 10,
    'facebook': 2,
    'instagram': 1,
    'alternative_gmail': 10
}

# নতুন: অল্টারনেটিভ জিমেইল এর জন্য নির্দিষ্ট মূল্য
ALTERNATIVE_GMAIL_PRICE = 10
ALTERNATIVE_GMAIL_AMOUNTS = [30, 50, 70, 100, 200, 300, 400, 500]

# ---
# Google Sheets API কনফিগারেশন
# ---
CREDENTIALS_FILE = 'credentials.json'
GOOGLE_SHEET_NAME = "Telegram bot"
USER_INFO_SHEET_NAME = "User Info"
# নতুন: প্রতিটি টাস্কের জন্য আলাদা শীটের নাম
GMAIL_SHEET_NAME = "Gmail Submissions"
FACEBOOK_SHEET_NAME = "Facebook Submissions"
INSTAGRAM_SHEET_NAME = "Instagram Submissions"
WITHDRAWAL_LOGS_SHEET_NAME = "Withdrawal Logs"
# নতুন: Alternative Gmail সাবমিশনের জন্য নতুন শীটের নাম
ALTERNATIVE_GMAIL_SHEET_NAME = "Alternative Gmail Submissions"

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
sheet_instances = {}

# ---
# ডেটা লোড এবং সেভ করার ফাংশন
# ---
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            if 'disabled_tasks' not in data:
                data['disabled_tasks'] = []
            for uid in data['users']:
                user_data = data['users'][uid]
                user_data.setdefault('gmail_submissions', 0)
                user_data.setdefault('facebook_submissions', 0)
                user_data.setdefault('instagram_submissions', 0)
                user_data.setdefault('alternative_gmail_submissions', 0)
                user_data.setdefault('withdraw_requests', 0)
                user_data.setdefault('successful_withdrawals', 0)
                user_data.setdefault('rejected_withdrawals', 0)
                user_data.setdefault('held_balance', 0)
            if 'payment_methods_status' not in data:
                data['payment_methods_status'] = {'Bkash': True, 'Nagad': True}
            if 'tasks_pending_review' not in data:
                data['tasks_pending_review'] = {}
            # নতুন: অল্টারনেটিভ জিমেইল এর মূল্য
            if 'alternative_gmail_price' not in data:
                data['alternative_gmail_price'] = ALTERNATIVE_GMAIL_PRICE
            return data
    except FileNotFoundError:
        return {
            'users': {},
            'disabled_tasks': [],
            'payment_methods_status': {'Bkash': True, 'Nagad': True},
            'tasks_pending_review': {},
            'alternative_gmail_price': ALTERNATIVE_GMAIL_PRICE
        }
    except Exception as e:
        print(f"Error loading data: {e}")
        return {
            'users': {},
            'disabled_tasks': [],
            'payment_methods_status': {'Bkash': True, 'Nagad': True},
            'tasks_pending_review': {},
            'alternative_gmail_price': ALTERNATIVE_GMAIL_PRICE
        }

def save_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

# ---
# টাস্ক জেনারেটিং ফাংশন
# ---
def generate_gmail():
    usa_first_names = [
        "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
        "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
        "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
        "Matthew", "Betty", "Anthony", "Margaret", "Donald", "Sandra", "Mark", "Ashley",
        "Paul", "Kimberly", "Steven", "Donna", "Andrew", "Emily", "Kenneth", "Carol",
        "Joshua", "Michelle", "George", "Helen", "Kevin", "Amanda", "Brian", "Dorothy"
    ]
    first = random.choice(usa_first_names)
    addr_prefix = ''.join(random.choices(string.ascii_lowercase, k=7))
    addr = f"{addr_prefix}{random.randint(100,999)}@gmail.com"
    pwd = daily_pwd
    return first, addr, pwd

def generate_facebook_info():
    user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    return user, pwd

def generate_instagram_info():
    user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    return user, pwd

# ---
# ইউটিলিটি ফাংশন
# ---
def is_admin(uid):
    return int(uid) in ADMIN_IDS

def get_text(user, key):
    lang = user.get('language', 'English')
    # লোড করা ডেটা থেকে অল্টারনেটিভ জিমেইল এর মূল্য নেওয়া হচ্ছে
    data = load_data()
    alt_gmail_price = data.get('alternative_gmail_price', ALTERNATIVE_GMAIL_PRICE)
    
    # নতুন: ফিক্সড উইথড্র ফি
    fee = WITHDRAWAL_FIXED_FEE

    texts = {
        'English': {
            'main_menu': '🏠 Main Menu:',
            'start_task_menu_text': 'Please choose a task:',
            'select_method': 'Select method:',
            'enter_number': 'Enter number:',
            'enter_amount': 'Enter amount:',
            'language_set': 'Language set: English',
            'unknown': "❓ Sorry, I didn't understand that.",
            'balance': "🏦 Your Balances:\n  - Main Balance: {} Tk\n  - Pending Balance: {} Tk",
            'back': '⬅️ Back',
            'min_withdraw_error': f"❌ Minimum withdrawal amount is {MIN_WITHDRAW_AMOUNT} Tk.",
            'insufficient_balance': "❌ Insufficient balance.",
            # পরিবর্তন: ফিক্সড ফি এর মেসেজ
            'withdraw_confirm_message': "Method: {method}\nNumber: {number}\nRequested Amount: {requested_amount} Tk\nFee (Fixed): {fee_amount} Tk\n**Net Payable Amount:** {net_amount} Tk\n\nConfirm?", 
            'withdraw_success_message': "✅ Withdraw request submitted. You will receive payment within 24 hours.",
            'enter_authenticator_key': "❗Have you removed gmail account from your device ?\n If yes , Write \"yes\". If no, Write \"no\" .",
            'enter_facebook_credentials': f"❗Please open a Facebook account and send me the details in the following format and get {TASK_REWARDS['facebook']} BDT per one :\n\nEmail :\nPassword :",
            'enter_instagram_credentials': f"❗Please open an Instagram account and send me the details in the following format and get {TASK_REWARDS['instagram']} BDT :\n\nEmail :\nPassword :\nGoogle Authenticator Key (2 step verification) :",
            'gmail_submission_complete': "✅ Gmail submitted for review ( 72 hours ) . Your reward is in pending balance.",
            'facebook_submission_complete': "✅ Facebook Account and Authenticator Key submitted for review. Your reward is in pending balance.",
            'instagram_submission_complete': "✅ Instagram Account and Authenticator Key submitted for review. Your reward is in pending balance.",
            'task_disabled': "❌ This task is currently disabled by the admin. Please try again later.",
            'all_tasks_disabled': "❌ All tasks are currently disabled by the admin. Please try again later.",
            'payment_method_disabled': "❌ This payment method is currently disabled by the admin. Please choose another method or try again later.",
            'details_message': (
                "🕵️‍♂️ **Your Task Details:**\n"
                "-----------------------------------\n"
                "📧 Gmail Submissions: {}\n"
                "🔵 Facebook Submissions: {}\n"
                "📸 Instagram Submissions: {}\n"
                "📝 Alternative Gmail Submissions: {}\n" 
                "-----------------------------------\n"
                "💵 Total Withdrawal Requests: {}\n"
                "✅ Successful Withdrawals: {}\n"
                "❌ Rejected Withdrawals: {}\n"
                "-----------------------------------"
            ),
            'current_task_pending': "❗ You have a pending task. Please complete or cancel it first.",
            'task_changed': "✅ Task changed. Please enter details for the new task.",
            'task_rejected_notification': "❌ Your task has been rejected.\n\nTask ID: {task_id}\nEarned Amount: {amount} BDT\n\nThe amount has been removed from your pending balance.",
            'rejected_gmail_full_details': "Gmail: {address}\nPassword: {password}",
            'rejected_social_full_details': "Email/User: {email}\nPassword: {password}\nAuthenticator Key: {auth_key}",
            'task_approved_notification': "✅ Your task '{task_type}' (ID: {task_id}) has been approved! {amount} BDT has been added to your main balance.",
            # নতুন: Alternative Gmail মেসেজ
            'alternative_gmail_privacy': (
                "Privacy Policy for 'Alternative Gmail' Submissions:\n\n"
                "By submitting your file/sheet link, you agree to the following terms and conditions:\n\n"
                """1. All Gmail accounts must be new and fresh.

2. Each account must be name-based (include a real person’s name in the address). 
Example : elizabeth213@gmail.com✅
Example : u6881177974@gmail.com✅


3. All accounts must use the same password . 
Example : JWKzRqgz6 ✅ 
Example : Wo1fHLT@K!*$#&4c4V9m ❌

4. No file or link may contain viruses, malware, or harmful content.

5. Payment: 10 BDT per valid Gmail account.

6. If the rules are not followed, the file will be returned and no payment will be made.

7. Review time: up to 72 hours for verification.

8. The supplier is fully responsible for providing legitimate and lawful data; any illegal or unauthorized data is the supplier’s responsibility.\n\n"""
                "Click the button below to confirm you have read and understood this policy."
            ),
            'read_and_accept_button': '💎 I read & accept this',
            'select_quantity_prompt': "How many Gmails will you provide? Please select a number:",
            # কনফার্মেশন মেসেজ
            'confirm_quantity_and_link_prompt': "✅ You have selected to provide {quantity} Gmails.\nFor each Gmail, you will get {price} BDT.\nYour total pending balance will be {amount} BDT.\n\nPlease send your  File/Sheet link now:",
            'invalid_link_warning': "❌ Invalid link format. Please send a valid file link starting with 'http' or 'https'.",
            'alternative_submission_complete': "✅ Your file link has been submitted. Your reward of {amount} BDT has been added to your pending balance.", # পরিবর্তন: পেন্ডিং ব্যালেন্স এ যোগ হবে
            'new_alternative_submission_admin': "🆕 New Alternative Gmail Submission by User ID: {uid}\nSubmission ID: {submission_id}\nSubmitted Link: {link}\nAmount: {amount} BDT\n\nTo approve, use /approve {submission_id}", # পরিবর্তন: অ্যাপ্রুভ কমান্ড
            'invalid_quantity_error': "❌ This amount is not acceptable. Please select a number from the specified list." # নতুন ত্রুটি বার্তা
        },
        'Bangla': {
            'main_menu': '🏠 মেইন মেনু:',
            'start_task_menu_text': 'একটি কাজ নির্বাচন করুন:',
            'select_method': 'মেথড সিলেক্ট করুন:',
            'enter_number': 'নাম্বার দিন:',
            'enter_amount': 'টাকা লিখুন:',
            'language_set': 'ভাষা সেট: বাংলা',
            'unknown': "❓ দুঃখিত, বুঝতে পারিনি।",
            'balance': "🏦 আপনার ব্যালেন্স:\n  - মূল ব্যালেন্স: {} টাকা\n  - পেন্ডিং ব্যালেন্স: {} টাকা",
            'back': '⬅️ ব্যাক',
            'min_withdraw_error': f"❌ সর্বনিম্ন উইথড্র পরিমাণ {MIN_WITHDRAW_AMOUNT} টাকা।",
            'insufficient_balance': "❌ অপর্যাপ্ত ব্যালেন্স।",
            # পরিবর্তন: ফিক্সড ফি এর মেসেজ
            'withdraw_confirm_message': "মেথড: {method}\nনাম্বার: {number}\nঅনুরোধকৃত পরিমাণ: {requested_amount} টাকা\nফি (Fixed): {fee_amount} টাকা\n**মোট নিকাশী পরিমাণ (Net Payable):** {net_amount} টাকা\n\nআপনি কি নিশ্চিত?", 
            'withdraw_success_message': "✅ উইথড্র রিকোয়েস্ট জমা দেওয়া হয়েছে। আপনি ২৪ ঘন্টার মধ্যে পেমেন্ট পেয়ে যাবেন।",
            'enter_authenticator_key': "❗আপনি কি আপনার ডিভাইস থেকে জিমেইল অ্যাকাউন্ট রিমুভ করেছেন? \n  যদি হ্যাঁ হয়, তাহলে \"হ্যাঁ\" লিখো। যদি না হয়, তাহলে \"না\" লিখো।",
            'enter_facebook_credentials': f"❗অনুগ্রহ করে একটি ফেসবুক অ্যাকাউন্ট খুলুন এবং নিম্নলিখিত ফরম্যাটে তথ্যগুলো পাঠান এবং {TASK_REWARDS['facebook']} টাকা পান :\n\nEmail :\nPassword :",
            'enter_instagram_credentials': f"❗অনুগ্রহ করে একটি ইনস্টাগ্রাম অ্যাকাউন্ট খুলুন এবং নিম্নলিখিত ফরম্যাটে তথ্যগুলো পাঠান এবং {TASK_REWARDS['instagram']} টাকা পান :\n\nEmail :\nPassword :\nGoogle Authenticator Key (2 step verification) :",
            'gmail_submission_complete': "✅ জিমেইল পর্যালোচনার জন্য জমা দেওয়া হয়েছে ( 72 hours ) । আপনার পুরস্কার পেন্ডিং ব্যালেন্সে আছে।",
            'facebook_submission_complete': "✅ ফেসবুক অ্যাকাউন্ট এবং অথেন্টিকেটর কী পর্যালোচনার জন্য জমা দেওয়া হয়েছে। আপনার পুরস্কার পেন্ডিং ব্যালেন্সে আছে।",
            'instagram_submission_complete': "✅ ইনস্টাগ্রাম অ্যাকাউন্ট এবং অথেন্টিকেটর কী পর্যালোচনার জন্য জমা দেওয়া হয়েছে। আপনার পুরস্কার পেন্ডিং ব্যালেন্সে আছে।",
            'task_disabled': "❌ এই কাজটি বর্তমানে অ্যাডমিন দ্বারা বন্ধ আছে। অনুগ্রহ করে পরে চেষ্টা করুন।",
            'all_tasks_disabled': "❌ সমস্ত কাজ বর্তমানে অ্যাডমিন দ্বারা বন্ধ আছে। অনুগ্রহ করে পরে চেষ্টা করুন।",
            'payment_method_disabled': "❌ এই পেমেন্ট মেথডটি বর্তমানে অ্যাডমিন দ্বারা বন্ধ আছে। অনুগ্রহ করে অন্য মেথড নির্বাচন করুন অথবা পরে চেষ্টা করুন।",
            'details_message': (
                "🕵️‍♂️ **আপনার কাজের বিবরণ:**\n"
                "-----------------------------------\n"
                "📧 জিমেইল জমা: {}\n"
                "🔵 ফেসবুক জমা: {}\n"
                "📸 ইনস্টাগ্রাম জমা: {}\n"
                "📝 বিকল্প জিমেইল জমা: {}\n" 
                "-----------------------------------\n"
                "💵 মোট উইথড্র রিকোয়েস্ট: {}\n"
                "✅ সফল উইথড্র: {}\n"
                "❌ বাতিল উইথড্র: {}\n"
                "-----------------------------------"
            ),
            'current_task_pending': "❗ আপনার একটি কাজ চলমান আছে। অনুগ্রহ করে সেটি সম্পূর্ণ করুন অথবা বাতিল করুন।",
            'task_changed': "✅ কাজ পরিবর্তন করা হয়েছে। নতুন কাজের জন্য বিবরণ লিখুন।",
            'task_rejected_notification': "❌ দুঃখিত, আপনার টাস্কটি বাতিল করা হয়েছে।\n\nটাস্ক আইডি: {task_id}\nপ্রাপ্ত পুরস্কার: {amount} টাকা\n\nএই টাকা আপনার পেন্ডিং ব্যালেন্স থেকে কেটে নেওয়া হয়েছে।",
            'rejected_gmail_full_details': "জিমেইল: {address}\nপাসওয়ার্ড: {password}",
            'rejected_social_full_details': "ইমেইল/ইউজার: {email}\nপাসওয়ার্ড: {password}\nঅথেন্টিকেটর কী: {auth_key}",
            'task_approved_notification': "✅ আপনার টাস্ক '{task_type}' (আইডি: {task_id}) অনুমোদিত হয়েছে! {amount} টাকা আপনার মূল ব্যালেন্সে যোগ করা হয়েছে।",
            # নতুন: Alternative Gmail মেসেজ
            'alternative_gmail_privacy': (
                "বিকল্প জিমেইল সাবমিশনের জন্য গোপনীয়তা নীতি:\n\n"
                "আপনার  ফাইলের/শীট এর লিংক জমা দিয়ে, আপনি নিম্নলিখিত শর্তাবলী মেনে নিতে সম্মত হচ্ছেন:\n\n"
                """1. সব Gmail অ্যাকাউন্ট নতুন ও ফ্রেশ হতে হবে।


2. প্রতিটি অ্যাকাউন্ট নামভিত্তিক হতে হবে (অ্যাড্রেসে একজন বাস্তব ব্যক্তির নাম থাকতে হবে)। 
Example : elizabeth213@gmail.com✅
Example : u6881177974@gmail.com✅


3. সব অ্যাকাউন্টে একই পাসওয়ার্ড ব্যবহার করতে হবে। 
Example : JWKzRqgz6 ✅ 
Example : Wo1fHLT@K!*$#&4c4V9m ❌


4. কোনো ফাইল বা লিঙ্কে ভাইরাস, ম্যালওয়্যার বা ক্ষতিকারক কনটেন্ট থাকতে পারবে না।


5. পেমেন্ট: প্রতি বৈধ Gmail অ্যাকাউন্টে ১০ টাকা।


6. নিয়মগুলো মানা না হলে ফাইল ফেরত দেওয়া হবে এবং কোনো পেমেন্ট করা হবে না।


7. রিভিউ সময়: যাচাইয়ের জন্য সর্বোচ্চ 72 ঘণ্টা।


8. সরবরাহকারীকে বৈধ ও আইনসঙ্গত ডেটা সরবরাহ করতে হবে; কোনো অবৈধ বা অনুমতিহীন ডেটার দায় সরবরাহকারীর।\n\n"""
                "নীতিটি পড়েছেন এবং বুঝেছেন তা নিশ্চিত করতে নিচের বাটনটি ক্লিক করুন।"
            ),
            'read_and_accept_button': '💎 আমি এটি পড়েছি',
            'select_quantity_prompt': "আপনি কতটি জিমেইল দিবেন? একটি সংখ্যা নির্বাচন করুন:",
            # কনফার্মেশন মেসেজ
            'confirm_quantity_and_link_prompt': "✅ আপনি {quantity}টি জিমেইল দিতে চেয়েছেন।\nপ্রতিটি জিমেইলের জন্য আপনি পাবেন {price} টাকা।\nআপনার মোট পেন্ডিং ব্যালেন্স হবে {amount} টাকা।\n\nএবার আপনার Google Drive ফাইলের লিংকটি দিন:",
            'invalid_link_warning': "❌ লিংকের ফরম্যাট ভুল। অনুগ্রহ করে 'http' বা 'https' দিয়ে শুরু হওয়া একটি বৈধ লিংক পাঠান।",
            'alternative_submission_complete': "✅ আপনার ফাইলের লিংক জমা দেওয়া হয়েছে। আপনার {amount} টাকা পেন্ডিং ব্যালেন্সে যোগ করা হয়েছে।", 
            'new_alternative_submission_admin': "🆕 নতুন বিকল্প জিমেইল সাবমিশন\nইউজার আইডি: {uid}\nসাবমিশন আইডি: {submission_id}\nজমা দেওয়া লিংক: {link}\nপরিমাণ: {amount} টাকা\n\nঅনুমোদনের জন্য, /approve {submission_id} কমান্ডটি ব্যবহার করুন।", 
            'invalid_quantity_error': "❌ এই পরিমাণটি গ্রহণযোগ্য নয়। অনুগ্রহ করে নির্দিষ্ট তালিকা থেকে একটি সংখ্যা নির্বাচন করুন।" # নতুন ত্রুটি বার্তা
        },
        'Hindi': {
            'main_menu': '🏠 मुख्य मेनू:',
            'start_task_menu_text': 'कृपया एक कार्य चुनें:',
            'select_method': 'मेथड चुनें:',
            'enter_number': 'नंबर डालें:',
            'enter_amount': 'राशि लिखें:',
            'language_set': 'भाषा सेट: हिंदी',
            'unknown': "❓ माफ करें, समझ नहीं आया।",
            'balance': "🏦 आपका बैलेंस:\n  - मुख्य बैलेंस: {} रुपये\n  - लंबित बैलेंस: {} रुपये",
            'back': '⬅️ वापस',
            'min_withdraw_error': f"❌ न्यूनतम निकासी राशि {MIN_WITHDRAW_AMOUNT} रुपये है।",
            'insufficient_balance': "❌ अपर्याप्त बैलेंस।",
            # পরিবর্তন: ফিক্সড ফি এর মেসেজ
            'withdraw_confirm_message': "मेथड: {method}\nनंबर: {number}\nअनुरोधित राशि: {requested_amount} रुपये\nशुल्क (Fixed): {fee_amount} रुपये\n**कुल देय राशि:** {net_amount} रुपये\n\nपुष्टि करें?", 
            'withdraw_success_message': "✅ निकासी अनुरोध जमा कर दिया गया है। आपको 24 घंटे के भीतर भुगतान प्राप्त होगा।",
            'enter_authenticator_key': "❗क्या आपने अपने डिवाइस से जीमेल अकाउंट हटा दिया है? \n अगर हाँ, तो \"हाँ\" लिखें। अगर नहीं, तो \"नहीं\" लिखें।",
            'enter_facebook_credentials': f"❗कृपया एक फेसबुक अकाउंट खोलें और निम्नलिखित प्रारूप में विवरण भेजें और {TASK_REWARDS['facebook']} रुपये प्राप्त करें:\n\nEmail :\nPassword :",
            'enter_instagram_credentials': f"❗ कृपया एक इंस्टाग्राम अकाउंट खोलें और निम्नलिखित प्रारूप में विवरण भेजें और {TASK_REWARDS['instagram']} रुपये प्राप्त करें:\n\nEmail :\nPassword :\nGoogle Authenticator Key (2 step verification) :",
            'gmail_submission_complete': "✅ जीमेल समीक्षा के लिए प्रस्तुत की गई ( 72 hours ) । आपका पुरस्कार लंबित बैलेंस में है।",
            'facebook_submission_complete': "✅ फेसबुक अकाउंट और ऑथेंटिकेटर कुंजी समीक्षा के लिए प्रस्तुत की गई। आपका पुरस्कार लंबित बैलेंस में है।",
            'instagram_submission_complete': "✅ इंस्टाग्राम अकाउंट और ऑथेंटिकेटर कुंजी समीक्षा के लिए प्रस्तुत की गई। आपका पुरस्कार लंबित बैलेंस में है।",
            'task_disabled': "❌ यह कार्य वर्तमान में व्यवस्थापक द्वारा अक्षम है। कृपया बाद में पुनः प्रयास करें।",
            'all_tasks_disabled': "❌ सभी कार्य वर्तमान में व्यवस्थापक द्वारा अक्षम हैं। कृपया बाद में पुनः प्रयास करें।",
            'payment_method_disabled': "❌ यह भुगतान विधि वर्तमान में व्यवस्थापक द्वारा अक्षम है। कृपया कोई अन्य विधि चुनें या बाद में पुनः प्रयास करें।",
            'details_message': (
                "🕵️‍♂️ **आपके कार्य विवरण:**\n"
                "-----------------------------------\n"
                "📧 जीमेल सबमिशन: {}\n"
                "🔵 फेसबुक सबमिशन: {}\n"
                "📸 इंस्टाग्राम सबमिशन: {}\n"
                "📝 वैकल्पिक जीमेल सबमिशन: {}\n"
                "-----------------------------------\n"
                "💵 कुल निकासी अनुरोध: {}\n"
                "✅ सफल निकासी: {}\n"
                "❌ अस्वीकृत निकासी: {}\n"
                "-----------------------------------"
            ),
            'current_task_pending': "❗ आपका एक कार्य लंबित है। कृपया इसे पहले पूरा या रद्द करें।",
            'task_changed': "✅ कार्य बदल गया। नए कार्य के लिए विवरण दर्ज करें।",
            'task_rejected_notification': "❌ क्षमा करें, आपका कार्य अस्वीकार कर दिया गया है।\n\nकार्य आईडी: {task_id}\nअर्जित राशि: {amount} रुपये\n\nयह राशि आपके लंबित बैलेंस से काट ली गई है।",
            'rejected_gmail_full_details': "जीमेल: {address}\nपासवर्ड: {password}",
            'rejected_social_full_details': "ईमेल/उपयोगकर्ता: {email}\nपासवर्ड: {password}\nऑथेंटिकेटर कुंजी: {auth_key}",
            'task_approved_notification': "✅ आपका कार्य '{task_type}' (आईडी: {task_id}) स्वीकृत हो गया है! {amount} रुपये आपके मुख्य बैलेंस में जोड़ दिए गए हैं।",
            # নতুন: Alternative Gmail মেসেজ
            'alternative_gmail_privacy': (
                "वैकल्पिक जीमेल सबमिशन के लिए गोपनीयता নীতি:\n\n"
                "अपना  फ़ाइल/शीट का लिंक सबमिट करके, आप निम्नलिखित नियमों और शर्तों से सहमत होते हैं:\n\n"
                """1. सभी Gmail अकाउंट नए और फ्रेश होने चाहिए।


2. हर अकाउंट नाम आधारित होना चाहिए (पते में किसी वास्तविक व्यक्ति का नाम होना चाहिए)।
Example : elizabeth213@gmail.com✅
Example : u6881177974@gmail.com✅


3. सभी अकाउंट्स में एक ही पासवर्ड इस्तेमाल करना होगा।
Example : JWKzRqgz6 ✅ 
Example : Wo1fHLT@K!*$#&4c4V9m ❌


4. किसी भी फ़ाइल या लिंक में वायरस, मैलवेयर या हानिकारक सामग्री नहीं होनी चाहिए।


5. भुगतान: प्रति वैध Gmail अकाउंट 10 টাকা (बीडीটি)।


6. नियमों का पालन न होने पर फ़ाइल वापस कर दी जाएगी और भुगतान नहीं किया जाएगा।


7. समीक्षा समय: सत्यापन के लिए अधिकतम 72 घंटे।


8. आपूर्तिकर्ता को वैध और कानूनी डेटा प्रदान करना होगा; किसी भी अवैध या अनधिकृत डेटा की पूरी जिम्मेदारी आपूर्तिकर्ता की होगी।\n\n"""
                "इस नीति को पढ़ने और समझने की पुष्टि करने के लिए नीचे दिए गए बटन पर क्लिक करें।"
            ),
            'read_and_accept_button': '💎 मैंने इसे पढ़ लिया',
            'select_quantity_prompt': "आप कितने जीमेल देंगे? कृपया एक संख्या चुनें:",
            # কনফার্মেশন মেসেজ
            'confirm_quantity_and_link_prompt': "✅ आपने {quantity} जीमेल देने के लिए चुना है।\nप्रत्येक जीमेल के लिए, आपको {price} रुपये मिलेंगे।\nआपका कुल लंबित बैलेंस {amount} रुपये होगा।\n\nअब कृपया अपनी Google Drive फ़ाइल लिंक भेजें:",
            'invalid_link_warning': "❌ अमान्य लिंक प्रारूप। कृपया 'http' या 'https' से शुरू होने वाला एक वैध फ़ाइल लिंक भेजें।",
            'alternative_submission_complete': "✅ आपका फ़ाइल लिंक जमा कर दिया गया है। आपका {amount} रुपये लंबित बैलेंस में जोड़ दिया गया है।", 
            'new_alternative_submission_admin': "🆕 नया वैकल्पिक जीमेल সাবমিশন\nইউজার আইডি: {uid}\nসাবমিশন আইডি: {submission_id}\nজমা করা লিংক: {link}\nराशि: {amount} रुपये\n\nঅনুমোদনের জন্য, /approve {submission_id} কমান্ডটি ব্যবহার করুন।", 
            'invalid_quantity_error': "❌ यह राशि स्वीकार्य नहीं है। कृपया निर्दिष्ट তালিকা থেকে একটি সংখ্যা নির্বাচন করুন।" # নতুন ত্রুটি বার্তা
        }
    }
    return texts.get(lang, texts['English']).get(key, key)


def menu_keyboard(user):
    return ReplyKeyboardMarkup(
        [['♻️ Start Task', '🕵️‍♂️ Details'],
         ['ℹ️ How to Work','💳 Balance', '💵 Withdraw'],
         ['🌍 Language', '☎️ Help & Support']], resize_keyboard=True)

def start_task_keyboard(user):
    return ReplyKeyboardMarkup(
        [['🎀 Gmail'],
         ['🎀 Alternative Gmail'], 
         ['🎀 Facebook'],
         ['🎀 Instagram'],
         [get_text(user, 'back')]], resize_keyboard=True)

async def send_to_all_admins(context: ContextTypes.DEFAULT_TYPE, message: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, message, parse_mode='Markdown')
        except Exception as e:
            print(f"Error sending message to admin {admin_id}: {e}")

# ---
# Google Sheets এর সাথে সংযোগ স্থাপনের ফাংশন
# ---
def get_sheet_instance(sheet_name):
    global sheet_instances
    if sheet_name in sheet_instances:
        return sheet_instances[sheet_name]

    try:
        logging.info(f"Attempting to connect to Google Sheets API for sheet '{sheet_name}'...")
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPES)
        client = gspread.authorize(creds)
        spreadsheet = client.open(GOOGLE_SHEET_NAME)

        try:
            sheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            logging.info(f"Worksheet '{sheet_name}' not found. Creating a new one...")
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="20")

            if sheet_name == USER_INFO_SHEET_NAME:
                header_row = ["User ID", "Username", "First Name", "Balance", "Held Balance", "Is Banned", "Language", "Gmail Submissions", "Facebook Submissions", "Instagram Submissions", "Alternative Gmail Submissions", "Withdraw Requests", "Successful Withdrawals", "Rejected Withdrawals", "Last Updated"]
            elif sheet_name == WITHDRAWAL_LOGS_SHEET_NAME:
                # নতুন হেডার: বিস্তারিত উইথড্র তথ্য শীটে যোগ করা হয়েছে
                header_row = ["Record ID", "Submission Type", "User ID", "Username", "First Name", "Payment Method", "Payment Number", "Requested Amount", "Fee Amount", "Net Amount", "Status", "Timestamp"]
            # পরিবর্তিত কোড: প্রতিটি টাস্কের জন্য আলাদা হেডার
            elif sheet_name == GMAIL_SHEET_NAME:
                header_row = ["Task ID", "User ID", "Username", "First Name", "Gmail First Name", "Gmail Address", "Gmail Password", "Auth Key", "Submission Time"]
            elif sheet_name == FACEBOOK_SHEET_NAME:
                header_row = ["Task ID", "User ID", "Username", "First Name", "Facebook Details", "Submission Time"]
            elif sheet_name == INSTAGRAM_SHEET_NAME:
                header_row = ["Task ID", "User ID", "Username", "First Name", "Instagram Details", "Submission Time"]
            elif sheet_name == ALTERNATIVE_GMAIL_SHEET_NAME:
                header_row = ["Submission ID", "User ID", "Username", "First Name", "Submitted Link", "Gmail Quantity", "Amount (BDT)", "Status", "Timestamp"]
            else:
                header_row = []

            if header_row:
                sheet.append_row(header_row)

        sheet_instances[sheet_name] = sheet
        logging.info(f"Google Sheet '{sheet_name}' connected successfully!")
        return sheet

    except FileNotFoundError:
        logging.error(f"Error: '{CREDENTIALS_FILE}' not found. Make sure it's in the same directory as this script.")
        print(f"Error connecting to Google Sheets API: File not found: '{CREDENTIALS_FILE}'")
        return None
    except Exception as e:
        logging.error(f"Error connecting to Google Sheets API: {e}", exc_info=True)
        print(f"Error connecting to Google Sheets API: {e}")
        return None

# ---
# ডেটা Google Sheet এ যুক্ত করার ফাংশন
# ---
async def append_data_to_google_sheet(context: ContextTypes.DEFAULT_TYPE, sheet_name, data_row, user_id):
    worksheet = get_sheet_instance(sheet_name)
    if worksheet:
        try:
            worksheet.append_row(data_row)
            logging.info(f"Data appended to Google Sheet '{sheet_name}': {data_row}")
            # এই মেসেজটি অপরিবর্তিত রাখা হয়েছে, কারণ এটি শুধু একটি কনফার্মেশন।
            # বিস্তারিত তথ্য নিচে পাঠানো হচ্ছে।
            await send_to_all_admins(context, f"✅ Data successfully logged to Google Sheet '{sheet_name}' for user {user_id}: {data_row[0]} (ID: {user_id})")
            return True
        except Exception as e:
            logging.error(f"Error appending data to Google Sheet '{sheet_name}': {e}", exc_info=True)
            print(f"Error appending data to Google Sheet '{sheet_name}': {e}")
            await send_to_all_admins(context, f"❌ Failed to log data to Google Sheet '{sheet_name}' for user {user_id}: {data_row[0]} - Error: {e}")
            return False
    else:
        logging.warning("Google Sheet worksheet '{sheet_name}' not available. Cannot append data.")
        await send_to_all_admins(context, f"❌ Google Sheet connection failed. Cannot log data for user {user_id}: {data_row[0]}. Please check bot logs.")
        return False

# ---
# ব্যবহারকারীর তথ্য আপডেট করার ফাংশন
# ---
async def update_user_info_sheet(user_id, user_info, context: ContextTypes.DEFAULT_TYPE):
    worksheet = get_sheet_instance(USER_INFO_SHEET_NAME)
    if worksheet:
        try:
            cell = worksheet.find(str(user_id))
            if cell:
                row_index = cell.row
                update_row = [
                    str(user_id),
                    user_info.get('username', 'N/A'),
                    user_info.get('first_name', 'N/A'),
                    user_info.get('balance', 0),
                    user_info.get('held_balance', 0),
                    user_info.get('banned', False),
                    user_info.get('language', 'N/A'),
                    user_info.get('gmail_submissions', 0),
                    user_info.get('facebook_submissions', 0),
                    user_info.get('instagram_submissions', 0),
                    user_info.get('alternative_gmail_submissions', 0),
                    user_info.get('withdraw_requests', 0),
                    user_info.get('successful_withdrawals', 0),
                    user_info.get('rejected_withdrawals', 0),
                    datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                ]
                worksheet.update(f'A{row_index}:O{row_index}', [update_row])
                logging.info(f"User info for {user_id} updated successfully.")
            else:
                new_row = [
                    str(user_id),
                    user_info.get('username', 'N/A'),
                    user_info.get('first_name', 'N/A'),
                    user_info.get('balance', 0),
                    user_info.get('held_balance', 0),
                    user_info.get('banned', False),
                    user_info.get('language', 'N/A'),
                    user_info.get('gmail_submissions', 0),
                    user_info.get('facebook_submissions', 0),
                    user_info.get('instagram_submissions', 0),
                    user_info.get('alternative_gmail_submissions', 0),
                    user_info.get('withdraw_requests', 0),
                    user_info.get('successful_withdrawals', 0),
                    user_info.get('rejected_withdrawals', 0),
                    datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                ]
                worksheet.append_row(new_row)
                logging.info(f"New user info for {user_id} appended successfully.")
            return True
        except Exception as e:
            logging.error(f"Error updating user info sheet for {user_id}: {e}", exc_info=True)
            return False
    else:
        logging.warning("User info sheet not available. Cannot update data.")
        return False

# ---
# বটের মূল কমান্ড এবং হ্যান্ডলার ফাংশন
# ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    if uid not in data['users']:
        data['users'][uid] = {
            'balance':0,
            'held_balance': 0,
            'banned':False,
            'language':'English',
            'gmail_submissions': 0,
            'facebook_submissions': 0,
            'instagram_submissions': 0,
            'alternative_gmail_submissions': 0,
            'withdraw_requests': 0,
            'successful_withdrawals': 0,
            'rejected_withdrawals': 0,
            'username': update.effective_user.username or 'N/A',
            'first_name': update.effective_user.first_name or 'N/A'
        }
        save_data(data)
        await update_user_info_sheet(uid, data['users'][uid], context)
    user = data['users'][uid]
    await update.message.reply_text(get_text(user,'main_menu'), reply_markup=menu_keyboard(user))
    await send_to_all_admins(context, f"✅ New user started: {uid} (Username: @{update.effective_user.username or 'N/A'}, First Name: {update.effective_user.first_name or 'N/A'})")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text
    data = load_data()
    user = data['users'].get(uid)

    if user is None:
        data['users'][uid] = {
            'balance':0,
            'held_balance': 0,
            'banned':False,
            'language':'English',
            'gmail_submissions': 0,
            'facebook_submissions': 0,
            'instagram_submissions': 0,
            'alternative_gmail_submissions': 0,
            'withdraw_requests': 0,
            'successful_withdrawals': 0,
            'rejected_withdrawals': 0,
            'username': update.effective_user.username or 'N/A',
            'first_name': update.effective_user.first_name or 'N/A'
        }
        save_data(data)
        await update_user_info_sheet(uid, data['users'][uid], context)
        user = data['users'][uid]

    if user.get('banned'):
        await update.message.reply_text("🚫 You are banned.")
        return

    current_step = context.user_data.get('step')

    if text in [get_text(user, 'back'), '⬅️ Back','⬅️ ব্যাক','⬅️ वापस']:
        context.user_data.clear()
        await update.message.reply_text(get_text(user,'main_menu'), reply_markup=menu_keyboard(user))
        return

    if text == '♻️ Start Task':
        if 'task' in data['disabled_tasks']:
            await update.message.reply_text(get_text(user, 'all_tasks_disabled'))
            return
        context.user_data['step'] = 'start_task_menu'
        await update.message.reply_text(get_text(user, 'start_task_menu_text'), reply_markup=start_task_keyboard(user))
        return

    elif text == '🕵️‍♂️ Details':
        details_msg = get_text(user, 'details_message').format(
            user.get('gmail_submissions', 0),
            user.get('facebook_submissions', 0),
            user.get('instagram_submissions', 0),
            user.get('alternative_gmail_submissions', 0),
            user.get('withdraw_requests', 0),
            user.get('successful_withdrawals', 0),
            user.get('rejected_withdrawals', 0)
        )
        await update.message.reply_text(details_msg, parse_mode='Markdown')
        context.user_data.clear()
        return

    if text == '🎀 Gmail':
        if 'gmail' in data['disabled_tasks'] or 'task' in data['disabled_tasks']:
            await update.message.reply_text(get_text(user, 'task_disabled'))
            return
        if current_step and current_step not in ['start_task_menu', 'awaiting_gmail_confirm', 'awaiting_gmail_authenticator_key']:
            await update.message.reply_text(get_text(user, 'task_changed'))
            context.user_data.clear()

        first, addr, pwd = generate_gmail()
        context.user_data['task_type'] = 'gmail'
        context.user_data['task_data'] = {'first': first, 'addr': addr, 'pwd': pwd}
        context.user_data['step'] = 'awaiting_gmail_confirm'
        buttons = [
            [InlineKeyboardButton("✅ Confirm", callback_data='confirm_gmail')],
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel_task')]
        ]
        msg = (
            f"New Gmail Info , Get {TASK_REWARDS['gmail']} BDT per one :\n\n"
            f"First name: {first}\n"
            f"Last name: ❌\n"
            f"Address: {addr}\n"
            f"Password: {pwd}\n"
            f"Recovery Email: ❌\n\n"
            f"⚠️ Don't add phone number\n\n"
            f"⚠️Remove the Gmail account from your device after finishing the task"
        )
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))
        return

    elif text == '🎀 Facebook':
        if 'facebook' in data['disabled_tasks'] or 'task' in data['disabled_tasks']:
            await update.message.reply_text(get_text(user, 'task_disabled'))
            return
        if current_step and current_step not in ['start_task_menu', 'awaiting_facebook_credentials']:
            await update.message.reply_text(get_text(user, 'task_changed'))
            context.user_data.clear()

        context.user_data['task_type'] = 'facebook'
        context.user_data['step'] = 'awaiting_facebook_credentials'
        await update.message.reply_text(get_text(user, 'enter_facebook_credentials'), reply_markup=ReplyKeyboardMarkup([[get_text(user,'back')]],resize_keyboard=True))
        return

    elif text == '🎀 Instagram':
        if 'instagram' in data['disabled_tasks'] or 'task' in data['disabled_tasks']:
            await update.message.reply_text(get_text(user, 'task_disabled'))
            return
        if current_step and current_step not in ['start_task_menu', 'awaiting_instagram_credentials']:
            await update.message.reply_text(get_text(user, 'task_changed'))
            context.user_data.clear()

        context.user_data['task_type'] = 'instagram'
        context.user_data['step'] = 'awaiting_instagram_credentials'
        await update.message.reply_text(get_text(user, 'enter_instagram_credentials'), reply_markup=ReplyKeyboardMarkup([[get_text(user,'back')]],resize_keyboard=True))
        return

    # নতুন: Alternative Gmail টাস্কের জন্য মেসেজ হ্যান্ডলার
    elif text == '🎀 Alternative Gmail':
        if 'alternative_gmail' in data['disabled_tasks'] or 'task' in data['disabled_tasks']:
            await update.message.reply_text(get_text(user, 'task_disabled'))
            return
        
        # নতুন: যদি অন্য কোনো টাস্ক চলছে, তাহলে তা বাতিল করা হবে
        if current_step and current_step not in ['start_task_menu']:
            await update.message.reply_text(get_text(user, 'task_changed'))
            context.user_data.clear()


        context.user_data['step'] = 'awaiting_alternative_gmail_read_confirm'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(user, 'read_and_accept_button'), callback_data='read_and_accept_alt_gmail')]])
        await update.message.reply_text(get_text(user, 'alternative_gmail_privacy'), reply_markup=keyboard)
        return

    # এই অংশটি আপডেট করা হয়েছে
    elif current_step == 'awaiting_alternative_gmail_quantity':
        try:
            quantity = int(text)
            if quantity not in ALTERNATIVE_GMAIL_AMOUNTS:
                await update.message.reply_text(get_text(user, 'invalid_quantity_error'))
                return
            
            context.user_data['alternative_gmail_quantity'] = quantity
            context.user_data['step'] = 'awaiting_alternative_gmail_link'
            
            price = data.get('alternative_gmail_price')
            amount = quantity * price
            context.user_data['alternative_gmail_amount'] = amount

            message_text = get_text(user, 'confirm_quantity_and_link_prompt').format(
                quantity=quantity,
                price=price,
                amount=amount
            )
            # ReplyKeyboardMarkup এর মেসেজটি মুছে ফেলার জন্য কোনো মেসেজ না দিয়ে সরাসরি নতুন মেসেজ পাঠানো হচ্ছে
            # এটি মেসেজ এডিটের পরিবর্তে নতুন মেসেজ পাঠাবে
            await update.message.reply_text(message_text, reply_markup=ReplyKeyboardMarkup([[get_text(user, 'back')]], resize_keyboard=True))

        except ValueError:
            await update.message.reply_text(get_text(user, 'invalid_quantity_error'))
            return

    # এই অংশটি আপডেট করা হয়েছে
    elif current_step == 'awaiting_alternative_gmail_link':
        file_link = text
        if file_link.startswith(('http://', 'https://')):
            submission_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            quantity = context.user_data.get('alternative_gmail_quantity', 0)
            amount = context.user_data.get('alternative_gmail_amount', 0)

            user['held_balance'] += amount
            
            data['tasks_pending_review'][submission_id] = {
                'user_id': uid,
                'task_type': 'alternative_gmail',
                'amount': amount,
                'submission_time': datetime.datetime.now().isoformat(),
                'status': 'pending',
                'details': {
                    'link': file_link,
                    'quantity': quantity
                }
            }
            save_data(data)

            await update.message.reply_text(get_text(user, 'alternative_submission_complete').format(amount=amount), reply_markup=menu_keyboard(user))

            submission_row = [
                submission_id,
                str(update.effective_user.id),
                update.effective_user.username or 'N/A',
                update.effective_user.first_name or 'N/A',
                file_link,
                quantity,
                amount,
                "Pending",
                datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            ]
            await append_data_to_google_sheet(context, ALTERNATIVE_GMAIL_SHEET_NAME, submission_row, uid)

            admin_message = get_text(user, 'new_alternative_submission_admin').format(
                uid=uid,
                submission_id=submission_id,
                link=file_link,
                amount=amount
            )
            await send_to_all_admins(context, admin_message)
            
            user['alternative_gmail_submissions'] += quantity
            save_data(data)
            await update_user_info_sheet(uid, user, context)

            context.user_data.clear()
            return
        else:
            await update.message.reply_text(get_text(user, 'invalid_link_warning'))
            return

    # জিমেইল, ফেসবুক, ইনস্টাগ্রামের জন্য নতুন কোড এখানে শুরু
    elif current_step == 'awaiting_gmail_authenticator_key':
        submission_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        task_data = context.user_data.get('task_data')
        authenticator_key = text 
        
        user['held_balance'] += TASK_REWARDS['gmail']
        
        data['tasks_pending_review'][submission_id] = {
            'user_id': uid,
            'task_type': 'gmail',
            'amount': TASK_REWARDS['gmail'],
            'submission_time': datetime.datetime.now().isoformat(),
            'status': 'pending',
            'details': {
                'first_name': task_data['first'],
                'address': task_data['addr'],
                'password': task_data['pwd'],
                'auth_key': authenticator_key
            }
        }
        save_data(data)

        await update.message.reply_text(get_text(user, 'gmail_submission_complete'), reply_markup=menu_keyboard(user))

        submission_row = [
            submission_id, str(update.effective_user.id),
            update.effective_user.username or 'N/A', update.effective_user.first_name or 'N/A',
            task_data['first'], task_data['addr'], task_data['pwd'],
            authenticator_key,
            datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        ]
        await append_data_to_google_sheet(context, GMAIL_SHEET_NAME, submission_row, uid)
        
        # নতুন কোড: এডমিনদের কাছে জিমেইল তথ্য পাঠানো
        admin_message = (
            f"🆕 **New Gmail Submission**\n"
            f"**User ID:** {uid}\n"
            f"**Username:** @{update.effective_user.username or 'N/A'}\n"
            f"**Task ID:** {submission_id}\n\n"
            f"**First Name:** {task_data['first']}\n"
            f"**Email:** {task_data['addr']}\n"
            f"**Password:** {task_data['pwd']}\n"
            f"**Authenticator Key:** {authenticator_key}\n\n"
            f"Amount to be approved: {TASK_REWARDS['gmail']} BDT\n"
            f"To approve, use: `/approve {submission_id}`"
        )
        await send_to_all_admins(context, admin_message)
        
        user['gmail_submissions'] += 1
        save_data(data)
        await update_user_info_sheet(uid, user, context)
        context.user_data.clear()
        return


    elif current_step == 'awaiting_facebook_credentials':
        submission_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        credentials_text = text
        
        user['held_balance'] += TASK_REWARDS['facebook']

        data['tasks_pending_review'][submission_id] = {
            'user_id': uid,
            'task_type': 'facebook',
            'amount': TASK_REWARDS['facebook'],
            'submission_time': datetime.datetime.now().isoformat(),
            'status': 'pending',
            'details': { 'credentials': credentials_text }
        }
        save_data(data)

        await update.message.reply_text(get_text(user, 'facebook_submission_complete'), reply_markup=menu_keyboard(user))

        submission_row = [
            submission_id, str(update.effective_user.id),
            update.effective_user.username or 'N/A', update.effective_user.first_name or 'N/A',
            credentials_text,
            datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        ]
        await append_data_to_google_sheet(context, FACEBOOK_SHEET_NAME, submission_row, uid)
        
        # নতুন কোড: এডমিনদের কাছে ফেসবুক তথ্য পাঠানো
        admin_message = (
            f"🆕 **New Facebook Submission**\n"
            f"**User ID:** {uid}\n"
            f"**Username:** @{update.effective_user.username or 'N/A'}\n"
            f"**Task ID:** {submission_id}\n\n"
            f"**Credentials:**\n{credentials_text}\n\n"
            f"Amount to be approved: {TASK_REWARDS['facebook']} BDT\n"
            f"To approve, use: `/approve {submission_id}`"
        )
        await send_to_all_admins(context, admin_message)
        
        user['facebook_submissions'] += 1
        save_data(data)
        await update_user_info_sheet(uid, user, context)
        context.user_data.clear()
        return


    elif current_step == 'awaiting_instagram_credentials':
        submission_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        credentials_text = text
        
        user['held_balance'] += TASK_REWARDS['instagram']

        data['tasks_pending_review'][submission_id] = {
            'user_id': uid,
            'task_type': 'instagram',
            'amount': TASK_REWARDS['instagram'],
            'submission_time': datetime.datetime.now().isoformat(),
            'status': 'pending',
            'details': { 'credentials': credentials_text }
        }
        save_data(data)

        await update.message.reply_text(get_text(user, 'instagram_submission_complete'), reply_markup=menu_keyboard(user))

        submission_row = [
            submission_id, str(update.effective_user.id),
            update.effective_user.username or 'N/A', update.effective_user.first_name or 'N/A',
            credentials_text,
            datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        ]
        await append_data_to_google_sheet(context, INSTAGRAM_SHEET_NAME, submission_row, uid)

        # নতুন কোড: এডমিনদের কাছে ইনস্টাগ্রাম তথ্য পাঠানো
        admin_message = (
            f"🆕 **New Instagram Submission**\n"
            f"**User ID:** {uid}\n"
            f"**Username:** @{update.effective_user.username or 'N/A'}\n"
            f"**Task ID:** {submission_id}\n\n"
            f"**Credentials:**\n{credentials_text}\n\n"
            f"Amount to be approved: {TASK_REWARDS['instagram']} BDT\n"
            f"To approve, use: `/approve {submission_id}`"
        )
        await send_to_all_admins(context, admin_message)

        user['instagram_submissions'] += 1
        save_data(data)
        await update_user_info_sheet(uid, user, context)
        context.user_data.clear()
        return

    # এখানে, মেসেজ হ্যান্ডলারের জন্য নতুন লজিক যুক্ত করা হবে
    # জিমেইল, ফেসবুক এবং ইনস্টাগ্রামের জন্য ইউজার ইনপুট হ্যান্ডলিং
    # এখানে ইউজার ইনপুট যা আছে, তাই গ্রহণ করার লজিক যুক্ত করতে হবে।
    # ফেসবুক এবং ইনস্টাগ্রামের ক্ষেত্রে কোনো নোটিফিকেশন বা প্রশ্ন থাকবে না, ইউজার সরাসরি তথ্য দেবে।

    # অন্যান্য হ্যান্ডলারগুলো
    elif text == '💳 Balance':
        await update.message.reply_text(get_text(user, 'balance').format(user['balance'], user.get('held_balance', 0)))
        context.user_data.clear()
        return

    elif text == '💵 Withdraw':
        context.user_data['step'] = 'choose_method'
        await update.message.reply_text(get_text(user,'select_method'), reply_markup=ReplyKeyboardMarkup([['Bkash','Nagad'],[get_text(user,'back')]],resize_keyboard=True))
        return

    elif text in ['Bkash','Nagad'] and current_step == 'choose_method':
        if not data['payment_methods_status'].get(text, False):
            await update.message.reply_text(get_text(user, 'payment_method_disabled'))
            return

        context.user_data['method'] = text
        context.user_data['step'] = 'number'
        await update.message.reply_text(get_text(user,'enter_number'), reply_markup=ReplyKeyboardMarkup([[get_text(user,'back')]],resize_keyboard=True))
        return

    elif current_step == 'number' and text.isdigit():
        context.user_data['number'] = text
        context.user_data['step'] = 'amount'
        await update.message.reply_text(get_text(user,'enter_amount'), reply_markup=ReplyKeyboardMarkup([[get_text(user,'back')]],resize_keyboard=True))
        return

    elif current_step == 'amount' and text.isdigit():
        requested_amount = int(text)
        
        # 1. সর্বনিম্ন উইথড্র চেক করা
        if requested_amount < MIN_WITHDRAW_AMOUNT:
            await update.message.reply_text(get_text(user, 'min_withdraw_error'))
            return
        
        # 2. অপর্যাপ্ত ব্যালেন্স চেক করা (পুরো Requested Amount এর জন্য)
        if requested_amount > user['balance']:
            await update.message.reply_text(get_text(user, 'insufficient_balance'))
            return
        
        # 3. ফি গণনা করা (পরিবর্তন: ফিক্সড ফি ৬ টাকা)
        fee_amount = WITHDRAWAL_FIXED_FEE
        net_amount = requested_amount - fee_amount

        # 4. ইউজার ডেটা সংরক্ষণ
        context.user_data['requested_amount'] = requested_amount
        context.user_data['fee_amount'] = fee_amount
        context.user_data['net_amount'] = net_amount
        
        # 5. নিশ্চিতকরণ মেসেজ তৈরি ও প্রেরণ
        buttons = [[InlineKeyboardButton("✅ Confirm", callback_data='withdraw_confirm')],
                   [InlineKeyboardButton("❌ Cancel", callback_data='withdraw_cancel')]]
        
        # মেসেজ ফরমেটিং এ পরিবর্তন
        confirm_message = get_text(user, 'withdraw_confirm_message').format(
            method=context.user_data['method'],
            number=context.user_data['number'],
            requested_amount=requested_amount,
            fee_amount=fee_amount, # ফিক্সড ফি
            net_amount=net_amount # নেট এমাউন্ট দেখানো হচ্ছে
        )
        
        await update.message.reply_text(confirm_message, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
        return

    elif text == '🌍 Language':
        context.user_data['step'] = 'language'
        await update.message.reply_text("Select language:", reply_markup=ReplyKeyboardMarkup([['English','Bangla','Hindi'],[get_text(user,'back')]],resize_keyboard=True))
        return

    elif current_step == 'language' and text in ['English','Bangla','Hindi']:
        user['language']=text
        save_data(data)
        await update_user_info_sheet(uid, user, context)
        context.user_data.clear()
        await update.message.reply_text(get_text(user,'language_set'), reply_markup=menu_keyboard(user))
        return

    elif text == '☎️ Help & Support':
        await update.message.reply_text("For help and support, please contact an administrator.\n admin 1 = @Shams_07s")
        context.user_data.clear()
        return

    elif text == 'ℹ️ How to Work':
        await update.message.reply_text("https://t.me/Credix_family_official/10")
        context.user_data.clear()
        return

    if not update.message.text.startswith('/'):
        await update.message.reply_text(get_text(user,'unknown'))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = load_data()
    user = data['users'].get(uid)

    if user is None:
        await context.bot.send_message(uid, "Your session might have expired. Please use /start to begin again.", reply_markup=menu_keyboard({'language':'English'}))
        return

    if query.data=='confirm_gmail':
        task_data = context.user_data.get('task_data')
        if task_data and context.user_data.get('task_type') == 'gmail':
            context.user_data['step'] = 'awaiting_gmail_authenticator_key'
            await query.edit_message_text("ㅤ")
            await context.bot.send_message(
                chat_id=uid,
                text=get_text(user, 'enter_authenticator_key'),
                reply_markup=ReplyKeyboardMarkup([[get_text(user,'back')]],resize_keyboard=True)
            )
        else:
            await query.edit_message_text("❌ Error: Task info not found or task type mismatch. Please try again from Main Menu.")
            context.user_data.clear()
            await context.bot.send_message(uid, get_text(user,'main_menu'), reply_markup=menu_keyboard(user))

    elif query.data=='cancel_task':
        await query.edit_message_text("❌ Task cancelled.")
        context.user_data.clear()
        await context.bot.send_message(uid, get_text(user,'main_menu'), reply_markup=menu_keyboard(user))

    # নতুন: Alternative Gmail এর জন্য বাটন হ্যান্ডলার
    elif query.data == 'read_and_accept_alt_gmail':
        context.user_data['step'] = 'awaiting_alternative_gmail_quantity'
        keyboard = [
            [InlineKeyboardButton(str(amount), callback_data=f'alt_gmail_quantity_{amount}') for amount in ALTERNATIVE_GMAIL_AMOUNTS[:5]],
            [InlineKeyboardButton(str(amount), callback_data=f'alt_gmail_quantity_{amount}') for amount in ALTERNATIVE_GMAIL_AMOUNTS[5:]],
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel_task')]
        ]
        # ভাষার সমস্যা সমাধান করা হয়েছে
        await query.edit_message_text(get_text(user, 'select_quantity_prompt'), reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # নতুন: অল্টারনেটিভ জিমেইল কোয়ান্টিটি বাটন হ্যান্ডলার
    elif query.data.startswith('alt_gmail_quantity_'):
        
        # মেসেজ এবং কীবোর্ড দুটোই অদৃশ্য করার জন্য কোডটি পরিবর্তন করা হয়েছে
        await query.message.edit_text(text="ㅤ", reply_markup=None) # ইনলাইন কীবোর্ড অদৃশ্য করা

        quantity = int(query.data.split('_')[-1])
        context.user_data['alternative_gmail_quantity'] = quantity
        context.user_data['step'] = 'awaiting_alternative_gmail_link'
        
        price = data.get('alternative_gmail_price')
        amount = quantity * price
        context.user_data['alternative_gmail_amount'] = amount
        
        message_text = get_text(user, 'confirm_quantity_and_link_prompt').format(
            quantity=quantity,
            price=price,
            amount=amount
        )
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=message_text,
            reply_markup=ReplyKeyboardMarkup([[get_text(user, 'back')]], resize_keyboard=True)
        )
        await query.answer()

    elif query.data=='withdraw_confirm':
        w = context.user_data
        requested_amount = int(w.get('requested_amount', 0))
        fee_amount = int(w.get('fee_amount', 0))
        net_amount = int(w.get('net_amount', 0))

        # রি-চেক: ফিক্সড ফি হওয়ায় নেট অ্যামাউন্ট চেক করার দরকার নেই, শুধু ব্যালেন্স চেক করলেই হবে।
        if requested_amount > user['balance']:
            await query.edit_message_text(get_text(user, 'insufficient_balance'))
            context.user_data.clear()
            return

        user['balance'] -= requested_amount # সম্পূর্ণ requested_amount কাটা হলো
        user['withdraw_requests'] += 1
        save_data(data)

        await query.edit_message_text(get_text(user, 'withdraw_success_message'))

        record_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        # Google Sheet এ বিস্তারিত লগিং
        withdraw_row = [
            record_id,
            "Withdraw Request",
            str(update.effective_user.id),
            query.from_user.username or 'N/A',
            query.from_user.first_name or 'N/A',
            w.get('method', 'N/A'),
            w.get('number', 'N/A'),
            str(requested_amount), # Requested Amount
            str(fee_amount),      # Fee Amount (Fixed 6 Tk)
            str(net_amount),      # Net Amount
            "Pending",
            datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        ]
        await append_data_to_google_sheet(context, WITHDRAWAL_LOGS_SHEET_NAME, withdraw_row, uid)

        await update_user_info_sheet(uid, user, context)

        # এডমিন মেসেজে বিস্তারিত তথ্য
        admin_message = (
            f"💵 Withdraw request (Pending Payout):\n"
            f"Record ID: {record_id}\n"
            f"User ID: {uid} (Username: @{query.from_user.username or 'N/A'}, First Name: {query.from_user.first_name or 'N/A'})\n"
            f"Method: {w.get('method', 'N/A')}\n"
            f"Number: {w.get('number', 'N/A')}\n"
            f"**Requested Amount:** {requested_amount} Tk\n"
            f"**Fee (Fixed):** {fee_amount} Tk\n"
            f"**Net Amount to Pay:** {net_amount} Tk\n"
            f"User's new balance: {user['balance']} Tk"
        )
        await send_to_all_admins(context, admin_message)

        context.user_data.clear()

    elif query.data=='withdraw_cancel':
        await query.edit_message_text("❌ Withdraw cancelled.")
        context.user_data.clear()


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_admin(uid):
        await update.message.reply_text("❌ Not authorized.")
        return

    cmd_parts = update.message.text.split(maxsplit=1)
    command = cmd_parts[0]
    args = cmd_parts[1] if len(cmd_parts) > 1 else ""
    data = load_data()

    if command=='/show_users':
        msg='All users:\n'
        for u in data['users']:
            user_info = data['users'][u]
            msg+=f"ID:{u} Bal:{user_info.get('balance', 0)} (Held:{user_info.get('held_balance', 0)}) Banned:{user_info.get('banned', False)} Lang:{user_info.get('language', 'N/A')}\n"
            msg+=f"  Gmail Submissions: {user_info.get('gmail_submissions', 0)}\n"
            msg+=f"  Alternative Gmail Submissions: {user_info.get('alternative_gmail_submissions', 0)}\n"
            msg+=f"  Facebook Submissions: {user_info.get('facebook_submissions', 0)}\n"
            msg+=f"  Instagram Submissions: {user_info.get('instagram_submissions', 0)}\n"
            msg+=f"  Withdraw Requests: {user_info.get('withdraw_requests', 0)}\n"
            msg+=f"  Successful Withdrawals: {user_info.get('successful_withdrawals', 0)}\n"
            msg+=f"  Rejected Withdrawals: {user_info.get('rejected_withdrawals', 0)}\n"
        await update.message.reply_text(msg)

    elif command == '/see_details' and args:
        target_uid = args.split()[0]
        if target_uid in data['users']:
            user_info = data['users'][target_uid]

            msg = (
                f"🕵️‍♂️ **User Details for {target_uid}:**\n"
                "-----------------------------------\n"
                f"👤 Status: {'Banned' if user_info.get('banned', False) else 'Active'}\n"
                f"🌍 Language: {user_info.get('language', 'N/A')}\n"
                "-----------------------------------\n"
                f"💰 Main Balance: {user_info.get('balance', 0)} Tk\n"
                f"⏳ Pending Balance: {user_info.get('held_balance', 0)} Tk\n"
                "-----------------------------------\n"
                f"📧 Gmail Submissions: {user_info.get('gmail_submissions', 0)}\n"
                f"📝 Alternative Gmail Submissions: {user_info.get('alternative_gmail_submissions', 0)}\n"
                f"🔵 Facebook Submissions: {user_info.get('facebook_submissions', 0)}\n"
                f"📸 ইনস্টাগ্রাম জমা: {user_info.get('instagram_submissions', 0)}\n"
                "-----------------------------------\n"
                f"💵 Total Withdrawal Requests: {user_info.get('withdraw_requests', 0)}\n"
                f"✅ Successful Withdrawals: {user_info.get('successful_withdrawals', 0)}\n"
                f"❌ Rejected Withdrawals: {user_info.get('rejected_withdrawals', 0)}\n"
                "-----------------------------------"
            )
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ User not found.")

    elif command == '/see_details' and not args:
        await update.message.reply_text("❗ Usage: /see_details <user_id>")

    elif command=='/ban' and args:
        user_to_ban = args.split()[0]
        if user_to_ban in data['users']:
            data['users'][user_to_ban]['banned']=True
            save_data(data)
            await context.bot.send_message(user_to_ban, "🚫 You are banned.")
            await update.message.reply_text(f"User {user_to_ban} banned.")
            await update_user_info_sheet(user_to_ban, data['users'][user_to_ban], context)
        else:
            await update.message.reply_text("User not found.")

    elif command=='/unban' and args:
        user_to_unban = args.split()[0]
        if user_to_unban in data['users']:
            data['users'][user_to_unban]['banned']=False
            save_data(data)
            await context.bot.send_message(user_to_unban, "✅ Ban removed!")
            await update.message.reply_text(f"User {user_to_unban} unbanned.")
            await update_user_info_sheet(user_to_unban, data['users'][user_to_unban], context)
        else:
            await update.message.reply_text("User not found.")

    # নতুন: পেন্ডিং ব্যালেন্স যোগ করার কমান্ড
    elif command == '/add_pending' and len(args.split()) > 1:
        target_uid = args.split()[0]
        try:
            amount = int(args.split()[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return

        if target_uid in data['users']:
            data['users'][target_uid]['held_balance'] += amount
            save_data(data)
            await context.bot.send_message(target_uid, f"⏳ Your pending balance has been increased by {amount} Tk.\nYour new pending balance: {data['users'][target_uid]['held_balance']} Tk")
            await update.message.reply_text(f"✅ {amount} Tk added to pending balance for user {target_uid}.")
            await update_user_info_sheet(target_uid, data['users'][target_uid], context)
        else:
            await update.message.reply_text("❌ User not found.")

    # নতুন: পেন্ডিং ব্যালেন্স কেটে নেওয়ার কমান্ড
    elif command == '/deduct_pending' and len(args.split()) > 1:
        target_uid = args.split()[0]
        try:
            amount = int(args.split()[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return

        if target_uid in data['users']:
            user_data = data['users'][target_uid]
            if user_data['held_balance'] >= amount:
                user_data['held_balance'] -= amount
                save_data(data)
                await context.bot.send_message(target_uid, f"⚠️ {amount} Tk has been deducted from your pending balance.\nYour new pending balance: {user_data['held_balance']} Tk")
                await update.message.reply_text(f"✅ {amount} Tk deducted from pending balance for user {target_uid}.")
                await update_user_info_sheet(target_uid, user_data, context)
            else:
                await update.message.reply_text("❌ Insufficient pending balance.")
        else:
            await update.message.reply_text("❌ User not found.")
            
    # নতুন: মেইন ব্যালেন্স যোগ করার কমান্ড
    elif command == '/add_main' and len(args.split()) > 1:
        target_uid = args.split()[0]
        try:
            amount = int(args.split()[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return

        if target_uid in data['users']:
            data['users'][target_uid]['balance'] += amount
            save_data(data)
            await context.bot.send_message(target_uid, f"✅ Your main balance has been increased by {amount} Tk.\nYour new main balance: {data['users'][target_uid]['balance']} Tk")
            await update.message.reply_text(f"✅ {amount} Tk added to main balance for user {target_uid}.")
            await update_user_info_sheet(target_uid, data['users'][target_uid], context)
        else:
            await update.message.reply_text("❌ User not found.")

    # নতুন: মেইন ব্যালেন্স কেটে নেওয়ার কমান্ড
    elif command == '/deduct_main' and len(args.split()) > 1:
        target_uid = args.split()[0]
        try:
            amount = int(args.split()[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return

        if target_uid in data['users']:
            user_data = data['users'][target_uid]
            if user_data['balance'] >= amount:
                user_data['balance'] -= amount
                save_data(data)
                await context.bot.send_message(target_uid, f"⚠️ {amount} Tk has been deducted from your main balance.\nYour new main balance: {user_data['balance']} Tk")
                await update.message.reply_text(f"✅ {amount} Tk deducted from main balance for user {target_uid}.")
                await update_user_info_sheet(target_uid, user_data, context)
            else:
                await update.message.reply_text("❌ Insufficient main balance.")
        else:
            await update.message.reply_text("❌ User not found.")

    elif command=='/approve' and args:
        task_id = args.split()[0]
        if task_id in data['tasks_pending_review']:
            task = data['tasks_pending_review'][task_id]
            target_uid = task['user_id']
            amount = task['amount']

            if target_uid in data['users'] and task['status'] == 'pending':
                user_to_update = data['users'][target_uid]
                user_to_update['held_balance'] -= amount
                user_to_update['balance'] += amount
                task['status'] = 'approved'
                save_data(data)

                user = data['users'][target_uid]
                approved_message = get_text(user, 'task_approved_notification').format(
                    task_type=task['task_type'],
                    task_id=task_id,
                    amount=amount
                )
                await context.bot.send_message(target_uid, approved_message)

                await update.message.reply_text(f"✅ Task '{task_id}' approved. {amount} Tk moved from held to main balance for user {target_uid}.")
                await update_user_info_sheet(target_uid, user_to_update, context)
            else:
                await update.message.reply_text("❌ Task already processed or user not found.")
        else:
            await update.message.reply_text("❌ Task ID not found in pending list.")

    elif command=='/reject' and args:
        task_id = args.split()[0]
        if task_id in data['tasks_pending_review']:
            task = data['tasks_pending_review'][task_id]
            target_uid = task['user_id']
            amount = task['amount']

            if target_uid in data['users'] and task['status'] == 'pending':
                user_to_update = data['users'][target_uid]
                user_to_update['held_balance'] -= amount
                task['status'] = 'rejected'
                save_data(data)

                user = data['users'][target_uid]
                final_message = get_text(user, 'task_rejected_notification').format(task_id=task_id, amount=amount)

                details_string = ""
                # এই অংশটি পরিবর্তন করা হলো
                if task['task_type'] == 'gmail':
                    details_string = get_text(user, 'rejected_gmail_full_details').format(
                        address=task['details'].get('address', 'N/A'),
                        password=task['details'].get('password', 'N/A')
                    )
                elif task['task_type'] in ['facebook', 'instagram']:
                    # এখানে সরাসরি ইউজার ইনপুটটি ব্যবহার করা হলো
                    details_string = task['details'].get('credentials', 'N/A')
                
                # আপনার কোড অনুযায়ী, অল্টারনেটিভ জিমেইল এর জন্য কোনো রিজেকশন লজিক নেই
                # যদি আপনি অল্টারনেটিভ জিমেইল এর জন্য রিজেকশন যোগ করতে চান,
                # তাহলে এখানে একটি নতুন elif ব্লক যোগ করতে পারেন।
                # elif task['task_type'] == 'alternative_gmail':
                #    details_string = f"Submitted Link: {task['details'].get('link', 'N/A')}"

                if details_string:
                    final_message += f"\n\n**Details:**\n{details_string}"

                await context.bot.send_message(target_uid, final_message, parse_mode='Markdown')

                await update.message.reply_text(f"❌ Task '{task_id}' rejected. {amount} Tk removed from user {target_uid}'s held balance.")
                await update_user_info_sheet(target_uid, user_to_update, context)
            else:
                await update.message.reply_text("❌ Task already processed or user not found.")
        else:
            await update.message.reply_text("❌ Task ID not found in pending list.")


    elif command=='/withdraw' and len(args.split())>1:
        target_uid = args.split()[0]
        try:
            amount = int(args.split()[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return

        if target_uid in data['users']:
            data['users'][target_uid]['successful_withdrawals'] += 1
            save_data(data)

            record_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

            await context.bot.send_message(target_uid, f"💸 Your withdraw of {amount} Tk processed.")
            await update.message.reply_text(f"Withdraw of {amount} Tk notified to user {target_uid}.")

            # এখানে Admin Processed লগেও বিস্তারিত তথ্য যোগ করা হলো
            success_withdraw_row = [
                record_id,
                "Successful Withdrawal",
                target_uid,
                "N/A", "N/A",
                "Admin Processed",
                "Admin Processed",
                str(amount), # Requested Amount
                "0",         # Fee Amount (zero for admin processing, assuming no fee deduction here)
                str(amount), # Net Amount
                "Successful",
                datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            ]
            await append_data_to_google_sheet(context, WITHDRAWAL_LOGS_SHEET_NAME, success_withdraw_row, target_uid)
            await update_user_info_sheet(target_uid, data['users'][target_uid], context)

        else:
            await update.message.reply_text("User not found.")

    elif command=='/reject_withdraw' and len(args.split())>1:
        target_uid = args.split()[0]
        try:
            amount = int(args.split()[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return

        if target_uid in data['users']:
            data['users'][target_uid]['rejected_withdrawals'] += 1
            save_data(data)

            record_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

            await context.bot.send_message(target_uid, f"❌ Your withdraw request for {amount} Tk has been rejected.")
            await update.message.reply_text(f"Withdrawal of {amount} Tk rejected for user {target_uid}.")
            
            # এখানে Rejected Withdrawal লগেও বিস্তারিত তথ্য যোগ করা হলো
            rejected_withdraw_row = [
                record_id,
                "Rejected Withdrawal",
                target_uid,
                "N/A", "N/A",
                "Admin Rejected",
                "Admin Rejected",
                str(amount), # Requested Amount
                "0",         # Fee Amount (zero for rejection)
                str(amount), # Net Amount (assuming the original requested amount is logged for reference)
                "Rejected",
                datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            ]
            await append_data_to_google_sheet(context, WITHDRAWAL_LOGS_SHEET_NAME, rejected_withdraw_row, target_uid)
            await update_user_info_sheet(target_uid, data['users'][target_uid], context)

        else:
            await update.message.reply_text("User not found.")

    elif command=='/message' and args:
        message_to_send = args
        success_count = 0
        fail_count = 0
        data = load_data()
        for user_id in data['users'].keys():
            try:
                await context.bot.send_message(user_id, message_to_send)
                success_count += 1
            except Exception as e:
                print(f"Failed to send message to user {user_id}: {e}")
                fail_count += 1
        await update.message.reply_text(f"✅ Message sent to {success_count} users.\n❌ Failed to send to {fail_count} users.")
    elif command=='/message' and not args:
        await update.message.reply_text("❗ Usage: /message <your message here>")

    elif command == '/sendto':
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text("❗ Usage: /sendto <user_id> <message>")
            return
        target_user_id = parts[0]
        message_to_user = parts[1]
        if target_user_id in data['users']:
            try:
                await context.bot.send_message(target_user_id, message_to_user)
                await update.message.reply_text(f"✅ Message sent to user {target_user_id}.")
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to send message to user {target_user_id}. Error: {e}")
        else:
            await update.message.reply_text("❌ User not found in bot's data.")

    elif command == '/stop' and args:
        target_task = args.lower()
        valid_tasks = ['gmail', 'facebook', 'instagram', 'alternative_gmail', 'task']
        if target_task in valid_tasks:
            if target_task == 'task':
                data['disabled_tasks'] = ['gmail', 'facebook', 'instagram', 'alternative_gmail', 'task']
                await update.message.reply_text("✅ All tasks (Gmail, Alternative Gmail, Facebook, Instagram) have been stopped.")
            elif target_task not in data['disabled_tasks']:
                data['disabled_tasks'].append(target_task)
                await update.message.reply_text(f"✅ Task '{target_task}' has been stopped.")
            else:
                await update.message.reply_text(f"❗ Task '{target_task}' is already stopped.")
            save_data(data)
        else:
            await update.message.reply_text("❌ Invalid task. Use 'gmail', 'alternative_gmail', 'facebook', 'instagram', or 'task'.")
    elif command == '/stop' and not args:
        await update.message.reply_text("❗ Usage: /stop <gmail|alternative_gmail|facebook|instagram|task>")

    elif command == '/start_task' and args:
        target_task = args.lower()
        valid_tasks = ['gmail', 'facebook', 'instagram', 'alternative_gmail', 'task']
        if target_task in valid_tasks:
            if target_task == 'task':
                data['disabled_tasks'] = []
                await update.message.reply_text("✅ All tasks (Gmail, Alternative Gmail, Facebook, Instagram) have been started.")
            elif target_task in data['disabled_tasks']:
                data['disabled_tasks'].remove(target_task)
                await update.message.reply_text(f"✅ Task '{target_task}' has been started.")
            else:
                await update.message.reply_text(f"❗ Task '{target_task}' is already running or was never stopped.")
            save_data(data)
        else:
            await update.message.reply_text("❌ Invalid task. Use 'gmail', 'alternative_gmail', 'facebook', 'instagram', or 'task'.")
    elif command == '/start_task' and not args:
        await update.message.reply_text("❗ Usage: /start_task <gmail|alternative_gmail|facebook|instagram|task>")

    elif command == '/disable_payment_method' and args:
        method = args.title()
        if method in data['payment_methods_status']:
            data['payment_methods_status'][method] = False
            save_data(data)
            await update.message.reply_text(f"✅ Payment method '{method}' has been disabled.")
        else:
            await update.message.reply_text(f"❌ Invalid payment method. Available methods: {', '.join(data['payment_methods_status'].keys())}")
    elif command == '/disable_payment_method' and not args:
        await update.message.reply_text("❗ Usage: /disable_payment_method <Bkash|Nagad>")

    elif command == '/enable_payment_method' and args:
        method = args.title()
        if method in data['payment_methods_status']:
            data['payment_methods_status'][method] = True
            save_data(data)
            await update.message.reply_text(f"✅ Payment method '{method}' has been enabled.")
        else:
            await update.message.reply_text(f"❌ Invalid payment method. Available methods: {', '.join(data['payment_methods_status'].keys())}")
    elif command == '/enable_payment_method' and not args:
        await update.message.reply_text("❗ Usage: /enable_payment_method <Bkash|Nagad>")

    elif command == '/show_payment_methods':
        msg = "Current Payment Method Status:\n"
        for method, status in data['payment_methods_status'].items():
            msg += f"- {method}: {'Enabled' if status else 'Disabled'}\n"
        await update.message.reply_text(msg)
        
    # নতুন: অল্টারনেটিভ জিমেইল এর মূল্য আপডেট করার কমান্ড
    elif command == '/update_alternative_price' and args:
        try:
            new_price = int(args.split()[0])
            if new_price > 0:
                data['alternative_gmail_price'] = new_price
                save_data(data)
                await update.message.reply_text(f"✅ অল্টারনেটিভ জিমেইল এর মূল্য সফলভাবে {new_price} টাকা হিসেবে আপডেট করা হয়েছে।")
            else:
                await update.message.reply_text("❌ মূল্য অবশ্যই একটি ধনাত্মক সংখ্যা হতে হবে।")
        except ValueError:
            await update.message.reply_text("❌ ভুল ইনপুট। অনুগ্রহ করে একটি সংখ্যা লিখুন।")
    elif command == '/update_alternative_price' and not args:
        await update.message.reply_text("❗ ব্যবহার: /update_alternative_price <নতুন_মূল্য>")


# ---
# অ্যাপ্লিকেশন বিল্ডার এবং হ্যান্ডলার রেজিস্ট্রেশন
# ---
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler(["show_users","see_details","ban","unban","add_balance","deduct_balance","add_pending","deduct_pending","add_main","deduct_main","withdraw", "reject_withdraw", "message", "stop", "start_task", "disable_payment_method", "enable_payment_method", "show_payment_methods", "sendto", "approve", "reject", "update_alternative_price"], admin_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(button_handler))


