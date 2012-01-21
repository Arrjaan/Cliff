var xmlhttp;
var xmlhttp2;
var xmlhttp3;

function load()
{
	xmlhttp=Ajax();
	var page = window.location.hash;
	
	if ( page == "" ) {
		page = "#home";
	}
	
	if ( page == "#server" ) 
	{
		document.getElementById('mServer').setAttribute('class', 'active');
		document.getElementById('mHome').setAttribute('class', 'inactive');
		document.getElementById('mConfig').setAttribute('class', 'inactive');
	}
	
	if ( page == "#home" ) 
	{
		document.getElementById('mServer').setAttribute('class', 'inactive');
		document.getElementById('mHome').setAttribute('class', 'active');
		document.getElementById('mConfig').setAttribute('class', 'inactive');
	}
	
	if ( page == "#config" ) 
	{
		document.getElementById('mServer').setAttribute('class', 'inactive');
		document.getElementById('mHome').setAttribute('class', 'inactive');
		document.getElementById('mConfig').setAttribute('class', 'active');
	}

	page = page.replace("#","");
	var url="admin/"+ page +".php";
	xmlhttp.onreadystatechange=cStateChanged;
	xmlhttp.open("GET",url,true);
	xmlhttp.send(null);
}

function dir(d)
{
	xmlhttp2=Ajax();
	xmlhttp2.onreadystatechange=dStateChanged;
	xmlhttp2.open("GET","admin/dir.php?dir="+encodeURIComponent(d),true);
	xmlhttp2.send(null);
}

function dirH(d)
{
	xmlhttp=Ajax();
	xmlhttp.onreadystatechange=cStateChanged;
	xmlhttp.open("GET","http://local.adfari.com/?maplist&dir="+encodeURIComponent(d),true);
	xmlhttp.send(null);
}

function reset(s)
{
	xmlhttp=Ajax();
	xmlhttp.onreadystatechange=cStateChanged;
	xmlhttp.open("GET","admin/server.php?r="+encodeURIComponent(s),true);
	xmlhttp.send(null);
}
function exit()
{
	xmlhttp=Ajax();
	xmlhttp.onreadystatechange=cStateChanged;
	xmlhttp.open("GET","admin/server.php?exit",true);
	xmlhttp.send(null);
}
function switchStart(service,mode)
{
	xmlhttp=Ajax();
	xmlhttp.onreadystatechange=cStateChanged;
	xmlhttp.open("GET","admin/server.php?service="+service+"&mode="+mode,true);
	xmlhttp.send(null);
}
function switchRunning(service,mode)
{
	xmlhttp=Ajax();
	xmlhttp.onreadystatechange=cStateChanged;
	xmlhttp.open("GET","admin/server.php?serv="+service+"&mode="+mode,true);
	xmlhttp.send(null);
}
function openAdmin(service)
{
	xmlhttp=Ajax();
	xmlhttp.open("GET","admin/server.php?admin="+service,true);
	xmlhttp.send(null);
}

function confCliff()
{
	var name=encodeURIComponent(document.getElementById("maplist").value);
	xmlhttp=Ajax();
	xmlhttp.onreadystatechange=iStateChangedC;
	xmlhttp.open("POST","admin/config.php",true);
	xmlhttp.setRequestHeader("Content-type","application/x-www-form-urlencoded");
	xmlhttp.send("maplist="+name);
}
function confMySQL()
{
	var pass=encodeURIComponent(document.getElementById("mysqlpass").value);
	var passold=encodeURIComponent(document.getElementById("mysqlpassold").value);
	xmlhttp=Ajax();
	xmlhttp.onreadystatechange=iStateChangedM;
	xmlhttp.open("POST","admin/config.php",true);
	xmlhttp.setRequestHeader("Content-type","application/x-www-form-urlencoded");
	xmlhttp.send("mysqlpass="+pass+"&mysqlpassold="+passold);
}

function dStateChanged()
{
if (xmlhttp.readyState==1)
  {
  document.getElementById("dir").innerHTML='<img src="html/img/loader.gif" alt="Laden..." border=0 />';
  } 
if (xmlhttp.readyState==4)
  {
  document.getElementById("dir").innerHTML=xmlhttp2.responseText;
  }
}

function cStateChanged()
{
if (xmlhttp.readyState==1)
  {
  document.getElementById("content").innerHTML='<img src="html/img/loader.gif" alt="Laden..." border=0 />';
  } 
if (xmlhttp.readyState==4)
  {
  document.getElementById("content").innerHTML=xmlhttp.responseText;
  }
}

function iStateChangedC()
{
if (xmlhttp.readyState==1)
  {
  document.getElementById("apache").innerHTML='<img src="html/img/loader.gif" alt="Laden..." border=0 />';
  } 
if (xmlhttp.readyState==4)
  {
  document.getElementById("apache").innerHTML=xmlhttp.responseText;
  }
}

function iStateChangedM()
{
if (xmlhttp.readyState==1)
  {
  document.getElementById("mysql").innerHTML='<img src="html/img/loader.gif" alt="Laden..." border=0 />';
  } 
if (xmlhttp.readyState==4)
  {
  document.getElementById("mysql").innerHTML=xmlhttp.responseText;
  }
}

function Ajax()
{
if (window.XMLHttpRequest)
  {
  // code for IE7+, Firefox, Chrome, Opera, Safari
  return new XMLHttpRequest();
  }
if (window.ActiveXObject)
  {
  // code for IE6, IE5
  return new ActiveXObject("Microsoft.XMLHTTP");
  }
return null;
}