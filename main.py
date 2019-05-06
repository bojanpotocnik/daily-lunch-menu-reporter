import asyncio
import datetime
import os
import re
from typing import List, Dict, Tuple

import aiohttp
import imageio
import lxml.html
import numpy as np

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


async def get_fenix_image(*, loop: asyncio.AbstractEventLoop = None):
    async with aiohttp.ClientSession(loop=loop) as session:
        async with session.get(r"http://fnx.si/images/jedilnik.jpg") as response:
            if response.status != 200:
                return None
            png_image = await response.read()

    # Load image from byte buffer.
    img: imageio.core.util.Array = imageio.imread(png_image)

    def _failure(err: str):
        fp = os.path.join(os.path.dirname(__file__), ".failed_fnx.si_images",
                          f"jedilnik_{datetime.datetime.now():%Y%m%d%H%M%S}")
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        imageio.imwrite(fp + ".jpg", img)
        with open(fp + ".txt", 'w') as f:
            f.write(err)
        raise ValueError(err)

    # Isolate one vertical RGB line (Nx3) - in line x=32 the black header squares are already visible, but not yet text.
    rgb_col = img[:, 32, :]
    # One vertical line (Nx1 - N-long array in fact) marking where the row is pure white.
    whites = np.all(rgb_col == 0xFF, axis=1)
    # Get indices where white parts become colored and vice-versa.
    changes = np.where(np.diff(whites) != 0)[0]
    # Image/column starts with white pixel, therefore two consecutive changes can be treated as one colored part.
    color_parts = [(changes[i], changes[i + 1]) for i in range(0, len(changes), 2)]
    # First, find a large rectangle with price.
    price_rectangle = list(filter(lambda part: 110 < (part[1] - part[0]) < 120, color_parts))
    if len(price_rectangle) != 1:
        _failure(f"Cannot parse image with 'price rectangles' at: {price_rectangle}")
    price_rectangle_end = price_rectangle[0][1]
    # Remove all colored parts too short or too long or before the price rectangle.
    color_parts = list(filter(
        lambda part: (part[0] > price_rectangle_end) and (30 < (part[1] - part[0]) < 60),
        color_parts
    ))
    # Suppose that there are black rectangles for every day and one colored for permanent menu.
    headers_days = color_parts[:5]
    # header_permanent_menu = color_parts[5]

    # Remove few lines (anti-aliasing).
    headers_days_colors = [np.mean(rgb_col[part[0] + 2:part[1] - 1]) for part in headers_days]
    if not all(c < 2 for c in headers_days_colors):
        _failure(f"Invalid colors {headers_days_colors} for {headers_days}")

    # One daily menu is considered from the start of header N to the start of header N+1 (minus anti-aliasing noise).
    daily_menu_parts = [(color_parts[i][0], color_parts[i + 1][0] - 3) for i in range(len(color_parts) - 1)]
    today_menu_part = daily_menu_parts[datetime.date.today().isoweekday() - 1]

    if not (150 < (today_menu_part[1] - today_menu_part[0]) < 300):
        _failure(f"Invalid daily menu cut size {today_menu_part}")

    # Cut image
    img_daily_menu = img[today_menu_part[0]:today_menu_part[1]]

    # TODO: Post image to Slack.
    # fp = os.path.join(os.path.dirname(__file__), "daily_menus",
    #                   f"jedilnik_{datetime.datetime.now():%Y%m%d%H%M%S}.jpg")
    # os.makedirs(os.path.dirname(fp), exist_ok=True)
    # imageio.imwrite(fp, img_daily_menu)


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
    # asyncio.run(get_fenix_image(), debug=True)
