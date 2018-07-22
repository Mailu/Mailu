""" Dovecot dict proxy implementation
"""

import asyncio
import logging


class DictProtocol(asyncio.Protocol):
    """ Protocol to answer Dovecot dict requests, as implemented in Dict proxy.

    There is very little documentation about the protocol, most of it was
    reverse-engineered from :

    https://github.com/dovecot/core/blob/master/src/dict/dict-connection.c
    https://github.com/dovecot/core/blob/master/src/dict/dict-commands.c
    https://github.com/dovecot/core/blob/master/src/lib-dict/dict-client.h
    """

    DATA_TYPES = {0: str, 1: int}

    def __init__(self, table_map):
        self.table_map = table_map
        self.major_version = None
        self.minor_version = None
        self.dict = None
        super(DictProtocol, self).__init__()

    def connection_made(self, transport):
        logging.info('Connect {}'.format(transport.get_extra_info('peername')))
        self.transport = transport

    def data_received(self, data):
        logging.debug("Received {}".format(data))
        results = []
        for line in data.split(b"\n"):
            logging.debug("Line {}".format(line))
            if len(line) < 2:
                continue
            command = DictProtocol.COMMANDS.get(line[0])
            if command is None:
                logging.warning('Unknown command {}'.format(line[0]))
                return self.transport.abort()
            args = line[1:].strip().split(b"\t")
            try:
                future = command(self, *args)
                if future:
                    results.append(future)
            except Exception:
                logging.exception("Error when processing request")
                return self.transport.abort()
        logging.debug("Results {}".format(results))
        return asyncio.gather(*results)

    def process_hello(self, major, minor, value_type, user, dict_name):
        self.major, self.minor = int(major), int(minor)
        logging.debug('Client version {}.{}'.format(self.major, self.minor))
        assert self.major == 2
        self.value_type = DictProtocol.DATA_TYPES[int(value_type)]
        self.user = user
        self.dict = self.table_map[dict_name.decode("ascii")]
        logging.debug("Value type {}, user {}, dict {}".format(
            self.value_type, self.user, dict_name))

    async def process_lookup(self, key):
        logging.debug("Looking up {}".format(key))
        result = await self.dict.get(key.decode("utf8"))
        if result is not None:
            if type(result) is str:
                response = result.encode("utf8")
            elif type(result) is bytes:
                response = result
            else:
                response = json.dumps(result).encode("ascii")
            return self.reply(b"O", response)
        else:
            return self.reply(b"N")

    def reply(self, command, *args):
        logging.debug("Replying {} with {}".format(command, args))
        self.transport.write(command)
        self.transport.write(b"\t".join(
            arg.replace(b"\t", b"\t\t") for arg in args
        ))
        self.transport.write(b"\n")

    @classmethod
    def factory(cls, table_map):
        """ Provide a protocol factory for a given map instance.
        """
        return lambda: cls(table_map)

    COMMANDS = {
        ord("H"): process_hello,
        ord("L"): process_lookup
    }
