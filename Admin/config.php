<?php
	$ini = parse_ini_file ("../conf.ini", true);
	define("ROOTDIR",$ini["Global"]["rootdir"]);
	
	if ( !empty($_POST['mysqlpass']) && !empty($_POST['mysqlpassold']) ) {
		echo system(ROOTDIR ."/mysql/bin/mysqladmin.exe -u root -p'".$_POST['mysqlpassold']."' password '".$_POST['mysqlpass']."'",$passi);
		die();
	}
	if ( !empty($_POST['name']) && !empty($_POST['url']) && !empty($_POST['email']) ) {
		$f = fopen("../conf.ini", "w");
		$wr = fwrite($f, "[Global]\r\nrootdir=".$ini["Global"]["rootdir"]."\r\n\r\n[Apache]\r\nname=".$_POST['name']."\r\nurl=".$_POST['url']."\r\nemail=".$_POST['email']."\r\n");
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

<div class="top_long"><h2>Apache</h2></div>
<div class="middle_long" id="apache">
	<form method="post" action="" onsubmit="false">
		<table>
			<tr>
				<td>Server naam:</td>
				<td><input id="name" value="<?php echo $ini["Apache"]["name"]; ?>" /></td>
			</tr>
			<tr>
				<td>Server url:</td>
				<td><input id="url" value="<?php echo $ini["Apache"]["url"]; ?>" /></td>
			</tr>
			<tr>
				<td>E-mail administrator:</td>
				<td><input id="email" value="<?php echo $ini["Apache"]["email"]; ?>" /></td>
			</tr>
		</table>
		<input type="submit" value="Update" onclick="confApache();" />
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

<div class="top_long"><h2>FTP</h2></div>
<div class="middle_long" id="ftp">
	<form method="post" action="" onsubmit="confFTP();">
		<table>
			<tr>
				<td>Huidig wachtwoord admin:</td>
				<td><input id="passftpold" type="password" /></td>
			</tr>
			<tr>
				<td>Nieuw achtwoord admin:</td>
				<td><input id="passftp" type="password" /></td>
			</tr>
		</table>
		<input type="submit" value="Update" />
	</form>
</div>
<div class="bottom_long"></div>