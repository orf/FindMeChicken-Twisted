from sources import ChickenSource, ChickenPlace, GeoPoint
from twisted.internet import defer
from twisted.web.client import getPage
from lib import cache
import json
import logging

BASE_URL = "http://www.kfc.co.uk/our-restaurants/search?latitude={0}&longitude={1}&radius=10&storeTypes="

kfc_cache = cache.getCache("kfc_places")

class KFCSource(ChickenSource):
    NAME = "KFC"
    MENUS = False

    @defer.inlineCallbacks
    def GetAvailablePlaces(self, location):

        cache_result = kfc_cache.get(location.geohash)
        if not cache_result is None:
            logging.info("Got KFC's from cache")
            defer.returnValue(cache_result)

        kfc_result = yield getPage(BASE_URL.format(location.geopoint.lat, location.geopoint.long))
        json_response = json.loads(kfc_result)

        returner = {}
        for place in json_response:
            chick_place = ChickenPlace(
                Source = self.NAME,
                Id = place["storeName"],
                Title = "KFC: " + place["storeName"].capitalize(),
                Address = "%s %s %s %s"%(place["address1"],
                                         place["address2"],
                                         place["address3"],
                                         place["postcode"]),
                Location = GeoPoint(place["latitude"], place["longitude"]),
                Distance = float(place.get("distance",-1)),
                MenuAvailable=False)
            returner[chick_place.Id] = chick_place

        kfc_cache.set(location.geohash, returner, timeout=60*60*24)
        defer.returnValue(returner)