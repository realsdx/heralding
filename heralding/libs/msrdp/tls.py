# Copyright (C) 2019 Sudipta Pandit <realsdx@protonmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import ssl
import logging

logger = logging.getLogger(__name__)


class TLS:
    """ TLS implamentation using memory BIO """

    def __init__(self, writer, reader, pem_file):
        """@param: writer and reader are asyncio stream writer and reader objects"""
        self._tlsInBuff = ssl.MemoryBIO()
        self._tlsOutBuff = ssl.MemoryBIO()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_1)
        ctx.options |= ssl.OP_NO_TLSv1
        ctx.set_ciphers('RSA:!aNULL')
        ctx.check_hostname = False
        ctx.load_cert_chain(pem_file)
        self._tlsObj = ctx.wrap_bio(self._tlsInBuff, self._tlsOutBuff, server_side=True)
        self.writer = writer
        self.reader = reader

    async def do_tls_handshake(self):
        client_hello = await self.reader.read(4096)
        self._tlsInBuff.write(client_hello)
        try:
            self._tlsObj.do_handshake()
        except ssl.SSLWantReadError:
            server_hello = self._tlsOutBuff.read()
            self.writer.write(server_hello)
            await self.writer.drain()

        client_fin = await self.reader.read(4096)
        self._tlsInBuff.write(client_fin)
        self._tlsObj.do_handshake()

        server_fin = self._tlsOutBuff.read()
        self.writer.write(server_fin)
        await self.writer.drain()

    async def write_tls(self, data):
        self._tlsObj.write(data)
        _data = self._tlsOutBuff.read()
        _res = self.writer.write(_data)
        await self.writer.drain()
        return _res

    async def read_tls(self, size):
        logger.debug("PENDING BYTES TO READ: " + str(self._tlsObj.pending()))
        _rData = await self.reader.read(size)
        logger.debug("RAW BYTES : "+str(len(_rData)))
        self._tlsInBuff.write(_rData)
        data = None
        tries = 5
        while not data and (tries > 0):
            tries = tries-1
            try:
                data = self._tlsObj.read(size)
                logger.debug("PENDING TLS READ: " + str(self._tlsObj.pending()))
                data += self._tlsObj.read(size)
            except ssl.SSLWantReadError:
                logger.debug("ssl.SSLWantReadError in tls.py")
                pass
        return data
