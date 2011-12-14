# import the wb module
from wb import DefineModule, wbinputs
# import the grt module
import grt
# import the mforms module for GUI stuff
import mforms

from sql_reformatter import formatter_for_statement_ast, ASTHelper


# define this Python module as a GRT module
ModuleInfo = DefineModule(name= "SQLIDEUtils", author= "Oracle Corp.", version="1.1")



@ModuleInfo.plugin("wb.sqlide.executeToTextOutput", caption= "Execute Query Into Text Output", input= [wbinputs.currentQueryBuffer()], pluginMenu= "SQL/Utilities")
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer)
def executeQueryAsText(qbuffer):
  editor= qbuffer.owner
  sql= qbuffer.selectedText or qbuffer.script
  resultsets= editor.executeScript(sql)
  editor.addToOutput("Query Output:\n", 1)
  for result in resultsets:
    editor.addToOutput("> %s\n\n" % result.sql, 0)
    line= []
    column_lengths=[]
    ncolumns= len(result.columns)
    for column in result.columns:
      line.append(column.name + " "*5)
      column_lengths.append(len(column.name)+5)

    separator = []
    for c in column_lengths:
        separator.append("-"*c)
    separator= " + ".join(separator)
    editor.addToOutput("+ "+separator+" +\n", 0)

    line= " | ".join(line)
    editor.addToOutput("| "+line+" |\n", 0)

    editor.addToOutput("+ "+separator+" +\n", 0)
 
    rows = []
    ok= result.goToFirstRow()
    while ok:
      line= []
      for i in range(ncolumns):
        value = result.stringFieldValue(i)
        if value is None:
          value = "NULL"
        line.append(value.ljust(column_lengths[i]))
      line= " | ".join(line)
      rows.append("| "+line+" |\n")
      ok= result.nextRow()
    # much faster to do it at once than add lines one by one
    editor.addToOutput("".join(rows), 0)

    editor.addToOutput("+ "+separator+" +\n", 0)
    editor.addToOutput("%i rows\n" % len(rows), 0)

  return 0


@ModuleInfo.plugin("wb.sqlide.capitalizeCell", caption= "Capitalize Cell", input= [wbinputs.currentEditableResultset(), wbinputs.clickedRow(), wbinputs.clickedColumn()], pluginMenu= "SQL/Resultset")
@ModuleInfo.export(grt.INT, grt.classes.db_query_Resultset, grt.INT, grt.INT)
def capitalizeCell(rs, row, column):
  rs.goToRow(row)
  s= rs.stringFieldValue(column)
  if s:
    s=" ".join([ss.capitalize() for ss in s.split()])
    rs.setStringFieldValue(column, s)

  return 0

@ModuleInfo.plugin("wb.sqlide.lowerCaseCell", caption= "Lowercase Cell", input= [wbinputs.currentEditableResultset(), wbinputs.clickedRow(), wbinputs.clickedColumn()], pluginMenu= "SQL/Resultset")
@ModuleInfo.export(grt.INT, grt.classes.db_query_Resultset, grt.INT, grt.INT)
def lowerCaseCell(rs, row, column):
  rs.goToRow(row)
  s= rs.stringFieldValue(column)
  if s:
    s= s.lower()
    rs.setStringFieldValue(column, s)

  return 0

@ModuleInfo.plugin("wb.sqlide.upperCaseCell", caption= "Uppercase Cell", input= [wbinputs.currentEditableResultset(), wbinputs.clickedRow(), wbinputs.clickedColumn()], pluginMenu= "SQL/Resultset")
@ModuleInfo.export(grt.INT, grt.classes.db_query_Resultset, grt.INT, grt.INT)
def upperCaseCell(rs, row, column):
  rs.goToRow(row)
  s= rs.stringFieldValue(column)
  if s:
    s= s.upper()
    rs.setStringFieldValue(column, s)
  return 0



