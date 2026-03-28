#!/usr/bin/env python3
"""
server.py — mnemo local server
Serves room.html and bridges browser to Claude API.
Run: python3 server.py
Then open: http://localhost:8765
"""

import os
import json
import anthropic
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8765
MODEL = "claude-sonnet-4-20250514"

class MnemoHandler(SimpleHTTPRequestHandler):

    def do_POST(self):
        if self.path == '/api/chat':
            length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(length))

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                self.send_error(500, "ANTHROPIC_API_KEY not set")
                return

            try:
                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=1024,
                    system=body.get('system','You are Claude within mnemo.'),
                    messages=body.get('messages',[])
                )
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Access-Control-Allow-Origin','*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'content': [{'text': response.content[0].text}]
                }).encode())

            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','POST,GET,OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Silent

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"\n\033[95mmnemo\033[0m  room server")
    print(f"\033[90mopen → http://localhost:{PORT}/room.html\033[0m")
    print(f"\033[90mstop → ctrl+c\033[0m\n")
    HTTPServer(('localhost', PORT), MnemoHandler).serve_forever()
