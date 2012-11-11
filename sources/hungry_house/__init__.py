from sources import ChickenSource, ChickenPlace, GeoPoint, ChickenMenuItem
from twisted.internet import defer
from lib import cache, geo

FETCH_URL = "http://search.hungryhouse.co.uk/~m/restaurants/{0}/Burgers-_-Chicken/0-20?q=chicken"

place_cache = cache.getCache("hungry_house_place")

class HungryHouseSource(ChickenSource):
    NAME = "HungryHouse"
    MENUS = True

    @defer.inlineCallbacks
    def GetAvailablePlaces(self, location):
        if not location.postcode:
            defer.returnValue({})

