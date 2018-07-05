import asyncio
import datetime
import enum
from typing import List, Dict, Tuple

import aiohttp

__author__ = "Bojan Potočnik"


@enum.unique
class Restaurants(enum.Enum):
    ANTARO = r"http://www.antaro.si/antaro/dnevni_menu/"
    PERLA = r"http://www.antaro.si/perla/dnevni_menu/"


async def fetch(restaurant: Restaurants, *, loop: asyncio.AbstractEventLoop = None) \
        -> Tuple[Restaurants, Dict[Tuple[str, datetime.date], List[str]]]:
    async with aiohttp.ClientSession(loop=loop) as session:
        async with session.get(restaurant.value) as response:
            response = await response.text()
            print(response)


def main():
    loop = asyncio.get_event_loop()

    result = loop.run_until_complete(fetch(Restaurants.ANTARO))
    print(result)


if __name__ == "__main__":
    main()