#@ModuleInfo.plugin("wb.sqlide.selectFromTable", caption= "Select From Table", input= [wbinputs.currentQueryBuffer(), wbinputs.selectedLiveTable()], pluginMenu= "SQL/Catalog")
#@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer, grt.classes.db_query_LiveDBObject)
#def selectTable(qbuffer, object):
#  sql= "SELECT * FROM %s"%object.name
#  qbuffer.replaceContents(sql)
#  return 0
  
  

@ModuleInfo.plugin("wb.sqlide.enbeautificate", caption = "Reformat SQL Query", input=[wbinputs.currentQueryBuffer()], pluginMenu="SQL/Utilities")
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer)
def enbeautificate(editor):
    from grt.modules import MysqlSqlFacade

    text = editor.selectedText
    selectionOnly = True
    if not text:
        selectionOnly = False
        text = editor.script

    helper = ASTHelper(text)

    ok_count = 0
    bad_count = 0
    
    curpos = 0
    new_text = ""
    ast_list = MysqlSqlFacade.parseAstFromSqlScript(text)
    for ast in ast_list:
        if type(ast) is str:
            # error
            print ast
            mforms.App.get().set_status_text("Cannot format invalid SQL: %s"%ast)
            return 1
        else:
            if 0: # debug
                from sql_reformatter import dump_tree
                import sys
                dump_tree(sys.stdout, ast)
            s, v, c, _base, _begin, _end = ast
            begin, end = helper.get_ast_range(ast)
            new_text += text[curpos:begin].rstrip(" ") # strip spaces that would come before statement
            
            # The token range does not include the quotation char if the token is quoted.
            # So extend the range by one to avoid adding part of the original token to the output.
            if end < len(text):
              possible_quote_char = text[end]
            else:
              possible_quote_char = None
            if possible_quote_char == '\'' or possible_quote_char == '"' or possible_quote_char == '`':
                curpos = end + 1
            else:
                curpos = end

            def trim_ast(node):
                s = node[0]
                v = node[1]
                c = node[2]
                l = []
                for i in c:
                    l.append(trim_ast(i))
                return (s, v, l)

            formatter = formatter_for_statement_ast(ast)
            if formatter:
                ok_count += 1
                p = formatter(trim_ast(ast))
                fmted = p.run()
            else:
                bad_count += 1
                fmted = text[begin:end]
            new_text += fmted
    new_text += text[curpos:]

    if selectionOnly:
        editor.replaceSelection(new_text)
    else:
        editor.replaceContents(new_text)

    if bad_count > 0:
        mforms.App.get().set_status_text("Formatted %i statements, %i unsupported statement types skipped."%(ok_count, bad_count))
    else:
        mforms.App.get().set_status_text("Formatted %i statements."%ok_count)

    return 0


def apply_to_keywords(editor, callable):
    from grt.modules import MysqlSqlFacade
    non_keywords = ["ident", "TEXT_STRING", "text_string", "TEXT_STRING_filesystem", "TEXT_STRING_literal", "TEXT_STRING_sys",
                    "part_name"]

    text = editor.selectedText
    selectionOnly = True
    if not text:
        selectionOnly = False
        text = editor.script
    
    new_text = ""
    ast_list = MysqlSqlFacade.parseAstFromSqlScript(text)
    bb = 0
    for ast in ast_list:
        if type(ast) is str:
            # error
            print ast
            mforms.App.get().set_status_text("Cannot format invalid SQL: %s"%ast)
            return 1
        else:
            if 0: # debug
                from sql_reformatter import dump_tree
                import sys
                dump_tree(sys.stdout, ast)

            def get_keyword_offsets(offsets, script, node):
                s, v, c, base, b, e = node
                if v:
                    b += base
                    e += base
                    if s not in non_keywords:
                        offsets.append((b, e))
                for i in c:
                    get_keyword_offsets(offsets, script, i)

            offsets = []
            get_keyword_offsets(offsets, text, ast)
            for b, e in offsets:
                new_text += text[bb:b] + callable(text[b:e])
                bb = e
    new_text += text[bb:]

    if selectionOnly:
        editor.replaceSelection(new_text)
    else:
        editor.replaceContents(new_text)

    mforms.App.get().set_status_text("SQL code reformatted.")
    return 0


