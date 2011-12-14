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

from mforms import newTabView, newBox, newTable, newPanel, TitledBoxPanel, newScrollPanel, newCheckBox, newTextEntry, newTextBox
from mforms import newLabel, HFillFlag, VFillFlag, HExpandFlag, Utilities, newSelector
from mforms import newButton, SmallHelpTextStyle, FileChooser, OpenDirectory
from mforms import SelectorPopup, SelectorCombobox
import mforms
import wb_admin_config_file_be
import os
from wb_common import dprint_ex, debug_level
from wb_admin_config_file_be import multi_separator
from wb_admin_utils import no_remote_admin_warning_label

CATOPTS = os.getenv("WB_CATOPTS")
if CATOPTS is not None:
  cat_sec = ('General', 'Advanced', 'MyISAM Parameters', 'Performance', 'Log Files', 'Security', 'InnoDB Parameters', 'Networking', 'Replication')
  cat_grp = ('Networking', 'Advanced log options', 'Slave replication objects', 'Slave default connection values', 'Activate Logging', 'Memory', 'Fulltext search', 'Data / Memory size', 'Datafiles', 'Localization', 'Thread specific settings', 'Advanced', 'Advanced Settings', 'Various', 'Binlog Options', 'Memory usage', 'Directories', 'Logfiles', 'Relay Log', 'Master', 'General slave', 'Security', 'Activate InnoDB', 'Slave Identification', 'Query cache', 'General', 'Insert delayed settings', 'Slow query log options', 'Naming', 'Timeout Settings')

  def handle_cat_opt(cat, grp, enabled):
    print "CATOPT", "'" + enabled + "', '" + cat.get_string_value() + "', '" + grp.get_string_value()

#===============================================================================
class Page:
  def __init__(self, page_name, page_content):
    self.page_name = page_name
    self.page_content = page_content
    self.panel = None
    self.created = False
    self.update_cb = None

  def set_update_cb(self, update_cb):
    self.update_cb = update_cb



