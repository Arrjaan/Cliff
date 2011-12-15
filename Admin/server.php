<?php 
$ini = parse_ini_file ("../conf.ini", true);
define("ROOTDIR",$ini["Global"]["rootdir"]);

if ( isset($_GET['exit']) ) {
	exec("sc config apache2.2 start= demand");
	exec("sc config MySQL start= demand");
	exec("sc config FTP start= demand");
	exec("sc stop FTP");
	exec("sc stop MySQL");
	exec("sc stop apache2.2");
}

if ( !empty($_GET['service']) && !empty($_GET['mode']) ) {
	if ( $_GET['mode'] == "demand" ) exec("sc config ".$_GET['service']." start= demand");
	if ( $_GET['mode'] == "auto" ) exec("sc config ".$_GET['service']." start= auto");
}

if ( !empty($_GET['serv']) && !empty($_GET['mode']) ) {
	if ( $_GET['mode'] == "start" ) exec("sc start ".$_GET['serv']);
	if ( $_GET['mode'] == "stop" ) exec("sc stop ".$_GET['serv']);
}

if ( !empty($_GET['admin']) ) {
	if ( $_GET['admin'] == "MySQL" ) exec("\"C:\Myst\mysql\MySQL Workbench CE 5.2.35\MySQLWorkbench.exe\"");
	if ( $_GET['mode'] == "FTP" ) exec("\"C:\Myst\ftp\FileZilla_Server_Interface.exe\"");
}
?>
<div class="top_long"><h2>Server Status</h2></div>
<div class="middle_long" id="html">

<table>
<tr><td><b>Service</b></td><td><b>Status</b></td><td><b>Opstartmodus</b></td><td><b>Versie</b></td><td><b>Herstarten</b></td><td><b>Administratie</b></td></tr>
<?php

exec("sc query apache2.2",$apache);
exec("sc query MySQL",$mysql);
exec("sc query FTP",$ftp);

exec("sc qc apache2.2",$apache2);
exec("sc qc MySQL",$mysql2);
exec("sc qc FTP",$ftp2);

function restartService($sName) {
	exec("sc stop ".$sName);
	exec("sc query ".$sName,$state);
	
	while ( !preg_match("/STOPPED/",$state[3]) ) {
		exec("sc query ".$sName,$state);
		print_r($state);
		sleep(2);
	}
	
	exec("sc start ".$sName);
}

function find_SQL_Version() {
   $output = shell_exec(ROOTDIR .'\mysql\bin\mysql -V');
   preg_match('@[0-9]+\.[0-9]+\.[0-9]+@', $output, $version);
   return $version[0];
}

function find_apache_Version() {
	$v = $_SERVER['SERVER_SOFTWARE'];
	$v = explode(" ",$v);
	$v = explode("/",$v[0]);
	return $v[1];
}

if ( !empty($_GET['r']) ) restartService($_GET['r']);
	
echo "<tr><td>Apache</td>";
if ( preg_match("/RUNNING/",$apache[3]) ) echo "<td>Online <a href=\"javascript:switchRunning('Apache2.2','stop');\"><img src=\"html/img/Start.png\" /></a></td>";
else echo "<td>OFFLINE <a href=\"javascript:switchRunning('Apache2.2','start');\"><img src=\"html/img/Shutdown.png\" /></a></td>";
if ( preg_match("/AUTO_START/",$apache2[4]) ) echo "<td><a href=\"javascript:switchStart('Apache2.2','demand');\">Automatisch</a></td>";
else echo "<td><a href=\"javascript:switchStart('Apache2.2','auto');\">Manueel</a></td>";
echo "<td>".find_apache_Version()."</td><td><a href=\"javascript:reset('Apache2.2');\">Herstart Apache</a></td><td> - </td></tr>\r\n";

echo "<tr><td>PHP</td><td>Online</td><td> - </td><td>".phpversion()."</td><td> - </td><td> - </td></tr>\r\n";

echo "<tr><td>MySQL</td>";
if ( preg_match("/RUNNING/",$mysql[3]) ) echo "<td>Online <a href=\"javascript:switchRunning('MySQL','stop');\"><img src=\"html/img/Start.png\" /></a></td>";
else echo "<td>OFFLINE <a href=\"javascript:switchRunning('Apache2.2','start');\"><img src=\"html/img/Shutdown.png\" /></a></td>";
if ( preg_match("/AUTO_START/",$mysql2[4]) ) echo "<td><a href=\"javascript:switchStart('MySQL','demand');\">Automatisch</a></td>";
else echo "<td><a href=\"javascript:switchStart('MySQL','auto');\">Manueel</a></td>";
echo "<td>".find_SQL_Version()."</td><td><a href=\"javascript:reset('MySQL');\">Herstart MySQL</a></td><td><a href=\"javascript:openAdmin('MySQL');\">MySQL Workbench</a></td></tr>\r\n";

echo "<tr><td>FTP</td>";
if ( preg_match("/RUNNING/",$ftp[3]) ) echo "<td>Online <a href=\"javascript:switchRunning('FTP','stop');\"><img src=\"html/img/Start.png\" /></a></td>";
else echo "<td>OFFLINE <a href=\"javascript:switchRunning('FTP','start');\"><img src=\"html/img/Shutdown.png\" /></a></td>";
if ( preg_match("/AUTO_START/",$ftp2[4]) ) echo "<td><a href=\"javascript:switchStart('FTP','demand');\">Automatisch</a></td>";
else echo "<td><a href=\"javascript:switchStart('FTP','auto');\">Manueel</a></td>";
echo "<td>0.9.40</td><td><a href=\"javascript:reset('FTP');\">Herstart FTP</a></td><td><a href=\"javascript:openAdmin('FTP');\">FileZilla Admin</a></td></tr>\r\n";
?>
</table>

<br />

<a href="javascript:exit();" onclick="return confirm('Weet u zeker dat u ALLE services van Myst wilt be&euml;indigen?');">&raquo; Sluit Myst Server af</a><br />
</div>
<div class="bottom_long"></div>