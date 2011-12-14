#  Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

import urllib2
import os

# import the wb module
from wb import *
# import the grt module
import grt

import mforms

# define this Python module as a GRT module
ModuleInfo = DefineModule(name= "WbUpdater", author= "Oracle Corp", version="1.0", description="Provides update related functionality for Workbench.")

@ModuleInfo.export(grt.STRING, grt.STRING, grt.STRING)
def downloadFile(url, destPath):
    if url.startswith("x-wbextra:"):
        url = "http:"+url.partition(":")[-1]

    try:
        import time
        f = urllib2.urlopen(url)
    except Exception, exc:
        raise
    try:
        file_size = int(f.info().getheaders("Content-Length")[0])
    except:
       file_size = -1
    try:
        outf = open(destPath, "w+b")
    except Exception, exc:
        raise Exception("Can't create file "+destPath+":"+str(exc))

    fetched = 0.0
    grt.send_info("0:%i:Downloading..." % file_size)
    while True:
        buf = f.read(8192)
        if not buf:
            break
        fetched += len(buf)
        outf.write(buf)
        grt.send_info("%i:%i:Downloading..."%(fetched,file_size))
    outf.close()
    grt.send_info("%i:%i:Finished"%(fetched,file_size))
    return destPath


@ModuleInfo.export(grt.INT, grt.STRING)
def checkUpdate(currentVersion):
    try:
        f = urllib2.urlopen("http://wb.mysql.com/workbench/version-check.php?version=%s&quiet=1"%currentVersion)
    except Exception, exc:
        print exc
        return -1

    data = f.read()
    if "No new version" in data:
        return 0
    return 1
    
