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

from mforms import newBox, newLabel, newTreeView, newTabView, newButton
import mforms
from wb_admin_utils import not_running_warning_label, not_running_warning_label_text

class LogBox(mforms.Box):
    owner = None
    total_count = 0
    show_start = 0
    show_count = 50
    showing_newest = True

    def __init__(self, owner):
        mforms.Box.__init__(self, False)
        self.set_managed()
        self.owner = owner
    
        self.set_padding(8)
        self.set_spacing(8)

        bbox = newBox(True)
        bbox.set_spacing(8)
        self.add_end(bbox, False, True)

        self.range_label = newLabel("")
        bbox.add(self.range_label, True, True)

        self.view_button = newButton()
        self.view_button.set_text("Copy Details")
        bbox.add(self.view_button, False, True)
        self.view_button.add_clicked_callback(self.copy_details)

        self.bof_button = newButton()
        self.bof_button.set_text("Oldest")
        bbox.add(self.bof_button, False, True)
        self.bof_button.add_clicked_callback(self.go_bof)

        self.back_button = newButton()
        self.back_button.set_text("Previous %i"%self.show_count)
        bbox.add(self.back_button, False, True)
        self.back_button.add_clicked_callback(self.go_back)

        self.next_button = newButton()
        self.next_button.set_text("Next %i"%self.show_count)
        bbox.add(self.next_button, False, True)
        self.next_button.add_clicked_callback(self.go_next)

        self.eof_button = newButton()
        self.eof_button.set_text("Newest")
        bbox.add(self.eof_button, False, True)
        self.eof_button.add_clicked_callback(self.go_eof)

        self.refresh_button = newButton()
        self.refresh_button.set_text("Refresh")
        bbox.add(self.refresh_button, False, True)
        self.refresh_button.add_clicked_callback(self.refresh)
        
        
    def refresh(self):
        self.range_label.set_text("Showing entries %i to %i out of %i" % (max(self.show_start, 0), self.show_start+self.show_count, self.total_count))

        self.bof_button.set_enabled(self.show_start > 0)
        self.eof_button.set_enabled(self.show_start + self.show_count < self.total_count)
        self.back_button.set_enabled(self.show_start > 0)
        self.next_button.set_enabled(self.show_start + self.show_count < self.total_count)


        
    def go_bof(self):
        self.show_start = 0
        self.showing_newest = False
        self.refresh()


    def go_eof(self):
        self.show_start = max(self.total_count - self.show_count/2, 0)
        self.showing_newest = True
        self.refresh()


    def go_next(self):
        self.show_start += self.show_count
        self.showing_newest = self.show_start + self.show_count >= self.total_count
        self.refresh()


    def go_back(self):
        self.show_start -= self.show_count
        self.showing_newest = False
        if self.show_start < 0:
            self.show_start = 0
        self.refresh()


class GeneralLogView(LogBox):
    owner = None
    def __init__(self, owner):
        LogBox.__init__(self, owner)

        self.tree = tree = newTreeView(mforms.TreeDefault)
        tree.add_column(mforms.StringColumnType, "Time", 150, False)
        tree.add_column(mforms.StringColumnType, "From", 120, False)
        tree.add_column(mforms.StringColumnType, "Thread", 80, False)
        #tree.add_column(mforms.StringColumnType, "Server", False)
        tree.add_column(mforms.StringColumnType, "Command Type", 80, False)
        tree.add_column(mforms.StringColumnType, "Detail", 500, False)
        tree.end_columns()

        self.add(tree, True, True)
        

    def refresh(self):
        try:
            result = self.owner.ctrl_be.exec_query("SELECT count(*) AS count FROM mysql.general_log")
        except Exception, e:
            raise Exception("Error fetching log contents: %s" % e)
        if not result or not result.nextRow():
            raise Exception("Error fetching log contents")
        self.total_count = result.intByName("count")

        if self.showing_newest:
            if self.show_count < self.total_count:
                self.show_start = self.total_count - self.show_count
            else:
                self.show_start = self.show_count
            if self.show_start < 0:
                self.show_start = 0
        try:
            result = self.owner.ctrl_be.exec_query("SELECT * FROM mysql.general_log ORDER BY event_time DESC LIMIT %i, %i"  % (max(self.total_count - self.show_start, 0), self.show_count))
        except Exception, e:
            raise Exception("Error fetching log contents: %s" % e)

        self.tree.clear_rows()
        while result.nextRow():
            event_time= result.stringByName("event_time")
            user_host= result.stringByName("user_host")
            thread_id= result.intByName("thread_id")
            server_id= result.intByName("server_id")
            command_type= result.stringByName("command_type")
            argument= result.stringByName("argument")
            
            row = self.tree.add_row()
            self.tree.set_string(row, 0, event_time)
            self.tree.set_string(row, 1, user_host)
            self.tree.set_string(row, 2, "%s @ %s"%(thread_id, server_id))
            self.tree.set_string(row, 3, command_type)
            self.tree.set_string(row, 4, argument)

        LogBox.refresh(self)


    def copy_details(self):
        sel = self.tree.get_selected()
        if sel >= 0:
            text = self.tree.get_string(sel, 4)
            mforms.Utilities.set_clipboard_text(text)


