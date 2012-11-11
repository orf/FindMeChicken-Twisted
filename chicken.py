from klein import run, route, resource
from twisted.internet import defer, reactor
from lib import geo, geohash
import json
from sources import kfc, just_eat, Location, GeoPoint, hungry_house
import operator
import logging
import time
import sys

SOURCES = {
    "KFC":kfc.KFCSource(),
    "JustEat":just_eat.JustEatSource(),
    "HungryHouse":hungry_house.HungryHouseSource()
}

@defer.inlineCallbacks
def setup_sources():
    for source in SOURCES.values():
        yield source.Setup()

    defer.returnValue(True)

reactor.callWhenRunning(setup_sources)

@route('/getMenu')
@defer.inlineCallbacks
def menu_finder(request):
    id = request.args["id"][0]
    source = request.args["source"][0]
    source_instance = SOURCES[source]
    request.setHeader("content-type", "application/json")
    if not source_instance.MENUS:
        defer.returnValue("[]")
    else:
        res = yield source_instance.GetPlaceMenu(id)
        defer.returnValue(res)

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
        if instance.NEEDS_POSTCODE and not location.postcode:
            continue
        futures.append(instance.GetAvailablePlaces(location))
    results = yield defer.DeferredList(futures)

    for result in results:
        if result[0]:
            places.update(result[1])

    # Some sources may already have set the location. Filter those out and get the geopoints
    geopoints = yield geo.address_to_geopoint({l.Id:l.Aaddress
                                               for l in places.values()
                                               if l.Location is None})

    for id,point in geopoints.items():
        places[id] = places[id]._replace(Location=point)

    for id,place in places.items():

        if not place.Distance and not place.Location:
            # We have a problem! For now exclude them from the results.
            # ToDo: Do something smart here.
            continue

        returner.append(place._replace(Distance=geo.distance(location.geopoint, place.Location)))

    # Now each location hopefully has a resolved GeoPoint we can sort the Locations by the distance from us
    returner = [p._asdict() for p in sorted(returner, key=operator.attrgetter('Distance'))[:10]]

    t2 = time.time()
    print "Request took %s"%(t2-t1)
    request.setHeader("content-type", "application/json")
    defer.returnValue(json.dumps(returner))

if "--run" in sys.argv:
    run("",8080)