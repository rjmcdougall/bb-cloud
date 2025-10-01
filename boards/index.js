const express = require("express");
const app = express();
const PORT = 5555;
const DownloadDirectoryDS = require("./DownloadDirectoryDS"); 
app.use(express.json());
const bucketPath = "https://storage.googleapis.com/burner-board/BurnerBoardApps/";

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});

app.get("/", async (req, res, next) => {
	console.log(req.protocol + "://"+ req.get('Host') + req.url);
	try {
        var i = await DownloadDirectoryDS.listBoards(null);
		res.status(200).json(i);
	}
	catch (err) {
		res.status(500).json(err.message);
	}
});

app.get("/CreateBoard/:deviceID", async (req, res, next) => {
	console.log(req.protocol + "://"+ req.get('Host') + req.url);
	var deviceID = req.params.deviceID;
 
	try {
		var i = await DownloadDirectoryDS.createNewBoard(deviceID);
		res.status(200).json(i);
	}
	catch (err) {
		res.status(500).json(err.message);
	}
});

app.post("/UpdateProfile/:profileID", async (req, res, next) => {
	console.log(req.protocol + "://"+ req.get('Host') + req.url);
	var profileID = req.params.profileID;
 
	try {
		var i = new Array();
		await DownloadDirectoryDS.deleteAllProfileMedia("video", profileID);
		i.push(await DownloadDirectoryDS.InsertProfile(profileID, "video", req.body.video));
		res.status(200).json(i);
	}
	catch (err) {
		res.status(500).json(err.message);
	}
});

app.get("/:boardID/DownloadDirectoryJSON", async (req, res, next) => {
	console.log(req.protocol + "://"+ req.get('Host') + req.url);

	var boardID = req.params.boardID;
	var result = [];
	try {
		var boardExists = await DownloadDirectoryDS.boardExists(boardID);
		if (boardExists) {
			// get the default profile
			var profileID = await DownloadDirectoryDS.listBoards(boardID);

			// is the deault profile global? if so, null it out!
			if (profileID[0].isProfileGlobal)
				boardID = null;

			result = await DownloadDirectoryDS.DirectoryJSON(boardID, profileID[0].profile);
			res.status(200).json(result);
		}
		else {
			throw new Error("Board named " + boardID + " does not exist");
		}
	}
	catch (err) {
		res.status(500).json(err);
	}

});

app.get("/apkVersions", async (req, res, next) => {
	
	try {
		
		var results = await DownloadDirectoryDS.listAPKVerions();
		var result = results.map((item) => {

			return {
				URL: bucketPath + item.localName,
				localName: item.localName,
				Version: item.Version,
				Size: item.Size,
			}
		})

		var i = {
			application: result
		}
		
		res.status(200).json(i);
	}
	catch (err) {
		res.status(500).json(err.message);
	}
});

app.get("/status", async (req, res, next) => {
	console.log(req.protocol + "://"+ req.get('Host') + req.url);
	
	try {
		var meshData = await DownloadDirectoryDS.listMeshData();
		res.status(200).json({
			mesh: meshData
		});
	}
	catch (err) {
		res.status(500).json(err.message);
	}
});
 
module.exports = {app};
