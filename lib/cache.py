from werkzeug.contrib.cache import FileSystemCache
from twisted.internet import defer
from twisted.python import log
import os


def getCache(name):
    return FileSystemCache(os.path.join("cache",name))



def CacheResult(func):
    @defer.inlineCallbacks
    def CacheWrapper(inst, location):
        cache_result = place_cache.get(inst.NAME + location.postcode)
        if cache_result is not None:
            log.msg("Got cached result for %s-%s"%(inst.NAME, location.postcode))
            defer.returnValue(cache_result)

        r = yield func(inst, location)
        place_cache.set(inst.NAME + location.postcode, r, timeout=60*30) # 30 min expire time

        defer.returnValue(r)

    return CacheWrapper


place_cache = getCache("results")