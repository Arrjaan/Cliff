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

?>