#===============================================================================
class WbAdminConfigFileUI(mforms.Box):
    #---------------------------------------------------------------------------
    def page_activated(self):
      self.main_view.set_content_label(" Options File")
      if not self.ui_created:
        self.ui_created = True
        self.suspend_layout()
        self.create_ui()
        self.resume_layout()
      else:
        on = self.server_profile.admin_enabled
        self.file_name_ctrl.set_enabled(on)
        self.section_ctrl.set_enabled(on)
        self.bottom_box.set_enabled(on)
        self.tab_view.set_enabled(on)
        self.search_panel.set_enabled(on)

    #---------------------------------------------------------------------------
    def __init__(self, server_profile, ctrl_be, main_view, version="5.1"):
      mforms.Box.__init__(self, False)
      self.tab_view = newTabView()
      self.main_view = main_view

      self.myopts = None
      self.opt2ctrl_map = {}
      self.loading = True
      self.section = None
      self.ui_created = False

      self.set_managed()
      self.version = version
      self.ctrl_be = ctrl_be
      self.server_profile = server_profile
      self.cfg_be = None # Will be created later in self.create_ui
      self.version = version

      self.pack_to_top()
      container = self.main_view.add_content_page(self, "CONFIGURATION", "Options File", "admin_option_file_win", True)

      self.search_panel = self.create_search_panel()
      container.add_end(self.search_panel, False, False);

    #---------------------------------------------------------------------------
    def create_search_panel(self):
      search_label = newLabel("Locate option:")
      self.option_lookup_entry  = newTextEntry()
      self.option_lookup_entry.set_size(200,-1)
      search_btn = newButton()
      search_btn.set_text("Find")
      search_btn.set_size(70, -1)

      search_box = newBox(True)
      search_box.set_padding(2)
      search_box.set_spacing(4)
      #search_box.set_size(300, -1)
      search_box.add(search_label, False, False)
      search_box.add(self.option_lookup_entry, False, True)
      search_box.add(search_btn, False, False)
      search_panel = newPanel(mforms.FilledPanel)
      search_panel.add(search_box)
      self.main_view.ui_profile.apply_style(search_panel, 'option-search-panel')

      def lookup_option_wrapper():
          self.locate_option(self.option_lookup_entry.get_string_value())

      search_btn.add_clicked_callback(lookup_option_wrapper)

      return search_panel

    #---------------------------------------------------------------------------
    def create_page(self, page_number):
      self.loading = True
      if page_number < 0 or page_number == 0:
        self.loading = False
        return

      if page_number not in self.pages:
        print "Unknown page number ", page_number
        self.loading = False
        return

      # page is a stored page data stored in self.pages in create_ui
      page = self.pages[page_number]
      if page.created == True:
        self.loading = False
        return

      page_content = page.page_content

      box = newBox(False)
      box.set_spacing(8)
      box.suspend_layout()

      # Actual option values from config file parsed by cfg_be, in form of list of tuples (<name>, <value>)
      options = self.cfg_be.get_options(self.section_ctrl.get_string_value())
      opts_map = dict(options)

      for group in page_content['groups']:
        controls = group['controls']

        number_of_controls = len(controls)

        if number_of_controls == 0:
          continue

        table = newTable()
        table.set_row_spacing(10)
        table.set_column_spacing(20)
        table.set_padding(5)
        table.suspend_layout()
        table.set_homogeneous(False)

        panel = newPanel(TitledBoxPanel)
        panel.add(table)
        panel.set_title(group['caption'])
        box.add(panel, False, True)

        table.set_row_count(number_of_controls)
        table.set_column_count(3)

        table_row = -1 # Counter to address table rows, as we may skip some control_idx.

        for control_idx in range(0, number_of_controls):
          ctrl_def = controls[control_idx]

          table_row += 1

          name = ctrl_def['name']
          # Handle aliases like server_id == server-id. We have only one form in 
          # opts.opts, and that form comes from documentaion team's xml file.
          # However if user config file contains alias, we substitute the alias 
          # instead of official option name to use for this WBA session. From now
          # on all operation with the option are done through alias.
          names = self.cfg_be.option_alt_names(name) #(name, name.replace("-","_"), name.replace("_","-"))
          right_name = filter(lambda x: x in opts_map, names)
          if len(right_name) > 0:
            right_name = right_name[0]
            caption = ctrl_def.get('caption')
            if caption and name in caption:
              ctrl_def['caption'] = caption.replace(name, right_name)
            name = right_name
            ctrl_def['name'] = name

          ctrl_tupple = self.place_control(ctrl_def, table, table_row)

          label = newLabel(ctrl_def['description'])
          label.set_size(500, -1)
          label.set_wrap_text(True)
          label.set_style(SmallHelpTextStyle)
          table.add(label, 2, 3, table_row, table_row + 1, HFillFlag | VFillFlag)

          ctrl     = ctrl_tupple[1]
          ctrl_def = ctrl_tupple[2]

          #load default value into control
          if ctrl is not None and ctrl_def is not None:
            ctrl[0].set_active(False)
            self.enabled_checkbox_click(name, False)
            if ctrl_def.has_key('default'):
              default = ctrl_def['default']
              if default is not None:
                self.set_string_value_to_control(ctrl_tupple, str(default))
            else:
              self.set_string_value_to_control(ctrl_tupple, "")

          #load control with values from config
          if name in opts_map:
            value = opts_map[name]
            self.enabled_checkbox_click(name, True)
            self.set_string_value_to_control(ctrl_tupple, value)

        # Remove empty rows
        table.set_row_count(table_row+1)#number_of_controls - (number_of_controls - table_row))
        table.resume_layout()

      page.panel.add(box)
      page.created = True
      box.resume_layout()
      self.loading = False

    #---------------------------------------------------------------------------
    def locate_option(self, option_name_fragment):
      ret = None
      for opt in self.cfg_be.get_options_containing(option_name_fragment):
        (tab_name, group_name) = self.cfg_be.get_option_location(opt)
        if tab_name is not None:
          for page_idx, page in self.pages.iteritems():
            if page.page_name == tab_name:
              self.create_page(page_idx)
              self.tab_view.set_active_tab(page_idx - 1)
              page.panel.flush_events()
              ctrl_tuple = self.opt2ctrl_map.get(opt)
              # ctrl_tuple is in for of ('<type>', <ui controls tuple>, <opt def from xml file>)
              if ctrl_tuple is not None:
                ctrl = ctrl_tuple[1] # in this ctrl we have format of (enabled_checkbox, ...)
                page.panel.scroll_to_view(ctrl[0]) # scroll to enabled checkbox
                return

    #---------------------------------------------------------------------------
    def tab_changed(self):
      page_number = self.tab_view.get_active_tab() + 1
      page = self.pages.get(page_number)
      if page is not None and page.update_cb is not None:
        page.update_cb(page)
      else:
        self.create_page(page_number)

    #---------------------------------------------------------------------------
    def create_ui(self):
      self.loading = True

      self.cfg_be = wb_admin_config_file_be.WbAdminConfigFileBE(self.server_profile, self.ctrl_be)

      sys_config_path = self.server_profile.config_file_path
      if sys_config_path is None:
        sys_config_path = ""
      self.file_name_ctrl.set_value(sys_config_path)
      self.section_ctrl.add_changed_callback(self.clear_and_load)
      try:
        self.myopts = self.cfg_be.get_possible_options()
      except KeyError:
        Utilities.show_error("Error", "Wrong version '" + self.version + "'given to admin plugin", "Close", None, None)

      self.load_options_from_cfg()

      #build ordered list of pages. Initially only skeleton pages are created, means only names.
      # Values into pages will be load as soon as page is switched to.
      self.pages = {}
      for page_name, page_content in self.myopts.iteritems():
        self.pages[int(page_content['position'])] = Page(page_name, page_content) # False means page not created
      # page key is its position in UI. As we can have pages positions set like (1,2,4,5)
      # the position set needs to be sorted so pages appear in specified order
      page_positions = self.pages.keys()
      page_positions.sort()

      # Create dummy pages according to assigned position
      for page_pos in page_positions:
        page = self.pages[page_pos]
        page.panel = newScrollPanel(mforms.ScrollPanelNoFlags)
        self.tab_view.add_page(page.panel, page.page_name)

      if debug_level > 0:
        # Create file page
        page = Page("File", None)
        page.panel = newTextBox(mforms.BothScrollBars)
        page.set_update_cb(self.update_file_content_tab)
        self.pages[max(self.pages.keys()) + 1] = page
        self.tab_view.add_page(page.panel, page.page_name)

      # Create first page, so we display something from start
      self.create_page(1)
      self.loading = True # create_page resets loading flag

      self.tab_view.add_tab_changed_callback(self.tab_changed)

      self.loading = False

    #---------------------------------------------------------------------------
    def update_file_content_tab(self, page):
      page.panel.clear()
      for line in self.cfg_be.get_file_content():
        page.panel.append_text(line)

    #---------------------------------------------------------------------------
    def create_textedit(self, name, ctrl_def):
      te = newTextEntry()
      te.set_enabled(False)
      te.add_changed_callback(lambda: self.control_action(name))
      te.set_tooltip("To convert option to a multi-line one, use " + multi_separator + " to separate values. The symbol " + multi_separator + " should not be the first char")
      return te

    #---------------------------------------------------------------------------
    def create_dir_file_edit(self, name, ctrl_def):
      dir_box = newBox(True)
      dir_box.set_spacing(4)

      te = newTextEntry()
      te.set_tooltip("To convert option to a multi-line one, use " + multi_separator + " to separate values. The symbol " + multi_separator + " should not be the first char")
      btn = newButton()
      btn.set_text("...")
      btn.enable_internal_padding(False)
      btn.add_clicked_callback(lambda: self.open_file_chooser(OpenDirectory, te, name))

      dir_box.add(te, True, True)
      dir_box.add(btn, False, False)
      te.set_enabled(False)
      btn.set_enabled(False)

      return (dir_box, te, btn)

    #---------------------------------------------------------------------------
    def create_numeric(self, name, ctrl_def):
      #spin_box = newBox(True)
      #spin_box.set_spacing(5)
      te = newTextEntry()
      #spin_box.add(te, True, True)
      te.set_enabled(False)
      te.set_tooltip("For numeric values, you may specify a K, M or G size suffix, if appropriate.")

      te.add_changed_callback(lambda: self.control_action(name))

      #unit = None
      #if ctrl_def.has_key('unitcontrol'):
      #  unit = ctrl_def['unitcontrol']

      #unitcontrol = None
      #unit_items = None

      #if unit is not None:
      #  unitcontrol = newSelector()
      #  unit_items = unit.split(";")
      #  for item in unit_items:
      #    unitcontrol.add_item(item)
      #
      #  spin_box.add(unitcontrol, False, False)
      #  unitcontrol.set_enabled(False)
      #  unitcontrol.add_changed_callback(lambda: self.control_action(name))

      #return (spin_box, te, unitcontrol, unit_items)
      return te

    #---------------------------------------------------------------------------
    def create_dropdownbox(self, name, ctrl_def, ctype):
      items = None
      if 'choice' in ctrl_def:
        items = ctrl_def['choice']

      style = SelectorPopup
      if ctype == 'dropdownboxentry':
        style = SelectorCombobox
      dropbox = newSelector(style)

      if type(items) is str:
        if items in wb_admin_config_file_be.pysource:
          code = wb_admin_config_file_be.pysource[items]
          result = eval(code)
          items = []
          for item in result.split(','):
            item = item.strip(" \t")
            items.append(item)

      for i in items:
        dropbox.add_item(i)
      dropbox.set_enabled(False)

      if ctrl_def.has_key('default'):
        default = ctrl_def['default']
        idx = 0
        for i in items:
          if i == default:
            dropbox.set_selected(idx)
          idx += 1

      dropbox.add_changed_callback(lambda: self.control_action(name))

      return (dropbox, items)

    #---------------------------------------------------------------------------
    def place_control(self, ctrl_def, table, row):
      ctrl = None
      ctype = ctrl_def['type']
      name = ctrl_def['name']

      enabled = newCheckBox()
      enabled.set_text(ctrl_def['caption'])
      enabled.set_size(200, -1) # Use a fixed fix to make all tables align their columns properly. Must be larger than the largest text, to make it work.
      enabled.set_tooltip(ctrl_def['name'])

      # place_control creates control as ctrl_def describes. Reference to a created control is placed 
      # to map of controls. That is done in order to access controls via option name
      if ctype == "checkbox" or ctype == "boolean":
        ctrl = ('chk', (enabled, enabled), ctrl_def)
        self.opt2ctrl_map[name] = ctrl
        enabled.set_active(False)
        #label = newLabel(" ")
        #table.add(label, 1, 2, row, row+1, HExpandFlag | HFillFlag)
      elif ctype == 'textedit' or ctype == 'string' or ctype == 'set':
        te = self.create_textedit(name, ctrl_def)
        table.add(te, 1, 2, row, row+1, HExpandFlag | HFillFlag)
        ctrl = ('txt', (enabled, te), ctrl_def)
        self.opt2ctrl_map[name] = ctrl
      elif ctype == "directory" or ctype == "filename" or ctype == "dirname":
        (dir_box, te, btn) = self.create_dir_file_edit(name, ctrl_def)
        table.add(dir_box, 1, 2, row, row + 1, HExpandFlag | HFillFlag)
        te.add_changed_callback(lambda: self.control_action(name))
        ctrl = ('dir', (enabled, te, btn), ctrl_def)
        self.opt2ctrl_map[name] = ctrl
      elif ctype == "numeric" or ctype == "spinedit":
        #(spin_box, te, unitcontrol, unit_items) = self.create_numeric(name, ctrl_def)
        #ctrl = ('spn', (enabled, te, unitcontrol, unit_items), ctrl_def)
        te = self.create_numeric(name, ctrl_def)
        #ctrl = ('spn', (enabled, te), ctrl_def)
        ctrl = ('txt', (enabled, te), ctrl_def)
        self.opt2ctrl_map[name] = ctrl
        #table.add(spin_box, 1, 2, row, row + 1, HExpandFlag | HFillFlag)
        table.add(te, 1, 2, row, row + 1, HExpandFlag | HFillFlag)
      elif ctype == "dropdownbox" or ctype == 'dropdownboxentry':
        if 'choice' not in ctrl_def:
          te = newTextEntry()
          te.set_enabled(False)
          te.add_changed_callback(lambda: self.control_action(name))
          table.add(te, 1, 2, row, row+1, HExpandFlag | HFillFlag)
          ctrl = ('txt', (enabled, te), ctrl_def)
          self.opt2ctrl_map[name] = ctrl
        else:
          (dropbox, items) = self.create_dropdownbox(name, ctrl_def, ctype)
          table.add(dropbox, 1, 2, row, row + 1, HExpandFlag | HFillFlag)
          ctrl = ('drp', (enabled, dropbox, items), ctrl_def)
          self.opt2ctrl_map[name] = ctrl

      if CATOPTS is None:
        table.add(enabled, 0, 1, row, row + 1, HFillFlag)
        enabled.add_clicked_callback(lambda: self.enabled_checkbox_click(name))
      else:
        catbox = newBox(True)
        cat = newSelector(mforms.SelectorCombobox)
        for item in cat_sec:
          cat.add_item(item)
        grp = newSelector(mforms.SelectorCombobox)
        for item in cat_grp:
          grp.add_item(item)
        cat.add_changed_callback(lambda : handle_cat_opt(cat, grp, ctrl_def['name']))
        grp.add_changed_callback(lambda : handle_cat_opt(cat, grp, ctrl_def['name']))
        catbox.add(cat, True, True)
        catbox.add(grp, True, True)
        catbox.add(enabled, True, True)
        table.add(catbox, 0, 1, row, row + 1, HExpandFlag | HFillFlag)

      return ctrl

    #---------------------------------------------------------------------------
    def open_file_chooser(self, file_chooser_type, textfield, name):
      filechooser = FileChooser(file_chooser_type)
      filechooser.set_directory(textfield.get_string_value())
      if filechooser.run_modal():
        filename = filechooser.get_directory()
        if filename and (type(filename) is str or type(filename) is unicode):
          filename = filename.replace("\\", "/") # TODO: Check for backslashed spaces and so on
          textfield.set_value("\"" + filename + "\"")
          self.control_action(name)
      
    #---------------------------------------------------------------------------
    def enabled_checkbox_click(self, name, force_enabled = None):
      if self.opt2ctrl_map.has_key(name):
        ctrl = self.opt2ctrl_map[name]

        def control(idx):
           return ctrl[1][idx]

        tag = ctrl[0] # tupple ctrl holds tag at index 0, the rest is control def. Exact format
                      # of control tupple(the one that goes after tag is defined by the type of control

        if force_enabled is not None:
          enabled = force_enabled
          control(0).set_active(enabled)
        else:
          enabled = control(0).get_active()

        if tag == "txt":
          control(1).set_enabled(enabled)
        elif tag == "spn":
          control(1).set_enabled(enabled)
          if control(2) is not None:
            control(2).set_enabled(enabled)
        elif tag == "drp":
          control(1).set_enabled(enabled)
        elif tag == "dir":
          control(1).set_enabled(enabled)
          control(2).set_enabled(enabled)

        if not self.loading:
          # Notify config BE about change
          if enabled:
            self.cfg_be.option_added(name, self.get_string_value_from_control(ctrl), self.section)
          else:
            self.cfg_be.option_removed(name, self.section)

    #---------------------------------------------------------------------------
    def control_action(self, name):
      if self.loading:
        return

      if self.opt2ctrl_map.has_key(name):
        ctrl = self.opt2ctrl_map[name]

        if not self.loading:
          self.cfg_be.option_changed(name, self.get_string_value_from_control(ctrl), self.section)

    #---------------------------------------------------------------------------
    def get_string_value_from_control(self, ctrl):
      #ctrl is a tupple from map
      value = ""

      tag = ctrl[0]
      def control(idx):
        return ctrl[1][idx]

      is_multiple = False
      control_name = control(1).get_name()
      if control_name == "Multiple":
        is_multiple = True

      if tag == "txt":
        value = (control(1).get_string_value(),)
      elif tag == "spn":
        # (enabled, te, unitcontrol, unit_items)). Note! unitcontrol and unit_items may be None
        value = control(1).get_string_value().strip(" \r\n\t")

        if control(2) is not None:
            value += control(2).get_string_value()
      elif tag == "drp":
        value = control(1).get_string_value()
      elif tag == "dir":
        value = control(1).get_string_value()
        if is_multiple:
          value = value.split(';')
      elif tag == "chk":
        value = (control(0).get_active(),)

      # Here we detect if value has signs of multi line option.
      # For example, user entered separator char.
      # It is enough to ensure that the first item in tuple is string
      is_string = False  # We only can detect multi-line in strings (rework is scheduled for 5.3)
      has_separator = False
      if type(value) is tuple:
        value_len = len(value)
        if value_len == 1: # Check only single item tuples
          is_string = type(value[0]) is str or type(value[0]) is unicode
          if is_string:
            has_separator = value[0].find(multi_separator) > 0
      else:
        is_string = type(value) is str or type(value) is unicode
        has_separator = value.find(multi_separator) > 0

      if is_multiple == False and is_string and has_separator and not self.loading:
        answer = Utilities.show_message("Confirm"
            ,"Multi-line option format entered. Would you like to convert option to multi-line?"
            , "Convert", "Skip", "")
        if answer == mforms.ResultOk:
          control(1).set_name("Multiple")

      # some controls return values in form of one-item tuples
      # so we need to extract that item for processing below
      if has_separator and is_string:
        if type(value) is tuple:
          if len(value) == 1:     # Only extract values from one-item tuples
            value = value[0]      # If tuple has more items it already has been converted to multi-line

        # skip multi line values - no need to convert. Also skip non-string option values
        if type(value) is not tuple:
          value = map(lambda x: x.strip(multi_separator), value.split(multi_separator))

      if type(value) is not list and type(value) is not tuple:   
        value = (value,)

      return value

    #---------------------------------------------------------------------------
    #Value is a an integer with
    def parse_spin_string(self, unit_items, value):
      value = value.strip(" \r\t\n")
      longest_suffix = 0
      if unit_items is not None:
        for item in unit_items:
          l = len(item)
          if (l > longest_suffix):
            longest_suffix = l

      suffix = ""

      def get_unit(sfx):
        sfx2 = sfx.lower()
        ret_item = None
        for item in unit_items:
          if sfx2 == item.lower():
            ret_item = item
            break
        return ret_item

      if longest_suffix > 0:
        value_len = len(value)
        for suffix_length in range(1,longest_suffix + 1):
          if suffix_length < value_len:
            cur_sfx = value[-suffix_length:]
            cur_unit = get_unit(cur_sfx)
            if cur_unit is not None:
              suffix = cur_unit
              value = value[:-suffix_length]

      return (filter(lambda x: x.isdigit() or x == '-', value), suffix)


    #---------------------------------------------------------------------------
    def set_string_value_to_control(self, ctrl, value):
      #ctrl is a tupple from map
      tag = ctrl[0]
      def control(idx):
        return ctrl[1][idx]

      is_multiple = False
      if type(value) is tuple and len(value) > 1:
        is_multiple = True
        control(1).set_name("Multiple")
      else:
        control(1).set_name("Single")

      if tag == "txt" or tag == "dir":
        if value is None or value.__class__ != "".__class__:
          # TODO: Add config file error message
          value = ""
        value = value.strip(" \r\n\t")
        control(1).set_value(value)
      elif tag == "spn":
        if value is None:
          value = ""
        elif type(value) is not str:
          # TODO: Add Warning
          pass
        value = value.strip(" \r\n\t")
        (value,suffix) = self.parse_spin_string(control(3), value)
        control(1).set_value(value)

        if control(2) is not None and suffix is not None:
          try:
            idx = control(3).index(suffix)
            control(2).set_selected(idx)
          except ValueError:
            pass
      elif tag == "drp":
        #search for value
        try:
          items = control(2)
          if items is not None:
            lowcase_value = value.lower()
            for (i, item) in enumerate(items):
              if item.lower() == lowcase_value:
                control(1).set_selected(i)
        except ValueError:
          pass
      elif tag == "chk":
        value = self.cfg_be.normalize_bool(value)
        control(1).set_active(value)
      else:
        print "Error"

    #---------------------------------------------------------------------------
    def config_apply_changes_clicked(self):
      option_types = {}
      
      errors = self.cfg_be.validate_changes(self.myopts)
      if errors:
        mforms.Utilities.show_warning("Configuration Error",
                    "The following errors were found in the changes you have made.\n"
                    "Please correct them before applying:\n"+errors, "OK", "", "")
      else:
        self.cfg_be.apply_changes()

    #---------------------------------------------------------------------------
    def config_discard_changes_clicked(self):
      #self.cfg_be.revert()
      self.clear_and_load()

    #---------------------------------------------------------------------------
    def clear_and_load(self):
      if self.loading == False:
        self.load_defaults()
        self.load_options_from_cfg(self.section_ctrl.get_string_value())

    #---------------------------------------------------------------------------
    def load_options_from_cfg(self, given_section = None):
      self.loading = True

      try:
          self.cfg_be.open_configuration_file(self.file_name_ctrl.get_string_value())
      except Exception, exc:
          mforms.Utilities.show_error("Error opening configuration file",
                                      "%s: %s" % (type(exc).__name__, exc),
                                      "OK", "", "")

      self.section_ctrl.clear()

      idx = 0
      if given_section is None or given_section == "":
        given_section = self.server_profile.config_file_section

      # Fill section selector at the bottom of config file page
      section_ctrl_was_filled = False
      for i,sec in enumerate(self.cfg_be.get_sections()):
        self.section_ctrl.add_item(sec)
        section_ctrl_was_filled = True
        if sec == given_section:
          idx = i
          self.section = sec

      # If we have an empty file or file with no section, add user-specified default section to the selector
      if section_ctrl_was_filled == False and given_section is not None:
        self.section_ctrl.add_item(given_section)
        idx = 0

      self.section_ctrl.set_selected(idx)

      # each opt is (name, value)
      for name, value in self.cfg_be.get_options(self.section):
        ctrl = self.opt2ctrl_map.get(name)
        if not ctrl:
          # We are here because of either 1) alias, or 2) unknown option, or 
          # 3) initial load when map is not created
          # Try to resolve alias and update UI and maps
          names = self.cfg_be.option_alt_names(name)
          for alt_name in names:
            ctrl = self.opt2ctrl_map.get(alt_name)
            if ctrl is not None:
              # Fix UI and map
              self.opt2ctrl_map[name] = ctrl
              # Rename checkbox with name
              ctrl[1][0].set_text(name)
              del self.opt2ctrl_map[alt_name]
              break

        if ctrl is None:
          continue

        self.enabled_checkbox_click(name, True)
        self.set_string_value_to_control(ctrl, value)

      self.loading = False

    #---------------------------------------------------------------------------
    def load_defaults(self):
      self.loading = True
      for name,ctrl_tupple in self.opt2ctrl_map.iteritems():
        if ctrl_tupple is not None:
          #tag      = ctrl_tupple[0]
          ctrl     = ctrl_tupple[1]
          ctrl_def = ctrl_tupple[2]

          if ctrl is not None and ctrl_def is not None:
            ctrl[0].set_active(False)
            self.enabled_checkbox_click(ctrl_def['name'], False)
            if ctrl_def.has_key('default'):
              default = ctrl_def['default']
              if default is not None:
                self.set_string_value_to_control(ctrl_tupple, str(default))
            else:
              self.set_string_value_to_control(ctrl_tupple, "")

      self.loading = False


    #-------------------------------------------------------------------------------
    def pack_to_top(self):
      self.suspend_layout()
      self.main_view.ui_profile.apply_style(self, 'page')

      #if self.server_profile.admin_enabled:
      self.file_name_ctrl = newTextEntry()
      sys_config_path = self.server_profile.config_file_path
      if sys_config_path is None:
        sys_config_path = ""
      self.file_name_ctrl.set_value(sys_config_path)
      self.file_name_ctrl.set_size(300, -1)

      self.section_ctrl = newSelector()
      self.section_ctrl.set_size(150, -1)

      #spacer = newPanel(mforms.TransparentPanel)
      #spacer.set_size(100, 10)

      self.bottom_box = newBox(True)

      accept_btn = newButton()
      accept_btn.set_text("Apply ...")

      discard_btn = newButton()
      discard_btn.set_text("Discard")

      #self.add(self.search_panel, False, True)
      self.add(self.tab_view, True, True)
      self.add(self.bottom_box, False, False)

      self.bottom_box.add(newLabel("Configuration File:"), False, True)
      self.bottom_box.add(self.file_name_ctrl, True, True)
      self.bottom_box.add(self.section_ctrl, False, True)

      Utilities.add_end_ok_cancel_buttons(self.bottom_box, accept_btn, discard_btn)

      self.bottom_box.set_spacing(8)
      self.bottom_box.set_padding(12)

      accept_btn.add_clicked_callback(self.config_apply_changes_clicked)
      discard_btn.add_clicked_callback(self.config_discard_changes_clicked)

      self.resume_layout()
