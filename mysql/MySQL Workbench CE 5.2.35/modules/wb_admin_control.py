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

import re
import time
import Queue
import threading
import wb_admin_utils
from wb_admin_ssh import SSHDownException
from db_utils import MySQLConnection, MySQLError, QueryError

from wb_common import dprint_ex, OperationCancelledError

from wb_server_control import PasswordHandler, ServerControlShell, ServerControlWMI
from wb_server_management import ServerManagementHelper, SSH

import mforms

MYSQL_ERR_ACCESS_DENIED = 1045


#===============================================================================
#
#===============================================================================
# Handling object should have corresponding method if the object wants to receive 
# events. For event shutdown method name must be shutdown_event
class EventManager:
  valid_events = ['server_started_event', 'server_stopped_event', 'shutdown_event']

  def __init__(self):
    self.events = {}
    self.defer = False
    self.deferred_events = []

  def add_event_handler(self, event_name, handler):
    event_name += "_event"
    if hasattr(handler, event_name):
      handlers_list = None

      if event_name in self.events:
        handlers_list = self.events[event_name]
      else:
        handlers_list = []
        self.events[event_name] = handlers_list

      handlers_list.append(handler)
      dprint_ex(2, "Added ", handler.__class__, "for event", event_name)
    else:
      print "Error! ", handler.__class__, " does not have method", event_name

  def defer_events(self):
    self.defer = True

  def continue_events(self):
    self.defer = False
    for ev_name in self.deferred_events:
      self.event(ev_name)
    self.deferred_events = []

  def event(self, name):
    if self.defer:
      self.deferred_events.append(name)
      return

    name += "_event"
    if name not in self.valid_events:
      print "EventManager: invalid event", name
    elif name in self.events:
      dprint_ex(3, "Found event", name, "in list")
      for obj in self.events[name]:
        if hasattr(obj, name):
          dprint_ex(3, "Passing event", name, "to", obj.__class__)
          getattr(obj, name)()
    else:
      dprint_ex(3, "Found valid but unrequested event", name, "in list")

#===============================================================================
import thread
class SQLQueryExecutor:
    dbconn = None
    mtx     = None

    def __init__(self, dbconn):
        dprint_ex(1, "Constructing SQL query runner, dbconn", dbconn)
        self.mtx = threading.Lock()
        self.dbconn = dbconn

    def is_connected(self):
        return self.dbconn is not None and self.dbconn.is_connected

    def close(self):
        if self.is_connected():
            self.mtx.acquire()
            try:
              self.dbconn.disconnect()
            finally:
              self.mtx.release()
        self.dbconn = None

    def exec_query(self, query):
        result = None
        self.mtx.acquire()
        try:
            if self.is_connected():
                result = self.dbconn.executeQuery(query)
        finally:
            self.mtx.release()
        return result

    def execute(self, query):
        result = None
        self.mtx.acquire()
        try:
            if self.is_connected():
                result = self.dbconn.execute(query)
        finally:
            self.mtx.release()
        return result


#===============================================================================

#-------------------------------------------------------------------------------
def wba_arithm(linenr, line, op, value):
  fv = line
  # We shoould have get two numbers
  try:
    fv = float(line.strip(" \r\t\n,.:"))
    value = float(value)
    if (op == "/"):
      if value != 0:
        fv /= value
    elif (op == "*"):
      fv *= value
    elif (op == "+"):
      fv += value
    elif (op == "-"):
      fv -= value
  except ValueError, e:
    fv = line

  return (str(fv), 0) # text and status. 0 - success

#-------------------------------------------------------------------------------
def wba_token(linenr, line, sep, nrs):
  tokens = filter(lambda s: len(s) > 0, line.split(sep))
  out = ""
  l = len(tokens)
  for nr in nrs:
    if nr < l and nr >= 0:
      out += tokens[nr] + sep
  return (out.strip(sep), 0)

