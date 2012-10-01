from klein import run, route, resource
from twisted.internet import defer
from lib import geo, geohash
import json
from sources import kfc, just_eat, Location, GeoPoint
import operator
import logging
import time


SOURCES = {
    "KFC":kfc.KFCSource(),
    "JustEat":just_eat.JustEatSource()
}

@route('/getChicken')
@defer.inlineCallbacks
def chicken_finder(request):
    t1 = time.time()
    lat, long = request.args["gps"][0].split(",")
    geopoint = GeoPoint(lat=float(lat), long=float(long))
    ghash = geohash.encode(geopoint.lat, geopoint.long, precision=10)
    postcode = yield geo.geopoint_to_postcode(geopoint, ghash)
    logging.info("Got postcode: %s"%postcode)
    location = Location(geopoint=geopoint, geohash=ghash, postcode=postcode)
    places = {}
    returner = []

    futures = []

    for name,instance in SOURCES.items():
        futures.append(instance.GetAvailablePlaces(location))
    results = yield defer.DeferredList(futures)

    for result in results:
        if result[0]:
            places.update(result[1])

    # Some sources may already have set the location. Filter those out and get the geopoints
    geopoints = yield geo.address_to_geopoint({l.id:l.address
                                               for l in places.values()
                                               if l.location is None})

    for id,point in geopoints.items():
        places[id] = places[id]._replace(location=point)

    for id,place in places.items():

        if not place.distance and not place.location:
            # We have a problem! For now exclude them from the results.
            # ToDo: Do something smart here.
            continue
        returner.append((geo.distance(location.geopoint, place.location), place))

    # Now each location hopefully has a resolved GeoPoint we can sort the Locations by the distance from us
    returner = [(d, p._asdict()) for d,p in sorted(returner, key=operator.itemgetter(0))]
    t2 = time.time()
    print "Request took %s"%(t2-t1)
    defer.returnValue(json.dumps(returner))