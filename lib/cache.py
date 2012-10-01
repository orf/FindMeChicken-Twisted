from werkzeug.contrib.cache import FileSystemCache
import os

def getCache(name):
    return FileSystemCache(os.path.join("cache",name))