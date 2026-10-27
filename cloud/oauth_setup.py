"""Explicit local owner OAuth setup. Never invoked by the cloud application."""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import webbrowser
import httpx
from cloud.mail_config import SCOPES, single_address
from cloud.gmail import normalized_scopes

REDIRECT = 'http://localhost:8765/oauth/callback'


def external(path, root):
    value = Path(path).expanduser().resolve()
    if value == root or root in value.parents: raise ValueError('private_path_must_be_outside_repository')
    if any(p.is_symlink() for p in (value,*value.parents)): raise ValueError('private_path_symlink_rejected')
    return value


def main():
    parser = argparse.ArgumentParser(description='Local Gmail OAuth with explicit owner consent; no email is sent.')
    parser.add_argument('--client-secrets',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--sender',required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source, target = external(args.client_secrets,root), external(args.output,root)
    if target.exists() or not target.parent.is_dir() or source.stat().st_size > 16384:
        raise ValueError('private_output_must_be_new')
    client = json.loads(source.read_text('utf-8'))['web']
    if REDIRECT not in client.get('redirect_uris',[]): raise ValueError('exact_local_redirect_required')
    sender = single_address(args.sender)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    result = {}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def do_GET(self):
            parsed = urlsplit(self.path)
            values = parse_qs(parsed.query)
            valid = (parsed.path == '/oauth/callback' and self.headers.get('host') == 'localhost:8765'
                     and len(self.path) <= 4096 and values.get('state') == [state]
                     and len(values.get('code',[])) == 1 and len(values['code'][0]) <= 2048)
            if valid: result['code'] = values['code'][0]
            self.send_response(200 if valid else 400)
            self.send_header('Content-Type','text/plain; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','no-referrer')
            self.end_headers()
            self.wfile.write(b'Authorization received. Return to the terminal.' if valid else b'Authorization refused.')
    server = HTTPServer(('127.0.0.1',8765),Callback)
    server.timeout = 180
    url = 'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':client['client_id'],
        'redirect_uri':REDIRECT,'response_type':'code','scope':' '.join(sorted(SCOPES)),
        'state':state,'access_type':'offline','prompt':'consent','code_challenge':challenge,
        'code_challenge_method':'S256','login_hint':sender})
    try:
        if not webbrowser.open(url): raise ValueError('browser_unavailable')
        server.handle_request()
    finally: server.server_close()
    if not result.get('code'): raise ValueError('oauth_not_completed')
    with httpx.Client(timeout=10,follow_redirects=False,trust_env=False) as http:
        response = http.post('https://oauth2.googleapis.com/token',data={'grant_type':'authorization_code',
            'client_id':client['client_id'],'client_secret':client['client_secret'],
            'code':result['code'],'redirect_uri':REDIRECT,'code_verifier':verifier})
        response.raise_for_status(); token = response.json()
        if normalized_scopes(token.get('scope')) != SCOPES or not token.get('refresh_token'):
            raise ValueError('offline_scope_binding_required')
        response = http.get('https://openidconnect.googleapis.com/v1/userinfo',
            headers={'Authorization':'Bearer '+token['access_token']})
        response.raise_for_status(); identity = response.json()
        if identity.get('email') != sender or identity.get('email_verified') is not True or not identity.get('sub'):
            raise ValueError('oauth_owner_binding_mismatch')
    credentials = {'type':'authorized_user','project_id':client['project_id'],
        'client_id':client['client_id'],'client_secret':client['client_secret'],
        'refresh_token':token['refresh_token'],'token_uri':'https://oauth2.googleapis.com/token',
        'account_email':sender,'account_sub':identity['sub'],'scopes':sorted(SCOPES)}
    fd = os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as file: json.dump(credentials,file,separators=(',',':'))
    print('Private OAuth configuration created outside the repository. No email was sent. Never publish that file.')


if __name__ == '__main__':
    try: main()
    except Exception:
        print('OAuth setup did not complete. No credentials or provider errors are printed; check the private configuration.')
        raise SystemExit(1) from None
