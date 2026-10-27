"""Actual local official MCP STDIO client. No HTTP tool transport."""
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
import hmac
import os
from pathlib import Path
import sys
from cloud.mail import canonical


@asynccontextmanager
async def connect():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    allowed = {'PATH','SYSTEMROOT','DATABASE_URL','STATE_NAMESPACE','STATE_ENCRYPTION_KEY',
               'MCP_BOUNDARY_KEY','EMAIL_ENABLE_REAL_SEND','GMAIL_SENDER','GMAIL_PROJECT_ID',
               'GMAIL_CLIENT_ID','GMAIL_OAUTH_JSON'}
    env = {k:v for k,v in os.environ.items() if k in allowed}
    env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    params = StdioServerParameters(command=sys.executable,args=['-B','-m','cloud.mcp_server'],
        cwd=str(Path(__file__).resolve().parents[1]),env=env)
    with open(os.devnull,'w',encoding='utf-8') as errors:
        async with stdio_client(params,errlog=errors) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=35)) as session:
                await session.initialize()
                yield session


async def send(payload):
    key = os.environ['MCP_BOUNDARY_KEY']
    if len(key) < 43: raise ValueError('mcp_boundary_key_required')
    signature = hmac.new(key.encode(),canonical(payload).encode(),hashlib.sha256).hexdigest()
    async with connect() as session:
        result = await session.call_tool('deliver_authorized_email',{'envelope':{'payload':payload,'signature':signature}})
        value = result.structuredContent
        if result.isError or not isinstance(value,dict) or value.get('status') not in {'accepted','unknown','rejected','not_attempted'}:
            raise ValueError('mcp_delivery_unknown')
        return value


async def health():
    async with connect() as session:
        tools = await session.list_tools()
        if {tool.name for tool in tools.tools} != {'email_health','deliver_authorized_email'}: raise ValueError('mcp_protocol_unavailable')
        result = await session.call_tool('email_health',{})
        if result.isError or result.structuredContent != {'status':'ok','oauth':'not_performed'}: raise ValueError('mcp_protocol_unavailable')
    return {'status':'ok','transport':'stdio','tools':2}


if __name__ == '__main__':
    import asyncio
    import logging
    logging.disable(logging.CRITICAL)
    print(asyncio.run(health()))
