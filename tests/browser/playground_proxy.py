import http.server, urllib.request, sys
sys.path.insert(0,'/sessions/bold-eager-knuth/mnt/PTPGE/mcp-server')
from ptpge_mcp.playground import PLAYGROUND_HTML
H=PLAYGROUND_HTML.encode()
class P(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(H)
    def do_POST(self):
        n=int(self.headers.get('Content-Length',0)); body=self.rfile.read(n)
        req=urllib.request.Request('https://open.mcp.ptpge.org/mcp', data=body, headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}, method='POST')
        with urllib.request.urlopen(req, timeout=60) as r:
            data=r.read(); self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(data)
http.server.ThreadingHTTPServer(('127.0.0.1',8790),P).serve_forever()
