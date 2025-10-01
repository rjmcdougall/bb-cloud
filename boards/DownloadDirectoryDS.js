const { Datastore } = require("@google-cloud/datastore");
const datastore = new Datastore({
	projectId: process.env.PROJECT_ID,
});

exports.createNewBoard = async (deviceID) => {

	try {

		var boardQuery;
 
		boardQuery = datastore.createQuery("board")
			.filter("bootName", "=", "template");

		var results = (await datastore.runQuery(boardQuery))[0][0];
 
		var addressQuery = datastore.createQuery("board")
			.order("address", {
				descending: true
			});
		var address =  (await datastore.runQuery(addressQuery))[0][0].address;
		
		results.bootName = deviceID;
		results.address = address + 1;
		results.createdDate = new Date().toLocaleString();

		var results = await datastore
			.insert({
				key: datastore.key("board"),
				data: results
			});

		return "board " + deviceID + " created ";
	}
	catch (error) {
		return error;
	}
};

exports.deleteAllProfileMedia = async function (mediaType, profileID) {
	try {
		const deleteMediaQuery = datastore.createQuery(mediaType)
			.filter("profile", "=", profileID)
			.filter("UpdatedByScript","=",true);

		var results = await datastore.runQuery(deleteMediaQuery);

		var results2 = await datastore.delete(results[0].map((item) => {
			return item[datastore.KEY];
		}));

		return "Deleted algorithms from " + profileID;
	}
	catch (error) {
		throw new Error(error);
	}
};

exports.createProfile = async function (boardID, profileID, isGlobal) {
	try {
		var i = 2;
		var results = await datastore
			.save({
				key: datastore.key(["profile"]),
				data: {
					name: profileID,
					board: boardID,
					isGlobal: isGlobal,
				},
			});

		if (isGlobal)
			return "global profile " + profileID + " created";
		else
			return "profile " + profileID + " created for board " + boardID;

	}
	catch (error) {
		throw new Error(error);
	}
};

exports.InsertProfile = async function (profileID, mediaType, algorithms) {

	try {
 
		var mappedMediaArray = new Array();

		for (var i = 0; i < algorithms.length; i++) {
			mappedMediaArray.push({
				key: datastore.key(mediaType),
				data: {
					algorithm: algorithms[i].algorithm,
					ordinal: i,
					profile: profileID,
					Length: algorithms[i].Length,
					UpdatedByScript: true,
				}
			});
		}
 
		await datastore.save(mappedMediaArray); 
		console.log("added " + JSON.stringify(mappedMediaArray));
		return JSON.stringify(mappedMediaArray);
	}
	catch (error) {
		throw new Error(error);
	}
}; 

exports.listAPKVerions = async () => {
	try{
		var apks;

		apks = datastore.createQuery("apkVersion");
		var results = await datastore.runQuery(apks);

		return results[0];
	}
	catch(error){
		throw new Error(error);
	}
}

exports.listBoards = async (boardID) => {
	try {
		var boardQuery;

		if (boardID != null)
			boardQuery = datastore.createQuery("board")
				.filter("name", "=", boardID);
		else
			boardQuery = datastore.createQuery("board")
				.filter("isActive","=",true)
				.order("name");

		var results = await datastore.runQuery(boardQuery);

		if (boardID == null)
			results[0].splice(results[0].findIndex(board => {
				return board.bootName == "template";
			}), 1);

		return (results[0]);

	}
	catch (error) {
		throw new Error(error);
	}
};
      

exports.boardExists = async function (boardID) {
	try {

		const boardExists = datastore.createQuery("board")
			.filter("name", "=", boardID);

		var results = await datastore.runQuery(boardExists);
		return (results[0].length > 0);
	}
	catch (error) {
		throw new Error(error);
	}
};

exports.listMedia = async function (boardID, profileID, mediaType) {

	try {
		var mediaList;

		if (boardID == null) {
			mediaList = datastore.createQuery(mediaType)
				.filter("profile", "=", profileID)
				.order("ordinal", {
					descending: false
				});
		}
		else {
			mediaList = datastore.createQuery(mediaType)
				.filter("board", "=", boardID)
				.filter("profile", "=", profileID)
				.order("ordinal", {
					descending: false
				});
		}

		var mediaList = await datastore.runQuery(mediaList);
		return mediaList[0];
	}
	catch (error) {
		throw new Error(error);
	}
};

exports.listMeshData = async () => {
	try {
		// Query all records from the mesh table
		const meshQuery = datastore.createQuery("mesh");
		const results = await datastore.runQuery(meshQuery);
		
		// Return the raw data from the mesh table
		return results[0];
	}
	catch (error) {
		throw new Error(error);
	}
};

exports.DirectoryJSON = async function (boardID, profileID) {

	try {
		var DirectoryJSON = {
			audio: null,
			video: null,
		};

		var results = await this.listMedia(boardID, profileID, "audio");

		DirectoryJSON.audio = results.map(function (item) {
			delete item["board"];
			delete item["profile"];
			return item;
		});

		var results2 = await this.listMedia(boardID, profileID, "video");

		DirectoryJSON.video = results2.map(function (item) {
			delete item["board"];
			delete item["profile"];
			return item;
		});

		return DirectoryJSON;

	}
	catch (error) {
		throw new Error(error);
	}
};
 