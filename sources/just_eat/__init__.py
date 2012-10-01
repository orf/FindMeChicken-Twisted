from sources import ChickenSource, ChickenPlace, GeoPoint
from twisted.internet import defer
from twisted.web.client import getPage
import logging
from lib import cache, BeautifulSoup, geo
from sources.just_eat import db
import time

IOS_USER_AGENT = "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_2 like Mac OS X; en-us) "\
                 "AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8H7 "\
                 "Safari/6533.18.5"
HOST = "http://www.just-eat.co.uk"
BASE_URL = HOST + "/area/{0}"

place_cache = cache.getCache("place_cache")
menu_cache = cache.getCache("menu_cache")

class JustEatSource(ChickenSource):
    NAME = "JustEat"
    MENUS = True

    @defer.inlineCallbacks
    def GetPlaceMenu(self, place_id):
        '''
        I take an ID and I fetch the menu from the website. Go me!
        '''
        cache_result = menu_cache.get(place_id)
        if cache_result is not None:
            defer.returnValue(cache_result)

        just_eat_page = yield getPage(str(HOST+place_id), agent=IOS_USER_AGENT)
        parser = BeautifulSoup.BeautifulSoup(just_eat_page)

        for tag in parser.findAll("h2", attrs={"class":"H2MC"}):
            if "chicken" in tag.text.lower():
                has_chicken = True


    @defer.inlineCallbacks
    def GetAvailablePlaces(self, location):

        cache_result = place_cache.get(location.postcode)
        if cache_result is not None:
            defer.returnValue(cache_result)

        if not location.postcode:
            logging.info("No postcode given in location, cannot get ChickenPlaces")
            defer.returnValue({})

        returner = {}

        just_eat_page = yield getPage(BASE_URL.format(location.postcode),
            agent=IOS_USER_AGENT)
        parser = BeautifulSoup.BeautifulSoup(just_eat_page)
        open_places_tag = parser.find(id="OpenRestaurants")
        page_places = {}
        for place_root_tag in open_places_tag.findAll("li"):
            place = {"title":place_root_tag.find("h2").text}
            place["identifier"] = place_root_tag.find("a")["href"]
            page_places[int(place_root_tag["data-restaurantid"])] = place

        if not page_places:
            defer.returnValue({})

        places_from_db, places_with_no_chicken = yield self.getPlacesFromDatabase(page_places.keys())
        returner.update(places_from_db)

        places_not_in_db = [i for i in set(page_places.keys()).difference(set(places_from_db.keys()))
                            if not i in places_with_no_chicken]

        if places_not_in_db:
            futures = [self.fetchChickenPlace(id,page_places[id]) for id in places_not_in_db]
            results = yield defer.DeferredList(futures)
            for success,result in results:
                if success:
                    if result[1]:
                        returner.update({result[0]:result[1]})

        place_cache.set(location.postcode, returner, timeout=60*20) # 20 min expire time

        defer.returnValue(returner)

    @defer.inlineCallbacks
    def fetchChickenPlace(self, id, info):
        '''
        I take an ID and a dictionary fetched from the JustEat page and I return a ChickenPlace with a geopoint.
        I have to fetch some stuff from the JustEat website though, which is silly :(
        I return (id, ChickenPlace)
        '''

        just_eat_page = yield getPage(str(HOST+info["identifier"]))
        print "Inserting ID %s"%id
        parser = BeautifulSoup.BeautifulSoup(just_eat_page)

        has_chicken = False
        for tag in parser.findAll("h2", attrs={"class":"H2MC"}):
            if "chicken" in tag.text.lower():
                has_chicken = True

        address_1 = parser.find(id="ctl00_ContentPlaceHolder1_RestInfo_lblRestAddress").text
        address_2 = parser.find(id="ctl00_ContentPlaceHolder1_RestInfo_lblRestZip").text

        address = "%s, %s"%(address_1, " ".join(address_2.split()))

        geopoint = yield geo.address_to_geopoint({0:address})

        place = ChickenPlace(
            id=info["identifier"],
            source=self.NAME,
            title=info["title"],
            address=address,
            location=geopoint[0],
            distance=None
        )

        db.pool.runOperation(
            """INSERT OR REPLACE INTO places (id, identifier, title, address, geopoint, created, has_chicken)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (id, place.id, place.title, place.address, "%s,%s"%(place.location.lat, place.location.long),
            time.time(), has_chicken)
        )
        # Return (id,None) if there is no chicken or (id,ChickenPlace) if there is chicken.
        defer.returnValue((id, [None, place][has_chicken]))


    @defer.inlineCallbacks
    def getPlacesFromDatabase(self, ids):
        print "Fetching IDs: %s"%ids
        a_week_ago = time.time() - 604800 # 604800 seconds in a week

        query = "SELECT * FROM places WHERE created > ? AND id IN (%s)"%",".join("?" for i in ids)
        params = [a_week_ago]
        params.extend(ids)
        places_from_database = yield db.pool.runQuery(query, params)

        returner = {}
        no_chicken = []

        for row in places_from_database:
            if row[6] == False:
                no_chicken.append(row[0])
            else:
                lat,long = row[4].split(",")
                returner[row[0]] = ChickenPlace(
                    id=row[1],
                    source=self.NAME,
                    title=row[2],
                    address=row[3],
                    location=GeoPoint(float(lat), float(long)),
                    distance=None
                )

        defer.returnValue((returner, no_chicken))

