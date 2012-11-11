# Database access for just_eat
from twisted.enterprise import adbapi
from sources import ChickenPlace, GeoPoint
from twisted.internet import defer
import settings
import sqlite3
import time

def addPlacesToDatabase(source, places):
    # Places is a dict = {id:ChickenPlace}
    insert_command =\
    """INSERT OR REPLACE INTO places (id, source, identifier, title, address, geopoint, created, has_chicken)
     %s"""%("UNION ".join(["SELECT ?, ?, ?, ?, ?, ?, ?, ? " for x in xrange(len(places))]))

    args = []
    for id,place in places.items():
        if place is None:
            args.extend((id, source, "", "", "", "", time.time(), False) )
        else:
            args.extend(
                (id, source, place.Id, place.Title, place.Address,
                    "%s,%s"%(place.Location.lat, place.Location.long),
                    time.time(), True))
    print insert_command
    print args
    pool.runQuery(insert_command, args)


@defer.inlineCallbacks
def getPlacesFromDatabase(source, ids):
    print "Fetching IDs: %s"%ids
    a_week_ago = time.time() - 604800 # 604800 seconds in a week

    query = "SELECT * FROM places WHERE source = ? AND created > ? AND id IN (%s)"%",".join("?" for i in ids)
    params = [source, a_week_ago]
    params.extend(ids)
    places_from_database = yield pool.runQuery(query, params)

    returner = {}
    no_chicken = []

    for row in places_from_database:
        if row[7] == False:
            no_chicken.append(row[0])
        else:
            lat,long = row[5].split(",")
            returner[row[0]] = ChickenPlace(
                Id=row[2],
                Source=source,
                Title=row[3],
                Address=row[4],
                Location=GeoPoint(float(lat), float(long)),
                Distance=None,
                MenuAvailable=True
            )

    defer.returnValue((returner, no_chicken))

def setup_database():
    conn = sqlite3.connect(settings.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS places (
        id INTEGER NOT NULL,
        source TEXT NOT NULL,
        identifier TEXT NOT NULL,
        title TEXT NOT NULL,
        address TEXT NOT NULL,
        geopoint TEXT NOT NULL,
        created INTEGER NOT NULL,
        has_chicken BOOLEAN NOT NULL,

        PRIMARY KEY (id, source)
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS id_index ON places (identifier ASC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS created_index ON places (created ASC)")
    cursor.close()
    conn.close()

setup_database()

pool = adbapi.ConnectionPool("sqlite3", settings.DB_NAME, check_same_thread=False)

