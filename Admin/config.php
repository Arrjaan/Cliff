<?php
	$ini = parse_ini_file ("../conf.ini", true);
	define("ROOTDIR",$ini["Global"]["rootdir"]);
	
	if ( !empty($_POST['mysqlpass']) && !empty($_POST['mysqlpassold']) ) {
		echo system(ROOTDIR ."/mysql/bin/mysqladmin.exe -u root -p'".$_POST['mysqlpassold']."' password '".$_POST['mysqlpass']."'",$passi);
		die();
	}
	if ( !empty($_POST['maplist']) ) {
		$f = fopen("../conf.ini", "w");
		$wr = fwrite($f, "[Cliff]\r\nrootdir=".$ini["Global"]["rootdir"]."\r\nmaplist=".$_POST['maplist']."\r\n");
		fclose($f);
		if ( $wr ) echo "Instellingen opgeslagen!<br />";
		else echo "Opslaan van instellingen mislukt.<br />";
		die();
	}
$ini = parse_ini_file ("../conf.ini", true);
?>
<div class="top_long"><h2>Configuratie</h2></div>
<div class="middle_long">
-- Inleiding -- 
</div>
<div class="bottom_long"></div>

<div class="top_long"><h2>Cliff</h2></div>
<div class="middle_long" id="cliff">
	<form method="post" action="" onsubmit="false">
		<table>
			<tr>
				<td>Mappenlijst zichtbaar voor gasten:</td>
				<td>
					<input id="maplist" name="maplist" type="radio" value="checked" checked="<?php echo $ini["Cliff"]["mapdir"]; ?>" /> Ja
					<input id="maplist" name="maplist" type="radio" value="unchecked" checked="<?php echo $ini["Cliff"]["mapdir"]; ?>" /> Nee</td>
			</tr>
		</table>
		<input type="submit" value="Update" onclick="confCliff();" />
	</form>
</div>
<div class="bottom_long"></div>

<div class="top_long"><h2>MySQL</h2></div>
<div class="middle_long" id="mysql">
	<form method="post" action="" onsubmit="false">
		<table>
			<tr>
				<td>Huidig wachtwoord root:</td>
				<td><input id="mysqlpassold" type="password" value="" /></td>
			</tr>
			<tr>
				<td>Nieuw Wachtwoord root:</td>
				<td><input id="mysqlpass" type="password" value="" /></td>
			</tr>
		</table>
		<input type="submit" value="Update" onclick="confMySQL();" />
	</form>
</div>
<div class="bottom_long"></div>