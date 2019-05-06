import datetime
import os
import traceback
import warnings
from typing import Optional, List, Tuple, Dict

# noinspection PyPackageRequirements
import slack

from restaurants import Restaurants

__author__ = "Bojan Potočnik"


class SlackClient(slack.WebClient):

    def __init__(self, token: Optional[str], channel: str, proxies=None, *, token_env_var: str = None):
        """
        Initialize the Slack client.

        :param token: Slack OAuth Workspace Access Token for this app.
                      Note: Be `careful with your token <https://api.slack.com/docs/oauth-safety>`_.
        :param channel: Default channel used to post messages.
        :param proxies: Proxies to use when create websocket or api calls, declare http and websocket proxies using
                        {'http': 'http://127.0.0.1'}, and https proxy using {'https': 'https://127.0.0.1:443'}.
        :param token_env_var: If `token` is not provided as a security measure, system environmental variable name
                              can be provided as this parameters and token will be retrieved from it.
        """
        if (not token) and token_env_var:
            # Get the token for authentication
            # https://slackapi.github.io/python-slackclient/auth.html
            token = os.environ.get(token_env_var, None)

        # Token is saved in any case as it is checked when posting messages.
        self.token: Optional[str] = token

        if not token:
            warnings.warn(
                "Slack OAuth token for the app was not provided"
                + (f", neither found in the '{token_env_var}' environmental variable'" if token_env_var else "")
                + f".\nAll intents of posting to Slack using {type(self).__name__} will be silently ignored."
            )
            return

        self.channel: str = channel
        super().__init__(token, proxies)

    def post_message(self, message: str, channel: Optional[str] = None) -> bool:
        """
        Post message to the channel.

        :param message: Message content.
        :param channel: If provided, this channel will override the defalt one provided in init.

        :return: Whether the message has been successfully posted.
        """
        # noinspection PyBroadException
        try:
            ret = self.chat_postMessage(
                channel=channel or self.channel,
                text=message
            )
        except Exception as e:
            traceback.print_exc()
            ret = False

        return ret and ret.get("ok", False)

    # noinspection SpellCheckingInspection
    def post_menu(self, data: Dict[Restaurants, Dict[datetime.date, Tuple[str, List[str]]]]) -> bool:
        """
        Post menu for every day for every restaurant.

        :param data: Menu data.

        :return: Whether the message has been successfully posted.
        """
        from collections import OrderedDict

        # Dictionaries are not sorted. Extract and sort dates.
        dates: List[datetime.date] = sorted({
            date for week_menu in data.values() for date in week_menu
        })

        # Convert original data to ordered dictionary using sorted dates.
        # If there is no daily menu for certain restaurant the value is None.
        data: Dict[Restaurants, Dict[datetime.date, List[str]]] = {
            restaurant: OrderedDict((date, week_menu[date][1] if date in week_menu else None) for date in dates)
            for restaurant, week_menu in data.items()
        }

        slovenian_day_mapping = {
            1: "ponedeljek",
            2: "torek",
            3: "sredo",
            4: "četrtek",
            5: "petek",
            6: "soboto",
            7: "nedeljo",
        }

        msg = []
        for date in dates:
            # Choose any restaurant to get day names from
            msg.append(f"Dnevni meni za {slovenian_day_mapping[date.isoweekday()]}, {date:%d.%m.%Y}:\n")
            for restaurant, week_menu in data.items():
                if week_menu[date]:
                    msg.append(f" *<{restaurant.url}|{restaurant}>* _({restaurant.price})_:\n")
                    for item in week_menu[date]:
                        # Remove salad as it is included in every meal
                        item = item.replace(", solata", "")

                        msg.append(f"    • {item}\n")

        msg = "".join(msg)
        # print(msg)

        return self.post_message(msg)
