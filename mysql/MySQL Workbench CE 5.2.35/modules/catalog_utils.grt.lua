--
-- Workbench Utility Plugins
--


--
-- standard module/plugin functions
-- 

function getModuleInfo()
	return {
		name= "WbUtils",
		author= "MySQL AB.",
		version= "1.0",
		implements= "PluginInterface",
		functions= {
		"getPluginInfo:l<o@app.Plugin>:",
		"copySQLToClipboard:i:o@db.DatabaseObject",
		"copyColumnNamesToClipboard:i:o@db.mysql.Table",
		"copyTableListToClipboard:i:o@db.Catalog",
        "obfuscateCatalog:i:o@db.Catalog",
        "prefixTables:i:o@db.Catalog",
        "changeStorageEngines:i:o@db.Catalog",
        "generateIndexes:i:o@db.Catalog"
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
		name= "wb.util.copySQLToClipboard",
        	caption= "Copy SQL to Clipboard",
		moduleName= "WbUtils",
		pluginType= "normal", 
		moduleFunctionName= "copySQLToClipboard",
		inputValues= {objectPluginInput("db.DatabaseObject")},
		groups= {"Catalog/Utilities", "Menu/Objects"}
	})

    -- add to the list of plugins
    grtV.insert(l, plugin)

    plugin= new_plugin({
		name= "wb.util.copyColumnNamesToClipboard",
        	caption= "Copy Column Names to Clipboard",
		moduleName= "WbUtils",
		pluginType= "normal", 
		moduleFunctionName= "copyColumnNamesToClipboard",
		inputValues= {objectPluginInput("db.mysql.Table")},
		groups= {"Catalog/Utilities", "Menu/Objects"}
	})

    grtV.insert(l, plugin)

    plugin= new_plugin({
		name= "wb.util.copyTableListToClipboard",
        caption= "Copy Table List to Clipboard",
		moduleName= "WbUtils",
		pluginType= "normal", 
		moduleFunctionName= "copyTableListToClipboard",
		inputValues= {objectPluginInput("db.Catalog")},
		groups= {"Catalog/Utilities", "Menu/Catalog"}
	})
    -- add to the list of plugins
    grtV.insert(l, plugin)

    plugin= new_plugin({
		name= "wb.util.obfuscateCatalog",
        caption= "Obfuscate Object Names in Catalog",
		moduleName= "WbUtils",
		pluginType= "normal", 
		moduleFunctionName= "obfuscateCatalog",
		inputValues= {objectPluginInput("db.Catalog")},
		rating= 100, 
		showProgress= 0,
		groups= {"Catalog/Utilities", "Menu/Utilities"}
	})
    -- add to the list of plugins
    grtV.insert(l, plugin)

    plugin= new_plugin({
		name= "wb.util.prefixTables",
        caption= "Give a Prefix to All Tables in Catalog",
		moduleName= "WbUtils",
		pluginType= "normal", 
		moduleFunctionName= "prefixTables",
		inputValues= {objectPluginInput("db.Catalog")},
		rating= 100, 
		showProgress= 0,
		groups= {"Catalog/Utilities", "Menu/Catalog"}
	})
    -- add to the list of plugins
    grtV.insert(l, plugin)

    plugin= new_plugin({
		name= "wb.util.generateIndexes",
        caption= "Put Indexes on Columns with Usertypes KEY and LookupString",
		moduleName= "WbUtils",
		pluginType= "normal", 
		moduleFunctionName= "generateIndexes",
		inputValues= {objectPluginInput("db.Catalog")},
		rating= 100, 
		showProgress= 0,
		groups= {"Catalog/Utilities", "Menu/Utilities"}
	})
    -- add to the list of plugins
    grtV.insert(l, plugin)

    plugin= new_plugin({
		name= "wb.util.changeStorageEngines",
        caption= "Change the Storage Engine of All Tables",
		moduleName= "WbUtils",
		pluginType= "normal", 
		moduleFunctionName= "changeStorageEngines",
		inputValues= {objectPluginInput("db.Catalog")},
		rating= 100, 
		showProgress= 0,
		groups= {"Catalog/Utilities", "Menu/Utilities"}
	})
    -- add to the list of plugins
    grtV.insert(l, plugin)

    return l
end

--    
-- implementation
--

function copySQLToClipboard(object)
        local script = ""
        local i
        
        -- workaround until diff sql generator handles routine groups
        if grtS.isOrInheritsFrom(grtS.get(object), "db.RoutineGroup") then
            for i, routine in ipairs(object.routines) do
                script = script .. DbMySQL:makeCreateScriptForObject(routine) .. ";\n\n"
            end
        else
            script= DbMySQL:makeCreateScriptForObject(object)
        end
        Workbench:copyToClipboard(script)

	return 0
end


