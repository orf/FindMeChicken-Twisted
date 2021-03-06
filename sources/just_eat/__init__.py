from sources import ChickenSource, ChickenPlace, GeoPoint, ChickenMenuItem
from twisted.internet import defer, reactor
from twisted.web.client import getPage
from twisted.python import log
from lib import cache, geo, db
from bs4 import BeautifulSoup
from ampoule import child, pool
from twisted.protocols import amp
import time
import json
import traceback

IOS_USER_AGENT = "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_2 like Mac OS X; en-us) "\
                 "AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8H7 "\
                 "Safari/6533.18.5"
HOST = "http://www.just-eat.co.uk"
BASE_URL = HOST + "/area/{0}"

ALLOWED_FOOD_TYPES = set(("pizza","kebabs","american"))

menu_cache = cache.getCache("menu_cache")

HAS_LXML = False
try:
    import lxml
    HAS_LXML = True
    del lxml
except ImportError:
    print "Lxml not detected: Consider installing it for a speed boost"

def get_parser(text):
    if HAS_LXML:
        return BeautifulSoup(text, "lxml")
    return BeautifulSoup(text)

class FetchChickenPlaceCommand(amp.Command):
    response = [('has_chicken', amp.Boolean()),
                ('place',amp.String()),
                ('id',amp.Integer())]

    arguments = [('id',amp.Integer()),
                 ('info',amp.String())]


class FetchChickenMenuCommand(amp.Command):
    response = [('response', amp.String())]
    arguments = [('id', amp.String())]

class FetchChickenMenu(child.AMPChild):
    @FetchChickenMenuCommand.responder
    @defer.inlineCallbacks
    def fetchChickenMenu(self, id):
        print "Running..."
        try:
            just_eat_page = yield getPage(str(HOST+id), agent=IOS_USER_AGENT,
                                          timeout=5)
        except Exception,e:
            print "Could not get just eat page: %s"%e
            defer.returnValue({"response":"{}"})

        parser = get_parser(just_eat_page)

        returner = []

        for tag in parser.findAll("li", attrs={"class":"cat"}):
            title_text = tag.find("h2").text
            if "chicken" in title_text.lower():
                # Extract the stuff
                for item in tag.find("ul").find_all("li", recursive=False):
                    try:
                        title = item.find("h3").text
                        price = item.find("span", attrs={"class":"varient vprice"}).text
                        returner.append(ChickenMenuItem(title, price)._asdict())
                    except Exception:
                        log.err()
        defer.returnValue({"response":json.dumps(returner)})


class FetchChickenPlace(child.AMPChild):
    @FetchChickenPlaceCommand.responder
    @defer.inlineCallbacks
    def fetchChickenPlace(self, id, info):
        try:
            r = yield self._fetchChickenPlace(id, info)
            defer.returnValue(r)
        except Exception,e:
            print traceback.format_exc()
            defer.returnValue(None)


    @defer.inlineCallbacks
    def _fetchChickenPlace(self, id, info):
        '''
        I take an ID and a dictionary fetched from the JustEat page and I return a ChickenPlace with a geopoint.
        I have to fetch some stuff from the JustEat website though, which is silly :(
        I return (id, ChickenPlace)
        '''
        info = json.loads(info)
        just_eat_page = yield getPage(str(HOST+info["identifier"]))
        t1 = time.time()
        print "Inserting ID %s"%id
        parser = get_parser(just_eat_page)

        print "%s - Parsed in %s"%(id,str(time.time()-t1))
        has_chicken = False
        for tag in parser.findAll("h2", attrs={"class":"H2MC"}):
            if "chicken" in tag.text.lower():
                has_chicken = True
                break

        print "%s - Chicken got in %s"%(id,str(time.time()-t1))
        addresses = []
        address_components = parser.find("span", attrs={"itemprop":"address"})

        for comp in address_components.findAll("span"):
            addresses.append(comp.text)

        address =(", ".join(addresses)).strip()
        print "%s - Page to GeoPoint is %s"%(id, str(time.time()-t1))

        if has_chicken:
            geopoint_res = yield geo.address_to_geopoint({0:address})
            geopoint = geopoint_res[0]
        else:
            geopoint = GeoPoint(0,0)

        place = ChickenPlace(
            Id=info["identifier"],
            Source=JustEatSource.NAME,
            Title=info["title"],
            Address=address,
            Location=geopoint,
            Distance=None,
            MenuAvailable=True
        )

        # Return (id,None) if there is no chicken or (id,ChickenPlace) if there is chicken.
        print "%s Page to return is %s"%(id, str(time.time()-t1))
        if has_chicken:
            returner = json.dumps(place._asdict())
        else:
            returner = json.dumps({})
        defer.returnValue({"has_chicken":has_chicken,
                           "place":returner,
                           "id":id})


