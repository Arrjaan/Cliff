<?php

$dir = getcwd();
$fwdir = str_replace("\\","/",$dir);

$f = $dir."\httpd\conf\httpd.conf";
$i = file_get_contents($f);
$fh = fopen($f,"r+");
$h = fwrite($fh, str_replace("C:/Cliff", $fwdir, $i));

if ( $h ) echo "Apache is configuerd succesfully.\r\n";
else echo "Error at configuring Apache.\r\n";

fclose($fh);

$f = $dir.'\ftp\FileZilla Server.xml';
$i = file_get_contents($f);
$fh = fopen($f,"r+");
$h = fwrite($fh, str_replace("C:\Cliff", $dir, $i));

if ( $h ) echo "FileZilla Server is configuerd succesfully.\r\n";
else echo "Error at configuring FileZilla Server.\r\n";

fclose($fh);

$f = $dir."\php\php.ini";
$i = file_get_contents($f);
$fh = fopen($f,"r+");
$h = fwrite($fh, str_replace("C:\Cliff", $dir, $i));

if ( $h ) echo "PHP is configuerd succesfully.\r\n";
else echo "Error at configuring PHP.\r\n";

fclose($fh);

$f = $dir."\mysql\my.ini";
$i = file_get_contents($f);
$fh = fopen($f,"r+");
$h = fwrite($fh, str_replace("C:/Cliff", $fwdir, $i));

if ( $h ) echo "MySQL is configuerd succesfully.\r\n";
else echo "Error at configuring MySQL.\r\n";

fclose($fh);

$f = $dir."\AWstats\wwwroot\cgi-bin\awstats.pl";
$i = file_get_contents($f);
$fh = fopen($f,"r+");
$h = fwrite($fh, str_replace("C:/Cliff", $fwdir, $i));

$f = $dir."\AWstats\wwwroot\cgi-bin\awstats.localhost.conf";
$i = file_get_contents($f);
$fh = fopen($f,"r+");
$h2 = fwrite($fh, str_replace("C:/Cliff", $fwdir, $i));

if ( $h && $h2 ) echo "AWstats is configuerd succesfully.\r\n";
else echo "Error at configuring AWstats.\r\n";

fclose($fh);

$f = fopen("conf.ini", "w");
$wr = fwrite($f, "[Global]\r\nrootdir=".getcwd()."\r\n\r\n[Apache]\r\nname=localhost\r\nurl=http://localhost\r\nemail=admin@localhost\r\n");
fclose($f);

if ( $wr ) echo "Algemene instellingen opgeslagen!\r\n";
else echo "Opslaan van algemene instellingen mislukt.\r\n";

?>