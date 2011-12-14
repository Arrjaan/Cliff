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

import Queue
import threading

class WBASched(threading.Thread):
  runq   = None
  running = False
  server  = None
  arg     = None

  def __init__(self, server):
    threading.Thread.__init__(self, name = "WBAExecThread")
    self.runq = Queue.Queue(32)
    self.server = server

  def exec_task(self, task):
    ev = threading.Event()

    self.runq.put((task, ev))

    while self.running and not ev.isSet():
      ev.wait(1.0)

  def stop(self):
    self.running = False

  def run(self):
    self.running = True
    while self.running:
      try:
        task_tupple = self.runq.get(block = True, timeout = 1)
        self.server(task_tupple[0])
        task_tupple[1].set() # Fire event that the task is done
        self.runq.task_done()
      except Queue.Empty:
        pass



if __name__ == "__main__":
  import time

  def tasker(e, i, running):
    while running():
      print "Tasker " + i + " putting task"
      e.exec_task(i + " Task " + str(time.time()))
      print "Tasker " + i + " after putting task"
    print "Leaving tasker " + i

  def runner(task):
    print "  >" + task
    time.sleep(2)
    print "  <" + task

  exc = WBASched(runner)
  exc.start()

  exc1 = WBASched(runner)
  exc1.start()

  run = True

  def running():
    return run

  t1 = threading.Thread(target = tasker, args = (exc, "#1.0", running))
  t1.start()

  t2 = threading.Thread(target = tasker, args = (exc, "#2.0", running))
  t2.start()

  t3 = threading.Thread(target = tasker, args = (exc, "#3.0", running))
  t3.start()

  t1 = threading.Thread(target = tasker, args = (exc1, "#1.1", running))
  t1.start()

  t2 = threading.Thread(target = tasker, args = (exc1, "#2.1", running))
  t2.start()

  t3 = threading.Thread(target = tasker, args = (exc1, "#3.1", running))
  t3.start()


  cnt = 2
  while cnt > 0:
    time.sleep(10)
    print "."
    cnt -= 1

  run = False
  exc.stop()
  exc1.stop()