#-------------------------------------------------------------------------------
def wba_filter(linenr, line, pattern):
  if line.find(pattern) >= 0:
    return (line, 0)
  return ("", 1)

#-------------------------------------------------------------------------------
def wba_line(linenr, line, expected_linenr):
  if linenr == expected_linenr:
    return (line, 0)
  return ("", 1)

#-------------------------------------------------------------------------------
def parse_wba_token(text):
  f = None

  p = text[9:].strip(" |\r\n\t()").split(",")
  args = []
  try:
    args = map(lambda x: int(x) ,p[1:])
    f = (wba_token, (p[0].strip(" ").strip("'"), tuple(args)))
  except ValueError, e:
    print "Wrong filter format: ", text, ". Required format is wba_token('pattern_symbol', # of token, optional # of tokens)"
    f = None

  return f

#-------------------------------------------------------------------------------
def parse_wba_filter(text):
  f = None

  if len(text) > 11:
    p = text.strip(" |\r\n\t")[11:][:-1]
    f = (wba_filter, (p,))

  return f

#-------------------------------------------------------------------------------
def parse_wba_line(text):
  f = None

  try:
    if len(text) > 8:
      p = int(text[8:].strip(" |\r\n\t()"))
      f = (wba_line, (p,))
  except ValueError, e:
    print str(e), " in filter line ", text
    f = None

  return f

#-------------------------------------------------------------------------------
def parse_wba_arithm(text):
  f = None

  if len(text) > 10:
    p = text[10:].strip(" |\r\n\t()").split(",")
    f = (wba_arithm, tuple(p))

  return f

#-------------------------------------------------------------------------------
filter_parsers = [("wba_token", parse_wba_token), ("wba_filter", parse_wba_filter), ("wba_line", parse_wba_line), ("wba_arithm", parse_wba_arithm)]

#-------------------------------------------------------------------------------
def build_filters(script):
  filters = []
  text = script
  leave = False

  if text is None:
    return (text, filters)

  while not leave:
    filter_was_parsed = False
    idx = text.rfind('|')
    if idx >= 0:
      raw_filter = text[idx:].strip(" \r\t\n|")
      for (pattern, parser) in filter_parsers:
        if raw_filter.find(pattern) == 0:
          parsed_filter = parser(raw_filter)
          if parsed_filter is not None:
            filters.insert(0, parsed_filter)
            filter_was_parsed = True
            break
          else:
            text = script
            filters = []
            leave = True
            break

      if filter_was_parsed:
        text = text[:idx]
      else:
        leave = True
    else:
      leave = True

  return (text, filters)


#-------------------------------------------------------------------------------
def empty_dbg(x):
  pass

def apply_filters(raw_text, filters, dbg = None):
  if dbg is None:
    dbg = empty_dbg

  if raw_text is None:
    return (None, 1)

  out = ""
  code = None
  lines = raw_text.split("\n")

  for f in filters:
    filter_status_code = 1
    new_lines = []
    dbg(f[0].__name__ + " " + str(f[1:]) + "\n")
    for i,line in enumerate(lines):
      line = line.strip("\r")
      orig_line = line
      (line, cur_code) = f[0](i, line, *f[1])
      dbg("   " + str(i) + " '" + orig_line + "' -> '" + line + "'. cur_code = " + str(cur_code) + "\n")
      if len(line) > 0:
        new_lines.append(line)

      if cur_code == 0:
        filter_status_code = 0

    lines = new_lines

    if code is None:
      code = filter_status_code
    elif code == 0:
      code = filter_status_code
    dbg(f[0].__name__ + " exec code = " + str(code) + "\n-------------\n")

  dbg("Filtered text:\n")
  for line in lines:
    if len(line) > 0:
      out += line + '\n'
      dbg(line + '\n')

  dbg("Filters execution code = " + str(code) + "\n===================\n")
  return (out, code) # return last code from filters

