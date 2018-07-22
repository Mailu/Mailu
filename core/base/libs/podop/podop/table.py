""" Table lookup backends for podop
"""

import aiohttp
import logging


class UrlTable(object):
    """ Resolve an entry by querying a parametrized GET URL.
    """

    def __init__(self, url_pattern):
        """ url_pattern must contain a format ``{}`` so the key is injected in
        the url before the query, the ``§`` character will be replaced with
        ``{}`` for easier setup.
        """
        self.url_pattern = url_pattern.replace('§', '{}')

    async def get(self, key):
        logging.debug("Getting {} from url table".format(key))
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url_pattern.format(key)) as request:
                if request.status == 200:
                    result = await request.json()
                    logging.debug("Got {} from url table".format(result))
                    return result
