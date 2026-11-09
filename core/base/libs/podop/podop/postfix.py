""" Postfix map proxy implementation
"""

import asyncio
import logging
import aiohttp

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


class DomainQuotaPolicyProtocol(asyncio.Protocol):
    """Serve Postfix's check_policy_service protocol for domain quotas."""

    def __init__(self, url):
        self.url = url
        self.buffer = bytearray()

    def connection_made(self, transport):
        self.transport = transport
        logging.debug("Policy connection from %s", transport.get_extra_info("peername"))

    def data_received(self, data):
        self.buffer.extend(data)
        while True:
            boundaries = [
                (self.buffer.find(separator), len(separator))
                for separator in (b"\r\n\r\n", b"\n\n")
                if self.buffer.find(separator) >= 0
            ]
            if not boundaries:
                break
            boundary, length = min(boundaries)
            request = self.buffer[:boundary]
            remainder = self.buffer[boundary + length:]
            self.buffer = bytearray(remainder)
            attributes = {}
            for line in request.splitlines():
                key, separator, value = line.partition(b"=")
                if separator:
                    attributes[key.decode("ascii", errors="replace")] = value.decode(
                        "utf-8", errors="replace"
                    )
            asyncio.ensure_future(self.respond(attributes))

    async def respond(self, attributes):
        action = "DUNNO"
        if attributes.get("protocol_state") == "RCPT" and attributes.get("recipient"):
            try:
                size = max(0, int(attributes.get("size") or 0))
                timeout = aiohttp.ClientTimeout(total=2)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        self.url,
                        json={"recipient": attributes["recipient"], "size": size},
                    ) as response:
                        response.raise_for_status()
                        result = await response.json()
                if not result.get("allowed", True):
                    action = "552 5.2.2 Domain storage quota exceeded"
            except (ValueError, aiohttp.ClientError, asyncio.TimeoutError, OSError) as error:
                # Domain quota checks are best-effort; per-user Dovecot quotas
                # remain authoritative if the Admin lookup is unavailable.
                logging.warning(
                    "Domain quota lookup failed for %s: %s",
                    attributes.get("recipient", ""), error,
                )
            except Exception:
                logging.exception("Unexpected domain quota policy error")
        self.transport.write(f"action={action}\n\n".encode("utf-8"))
