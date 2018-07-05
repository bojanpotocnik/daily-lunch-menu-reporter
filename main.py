import asyncio
import datetime
import enum
import re
from typing import List, Dict, Tuple

import aiohttp
import lxml.html

__author__ = "Bojan Potočnik"


@enum.unique
class Restaurants(enum.Enum):
    ANTARO = r"http://www.antaro.si/antaro/dnevni_menu/"
    PERLA = r"http://www.antaro.si/perla/dnevni_menu/"


async def get_week_menu(restaurant: Restaurants, *, loop: asyncio.AbstractEventLoop = None) \
        -> Tuple[Restaurants, Dict[Tuple[str, datetime.date], List[str]]]:
    """
    Asynchronously fetch data from the selected web page.

    :param restaurant: Selected restaurant for which to fetch data.
    :param loop: Optional event loop.

    :return: Restaurant, dictionary {tuple (Slovenian day name, date): list of listed food items}.
    """
    async with aiohttp.ClientSession(loop=loop) as session:
        async with session.get(restaurant.value) as response:
            response = await response.text()

    parser: lxml.html.HtmlElement = lxml.html.fromstring(response)
    weekdays: List[lxml.html.HtmlElement] = parser.cssselect(".weekday")

    menu = {}
    for weekday in weekdays:
        header: lxml.html.HtmlElement = weekday.cssselect("h2")[0]
        food_items: List[lxml.html.HtmlElement] = weekday.cssselect("li")

        day_name, day, month, year = re.fullmatch(r"(\w+) (\d{1,2})\.(\d{1,2})\.(\d{4})", header.text).groups()
        date = datetime.date(int(year), int(month), int(day))

        menu[(day_name, date)] = [item.text for item in food_items]

    return restaurant, menu


def print_all_menus():
    loop = asyncio.get_event_loop()

    tasks = asyncio.wait([get_week_menu(Restaurants.ANTARO),
                          get_week_menu(Restaurants.PERLA)], timeout=10)

    finished_tasks = loop.run_until_complete(tasks)[0]
    results: Dict[Restaurants, Dict[Tuple[str, datetime.date], List[str]]] = {
        task.result()[0]: task.result()[1] for task in finished_tasks
    }

    for restaurant, week_menu in results.items():  # type: Restaurants, Dict[Tuple[str, datetime.date], List[str]]
        print(f"Restaurant: {restaurant.name}")
        for (day_name, day), menu in week_menu.items():
            print(f"\t{day_name}, {day:%d.%m.%Y}:")
            for item in menu:
                print(f"\t\t- {item}")


if __name__ == "__main__":
    print_all_menus()
