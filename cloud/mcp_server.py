"""Signed, expiring Gmail tool. Stdout belongs only to MCP protocol."""
import asyncio
import hashlib
import hmac
import logging
import os
import time
from typing import Any
from cloud.mail import canonical, direct_send


async def deliver(envelope):
    if os.environ.get('EMAIL_ENABLE_REAL_SEND','false') != 'true': return {'status':'not_attempted','delivery':'disabled'}
    try:
        if not isinstance(envelope,dict) or set(envelope) != {'payload','signature'}: raise ValueError
        data = envelope['payload']
        if not isinstance(data,dict) or set(data) != {'to','subject','body','issued_at','expires_at','action_key','order_digest'}: raise ValueError
        key = os.environ['MCP_BOUNDARY_KEY']
        if len(key) < 43: raise ValueError
        expected = hmac.new(key.encode(),canonical(data).encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,envelope['signature']): raise ValueError
        if not data['issued_at'] <= time.time() < data['expires_at'] <= data['issued_at']+300: raise ValueError
        from cloud.store import DurableStore
        store = DurableStore('gmail-mcp-server:'+os.environ['STATE_NAMESPACE'])
        try:
            digest = hashlib.sha256(canonical({k:v for k,v in data.items() if not k.endswith('_at')}).encode()).hexdigest()
            if await asyncio.to_thread(store.claim,data['action_key'],digest) != 'new': return {'status':'unknown','delivery':'not_repeated'}
            await asyncio.to_thread(store.alive)
            outcome = await direct_send(data)
            if outcome['status'] in {'accepted','rejected','not_attempted'}: await asyncio.to_thread(store.finish,data['action_key'],outcome['status'])
            return outcome
        finally: store.close()
    except Exception: return {'status':'unknown','delivery':'not_confirmed'}


def main():
    from mcp.server.fastmcp import FastMCP
    logging.disable(logging.CRITICAL)
    server = FastMCP('Autonomous authorized Gmail')
    @server.tool(structured_output=True)
    def email_health() -> dict[str,Any]: return {'status':'ok','oauth':'not_performed'}
    @server.tool(structured_output=True)
    async def deliver_authorized_email(envelope: Any = None) -> dict[str,Any]: return await deliver(envelope)
    server.run(transport='stdio')


if __name__ == '__main__': main()
