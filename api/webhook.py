# api/webhook.py

import json
from http.server import BaseHTTPRequestHandler
from telegram import Update
from bot_core import app 

class handler(BaseHTTPRequestHandler):
    
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            update_data = json.loads(post_data)
            update = Update.de_json(update_data, app.bot)
            
            app.update_queue.put(update)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
            
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("Telegram Bot Webhook is running.".encode('utf-8'))
