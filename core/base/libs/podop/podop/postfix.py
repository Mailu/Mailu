""" Postfix map proxy implementation
"""

import asyncio
import logging

class NetstringProtocol(asyncio.Protocol):
    """ Netstring asyncio protocol implementation.

    For protocol details, see https://cr.yp.to/proto/netstrings.txt
    """

    # Length of the smallest allocated buffer, larger buffers will be
    # allocated dynamically
    BASE_BUFFER = 1024

    # Maximum length of a buffer, will crash when exceeded
    MAX_BUFFER = 65535

    def __init__(self):
        super(NetstringProtocol, self).__init__()
        self.init_buffer()

    def init_buffer(self):
        self.len = None  # None when waiting for a length to be sent)
        self.separator = -1  # -1 when not yet detected (str.find)
        self.index = 0  # relative to the buffer
        self.buffer = bytearray(NetstringProtocol.BASE_BUFFER)

    def data_received(self, data):
        # Manage the buffer
        missing = len(data) - len(self.buffer) + self.index
        if missing > 0:
            if len(self.buffer) + missing > NetstringProtocol.MAX_BUFFER:
                raise IOError("Not enough space when decoding netstring")
            self.buffer.append(bytearray(missing + 1))
        new_index = self.index + len(data)
        self.buffer[self.index:new_index] = data
        self.index = new_index
        # Try to detect a length at the beginning of the string
        if self.len is None:
            self.separator = self.buffer.find(0x3a)
            if self.separator != -1 and self.buffer[:self.separator].isdigit():
                self.len = int(self.buffer[:self.separator], 10)
        # Then get the complete string
        if self.len is not None:
            if self.index - self.separator == self.len + 2:
                string = self.buffer[self.separator + 1:self.index - 1]
                self.init_buffer()
                self.string_received(string)

    def string_received(self, string):
        """ A new netstring was received
        """
        pass

    def send_string(self, string):
        """ Send a netstring
        """
        logging.debug("Replying {}".format(string))
        self.transport.write(str(len(string)).encode('ascii'))
        self.transport.write(b':')
        self.transport.write(string)
        self.transport.write(b',')


class SocketmapProtocol(NetstringProtocol):
    """ Protocol to answer Postfix socketmap and proxify lookups to
    an outside object.

    See http://www.postfix.org/socketmap_table.5.html for details on the
    protocol.

    A table map must be provided as a dictionary to lookup tables.
    """

    def __init__(self, table_map):
        self.table_map = table_map
        super(SocketmapProtocol, self).__init__()

    def connection_made(self, transport):
        logging.info('Connect {}'.format(transport.get_extra_info('peername')))
        self.transport = transport

    def string_received(self, string):
        # The postfix format contains a space for separating the map name and
        # the key
        logging.debug("Received {}".format(string))
        space = string.find(0x20)
        if space != -1:
            name = string[:space].decode('ascii')
            key = string[space+1:].decode('utf8')
            return asyncio.ensure_future(self.process_request(name, key))

    async def process_request(self, name, key):
        """ Process a request by querying the provided map.
        """
        logging.debug("Request {}/{}".format(name, key))
        try:
            table = self.table_map.get(name)
        except KeyError:
            return self.send_string(b'TEMP no such map')
        try:
            result = await table.get(key)
            return self.send_string(b'OK ' + str(result).encode('utf8'))
        except KeyError:
            return self.send_string(b'NOTFOUND ')
        except Exception:
            logging.exception("Error when processing request")
            return self.send_string(b'TEMP unknown error')

    @classmethod
    def factory(cls, table_map):
        """ Provide a protocol factory for a given map instance.
        """
        return lambda: cls(table_map)