class JustEatSource(ChickenSource):
    NAME = "JustEat"
    MENUS = True
    NEEDS_POSTCODE = True

    POOL = pool.ProcessPool(FetchChickenPlace, min=8,max=15)
    MENU_POOL = pool.ProcessPool(FetchChickenMenu, min=4, max=4)

    @defer.inlineCallbacks
    def Setup(self):
        yield self.POOL.start()
        reactor.addSystemEventTrigger("before", "shutdown", self.POOL.stop)
        reactor.addSystemEventTrigger("before", "shutdown", self.MENU_POOL.stop)
        defer.returnValue(None)

    @cache.CacheResult("menu")
    @defer.inlineCallbacks
    def GetPlaceMenu(self, place_id):
        '''
        I take an ID and I fetch the menu from the website. Go me!
        '''
        result = yield self.MENU_POOL.doWork(FetchChickenMenuCommand, id=place_id)
        defer.returnValue(result["response"])


    @cache.CacheResult("places")
    @defer.inlineCallbacks
    def GetAvailablePlaces(self, location):
        log.msg("Starting JustEat")

        returner = {}
        log.msg("Opening just eat page")
        just_eat_page = yield getPage(BASE_URL.format(location.postcode),
            agent=IOS_USER_AGENT)

        parser = get_parser(just_eat_page)
        open_places_tag = parser.find(id="OpenRestaurants")
        if open_places_tag is None:
            defer.returnValue({})

        page_places = {}
        for place_root_tag in open_places_tag.findAll("li"):

            place = {"title":place_root_tag.find("h2").text.strip()}

            types_of_food = set([x.strip()
                                 for x in place_root_tag.find("p", attrs={"class":"cuisineTypeList"}).text.lower().split(",")])

            if not ALLOWED_FOOD_TYPES.intersection(types_of_food):
                print "Skipping place %s"%place["title"]
                continue

            place["identifier"] = place_root_tag.find("a")["href"]
            page_places[place_root_tag["data-restaurantid"]] = place

        if not page_places:
            defer.returnValue({})

        places_from_db, places_with_no_chicken = yield db.getPlacesFromDatabase(self.NAME, page_places.keys())
        returner.update(places_from_db)

        places_not_in_db = [i for i in set(page_places.keys()).difference(set([x for x in places_from_db.keys()]))
                            if not i in places_with_no_chicken]
        print len(page_places.keys())
        print "%s places not in db"%len(places_not_in_db)
        if places_not_in_db:
            futures = [self.POOL.doWork(FetchChickenPlaceCommand, id=id,
                                        info=json.dumps(page_places[id])) for id in places_not_in_db]
            results = yield defer.DeferredList(futures)

            to_add = {}

            for success,result in results:
                if success:
                    if result["has_chicken"]:
                        place_dict = json.loads(result["place"])
                        place_dict["Location"] = GeoPoint(*place_dict["Location"])
                        place = ChickenPlace(**place_dict)
                        returner.update({result["id"]:place})
                        to_add[result["id"]] = place
                    else:
                        to_add[result["id"]] = None

            if len(to_add):
                db.addPlacesToDatabase(self.NAME, to_add)

        defer.returnValue(returner)