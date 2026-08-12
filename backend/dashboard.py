import json
import os
from http.server import SimpleHTTPRequestHandler, HTTPServer
import urllib.parse

class DashboardHandler(SimpleHTTPRequestHandler):
    def get_file_path(self):
        return os.path.join(os.path.dirname(__file__), "src", "escalations.json")

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            file_path = self.get_file_path()
            escalations = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r") as f:
                        escalations = json.load(f)
                except Exception:
                    pass
                    
            html = """
            <html>
            <head>
                <title>Human Help Requests Dashboard</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 2rem; background: #f4f4f5; color: #333; }
                    .header { display: flex; justify-content: space-between; align-items: center; }
                    h1 { color: #111; }
                    .card { background: white; padding: 1.5rem; margin-bottom: 1rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); line-height: 1.5; }
                    .high { border-left: 5px solid #ef4444; }
                    .medium { border-left: 5px solid #f97316; }
                    .low { border-left: 5px solid #22c55e; }
                    .open { color: #d97706; font-weight: bold; background: #fef3c7; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; }
                    p { margin: 0.5rem 0; }
                    small { color: #666; }
                    .btn-clear { background: #ef4444; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; font-size: 1rem; }
                    .btn-clear:hover { background: #dc2626; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Open Escalations</h1>
                    <form method="POST" action="/clear" style="margin: 0;">
                        <button type="submit" class="btn-clear">Clear All Requests</button>
                    </form>
                </div>
            """
            
            if not escalations:
                html += "<p>No open requests right now.</p>"
            else:
                for req in reversed(escalations):
                    urgency_class = str(req.get("urgency", "low")).lower()
                    if urgency_class not in ["high", "medium", "low"]:
                        urgency_class = "medium"
                    html += f"""
                    <div class="card {urgency_class}">
                        <h3 style="margin-top: 0;">Request ID: {req.get("id", "Unknown")} <span style="float:right;" class="open">{req.get("status", "OPEN")}</span></h3>
                        <p><strong>Caller:</strong> {req.get("who_needs_help", "Unknown")} | <strong>Language:</strong> {req.get("language", "Unknown")}</p>
                        <p><strong>Issue:</strong> {req.get("what_happened", "N/A")}</p>
                        <p><strong>Agent Checked:</strong> {req.get("what_checked", "N/A")}</p>
                        <p><strong>Follow-up Preference:</strong> {req.get("follow_up_method", "N/A")} | <strong>Urgency:</strong> {req.get("urgency", "N/A")}</p>
                        <small>Created at: {req.get("timestamp", "Unknown")}</small>
                    </div>
                    """
                    
            html += """
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/clear':
            file_path = self.get_file_path()
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error removing file: {e}")
            
            # Redirect back to home
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
        else:
            self.send_error(404)

if __name__ == "__main__":
    port = 8000
    server_address = ('', port)
    httpd = HTTPServer(server_address, DashboardHandler)
    print(f"Dashboard is live! View your open requests at: http://localhost:{port}")
    httpd.serve_forever()
