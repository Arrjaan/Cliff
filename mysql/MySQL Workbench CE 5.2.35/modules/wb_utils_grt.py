#  Copyright (c) 2009 Sun Microsystems Inc. All rights reserved.
#

import subprocess
import os

# import the wb module
from wb import *
# import the grt module
import grt

import mforms

# define this Python module as a GRT module
ModuleInfo = DefineModule(name= "PyWbUtils", author= "Sun Microsystems Inc.", version="1.0")


# this is just a function used by the plugin, it's not exported
def printTableLine(fields, filler= " "):
  print "|",
  for text, size in fields:
    print text.ljust(size, filler), "|",
  print


# @wbexport makes this function be exported by the module and also describes the return and 
# argument types of the function
# @wbplugin defines the name of the plugin to "wb.catalog.util.dumpColumns", sets the caption to be 
# shown in places like the menu, where to take input arguments from and also that it should be included
# in the Catalog submenu in Plugins.
@ModuleInfo.plugin("wb.catalog.util.dumpColumns", caption= "Dump All Table Columns", input= [wbinputs.currentCatalog()], pluginMenu= "Catalog")
@ModuleInfo.export(grt.INT, grt.classes.db_Catalog)
def printAllColumns(catalog):
  lines= []
  schemalen= 0
  tablelen= 0
  columnlen= 0
  typelen= 0

  for schema in catalog.schemata:
    schemalen= max(schemalen, len(schema.name))
    for table in schema.tables:
      tablelen= max(tablelen, len(table.name))
      for column in table.columns:
        columnlen= max(columnlen, len(column.name))
        typelen= max(typelen, len(column.formattedType))
        lines.append((schema.name, table.name, column.name, column.formattedType))

  printTableLine([("-", schemalen), ("-", tablelen), ("-", columnlen), ("-", typelen)], "-")
  printTableLine([("Schema", schemalen), ("Table", tablelen), ("Column", columnlen), ("Type", typelen)])

  printTableLine([("-", schemalen), ("-", tablelen), ("-", columnlen), ("-", typelen)], "-")

  for s,t,c,dt in lines:
    printTableLine([(s, schemalen), (t, tablelen), (c, columnlen), (dt, typelen)])

  printTableLine([("-", schemalen), ("-", tablelen), ("-", columnlen), ("-", typelen)], "-")
  print len(lines), "columns printed"

  return 0
  

def get_linux_terminal_program():
    paths = os.getenv("PATH").split(":")
    if not paths:
        paths = ['/usr/bin', '/usr/local/bin', '/bin']

    for term in ["gnome-terminal", "konsole", "xterm", "rxvt"]:
        for d in paths:
            full_path = os.path.join(d, term)
            if os.path.exists(full_path):
                return full_path

    return None


@ModuleInfo.plugin("wb.tools.cmdlineClient", caption="Start Command Line Client", input= [wbinputs.selectedConnection()], pluginMenu="Home/Connections")
@ModuleInfo.export(grt.INT, grt.classes.db_mgmt_Connection)
def startCommandLineClientForConnection(conn):
    import platform
    import os
    if "ssh" in conn.driver.name.lower():
        raise Exception("Tunneled connections not supported")

    if "socket" in conn.driver.name.lower():
        if platform.system() == "Windows":
            host = "."
        else:
            host = "localhost"
        socketName = conn.parameterValues["socket"]
        if socketName is None:
            socketName = "MySQL"
        socket = "--socket=" + socketName
    else:
        host = conn.parameterValues["hostName"].replace("\\", "\\\\").replace('"', '\\"')
        socket = ""

    user = conn.parameterValues["userName"].replace("\\", "\\\\").replace('"', '\\"')
    port = conn.parameterValues["port"]
    if port is None:
        port = 3306
    schema = conn.parameterValues["schema"]
    if schema:
        schema = schema.replace("\\", "\\\\").replace('"', '\\"')
    else:
        schema = ""

    if platform.system() == "Darwin":
        command = """mysql \\"-u%s\\" \\"-h%s\\" -P%i %s -p %s""" % (user, host, port, socket, schema)
        os.system("""osascript -e 'tell application "Terminal" to do script "%s"'""" % command)
    elif platform.system() == "Windows":
        command = """start cmd /C mysql -u%s -h%s -P%i %s -p %s""" % (user, host, port, socket, schema)
        subprocess.Popen(command, shell = True)
    else:
        command = """mysql \\"-u%s\\" \\"-h%s\\" -P%i %s -p %s""" % (user, host, port, socket, schema)
        subprocess.call(["/bin/bash", "-c", "%s -e \"%s\" &" % (get_linux_terminal_program(), command)])


# Utilities only work in Py 2.6
disable_utilities = False
import sys
# find out version of default python interpreter
if sys.platform != "win32":
    pyversion, junk = subprocess.Popen("python --version", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()
    if [int(i) for i in pyversion.split(" ")[1].strip().split(".")[:2]] < [2, 6]:
        disable_utilities = True

if not disable_utilities:
    @ModuleInfo.plugin("wb.tools.utilitiesShell", caption="Start Shell for MySQL Utilities", groups=["Others/Menu/Ungrouped"])
    @ModuleInfo.export(grt.INT)
    def startUtilitiesShell():
        import platform
        import os
        import time

        if platform.system() == "Windows":
            command = 'start cmd /K \"cd utilities && echo The following utilities are available: && echo. && dir *.exe /B /W\"'
            subprocess.Popen(command, shell = True)
        elif platform.system() == "Darwin":
            import tempfile
            fd, setup_script = tempfile.mkstemp(prefix="delme.", dir=mforms.App.get().get_user_data_folder())
            f = os.fdopen(fd, "w+")
            f.write('PATH="$PATH:%s/scripts"\n' % mforms.App.get().get_resource_path(""))
            f.write('MYSQL_UTILITIES_FOLDER="%s/scripts"\n' % mforms.App.get().get_resource_path(""))
            f.write('export PYTHONPATH="%s"\n' % os.getenv("PYTHONPATH", ""))
            f.write('clear\n')
            f.write('echo "The following MySQL Utilities are available:"\n')
            f.write('ls "%s/scripts"\n' %  mforms.App.get().get_resource_path(""))
            f.write('rm -f "%s"\n' % setup_script)
            f.close()
            os.chmod(setup_script, 0700)
            os.system("""osascript -e 'tell application "Terminal" to do script "source \\"%s\\""' -e 'tell front window of application "Terminal" to set custom title to "MySQL Utilities"'""" % setup_script)
        else:
            term = get_linux_terminal_program()
            if term:
                import tempfile
                fd, setup_script = tempfile.mkstemp(prefix="delme.", dir=mforms.App.get().get_user_data_folder())
                f = os.fdopen(fd, "w+")
                f.write('echo "The following MySQL Utilities are available:"\n')
                f.write('echo $MYSQL_UTILITIES_COMMANDS\n')
                f.write('rm -f "%s"\n' % setup_script)
                f.write('bash -i\n')
                f.close()
                os.chmod(setup_script, 0700)

                if 'konsole' in term:
                    subprocess.call([term, "-e", "/bin/bash", setup_script])
                else:
                    subprocess.call(["/bin/bash", "-c", "%s -e %s &" % (term, setup_script)])


#@ModuleInfo.plugin("wb.tools.utilitiesShellFor", caption="Start MySQL Utilities Shell for Connection", input= [wbinputs.selectedConnection()], pluginMenu="Home/Connections")
#@ModuleInfo.export(grt.INT, grt.classes.db_mgmt_Connection)
#def startUtilitiesShellFor(conn):
#    return 0

