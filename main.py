import enum

__author__ = "Bojan Potočnik"


@enum.unique
class Restaurants(enum.Enum):
    ANTARO = r"http://www.antaro.si/antaro/dnevni_menu/"
    PERLA = r"http://www.antaro.si/perla/dnevni_menu/"


if __name__ == "__main__":
    pass