def run_filter_debugger(loginInfo, serverInfo):
  wb_admin_utils.run_filter_debugger(loginInfo, serverInfo, build_filters, apply_filters)


#===============================================================================

class WbAdminControl:
    server_helper = None # Instance of ServerManagementHelper for doing file and process operations on target server
    server_control = None # Instance of ServerControlBase to do start/stop/status of MySQL server
    
    ssh = None
    sql = None
    
    raw_version = "unknown"
    server_version = "unknown"
    
    def __init__(self, server_profile,
                            connect_sql=True):

        self.server_control = None
        self.events   = EventManager()
        self.defer_events() # continue events should be called when all listeners are registered, that happens later in the caller code
                          # Until then events are piled in the queue

        self.server_profile = server_profile
        self.server_control_output_handler = None
        
        self.task_queue = Queue.Queue(512)
        
        self.sql_enabled = connect_sql
        self.password_handler = PasswordHandler(server_profile)
        
        self.server_active_plugins = set()
        
        self.running = True

        self.add_me_for_event("server_started", self)
        self.add_me_for_event("server_stopped", self)
        # We'll use server_status to store information from self.sql_status_callback
        # The callback is called on success and failure of execution of a query
        self.server_status = {}

        
    def init(self):
        # connect SQL
        while self.sql_enabled:
            try:
                self.connect_sql()
                break
            except MySQLError, err:
                if err.code == MYSQL_ERR_ACCESS_DENIED:
                    # Invalid password, request password
                    r = mforms.Utilities.show_error("Could not connect to MySQL Server at %s" % err.location,
                            "Could not connect to MySQL server: %s\nClick Continue to proceed without functionality that requires a DB connection." % err,
                            "Retry", "Cancel", "Continue")
                    if r == mforms.ResultOk:
                        continue
                    elif r == mforms.ResultCancel:
                        raise OperationCancelledError("Connection cancelled")
                    else:
                        # continue without a db connection
                       self.sql_enabled = False 
                else:
                    if mforms.Utilities.show_warning("Could not connect to MySQL Server at %s" % err.location,
                            "%s\nYou may continue anyway, but some functionality will be unavailable." % err,
                            "Continue", "Cancel", "") != mforms.ResultOk:
                        raise OperationCancelledError("Could not connect to MySQL")
                    else:
                        self.sql_enabled = False

        if self.server_profile.uses_ssh:
            try:
                self.ssh = SSH(self.server_profile, self.password_handler)
            except OperationCancelledError, e:
                self.ssh = None
                if not self.sql_enabled:
                    raise OperationCancelledError("SSH connection cancelled")
                else:
                    if mforms.Utilities.show_warning('SSH connection cancelled', 
                            "Would you like to continue with a database connection only?\nSome features will be disabled.", 
                            "Continue", "Cancel", "") != mforms.ResultOk:
                        raise OperationCancelledError("SSH connection cancelled")

            except SSHDownException, e:
                self.ssh = None
                if self.sql_enabled:
                    if mforms.Utilities.show_warning('SSH connection failed', 
                            "Check if the SSH server is up on the remote side.\nYou may continue anyway, but some functionality will be unavailable", 
                            "Continue", "Cancel", "") != mforms.ResultOk:
                        raise OperationCancelledError("Could not connect to SSH server")
                else:
                    mforms.Utilities.show_warning('SSH connection failed', 
                            "Check if the SSH server is up on the remote side.", "OK", "", "")
        else:
            self.ssh = None

        # init server management helper (for doing remote file operations, process management etc)
        self.server_helper = ServerManagementHelper(self.server_profile, self.ssh)
        
        if self.server_helper:
             self.server_profile.expanded_config_file_path = self.server_helper.shell.expand_path_variables(self.server_profile.config_file_path)
    
        # init server control instance appropriate for what we're connecting to
        if not self.server_profile.admin_enabled:
            self.server_control = None
        else:
            if self.server_profile.uses_wmi:
                self.server_control = ServerControlWMI(self.server_profile, self.server_helper, self.password_handler)
                self.server_control.set_filter_functions(build_filters, apply_filters)
            elif self.server_profile.uses_ssh or self.server_profile.is_local:
                self.server_control = ServerControlShell(self.server_profile, self.server_helper, self.password_handler)
                self.server_control.set_filter_functions(build_filters, apply_filters)
            else:
                dprint_ex(1, "uses_ssh: %i uses_wmi: %i" % (self.server_profile.uses_ssh, self.server_profile.uses_wmi))
                raise Exception("Unknown management method selected. Server Profile is possibly inconsistent")


    def shutdown(self):
        self.events.event('shutdown')
        self.running = False
        self.disconnect_sql()
        if self.ssh:
            self.ssh.close()

    #---------------------------------------------------------------------------
    def is_server_running(self, verbose = 0, force_process_check = False):
        # Check recent information from query runs. If last query (not older than 4 secs)
        # was performed successfully, then we imply that server is up.
        ret = "unknown"

        use_process_check = True

        if not self.server_control:
          use_process_check = False
          force_process_check = False

        if not force_process_check:
            ts = time.time()
            connid = self.server_profile.db_connection_params.hostIdentifier
            if connid is not None:
                (status, stime) = self.server_status.get(connid, (False, 0))
                # time diff is not sufficient for MacOS->RemoteWin, so WBA 
                # has recurring sql connection drop with follwing re-connect.
                if ts - stime < 8 and status:
                    ret = 'running'
                    use_process_check = False

        if use_process_check:
            ret = self.server_control.get_status(verbose=verbose)

        return ret

    #---------------------------------------------------------------------------
    def uitask(self, task, *args):
        self.task_queue.put((task, args))

    def process_ui_task_queue(self):
        while not self.task_queue.empty():
            func, args = self.task_queue.get()
            func(*args)
            self.task_queue.task_done()

    """
      Adds object for event named @event. In order for object to handle event
    it needs to conform to some requirements. For example if there is a need for 
    some object to handle an event named 'server_started', the object's class must
    have method named server_started_event. Valid event names can be found in 
    EventManager class.

    param event: name of the event, for example 'server_started'
    param obj: object which method named <event_name>_event will be called
    """
    def add_me_for_event(self, event, obj):
        self.events.add_event_handler(event, obj)

    #---------------------------------------------------------------------------
    """
      Tells to notify all listener objects that event occured.
    """
    def event(self, name):
        self.events.event(name)


    def event_from_main(self, event_name):
        self.uitask(self.event, event_name)

    #---------------------------------------------------------------------------
    """
    This method should not be used outside of MyCtrl. The aim of the method to
    queue coming events for later processing. This is used when events start tp
    appear at load stage, but all listeners may not be registered yet.
    """
    def defer_events(self):
        self.events.defer_events()

    #---------------------------------------------------------------------------
    """
    This method should not be used outside of MyCtrl. It indicate that deferred
    events can be delivered to listeners and resumes normal events flow processing.
    """
    def continue_events(self):
        self.events.continue_events()


    def expand_path_variables(self, path):
        ret = path
        if self.server_helper:
            ret = self.server_helper.shell.expand_path_variables(self.server_profile.config_file_path)
        return ret

    #---------------------------------------------------------------------------
    def server_started_event(self):
        self.uitask(self.connect_sql)


    #---------------------------------------------------------------------------
    def server_stopped_event(self):
        self.uitask(self.disconnect_sql)
    

    #---------------------------------------------------------------------------
    def get_new_sql_connection(self, interactive):
        connection = None
        try:
            connection = MySQLConnection(self.server_profile.db_connection_params, self.sql_status_callback)
            connection.connect()
        except MySQLError, err:
            print "Error creating SQL connection for monitoring: %r" % err
            connection = None
            if interactive:
                mforms.Utilities.show_error("Connection Error", "Error connecting to MySQL: %s\nMySQL stat graphs may be disabled." % err, "OK", "", "")
            return None
          
        return connection

    #---------------------------------------------------------------------------
    """
    This method is passed to MySQLConnection.__init__. MySQLConnection will call
    this method when connection created/destroyed, also on success or error when
    executing query
    """
    def sql_status_callback(self, code, error, connect_info):
        connid = connect_info.hostIdentifier
        self.server_status = {}
        ts = time.time()

        if connid is not None:
            if code == 0:
                self.server_status[connid] = (True, ts)
        else:
            e = QueryError(code, error)
            if e.is_connection_error():
                self.server_status[connid] = (False, ts)

    #---------------------------------------------------------------------------
    def connect_sql(self): # from GUI thread only, throws MySQLError
        if self.sql is None or not self.sql.is_connected():
            connection = MySQLConnection(self.server_profile.db_connection_params, self.sql_status_callback)
            connection.connect()

            self.sql = SQLQueryExecutor(connection)

        if self.sql and self.sql.is_connected():
            # perform some server capabilities checking
            
            # check version
            result = self.exec_query("select version() as version")
            if result and result.nextRow():
                self.server_version= result.stringByName("version")
                self.raw_version = self.server_version
                dprint_ex(1, "Got MySQL version -", self.server_version)
            
            result = self.exec_query("show plugins")
            # check whether Windows authentication plugin is available
            while result and result.nextRow():
                name = result.stringByName("Name")
                status = result.stringByName("Status")
                plugin_type = result.stringByName("Type")
                if status == "ACTIVE":
                    self.server_active_plugins.add((name, plugin_type))

            dprint_ex(1,"Created SQL connection to MySQL server. Server version is", self.server_version, ", conn status = ", self.is_sql_connected(), ", active plugins = ", str(self.server_active_plugins))
        else:
            print "Failed to connect to MySQL server"

    #---------------------------------------------------------------------------
    def disconnect_sql(self):
        dprint_ex(3, "Enter")
        if self.sql:
            self.sql.close()
        self.sql = None
        self.server_version = "unknown"
        dprint_ex(3, "Leave")

    #---------------------------------------------------------------------------
    def is_sql_connected(self):
        ret = False
        if self.sql:
            ret = self.sql.is_connected()
        dprint_ex(2, "ret = ", ret)
        return ret

    #---------------------------------------------------------------------------
    def sql_ping(self):
      ret = False
      if self.sql and self.sql.is_connected():
        try:
          self.sql.exec_query("select 1")
          ret = True
        except QueryError, e:
          if not e.is_connection_error():
            ret = True # Any other error except connection ones is from server
      else:
        try:
          self.connect_sql()
        except MySQLError, e:
          pass # ignore connection errors, since it likely means the server is down

        # Do not do anything for now, connection status check will be perfomed
        # on the next sql_ping call
      return ret

    #---------------------------------------------------------------------------
    def exec_query(self, q):
        ret = None
        if self.sql is not None:
            try:
                ret = self.sql.exec_query(q)
            except QueryError, e:
                print "ctrl_be: Query Error", e
                if e.is_connection_error():
                    dprint_ex(1, "Loss of connection to mysql server was detected.")
                    self.disconnect_sql()
                    if e.is_error_recoverable():
                        dprint_ex(1, "Error is recoverable. Reconnecting to MySQL server.")
                        self.connect_sql()
                else: # if exception is not handled, give a chance to the caller do it
                    raise e
        else:
            dprint_ex(1,"sql connection is down")

        return ret

    def exec_sql(self, q):
      ret = None
      if self.sql is not None:
        try:
          ret = self.sql.execute(q)
        except QueryError, e:
          print "ctrl_be: Query Error", e
          if e.is_connection_error():
            dprint_ex(1, "Loss of connection to mysql server was detected.")
            self.disconnect_sql()
            if e.is_error_recoverable():
              dprint_ex(1, "Error is recoverable. Reconnecting to MySQL server.")
              self.connect_sql()
          else:
            raise e
      else:
        dprint_ex(1,"sql connection is down")

      return ret

    #---------------------------------------------------------------------------    
    def get_server_version(self):
      if type(self.server_version) is str:
        self.server_version = self.server_version.lower()

      if self.server_version is not None and type(self.server_version) is not tuple and self.server_version != "unknown":
        version = ""
        res = re.search('(\d+\.\d+\.*\d*)*', self.server_version)
        if len(res.groups()) > 0:
          match = res.groups()[0]
          if res is not None and match is not None:
            version = match.strip(' ')

        converted = True
        try:
          v = tuple([int(x) for x in version.split('.')])
        except ValueError:
          converted = False
        if converted:
          self.server_version = v
          #print "get_server_version: parsed", self.server_version
      elif type(self.server_version) is not tuple:
        self.server_version = (5,1)

      return self.server_version

    #---------------------------------------------------------------------------    
    def open_ssh_session_for_monitoring(self):
        ssh = SSH(self.server_profile, self.password_handler)

        return ssh

    #---------------------------------------------------------------------------    
    def is_ssh_connected(self):
        return self.ssh is not None

    #---------------------------------------------------------------------------    
    def execute_filtered_command(self, script, as_admin = False, admin_password = False, verbose = None):
        dprint_ex(3, "Enter: ", script)
        (script, filters) = build_filters(script)

        output_text = []
        def gather_output(line, l=output_text):
            l.append(line) 
        retcode = self.server_helper.execute_command(script, as_admin=as_admin, admin_password=admin_password, output_handler=gather_output)
        output_text = "".join(output_text)

        if verbose:
            self.output("Raw output from '%s': status - %s, text - %s" % (script, retcode, output_text))

        (filtered_text, filters_code) = apply_filters(output_text, filters)

        dprint_ex(3, "execute_filtered_command: ", script, " => ", str(filtered_text), "(%s)"%str(filters_code))

        if filters_code is not None:
            if retcode is not None:
                retcode = int(retcode) or filters_code
            else:
                retcode = filters_code

        dprint_ex(3, "Done:", script, ", retcode =", retcode, " filters_code =", str(filters_code))
        return (filtered_text, retcode)





