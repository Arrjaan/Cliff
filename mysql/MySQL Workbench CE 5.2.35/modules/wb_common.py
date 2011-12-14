# Copyright (c) 2007, 2010, Oracle and/or its affiliates. All rights reserved.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; version 2 of the
# License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA

import os

write_log = False
logfile = "wbadebug.log"
debug_level = os.getenv("DEBUG_ADMIN")
if debug_level is not None:
  debug_level = int(debug_level)
  import inspect
else:
  debug_level = 0

if debug_level:
    print "Debug level -", debug_level

def dprint_ex(level, *args):
  if level <= debug_level:
    fr = inspect.currentframe().f_back
    cls = ""
    slf = fr.f_locals.get('self')
    if slf:
      cls = str(slf.__class__) + '.'
    ctx = inspect.getframeinfo(fr)
    # In Python 2.5, ctx is a tuple
    #method = cls + ctx.function + ':' + str(ctx.lineno)
    method = cls + ctx[2] + ":" + str(ctx[1])

    msg = method + " : " + " ".join([type(s) is str and s or str(s) for s in args])

    print msg
    if write_log:
      f = open(logfile, "a")
      f.write(msg)
      f.write("\n")
      f.close()



def splitpath(path):
  path_tuple = None

  idx = path.rfind('/')
  if idx == -1:
    idx = path.rfind('\\')

  if idx >= 0:
    path_tuple = (path[:idx + 1], path[1 + idx:])
  else:
    path_tuple = ('', path)

  return path_tuple



class OperationCancelledError(Exception):
    pass

# Put what is the wrong password in the exception message
class InvalidPasswordError(RuntimeError):
    pass

class PermissionDeniedError(RuntimeError):
    pass

class InvalidPathError(RuntimeError):
    pass
