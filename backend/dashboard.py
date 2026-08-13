import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
import urllib.parse

# Add src to path so we can import db
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
try:
    from db import get_call_stats
except ImportError:
    # Fallback if db not found
    def get_call_stats():
        return {"total": 0, "successful": 0, "failed": 0}

class DashboardHandler(SimpleHTTPRequestHandler):
    def get_file_path(self):
        return os.path.join(os.path.dirname(__file__), "src", "escalations.json")

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            # Fetch call stats
            stats = get_call_stats()
            
            file_path = self.get_file_path()
            escalations = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r") as f:
                        escalations = json.load(f)
                except Exception:
                    pass
                    
            html = f"""
            <html>
            <head>
                <title>Human Help Requests Dashboard</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 2rem; background: #f4f4f5; color: #333; }}
                    .header {{ display: flex; justify-content: space-between; align-items: center; }}
                    h1 {{ color: #111; }}
                    .stats-container {{ display: flex; gap: 1rem; margin-bottom: 2rem; }}
                    .stat-card {{ background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; text-align: center; }}
                    .stat-card h2 {{ margin: 0; font-size: 2.5rem; color: #2563eb; }}
                    .stat-card.success h2 {{ color: #16a34a; }}
                    .stat-card.failed h2 {{ color: #dc2626; }}
                    .stat-card p {{ margin: 0.5rem 0 0; color: #666; font-weight: bold; text-transform: uppercase; font-size: 0.9rem; }}
                    .card {{ background: white; padding: 1.5rem; margin-bottom: 1rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); line-height: 1.5; }}
                    .high {{ border-left: 5px solid #ef4444; }}
                    .medium {{ border-left: 5px solid #f97316; }}
                    .low {{ border-left: 5px solid #22c55e; }}
                    .open {{ color: #d97706; font-weight: bold; background: #fef3c7; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; }}
                    p {{ margin: 0.5rem 0; }}
                    small {{ color: #666; }}
                    .btn-clear {{ background: #ef4444; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; font-size: 1rem; }}
                    .btn-clear:hover {{ background: #dc2626; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Call Analytics Dashboard</h1>
                </div>
                
                <div class="stats-container">
                    <div class="stat-card">
                        <h2>{stats['total']}</h2>
                        <p>Total Calls</p>
                    </div>
                    <div class="stat-card success">
                        <h2>{stats['successful']}</h2>
                        <p>Successful Calls</p>
                    </div>
                    <div class="stat-card failed">
                        <h2>{stats['failed']}</h2>
                        <p>Failed Calls</p>
                    </div>
                </div>

                <div class="header">
                    <h2>Open Escalations</h2>
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
