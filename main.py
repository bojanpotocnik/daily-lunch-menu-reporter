import asyncio
import datetime
import re
from typing import List, Dict, Tuple, Optional

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


async def get_fenix_image(*, loop: asyncio.AbstractEventLoop = None,
                          image_path: Optional[str] = r"G:\Users\Bojan\Downloads\jedilnik.jpg"):
    import cv2
    import numpy as np

    if image_path:
        img: np.ndarray = cv2.imread(r"G:\Users\Bojan\Downloads\jedilnik.jpg", cv2.IMREAD_COLOR)
    else:
        async with aiohttp.ClientSession(loop=loop) as session:
            async with session.get(r"http://fnx.si/images/jedilnik.jpg") as response:
                if response.status != 200:
                    return None
                png_image = await response.read()

        # Load image from byte buffer.
        img: np.ndarray = cv2.imdecode(np.frombuffer(png_image, np.uint8), cv2.IMREAD_COLOR)

    # Image is BGR (img[:, :, 0] = B, img[:, :, 1] = G, img[:, :, 2] = R)
    # Make a binary image - this can be done as ROIs (region of interests) are pure black on pure white,
    # except the soft edges of the white-on-black text inside the ROI. This (anti-aliased edges) is visible
    # only when thresh value ranges from 0 to 3 - there is no difference between thresh=3 and thresh=10 in
    # the regions of interest (ROI).
    # It does not matter if inverted mode is used, but use it just because "In OpenCV, finding contours is
    # like finding white object from black background. So remember, object to be found should be white and
    # background should be black.".
    # As squares are black, they are present on all channels.
    img_mask_bgr = [cv2.threshold(img[:, :, i], 3, 0xFF, cv2.THRESH_BINARY_INV)[1] for i in range(3)]
    img_mask = cv2.bitwise_and(img_mask_bgr[0], img_mask_bgr[1])
    img_mask = cv2.bitwise_and(img_mask, img_mask_bgr[2])
    del img_mask_bgr
    # Perform edge detection to make contour detection easier and more robust.
    img_edged = cv2.Canny(img_mask, 255, 255)
    # Detect contours.
    #  RETR_EXTERNAL retrieves only the extreme outer contours.
    #  CHAIN_APPROX_SIMPLE removes all redundant points and compresses the contour, thereby saving memory.
    all_contours, _ = cv2.findContours(img_edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Discard all contours considered "noise" for this application.
    contours = []
    for ct in all_contours:
        # Because of the dotted lines, some contours are not closed,
        # so their area is minimal (the same as noise contours). Use the perimeter as the most basic filter.
        if cv2.arcLength(ct, True) < 200:
            continue
        xs = ct[:, 0, 0]
        ys = ct[:, 0, 1]
        if ys.ptp() < 5:  # This is a horizontal line. Only keep the edge points.
            y = int(np.median(ys))
            ct = np.array([[[xs.min(), y]], [[xs.max(), y]]])
        print(ct)
        contours.append(ct)
    del all_contours

    # TODO: Merge contours which shall be detected as one rectangle but are not due to the dotted lines.
    for i in range(1, len(contours)):
        ct0 = contours[i - 1]
        xs0 = ct0[:, 0, 0]
        ys0 = ct0[:, 0, 1]
        ct1 = contours[i]
        xs1 = ct1[:, 0, 0]
        ys1 = ct1[:, 0, 1]
        pass

    from matplotlib import pyplot as plt
    plt.ion()
    cv2.imshow("Original", img)
    cv2.imshow("Binary", img_mask)
    cv2.imshow("Edged", img_edged)
    # plt.imshow(cv2.drawContours(img, contours, -1, (255, 0, 255), 3, hierarchy=hierarchy))  # Show coordinates

    # Create TrackBar for selective contour drawing
    cv2.namedWindow("Contours")

    def _on_trackbar(pos: int):
        contour = contours[pos]
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, False)
        x, y, w, h = cv2.boundingRect(contour)

        cv2.imshow("Contours", cv2.drawContours(img.copy(), [contour], 0, (255, 0, 255), 3))
        cv2.setWindowTitle("Contours", f"Contour {pos}, A={area}, p={perimeter}, ({contour})")

    cv2.createTrackbar("Contour", "Contours", 0, len(contours) - 1, _on_trackbar)
    _on_trackbar(0)

    while True:
        k = cv2.waitKeyEx(0)
        if k == 2424832:  # Left Arrow
            cv2.setTrackbarPos("Contour", "Contours", max(0,
                                                          cv2.getTrackbarPos("Contour", "Contours") - 1))
        elif k == 2555904:  # Right Arrow
            cv2.setTrackbarPos("Contour", "Contours", min(len(contours) - 1,
                                                          cv2.getTrackbarPos("Contour", "Contours") + 1))
        elif k == 27:  # Escape
            break

    cv2.destroyAllWindows()

    pass


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
    # print_all_menus(report_to_slack=False)
    asyncio.run(get_fenix_image(), debug=True)
