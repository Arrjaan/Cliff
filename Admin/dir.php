<?php

if ( !empty($_GET['dir']) ) $path = $_GET['dir'];
else $path = "";

$dir = scandir("C:/Myst/htdocs/".$path);
array_shift($dir);
array_shift($dir);

echo "<ul>";

foreach ( $dir as $element ) {
	if ( preg_match("/\./",$element) ) echo '<li><a href="'.$path."/".$element.'">'.$element.'</a></li>';
	else echo '<li><a href="javascript:dir(\''.$path."/".$element.'\');">'.$element.'</a></li>';
	echo "\r\n";
}

echo "</ul>";

if ( !empty($path) ) echo '<a href="javascript:dir(\'\');" >&laquo; Terug</a>';
?>