# === Unit tests ===
def unit_tests(settings, ctrl_be):
  print "is running", ctrl_be.is_running()
  return ()


if __name__ == "__main__":
    test_nr = 0

    #-------------    
    if run_cmd("echo 'Test'", 0, "")[1] is not None:
        print "Test", test_nr, " - Ok"
    else:
        print "Test", test_nr, " - Fail"
    test_nr += 1
    
    #-------------    
    if run_cmd("", 1, "")[1] is None:
        print "Test", test_nr, " - Ok"
    else:
        print "Test", test_nr, " - Fail"
    test_nr += 1

    #-------------    
    import getpass
    password = getpass.getpass("Enter password: ")

    if run_cmd("", 1, password)[1] is None:
        print "Test", test_nr, " - Ok"
    else:
        print "Test", test_nr, " - Fail"
    test_nr += 1

    #-------------    
    if run_cmd("echo Test", 1, password)[1] == 0:
        print "Test", test_nr, " - Ok"
    else:
        print "Test", test_nr, " - Fail"
    test_nr += 1

    #-------------    
    if run_cmd("/bin/false", 1, password)[1] == 1:
        print "Test", test_nr, " - Ok"
    else:
        print "Test", test_nr, " - Fail"
    test_nr += 1

    #-------------    
    result = run_cmd("echo 'Test\ message'", 0, None)
    if result[1] == 0 and result[0].strip("\r\n ") == "Test message":
        print "Test", test_nr, " - Ok"
    else:
        print "Test", test_nr, " - Fail"
    test_nr += 1

