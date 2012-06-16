<?php 
$ini = parse_ini_file ("../conf.ini", true);
define("ROOTDIR",$ini["Global"]["rootdir"]);

if ( isset($_GET['maplist']) && $ini["Global"]["maplist"] ) {
	$f = file_get_contents('../adminCliff/dir.php');
	eval("?><div class=\"top_long\"><h2>Mappenlijst</h2></div>
<div class=\"middle_long\">".str_replace(":dir",":dirH",$f)."</div>
<div class=\"bottom_long\"></div>");
	die();
}
if ( isset($_GET['maplist']) && !$ini["Apache"]["maplist"] ) die();
?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XhtmlCliff 1.0 Strict//EN" 
      "http://www.w3.org/TR/xhtml1/DTD/xhtmlCliff1-strict.dtd"> 
 
<htmlCliff xmlns="http://www.w3.org/1999/xhtml" xml:lang="nl" lang="nl"> 
 
<head> 
	<title>Cliff</title>
  	<meta http-equiv="content-type" content="text/html; charset=iso-8859-1" />
    <script src="http://cdn.jquerytools.org/1.2.5/full/jquery.tools.min.js"></script>
	<link rel="stylesheet" type="text/css" href="htmlCliff/style.css" />
    <link rel="shortcut icon" href="htmlCliff/favicon.ico" />
	
	<script src="htmlCliff/ajax.js"></script>
</head> 
 
<body>
	<script>
		<?php if ( $_SERVER["SERVER_ADDR"] == "127.0.0.1" ) { ?>
		$(window).bind('hashchange', function() {
			load();
		});
	    $(document).ready(function() {
			load();
			dir('');
		});
		<?php } else { ?>
		$(document).ready(function() {
			dirH('');
		});
		<?php } ?>
	</script>
	<div id="container">
		<div id="logo">
			<a href="/home"><img src="htmlCliff/img/logo.png" alt="Cliff" /></a>
		</div>
		
		<?php if ( $_SERVER["SERVER_ADDR"] == "127.0.0.1" ) { ?>
		<div id="menu">
			<ul>
				<li id="mHome" class="active"><a href="#home"><b>Home</b></a></li>
				<li><a href="/phpmyadminCliff"><b>phpMyadminCliff</b></a></li>
				<li id="mServer" class=""><a href="#server"><b>Server Status</b></a></li>
				<li id="mConfig" class=""><a href="#config"><b>Instellingen</b></a></li>
				<li class=""><a href="/stats"><b>Statistieken</b></a></li>
			</ul>  
		</div>
		<?php } ?>
		
		<div id="content">
			<div class="top_long"><h2>Laden...</h2></div>
			<div class="middle_long">
				<img src="htmlCliff/img/loader.gif" alt="Laden..." border="0" /> 
			</div>
			<div class="bottom_long"></div>
		</div>
		
		<?php if ( $_SERVER["SERVER_ADDR"] == "127.0.0.1" ) { ?>
		<div id="sidebar">
			<div class="top_small" id="loginmenutop"><h2>Index</h2></div>
			<div class="middle_small" id="dir"></div>
			<div class="bottom_small"></div>
		</div>
		<?php } ?>
		
		<div id="footer">
			<p class="left">Cliff Server <?php echo file_get_contents("../version.txt"); ?></p>
			<p class="right"><a href="#help">Help</a> - <a href="#about">About</a></p>
			<br />
			<br />
		</div>
	</div>
</body>
</html>