function copyColumnNamesToClipboard(table)
        local script = ""
        
        for i, column in ipairs(table.columns) do
            if script == "" then
                script = column.name
            else
                script = script .. ", " .. column.name
            end
        end
        Workbench:copyToClipboard(script)

	return 0
end


function copyTableListToClipboard(cat)

    local i, j, schema, tbl
    local script = ""
    local separator = ""
    local insert = ""
    
    for i = 1, grtV.getn(cat.schemata) do
        schema = cat.schemata[i]
        for j = 1, grtV.getn(schema.tables) do
            tbl = schema.tables[j]
            insert = insert .. separator .. "`" .. schema.name .. "`.`" .. tbl.name .. "`"
            separator = ", "
        end
    end
    
    Workbench:copyToClipboard(insert)

	return 0
end

local function generateName(name_prefix, map)
    local i
    local name_suffix = 0
    local byte_a = string.byte('a')
    
    while 1 do
        for i = 0, 25 do
            local next_name
            if name_prefix == "" then
                next_name = string.char(byte_a + i) .. name_suffix
            else
                next_name = name_prefix .. name_suffix
            end
            
            if map[next_name] == nil then
                map[next_name] = 1
                return next_name
            end
        end
        
        name_suffix = name_suffix + 1
    end -- while        
end

function obfuscateCatalog(cat)
    local alphabet = {}
    local i
    
    local i, j, schema, tbl
    local schemata_map = {}

    if(Workbench:confirm(
        "Warning",
        "This operation will change names of all schemata and tables in the model. Proceed?") == 0) then
        return
    end

    if(Workbench:confirm(
        "Warning",
        "ATTENTION: This action cannot be undone! Proceed anyway?") == 0) then
        return
    end

    for i = 1, grtV.getn(cat.schemata) do
        local table_map = {}
        schema = cat.schemata[i]
        schema.name = generateName("", schemata_map)

        for j = 1, grtV.getn(schema.tables) do
            tbl = schema.tables[j]
            tbl.name = generateName("", table_map)
        end
    end
end

function prefixTables(cat)
    local prefix = Workbench:input("Please specify the prefix")
    
    if prefix == nil then
        return
    end
    
    local i, j

    for i = 1, grtV.getn(cat.schemata) do
        schema = cat.schemata[i]
        for j = 1, grtV.getn(schema.tables) do
            tbl = schema.tables[j]
            tbl.name = prefix .. tbl.name
        end
    end
end

function generateIndexes(cat)
    local function addToList(list, object)
        list[grtV.getn(list)+1] = object
    end
    
    local function nameMapForList(list)
	local i
	local map = {}
    
	for i = 1, grtV.getn(list) do
		map[list[i].name] = 1
	end
	
	return map
    end
    
    local function createIndex(tbl, col)
        local index_name = generateName("ix", nameMapForList(tbl.indices))
        
        local index = grtV.newObj("db.mysql.Index")
        index.owner = tbl
        index.name = index_name
        
        local index_column = grtV.newObj("db.mysql.IndexColumn")
        index_column.owner = index
        index_column.name = col.name
        index_column.referencedColumn = col
        
        addToList(index.columns, index_column)
        addToList(tbl.indices, index)

        return index
    end
    
    local i, j, k
    
    for i = 1, grtV.getn(cat.schemata) do
        schema = cat.schemata[i]
        for j = 1, grtV.getn(schema.tables) do
            tbl = schema.tables[j]
            for k = 1, grtV.getn(tbl.columns) do
                column = tbl.columns[k]
                if column.userType ~= nil then
                    if column.userType.name == "KEY" then
                        createIndex(tbl, column)
                    elseif column.userType.name == "LookupString" then
                        createIndex(tbl, column)
                    end
                end
            end
        end
    end
end


function changeStorageEngines(cat)
    local new_engine = Workbench:input("Type the new storage engine name for all tables in your model:")
    local i, j, k

    -- validate the engine name and fix its case
    local engines = grtV.getGlobal("/wb/options/options")["@db.mysql.Table:tableEngine/Items"]
    j = false
    while true do
      local name

      if engines == nil then
	break
      end
      i = string.find(engines, ",")
      if i ~= nil then
	name = string.sub(engines, 1, i-1)
	engines = string.sub(engines, i+1)
      else
        name = engines
        engines = nil
      end

      if string.find(name, ":") ~= nil then
	name = string.sub(name, string.find(name, ":") + 1)
      end
      if string.lower(name) == string.lower(new_engine) then
        j = true
        new_engine = name
        break
      end
    end
    if j == false then
        Workbench:confirm("Change Storage Engines", "Invalid storage engine name: "..new_engine)
	return
    end

    for i = 1, grtV.getn(cat.schemata) do
        schema = cat.schemata[i]
        for j = 1, grtV.getn(schema.tables) do
            tbl = schema.tables[j]
            tbl.tableEngine = new_engine
        end
    end

end





