import os
import unittest
from unittest.mock import patch
from cloud.mcp_server import deliver


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_tool_never_loads_database_or_oauth(self):
        with patch.dict(os.environ,{'EMAIL_ENABLE_REAL_SEND':'false'}):
            self.assertEqual((await deliver(None))['status'],'not_attempted')

    async def test_unsigned_tool_order_is_not_dispatched(self):
        with patch.dict(os.environ,{'EMAIL_ENABLE_REAL_SEND':'true'}):
            self.assertEqual((await deliver({'payload':{},'signature':'invalid'}))['status'],'unknown')
