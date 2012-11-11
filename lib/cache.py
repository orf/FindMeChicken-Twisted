from werkzeug.contrib.cache import FileSystemCache
from twisted.internet import defer
from twisted.python import log
from sources import Location
import os

def getCache(name):
    return FileSystemCache(os.path.join("cache",name))



def CacheResult(name):

    _cache = getCache(name)

    def wrapper(func):
        @defer.inlineCallbacks
        def CacheWrapper(inst, arg):
            if isinstance(arg, Location):
                k = arg.postcode
            else:
                k = arg
            cache_result = _cache.get(inst.NAME + k)
            if cache_result is not None:
                log.msg("Got cached result for %s-%s"%(inst.NAME, k))
                defer.returnValue(cache_result)

            r = yield func(inst, arg)
            _cache.set(inst.NAME + k, r, timeout=60*30) # 30 min expire time

            defer.returnValue(r)

        return CacheWrapper

    return wrapper


place_cache = getCache("results")