class SlowLogView(LogBox):
    owner = None
    def __init__(self, owner):
        LogBox.__init__(self, owner)

        self.tree = tree = newTreeView(mforms.TreeDefault)
        tree.add_column(mforms.StringColumnType, "Start Time", 150, False)
        tree.add_column(mforms.StringColumnType, "From", 120, False)
        tree.add_column(mforms.StringColumnType, "Query Time", 150, False)
        tree.add_column(mforms.StringColumnType, "Lock Time", 150, False)
        tree.add_column(mforms.StringColumnType, "Rows Sent", 50, False)
        tree.add_column(mforms.StringColumnType, "Rows Examined", 50, False)
        tree.add_column(mforms.StringColumnType, "Db", 80, False)
        tree.add_column(mforms.StringColumnType, "Last Insert ID", 50, False)
        tree.add_column(mforms.StringColumnType, "Insert ID", 50, False)
        tree.add_column(mforms.StringColumnType, "Server ID", 50, False)
        tree.add_column(mforms.StringColumnType, "SQL", 500, False)
        tree.end_columns()

        self.add(tree, True, True)


    def refresh(self):
        result = self.owner.ctrl_be.exec_query("SELECT count(*) AS count FROM mysql.slow_log")
        if not result.nextRow():
            raise Exception("Error fetching slow log contents")
        self.total_count = result.intByName("count")

        result = self.owner.ctrl_be.exec_query("SELECT * FROM mysql.slow_log ORDER BY start_time LIMIT %i, %i"  % (self.show_start, self.show_count))

        self.tree.clear_rows()
        while result.nextRow():
            start_time = result.stringByName("start_time")
            user_host = result.stringByName("user_host")    
            query_time = result.stringByName("query_time")   
            lock_time = result.stringByName("lock_time")    
            rows_sent = result.intByName("rows_sent")    
            rows_examined = result.intByName("rows_examined")
            db = result.stringByName("db")           
            last_insert_id = result.intByName("last_insert_id")
            insert_id = result.intByName("insert_id")     
            server_id = result.intByName("server_id")     
            sql_text = result.stringByName("sql_text")
            
            row = self.tree.add_row()
            self.tree.set_string(row, 0, start_time)
            self.tree.set_string(row, 1, user_host)
            self.tree.set_string(row, 2, query_time)
            self.tree.set_string(row, 3, lock_time)
            self.tree.set_int(row, 4, rows_sent)
            self.tree.set_int(row, 5, rows_examined)
            self.tree.set_string(row, 6, db)
            self.tree.set_int(row, 7, last_insert_id)
            self.tree.set_int(row, 8, insert_id)
            self.tree.set_int(row, 9, server_id)
            self.tree.set_string(row, 10, sql_text)
        
        LogBox.refresh(self)


    def copy_details(self):
        sel = self.tree.get_selected()
        if sel >= 0:
            text = self.tree.get_string(sel, 10)
            mforms.Utilities.set_clipboard_text(text)


class WbAdminLogs(mforms.Box):
    ui_created = False

    def __init__(self, ctrl_be, server_profile, main_view):
        mforms.Box.__init__(self, False)
        main_view.ui_profile.apply_style(self, 'page')
        self.set_managed()
        self.ctrl_be = ctrl_be
        self.main_view = main_view
        self.disable_log_refresh = False
        self.main_view.add_content_page(self, "MANAGEMENT", "Server Logs", "admin_server_logs_win")


    def create_ui(self):
        self.warning = not_running_warning_label()
        self.add(self.warning, False, True)
        self.warning.show(False)

        self.tabView = newTabView(False)
        self.add(self.tabView, True, True)

        self.general_log = GeneralLogView(self)
        self.tabView.add_page(self.general_log, "General")

        self.slow_log = SlowLogView(self)
        self.tabView.add_page(self.slow_log, "Slow Query Log")


    def get_log_destination(self):
        if not self.ctrl_be.is_sql_connected():
            return None

        try:
          result = self.ctrl_be.exec_query("SELECT @@log_output")
          if not result.nextRow():
              return "Unknown"
        except:
          return "Unknown" # Do nothing if we get here. This usually means we are on an older server (@@log_output is defined for 5.1+).
        return result.stringByName("@@log_output")


    def update_ui(self):

        dest = self.get_log_destination()
        if not dest or dest.find("TABLE") == -1:
            self.slow_log= None
            self.general_log= None
            if dest:
                msg = """Your current Log Destination is set to %s.
For logs to be viewed within Workbench they must be configured to be sent to TABLE.
This option is only available in MySQL version 5.1 and newer.
Fore more information read http://dev.mysql.com/doc/refman/5.1/en/log-tables.html"""%dest
                self.warning.set_text(msg)
            else:
                self.warning.set_text(not_running_warning_label_text)
            self.warning.show(True)
            self.tabView.show(False)
        else:
            self.warning.show(False)
            self.tabView.show(True)


    def page_activated(self):
        self.main_view.set_content_label(" Server Logs")
        if not self.ui_created:
            self.create_ui()
            self.ui_created = True

        self.update_ui()
        try:
            self.refresh()
        except Exception, e:
            r = mforms.Utilities.show_warning("Log Refresh", "An error occurred while displaying MySQL server logs: %s" % e, "Ignore", "Cancel", "")
            if r == mforms.ResultCancel:
                self.disable_log_refresh = True


    def refresh(self):
        if self.disable_log_refresh:
            return
        if self.ctrl_be.is_sql_connected():
            if self.general_log:
                self.general_log.refresh()
            if self.slow_log:
                self.slow_log.refresh()


    def do_refresh(self):
        pass
