""" Dovecot dict proxy implementation
"""

import asyncio
import logging
import json


class DictProtocol(asyncio.Protocol):
    """ Protocol to answer Dovecot dict requests, as implemented in Dict proxy.

    Only a subset of operations is handled properly by this proxy: hello,
    lookup and transaction-based set.

    There is very little documentation about the protocol, most of it was
    reverse-engineered from :

    https://github.com/dovecot/core/blob/master/src/dict/dict-connection.c
    https://github.com/dovecot/core/blob/master/src/dict/dict-commands.c
    https://github.com/dovecot/core/blob/master/src/lib-dict/dict-client.h
    """

    DATA_TYPES = {0: str, 1: int}

    def __init__(self, table_map):
        self.table_map = table_map
        # Minor and major versions are not properly checked yet, but stored
        # anyway
        self.major_version = None
        self.minor_version = None
        # Every connection starts with specifying which table is used, dovecot
        # tables are called dicts
        self.dict = None
        # Dictionary of active transaction lists per transaction id
        self.transactions = {}
        super(DictProtocol, self).__init__()

    def connection_made(self, transport):
        logging.info('Connect {}'.format(transport.get_extra_info('peername')))
        self.transport = transport

    def data_received(self, data):
        logging.debug("Received {}".format(data))
        results = []
        # Every command is separated by "\n"
        for line in data.split(b"\n"):
            # A command must at list have a type and one argument
            if len(line) < 2:
                continue
            # The command function will handle the command itself
            command = DictProtocol.COMMANDS.get(line[0])
            if command is None:
                logging.warning('Unknown command {}'.format(line[0]))
                return self.transport.abort()
            # Args are separated by "\t"
            args = line[1:].strip().split(b"\t")
            try:
                future = command(self, *args)
                if future:
                    results.append(future)
            except Exception:
                logging.exception("Error when processing request")
                return self.transport.abort()
        # For asyncio consistency, wait for all results to fire before
        # actually returning control
        return asyncio.gather(*results)

    def process_hello(self, major, minor, value_type, user, dict_name):
        """ Process a dict protocol hello message
        """
        self.major, self.minor = int(major), int(minor)
        self.value_type = DictProtocol.DATA_TYPES[int(value_type)]
        self.user = user.decode("utf8")
        self.dict = self.table_map[dict_name.decode("ascii")]
        logging.debug("Client {}.{} type {}, user {}, dict {}".format(
            self.major, self.minor, self.value_type, self.user, dict_name))

    async def process_lookup(self, key):
        """ Process a dict lookup message
        """
        logging.debug("Looking up {}".format(key))
        # Priv and shared keys are handled slighlty differently
        key_type, key = key.decode("utf8").split("/", 1)
        try:
            result = await self.dict.get(
                key, ns=(self.user if key_type == "priv" else None)
            )
            if type(result) is str:
                response = result.encode("utf8")
            elif type(result) is bytes:
                response = result
            else:
                response = json.dumps(result).encode("ascii")
            return self.reply(b"O", response)
        except KeyError:
            return self.reply(b"N")

    def process_begin(self, transaction_id):
        """ Process a dict begin message
        """
        self.transactions[transaction_id] = {}

    def process_set(self, transaction_id, key, value):
        """ Process a dict set message
        """
        # Nothing is actually set until everything is commited
        self.transactions[transaction_id][key] = value

    async def process_commit(self, transaction_id):
        """ Process a dict commit message
        """
        # Actually handle all set operations from the transaction store
        results = []
        for key, value in self.transactions[transaction_id].items():
            logging.debug("Storing {}={}".format(key, value))
            key_type, key = key.decode("utf8").split("/", 1)
            result = await self.dict.set(
                key, json.loads(value),
                ns=(self.user if key_type == "priv" else None)
            )
        # Remove stored transaction
        del self.transactions[transaction_id]
        return self.reply(b"O", transaction_id)

    def reply(self, command, *args):
        logging.debug("Replying {} with {}".format(command, args))
        self.transport.write(command)
        self.transport.write(b"\t".join(map(tabescape, args)))
        self.transport.write(b"\n")

    @classmethod
    def factory(cls, table_map):
        """ Provide a protocol factory for a given map instance.
        """
        return lambda: cls(table_map)

    COMMANDS = {
        ord("H"): process_hello,
        ord("L"): process_lookup,
        ord("B"): process_begin,
        ord("C"): process_commit,
        ord("S"): process_set
    }


def tabescape(unescaped):
    """ Escape a string using the specific Dovecot tabescape
    See: https://github.com/dovecot/core/blob/master/src/lib/strescape.c
    """
    return unescaped.replace(b"\x01", b"\x011")\
                    .replace(b"\x00", b"\x010")\
                    .replace(b"\t",   b"\x01t")\
                    .replace(b"\n",   b"\x01n")\
                    .replace(b"\r",   b"\x01r")


def tabunescape(escaped):
    """ Unescape a string using the specific Dovecot tabescape
    See: https://github.com/dovecot/core/blob/master/src/lib/strescape.c
    """
    return escaped.replace(b"\x01r", b"\r")\
                  .replace(b"\x01n", b"\n")\
                  .replace(b"\x01t", b"\t")\
                  .replace(b"\x010", b"\x00")\
                  .replace(b"\x011", b"\x01")