@ModuleInfo.plugin("wb.sqlide.upcaseKeywords", caption = "Make keywords in query uppercase", input=[wbinputs.currentQueryBuffer()], pluginMenu="SQL/Utilities")
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer)
def upcaseKeywords(editor):
    return apply_to_keywords(editor, lambda s: s.upper())


@ModuleInfo.plugin("wb.sqlide.lowercaseKeywords", caption = "Make keywords in query lowercase", input=[wbinputs.currentQueryBuffer()], pluginMenu="SQL/Utilities")
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer)
def lowercaseKeywords(editor):
    return apply_to_keywords(editor, lambda s: s.lower())


def get_lines_in_range(text, range_start, range_end):
    lines = []
    offs = 0
    while True:
        end = text.find("\n")
        if end >= 0:
            end += 1
            line = text[0:end]
            if offs >= range_start and offs < range_end:
                lines.append(line)
            offs += end
            text = text[end:]
        else:
            if offs >= range_start and offs < range_end:
                lines.append(text)
            break
    return lines


@ModuleInfo.plugin("wb.sqlide.indent", caption = "Indent Selected Lines", input=[wbinputs.currentQueryBuffer()], pluginMenu="SQL/Utilities")
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer)
def indent(editor):
    # indent and unindent handle selection a bit differently:
    # - if there is no selection, only the line where the cursor is should be indented
    # - if there is a selection, all selected lines should be indented, even if selected partially
        
    indentation = " "*4
    start = editor.selectionStart
    end = editor.selectionEnd
    full_text = editor.script

    if end > start:
        lines = get_lines_in_range(full_text, start, end)
        new_text = indentation + indentation.join(lines)
        last_line_end = end
        while last_line_end < len(full_text) and full_text[last_line_end-1] != "\n":
            last_line_end += 1
        if last_line_end != end:
            new_text = new_text[:-(last_line_end-end)]
        editor.replaceSelection(new_text)
    else:
        line_start = pos = editor.insertionPoint
        while line_start > 0 and full_text[line_start-1] != "\n":
            line_start -= 1
        editor.replaceContents(full_text[:line_start] + indentation + full_text[line_start:]) 
        editor.insertionPoint = pos

    return 0



@ModuleInfo.plugin("wb.sqlide.unindent", caption = "Unindent Selected Lines", input=[wbinputs.currentQueryBuffer()], pluginMenu="SQL/Utilities")
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer)
def unindent(editor):
    indentation = " "*4
    start = editor.selectionStart
    end = editor.selectionEnd
    full_text = editor.script

    if end > start:
        lines = get_lines_in_range(full_text, start, end)
        for i in range(len(lines)):
            if lines[i].startswith(indentation):
                lines[i] = lines[i][len(indentation):]
        new_text = "".join(lines)
        last_line_end = end
        while last_line_end < len(full_text) and full_text[last_line_end-1] != "\n":
            last_line_end += 1
        if last_line_end != end:
            new_text = new_text[:-(last_line_end-end)]
        editor.replaceSelection(new_text)
    else:
        line_start = pos = editor.insertionPoint
        while line_start > 0 and full_text[line_start-1] != "\n":
            line_start -= 1
        if full_text[line_start:].startswith(indentation):
            editor.replaceContents(full_text[:line_start] + full_text[line_start+len(indentation):]) 
            editor.insertionPoint = pos

    return 0


@ModuleInfo.plugin("wb.sqlide.comment", caption = "Un/Comment Selection", input=[wbinputs.currentQueryBuffer()], pluginMenu="SQL/Utilities")
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer)
def commentText(editor):
    text = editor.selectedText
    if text:
        lines = text.split("\n")
        if lines[0].startswith("-- "):
            new_text = "\n".join((line[3:] if line.startswith("-- ") else line) for line in lines)
        else:
            new_text = "\n".join("-- "+line for line in lines)
        editor.replaceSelection(new_text)
    else:
        editor.replaceSelection("-- ")
    return 0




