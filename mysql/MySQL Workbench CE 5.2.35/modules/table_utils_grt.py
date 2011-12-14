# import the wb module, where various utilities for working with plugins are defined
from wb import *
from mforms import App

# import module for working with Workbench data structures
import grt

# create a module information descriptor. The variable name must be ModuleInfo
ModuleInfo = DefineModule(name= "WbTableUtils", author= "MySQL Team", version="1.0")


# export a function from this module, declaring its return and parameter types and then
# tell WB that it is a plugin to be shown in the context menu for the selected table
# and the Objects menu receiving the current selected table as input
@ModuleInfo.plugin("wb.table.util.copyInsertToClipboard", caption= "Copy Insert to Clipboard", input= [wbinputs.objectOfClass("db.Table")], groups=["Catalog/Utilities","Menu/Objects"])
@ModuleInfo.export(grt.INT, grt.classes.db_Table)
def copyInsertToClipboard(table):

  inserts = table.inserts()
  if inserts != "":
     grt.modules.Workbench.copyToClipboard(table.inserts())
     App.get().set_status_text("Ready")
  else:
     App.get().set_status_text("The table " + table.owner.name + "." + table.name + " has no records for insert statements")
  return 0

# export a function from this module, declaring its return and parameter types and then
# tell WB that it is a plugin to be shown in the context menu for the selected table
# and the Objects menu receiving the current selected table as input
@ModuleInfo.plugin("wb.table.util.copyInsertTemplateToClipboard", caption= "Copy Insert Template to Clipboard", input= [wbinputs.objectOfClass("db.Table")], groups=["Catalog/Utilities","Menu/Objects"])
@ModuleInfo.export(grt.INT, grt.classes.db_Table)
def copyInsertTemplateToClipboard(table):
  code = "INSERT INTO `" + table.owner.name + "`.`" + table.name + "` ("
  first = 1
  for col in table.columns:
    if first == 0:
      code += "`, `" + col.name
    else:
      code += "`" + col.name
    first = 0
    
  code += "`) VALUES ("

  first = 1
  for col in table.columns:
    if first == 0:
      code += ", " + "NULL"
    else:
      code += "NULL"
    first = 0
    
  code += ");"

  grt.modules.Workbench.copyToClipboard(code)
  App.get().set_status_text("Ready")
  return 0
