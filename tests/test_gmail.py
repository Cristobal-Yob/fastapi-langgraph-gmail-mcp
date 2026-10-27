import json
import os
import time
import unittest
from unittest.mock import patch
import httpx
from cloud.gmail import GmailTransport
from cloud.mail_config import Settings, SCOPES


class GmailTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_oauth_and_gmail_transport_with_only_synthetic_http(self):
        calls=[]
        def request(req):
            calls.append(str(req.url))
            if req.url.path == '/token':
                return httpx.Response(200,json={'access_token':'synthetic','token_type':'Bearer','scope':' '.join(SCOPES)})
            if req.url.path.endswith('/userinfo'):
                return httpx.Response(200,json={'email':'operator@example.invalid','sub':'synthetic-sub','email_verified':True})
            return httpx.Response(200,json={'id':'synthetic-provider-id'})
        credentials={'type':'authorized_user','project_id':'synthetic-project','account_email':'operator@example.invalid',
          'account_sub':'synthetic-sub','client_id':'synthetic.apps.googleusercontent.com','client_secret':'synthetic',
          'refresh_token':'synthetic','token_uri':'https://oauth2.googleapis.com/token','scopes':list(SCOPES)}
        env={'EMAIL_ENABLE_REAL_SEND':'true','GMAIL_SENDER':'operator@example.invalid','GMAIL_PROJECT_ID':'synthetic-project',
             'GMAIL_CLIENT_ID':'synthetic.apps.googleusercontent.com','GMAIL_OAUTH_JSON':json.dumps(credentials)}
        with patch.dict(os.environ,env):
            async with httpx.AsyncClient(transport=httpx.MockTransport(request)) as http:
                result = await GmailTransport(Settings(),client=http).send({'to':'recipient@example.invalid',
                    'subject':'Synthetic','body':'Synthetic','issued_at':time.time()-1,'expires_at':time.time()+30})
        self.assertEqual(result.status,'accepted')
        self.assertEqual(len(calls),3)
        self.assertEqual(sum('/messages/send' in url for url in calls),1)
