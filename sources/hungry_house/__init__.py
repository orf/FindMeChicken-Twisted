from sources import ChickenSource, ChickenPlace, GeoPoint, ChickenMenuItem
from twisted.internet import defer
from twisted.web.client import getPage
from lib import cache
from twisted.python import log
from bs4 import BeautifulSoup, NavigableString
import urlparse

FETCH_URL = "http://search.hungryhouse.co.uk/restaurants/{0}/Burgers-_-Chicken/0-20?q=chicken"
CHROME_USER_AGENT = "Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11"

place_cache = cache.getCache("hungry_house_place")

class HungryHouseSource(ChickenSource):
    NAME = "HungryHouse"
    MENUS = True
    NEEDS_POSTCODE = True

    @cache.CacheResult
    @defer.inlineCallbacks
    def GetAvailablePlaces(self, location):
        log.msg("Fetching HungryHouse places")

        hungry_house_page = yield getPage(FETCH_URL.format(location.postcode),
                                        agent=CHROME_USER_AGENT)
        log.msg("Fetched, parsing")
        parser = BeautifulSoup(hungry_house_page)
        log.msg("Parsed")
        places = {}

        for place in parser.findAll("div", attrs={"class":"restsSearchItemRes"}):
            place_link = place.find("a", attrs={"class":"restPageLink"})
            place_id = place_link["href"]
            place_title = place_link["title"]

            place_map_div = place.find("div", attrs={"class":"restsMap"})
            place_address = " ".join([x.strip() for x in place_map_div.find("div")
                                      if isinstance(x, NavigableString)])
            place_address_uri = place_map_div.find("a", attrs={"class":"restsMapImage"})["style"]
            gps = urlparse.parse_qs(place_address_uri.split("'")[1])["center"][0].split(",")
            gp = GeoPoint(
                float(gps[0]), float(gps[1])
            )
            places[place_id] = ChickenPlace(
                Id=place_id,
                Source=self.NAME,
                Title=place_title,
                Address=place_address.strip("\t"),
                Location=gp,
                Distance=None,
                MenuAvailable=self.MENUS
            )

        defer.returnValue(places)


