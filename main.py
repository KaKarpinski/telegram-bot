import os
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from bot.bot_init import initialize_bot

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.getenv("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

def main():
    Thread(target=run_health_server, daemon=True).start()

    initialize_bot()


if __name__ == "__main__":
    main()