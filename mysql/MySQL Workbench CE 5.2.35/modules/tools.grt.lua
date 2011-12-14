--
-- Workbench Tools Plugins
--


--
-- standard module/plugin functions
-- 

function getModuleInfo()
	return {
		name= "WbTools",
		author= "MySQL AB.",
		version= "1.1",
		implements= "PluginInterface",
		functions= {
		"getPluginInfo:l<o@app.Plugin>:",
		"quickTablesInCatalog:i:o@db.Catalog",
		"quickTables:i:"
		}
	}
end


-- helper function to create a descriptor for an argument of a specific type of object
function objectPluginInput(type)
	return grtV.newObj("app.PluginObjectInput", {objectStructName= type})
end


function getPluginInfo()
    local l
    local plugin

    -- create the list of plugins that this module exports
    l= new_plugin_list()

    plugin= new_plugin({
	name="wb.tools.quickTables", 
	caption="Create Multiple Tables", 
	moduleName= "WbTools", 
	moduleFunctionName= "quickTables", 
        inputValues= {}, 
        pluginType= "standalone",
	groups= {"Catalog/Utilities","Menu/Objects"}
	})
    grtV.insert(l, plugin)

    return l
end



function strsplit(str, sep)
    local parts= {}
    local pos

    pos = string.find(str, sep)
    while pos ~= nil do
        local s

        s= string.sub(str, 1, pos-1)
        str= string.sub(str, pos+1)
        table.insert(parts, s)

        pos = string.find(str, sep)
    end
    if str ~= "" then
        table.insert(parts, str)
    end

    return parts
end

function strtrim(str)
    local s,e

    s=1
    e=string.len(str)
    while string.sub(str, s, s)==" " or string.sub(str, s, s)=="\t" do
        s=s+1
    end

    while string.sub(str, e, e)==" " or string.sub(str, e, e)=="\t" do
        e=e-1
    end
    return string.sub(str,s,e)
end


function _parse_table_definitions(code)
    local defs= {}
    local tables
    local tbl
    local t,c
    local s,e

    tables= strsplit(code, "\n")
    
    for i,t in ipairs(tables) do
        t= strtrim(t)
        s= string.find(t, "[ ]")
        if s == nil then
            tbl={t}
        else
            local columns
            
            e= string.len(t)

            tbl={strtrim(string.sub(t, 1, s-1))}
            if e ~= nil then
                columns= string.sub(t,s+1,e)
            else
                columns= string.sub(t,s+1)
            end
            columns= strsplit(columns, ",") 
            for i,c in ipairs(columns) do
		local cdef= {}
                c= strtrim(c)
		if string.sub(c,1,1) == "*" then
			c= strtrim(string.sub(c,2))
			cdef["pk"]= true
		end
		if string.find(c, "[ ]")~=nil then
			local pos= string.find(c, "[ \t]")
			cdef["name"]= strtrim(string.sub(c, 1, pos))
			cdef["type"]= strtrim(string.sub(c, pos+1))
		else
			cdef["name"]= c
		end
                table.insert(tbl, cdef)
            end
        end
        table.insert(defs, tbl)
    end

    return defs
end


function _create_table(name,columns)
    local tbl
    local column
    local cdef
    local types= grtV.getGlobal("/wb/doc/physicalModels/0/catalog/simpleDatatypes")

    tbl= grtV.newObj("db.mysql.Table")
    tbl.name= name
    
    for i,cdef in ipairs(columns) do
        column= grtV.newObj("db.mysql.Column", {owner=tbl, name=cdef["name"]})
	tbl:addColumn(column)
	if cdef["pk"] ~= nil then
		tbl:addPrimaryKeyColumn(column)
	end
	if cdef["type"] ~= nil then
		column:setParseType(cdef["type"], types)
	end
    end

    return tbl
end


--    
-- implementation
--


function quickTables()
    local catalog= grtV.getGlobal("/wb/doc/physicalModels/0/catalog")
    quickTablesInCatalog(catalog)
end

function quickTablesInCatalog(catalog)
    local values
    local res
    local form
    local code
    local schema= catalog.schemata[1]

    form="label;You can create multiple tables by giving their outline in the following format:\\ntable1 *column1 int,column2 varchar(32),column3\\ntable2 column1,column2\\ntable3\\netc... * indicates a primary key. Column type is optional.\n"
    form= form.."textarea;code;;5;\n"
--    form= form.."checkbox;place;5;Place tables on diagram;0\n"
    values= grtV.newDict()
    res= Forms:show_simple_form("Create Multiple Tables", form, values)

    if res == 1 then
        local tabledefs
        local def

        code= values["code"]

        tabledefs= _parse_table_definitions(code)

        for i,def in ipairs(tabledefs) do
            local tbl
            local name= def[1]
            local columns= def
            if name ~= nil then
                table.remove(columns, 1)
                tbl= _create_table(name, columns)
                if tbl ~= nil then
                    tbl.owner= schema
                    grtV.insert(schema.tables, tbl)
                end

		if values["place"] == 1 then
		    
		end
            end
        end
        return 1
    end

    return 0
end

