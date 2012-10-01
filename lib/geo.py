# Geocode stuff
from twisted.internet import defer
from twisted.web.client import getPage
from sources import GeoPoint
import settings, json, urllib
from lib import cache, geohash
import logging
import math

BASE_URI = "http://where.yahooapis.com/geocode"

address_cache = cache.getCache("geo_address")
postcode_cache = cache.getCache("geo_postcode")

@defer.inlineCallbacks
def geopoint_to_postcode(geopoint, ghash=None):
    result = yield geopoint_to_address(geopoint, ghash)
    pcode = result["postal"]
    if not pcode:
        defer.returnValue(None)
    else:
        defer.returnValue(pcode.split(" ")[0])

@defer.inlineCallbacks
def geopoint_to_address(geopoint, ghash=None):
    if ghash is None:
        ghash = geohash.encode(geopoint.lat, geopoint.long, precision=10)

    cache_result = postcode_cache.get(ghash)
    if cache_result is not None:
        defer.returnValue(cache_result)
    else:
        # Lookup the address
        page = yield getPage(get_reverse_uri(geopoint))
        address = json.loads(page)["ResultSet"]["Result"]
        postcode_cache.set(ghash, address)
        defer.returnValue(address)

@defer.inlineCallbacks
def address_to_geopoint(addresses):
    '''
    Give me a dictionary with {id:address} and I will give you
    a dictionary of {id:GeoPt}.
    '''
    returner, futures = {}, {}

    for id,address in addresses.items():
        loc = address_cache.get(address)
        if loc:
            returner[id] = loc
        else:
            futures[id] = getPage(get_lookup_uri(address))
    logging.info("Got %s addresses from the cache"%len(returner))
    if futures:
        yield defer.DeferredList(futures.values())

        for id,deferred in futures.items():
            parsed = json.loads(deferred.result)
            location = parsed["ResultSet"]["Result"]
            returner[id] = GeoPoint(float(location["latitude"]),
                                    float(location["longitude"]))
            address_cache.set(addresses[id], returner[id])

    defer.returnValue(returner)

def get_lookup_uri(address):
    return "%s?%s"%(BASE_URI, urllib.urlencode({
        "location":address,"country":"UK",
        "appid":settings.GEOCODE_APP_ID,
        "flags":"CJ"
    }))

def get_reverse_uri(geopoint):
    return "%s?%s"%(BASE_URI, urllib.urlencode({
        "location":"%s,%s"%(geopoint.lat, geopoint.long),
        "country":"UK",
        "appid":settings.GEOCODE_APP_ID,
        "flags":"J",
        "gflags":"R"
    }))

def distance(point1, point2):
    R = 3956 # Earth Radius in Miles

    lat1, long1 = (point1.lat, point1.long)
    lat2, long2 = (point2.lat, point2.long)

    dLat = math.radians(lat2 - lat1) # Convert Degrees 2 Radians
    dLong = math.radians(long2 - long1)
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    a = math.sin(dLat/2) * math.sin(dLat/2) + math.sin(dLong/2) * math.sin(dLong/2) * math.cos(lat1) * math.cos(lat2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = R * c
    return round(d,1)