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

from mforms import App, Utilities, newBox, newPanel, newButton, newLabel, newTabView, newTabSwitcher, newTextEntry, newSelector, Form, TreeView
import mforms
import wb_admin_ssh
import errno
from paramiko import SFTPError
from wb_common import OperationCancelledError, InvalidPasswordError, dprint_ex

#===============================================================================
#
#================== =============================================================
class RemoteFileSelector:
  def __init__(self, ls, cwd, cd):
    self.ls = ls
    self.cwd = cwd
    self.cd = cd
    self.selection = ""

  def get_filenames(self):
    return self.selection

  def on_change(self):
    selid = self.flist.get_selected()
    fname = self.flist.get_string(selid, 1)

    self.selection = self.curdir.get_string_value() + fname

  def on_cd(self, row, column):
    fname = None
    selid = self.flist.get_selected()
    if selid > -1:
      fname = self.flist.get_string(selid, 1)

    if fname is not None and fname != "":
      cd_success = False
      try:
        cd_success = self.cd(fname)
      except SFTPError, e:
        if len(e.args) > 0 and e[0] == errno.ENOTDIR:
          cd_success = False
        else:
          raise

      # not cd_success means that cd to a file was attempted
      if not cd_success:
        self.selection = self.curdir.get_string_value() + fname
        self.form.close()
        return

    curdir = self.cwd()
    if curdir[-1] != "/":
      curdir += "/"
    self.curdir.set_value(curdir)
    self.flist.clear_rows()

    (disr, files) = ((),())
    try:
      (dirs, files) = self.ls('.')
    except IOError, e:
      # At least on osx paramiko is silent on attempts to chdir to a file
      # so that leads to some unpleasant results
      if e.errno == errno.ENOENT:
        path = self.curdir.get_string_value()
        if (type(path) is str or type(path) is unicode):
          path = path.rstrip("/ ")
        else:
          path = None
        self.selection = path
        self.form.close()
        return

    row_id = self.flist.add_row()
    self.flist.set_string(row_id, 0, 'd')
    self.flist.set_string(row_id, 1, '..')

    for d in dirs:
      row_id = self.flist.add_row()
      self.flist.set_string(row_id, 0, 'd')
      self.flist.set_string(row_id, 1, d)

    for f in files:
      row_id = self.flist.add_row()
      self.flist.set_string(row_id, 0, ' ')
      self.flist.set_string(row_id, 1, f)

  def cancel_action(self):
    self.selection = None

  def accept_action(self):
    self.form.close()

  def run(self):
    self.form  = Form(None, mforms.FormResizable)
    self.form.set_title("Select configuration file on remote server")
    self.flist = TreeView(mforms.TreeDefault)
    self.curdir = newTextEntry()

    self.flist.add_column(mforms.StringColumnType, " ", 20, False)
    self.flist.add_column(mforms.StringColumnType, "Name", 400, False)
    self.flist.end_columns()

    self.flist.add_activated_callback(self.on_cd)
    self.flist.add_changed_callback(self.on_change)

    accept = newButton()
    accept.set_text("OK")
    cancel = newButton()
    cancel.set_text("Cancel")
    button_box = newBox(True)
    button_box.set_padding(10)
    button_box.set_spacing(8)
    Utilities.add_end_ok_cancel_buttons(button_box, accept, cancel)

    box = newBox(False) # Hosts all entries on that dialog.
    box.set_padding(10)
    box.set_spacing(10)
    box.add(self.curdir, False, False)
    box.add(self.flist, True, True)
    box.add(button_box, False, False)

    self.form.set_content(box)
    self.form.set_size(400, 300)

    cancel.add_clicked_callback(self.cancel_action)
    accept.add_clicked_callback(self.accept_action)

    self.form.relayout()
    self.form.center()

    self.on_cd(0, 0)

    # Don't use the accept button in run_modal or you won't be able to press <enter>
    #  to change the path via the top edit control.
    self.form.run_modal(None, cancel)

#-------------------------------------------------------------------------------
def remote_file_selector(profile, password_delegate):
  ssh = None
  #TODO this needs to be rewritten
  try:
    ssh = wb_admin_ssh.WbAdminSSH()
    ssh.wrapped_connect(profile, password_delegate)
  except OperationCancelledError:
    ssh = None
  except wb_admin_ssh.SSHDownException:
    ssh = None

  file_names = []

  if ssh is not None and ssh.is_connected():
    ftp = ssh.getftp()

    if ftp:
      rfs = RemoteFileSelector(ls = ftp.ls, cwd = ftp.pwd, cd = ftp.cd)
      rfs.run()
      result = rfs.get_filenames()
      if result is not None:
        file_names = result

      ftp.close()
    ssh.close()

  ret = ""
  if type(file_names) is list:
    if len(file_names) > 0:
      ret = file_names[0]
  else:
    ret = file_names

  return ret
