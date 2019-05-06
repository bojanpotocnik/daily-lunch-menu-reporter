import asyncio
import datetime
import re
from typing import List, Dict, Tuple

import aiohttp
import lxml.html

from restaurants import Restaurants
from slack_client import SlackClient

__author__ = "Bojan Potočnik"


async def get_week_menu(restaurant: Restaurants, *, loop: asyncio.AbstractEventLoop = None) \
        -> Tuple[Restaurants, Dict[datetime.date, Tuple[str, List[str]]]]:
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

        menu[date] = day_name, [item.text for item in food_items]

    return restaurant, menu


def print_all_menus(*, only_today: bool = True, report_to_slack: bool = True):
    loop = asyncio.get_event_loop()

    tasks = asyncio.wait([get_week_menu(Restaurants.ANTARO),
                          get_week_menu(Restaurants.PERLA)], timeout=10)

    finished_tasks = loop.run_until_complete(tasks)[0]

    results: Dict[Restaurants, Dict[datetime.date, Tuple[str, List[str]]]] = {
        task.result()[0]: task.result()[1] for task in finished_tasks
    }

    if only_today:
        results = {
            restaurant: {
                day: menu for day, menu in week_menu.items() if (day == datetime.date.today())
            } for restaurant, week_menu in results.items()
        }

    for restaurant, week_menu in results.items():  # type: Restaurants, Dict[datetime.date, Tuple[str, List[str]]]
        print(f"Restaurant: {restaurant.name}")
        for day, (day_name, menu) in week_menu.items():
            print(f"\t{day_name}, {day:%d.%m.%Y}:")
            for item in menu:
                print(f"\t\t- {item}")

    if report_to_slack:
        sc = SlackClient(None, "food", token_env_var="SLACK_TOKEN_REPORTS")
        sc.post_menu(results)


if __name__ == "__main__":
    print_all_menus()
