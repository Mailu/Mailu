""" Podop is a *Po*stfix and *Do*vecot proxy

It is able to proxify postfix maps and dovecot dicts to any table
"""

import asyncio
import logging
import sys

from podop import postfix, dovecot, table


SERVER_TYPES = dict(
    postfix=postfix.SocketmapProtocol,
    dovecot=dovecot.DictProtocol
)

TABLE_TYPES = dict(
    url=table.UrlTable
)


def run_server(verbosity, server_type, socket, tables):
    """ Run the server, given its type, socket path and table list

    The table list must be a list of tuples (name, type, param)
    """
    # Prepare the maps
    table_map = {
        name: TABLE_TYPES[table_type](param)
        for name, table_type, param in tables
    }
    # Run the main loop
    logging.basicConfig(stream=sys.stderr, level=max(3 - verbosity, 0) * 10,
                        format='%(name)s (%(levelname)s): %(message)s')
    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(loop.create_unix_server(
        SERVER_TYPES[server_type].factory(table_map), socket
    ))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
