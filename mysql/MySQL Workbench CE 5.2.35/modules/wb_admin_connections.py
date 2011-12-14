# Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
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

from mforms import newTreeView, newButton, newBox
import mforms

from wb_admin_utils import not_running_warning_label, weakcb, dprint_ex

class WbAdminConnections(mforms.Box):
    ui_created = False
    def __init__(self, instance_info, ctrl_be):
        mforms.Box.__init__(self, False)
        self.instance_info = instance_info
        self.ctrl_be = ctrl_be
        self.page_active = False

        
    def create_ui(self):
        dprint_ex(3, "Enter")
        self.suspend_layout()
        
        self.warning = not_running_warning_label()
        self.add(self.warning, False, True)
    
        self.connection_list = newTreeView(mforms.TreeDefault)
        self.connection_list.add_column(mforms.StringColumnType, "Id", 50, False)
        self.connection_list.add_column(mforms.StringColumnType, "User", 80, False)
        self.connection_list.add_column(mforms.StringColumnType, "Host", 120, False)
        self.connection_list.add_column(mforms.StringColumnType, "DB", 100, False)
        self.connection_list.add_column(mforms.StringColumnType, "Command", 80, False)
        self.connection_list.add_column(mforms.IntegerColumnType, "Time", 80, False)
        self.connection_list.add_column(mforms.StringColumnType, "State", 80, False)
        self.connection_list.add_column(mforms.StringColumnType, "Info", 300, False)        
        self.connection_list.end_columns()
        self.connection_list.set_allow_sorting(True)
        
        self.connection_list.add_changed_callback(weakcb(self, "connection_selected"))

        #self.set_padding(8)
        self.add(self.connection_list, True, True)

        self.button_box = box = newBox(True)
        self.add(box, False, True)
        
        box.set_spacing(12)
        box.set_padding(12)
        
        refresh_button = newButton()
        refresh_button.set_text("Refresh")
        box.add_end(refresh_button, False, True)
        refresh_button.add_clicked_callback(weakcb(self, "refresh"))

        self.kill_button = newButton()
        self.kill_button.set_text("Kill Connection")
        box.add_end(self.kill_button, False, True)
        self.kill_button.add_clicked_callback(weakcb(self, "kill_connection"))

        self.killq_button = newButton()
        self.killq_button.set_text("Kill Query")
        box.add_end(self.killq_button, False, True)
        self.killq_button.add_clicked_callback(weakcb(self, "kill_query"))


        self.add(box, False, True)
        
        self.resume_layout()

        self.connection_selected()
        dprint_ex(3, "Leave")


    def connection_selected(self):
        dprint_ex(3, "Enter")
        if self.connection_list.get_selected() < 0:
            self.kill_button.set_enabled(False)
            self.killq_button.set_enabled(False)
        else:
            self.kill_button.set_enabled(True)
            self.killq_button.set_enabled(True)
        dprint_ex(3, "Leave")

    def page_activated(self):
        if not self.ui_created:
          self.create_ui()
          self.ui_created = True

        self.page_active = True
        if self.ctrl_be.is_sql_connected():
          self.warning.show(False)
          self.connection_list.show(True)
          self.button_box.show(True)
        else:
          self.warning.show(True)
          self.connection_list.show(False)
          self.button_box.show(False)

        self.refresh()

    def page_deactivated(self):
      self.page_active = False

    def get_process_list(self):
      fields = ["Id", "User", "Host", "db", "Command", "Time", "State", "Info"]
      result = self.ctrl_be.exec_query("SHOW PROCESSLIST")
      if result is not None:
        result_rows = []
        while result.nextRow():
          row = []
          for field in fields:
            value = result.stringByName(field)
            row.append(value)
          result_rows.append(row)
        return result_rows

      return None

    def refresh_mt(self, ctrl_be):
      dprint_ex(2, "Enter")
      if not self.page_active:
        dprint_ex(2, "Leave. Page inactive")
        return

      result_rows = self.get_process_list()
      ctrl_be.uitask(self.refresh, result_rows)
      dprint_ex(2, "Leave")

    def refresh(self, query_result = None):
        if not self.ctrl_be.is_sql_connected():
          dprint_ex(2, "Leave. SQL connection is offline")
          return

        if not self.page_active:
          dprint_ex(2, "Leave. Page is inactive")
          return

        i = self.connection_list.get_selected()
        if i >= 0:
          old_selected = self.connection_list.get_string(i, 0)
        else:
          old_selected = None

        if query_result is None:
          query_result = self.get_process_list()

        if query_result is not None:
          self.connection_list.freeze_refresh()
          self.connection_list.clear_rows()
          id_width = 0
          try:
            for row in query_result:
              r = self.connection_list.add_row()
              for c, field in enumerate(row):
                if c == 5:
                  try:
                    field= int(field)
                  except:
                    field= 0
                  self.connection_list.set_int(r, c, field)
                else:
                  field = str(field)
                  if c == 0:
                      id_width = max(id_width, len(field))
                  self.connection_list.set_string(r, c, field)

                if c == 0 and field == old_selected:
                  self.connection_list.set_selected(r)
          finally:
            self.connection_list.thaw_refresh()

          if id_width > 0:
              cnt = self.connection_list.count()
              for row in range(0, cnt):
                  cid = self.connection_list.get_string(row, 0)
                  self.connection_list.set_string(row, 0, cid.rjust(id_width, ' '))

          self.connection_selected()

    def kill_connection(self):
      if not self.ctrl_be.is_sql_connected():
          return

      sel = self.connection_list.get_selected()
      if sel < 0:
        return

      connid = self.connection_list.get_string(sel, 0)

      try:
        self.ctrl_be.exec_sql("KILL CONNECTION %s"%connid)
      except Exception, e:
        raise Exception("Error executing KILL CONNECTION: %s" % e)

      self.refresh()


    def kill_query(self):
      if not self.ctrl_be.is_sql_connected():
          return

      sel = self.connection_list.get_selected()
      if sel < 0:
        return

      connid = self.connection_list.get_string(sel, 0)

      try:
        self.ctrl_be.exec_sql("KILL QUERY %s"%connid)
      except Exception, e:
        raise Exception("Error executing KILL QUERY: %s" % e)

      self.refresh()

