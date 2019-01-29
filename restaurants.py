import enum

__author__ = "Bojan Potočnik"


@enum.unique
class Restaurants(enum.Enum):
    ANTARO = r"http://www.antaro.si/antaro/dnevni_menu/"
    PERLA = r"http://www.antaro.si/perla/dnevni_menu/"

    def __str__(self):
        return {
            self.ANTARO: "Antaro",
            self.PERLA: "Perla"
        }[self]

    @property
    def url(self) -> str:
        return {
            self.ANTARO: "http://www.antaro.si/antaro/dnevni_menu/",
            self.PERLA: "http://www.antaro.si/perla/dnevni_menu/"
        }[self]

    @property
    def price(self) -> str:
        return {
            self.ANTARO: "4.50 €, s solato 4.90 €",
            self.PERLA: "4.50 €, s solato 4.90 €"
        }[self]
