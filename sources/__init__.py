# This is the base class for all sources.
from collections import namedtuple

Location = namedtuple("Location", "postcode geopoint geohash")
GeoPoint = namedtuple("GeoPoint","lat long")
ChickenPlace = namedtuple("ChickenPlace", "id source title address location distance")

class ChickenSource(object):
    # The name of the source
    NAME = ""
    # If the source supports fetching menus via GetPlaceMenu
    MENUS = None

    def Setup(self):
        '''
        Get the source ready for work
        '''
        return None

    def GetAvailablePlaces(self, location):
        '''
        I take a Location namedtuple which contains a postcode (maybe) and a lat-long pair as well as a geohash of the
        lat-long pair to make caching easy.
        I return a dictionary mapping an ID to a ChickenPlace. The ID should be unique as possible.
        '''
        raise NotImplementedError()

    def GetPlaceMenu(self, place_id):
        '''
        I take a ID of a Place and I return a list of tuples: [(Item Name, Item Price)], or None if no menu is found.
        '''
        raise NotImplementedError()
