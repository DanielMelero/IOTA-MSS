// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract Platform {
    address owner = msg.sender;
    uint DIST_FEE = 10; // distributor fee in percentage
    mapping(address => User) public users;
    mapping(bytes32 => Song) public songs;
    mapping(bytes32 => Session) public sessions;
    mapping(bytes32 => uint256) private distributor_index;
    bytes32[] public song_list;

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner is allowed");
        _;
    }

    modifier userExists() {
        require(users[msg.sender].exists, "User do not exist");
        _;
    }

    modifier songExists(bytes32 song) {
        require(songs[song].exists, "Song do not exist");
        _;
    }

    modifier songValid(bytes32 song) {
        if (songs[song].author != msg.sender && !users[msg.sender].is_validator) {
            require(songs[song].is_valid, "Song has not been validated");
        }
        _;
    }

    modifier activeSession(bytes32 session) {
        require(sessions[session].active, "Session is not active");
        _;
    }

    struct User {
        bool exists;
        string username;
        string description;
        string server;
        uint256 balance;
        bool is_validator;
    }

    struct Song {
        bool exists;
        bool is_valid;
        address author;
        string name;
        uint256 price;
        uint256 length;
        uint256 duration;
        bytes32[] chunks;
        address[] distributors;
    }

    struct Session {
        bool active;
        address listener;
        address distributor;
        bytes32 song;
        uint256 price;
        uint256 balance;
        bool[] is_chunk_paid;
    }

    // ADMIN MANAGEMENT
    //  - Manage validators
    function manage_validators(address _val) external onlyOwner {
        require(users[_val].exists, "Validator is not a valid user");
        users[_val].is_validator = !users[_val].is_validator;
    }

    // USER MANAGEMENT
    //  - Create user
    function create_user(string memory _name, string memory _desc) external {
        require(!users[msg.sender].exists, "User already exists");
        users[msg.sender] = User(true, _name, "", _desc, 0, false);
    }

    //  - Deposit
    function deposit() external userExists payable {
        users[msg.sender].balance += msg.value;
    }

    //  - Withdraw
    function withdraw(uint256 amount) external userExists {
        uint256 balance = users[msg.sender].balance;
        require(balance >= amount, "User do not have the demanded balance");
        users[msg.sender].balance -= amount;
        //TODO: Transfer to L1 instead
        payable(msg.sender).transfer(amount);
    }

    // SONG MANAGEMENT
    //  - Upload Song
    function upload_song(string memory _name, uint _price, uint _length, uint _duration, bytes32[] memory _chunks) external userExists {
        require(_chunks.length > 0 && _price % _chunks.length == 0, "Price is not divisible by amount of chunks");
        require(_price / _chunks.length % DIST_FEE == 0, "Chunk price is not divisible by distributor fee");
        bytes32 song = gen_song_id(_name, msg.sender);
        require(!songs[song].exists, "Song is already uploaded");

        //Create and upload song's object
        Song memory object;
        object.exists = true;
        object.author = msg.sender;
        object.name = _name;
        object.price = _price;
        object.length = _length;
        object.duration = _duration;
        object.chunks = _chunks;
        songs[song] = object;

        // Set up distribution list
        songs[song].distributors.push(address(0x0));
        bytes32 hash = get_distributor_hash(song, msg.sender);
        distributor_index[hash] = songs[song].distributors.length;
        songs[song].distributors.push(msg.sender);

        //Add song id to list
        song_list.push(song);
    }

    function gen_song_id(string memory _name, address _sender) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(_name, _sender));
    }

    //  - Validate Song
    function manage_validation(bytes32 song) external songExists(song) {
        require(users[msg.sender].is_validator, "User is not validator");
        songs[song].is_valid = !songs[song].is_valid;
    }

    //  - Edit Song
    function edit_price(bytes32 song, uint256 _price) external songExists(song) {
        Song storage song_obj = songs[song];
        require(msg.sender == song_obj.author, "Sender is not the author of the song");
        require(_price % song_obj.chunks.length == 0, "Price is not divisible by amount of chunks");
        require(_price / song_obj.chunks.length % DIST_FEE == 0, "Chunk price is not divisible by distributor fee");
        song_obj.price = _price;
    }

    // DISTRIBUTION MANAGEMENT
    //  - Get distributor hash
    function get_distributor_hash(bytes32 song, address dist) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(song, dist));
    }

    //  - Edit server url of user
    function edit_url(string memory url) external userExists {
        users[msg.sender].server = url;
    }

    //  - Register for a song
    function distribute(bytes32 song) public songValid(song) userExists {
        bytes32 hash = get_distributor_hash(song, msg.sender);
        require(distributor_index[hash] == 0, "Already distributing");
        distributor_index[hash] = songs[song].distributors.length;
        songs[song].distributors.push(msg.sender);
    }

    //  - Cancel distribution
    function undistribute(bytes32 song) external {
        require(is_distributing(song, msg.sender), "Song is not being distributed");
        Song storage song_obj = songs[song];
        bytes32 hash = get_distributor_hash(song, msg.sender);
        for(uint256 i = distributor_index[hash]; i < song_obj.distributors.length - 1; i++) {
            song_obj.distributors[i] = song_obj.distributors[i+1];
        }
        song_obj.distributors.pop();
        distributor_index[hash] = 0;
    }

    function is_distributing(bytes32 song, address distributor) public view returns (bool) {
        return distributor_index[get_distributor_hash(song, distributor)] > 0;
    }
    
    // LISTENING MANAGEMENT
    //  - Create session
    function create_session(bytes32 _song, address _distributor) external songValid(_song) userExists {
        Song storage song_obj = songs[_song];
        uint256 required_balance = song_obj.price + compute_distributor_fee(song_obj.price);
        require(users[msg.sender].balance >= required_balance, "Insufficient balance");
        require(is_distributing(_song, _distributor), "Song is not being distributed");

        // Compute session id
        bytes32 session = gen_session_id(msg.sender, _distributor, _song);
        require(!sessions[session].active, "session already exists");

        // Create and upload session
        Session memory object;
        object.active = true;
        object.listener = msg.sender;
        object.distributor = _distributor;
        object.song = _song;
        object.price = song_obj.price;
        object.balance = required_balance;

        // transfer balance
        users[msg.sender].balance -= object.balance;
        sessions[session] = object;

        // Initialize is_paid array
        Session storage session_obj = sessions[session];
        for(uint i = 0; i < song_obj.chunks.length; i++) {
            session_obj.is_chunk_paid.push(false);
        }
    }

    // - Compute distributors fee (10%)
    function compute_distributor_fee(uint price) public view returns (uint) {
        return price / 100 * DIST_FEE;
    }

    function get_rand_distributor(bytes32 _song) external view returns (address){
        address[] storage distributors = songs[_song].distributors;
        uint256 rand = uint(keccak256(abi.encodePacked(block.timestamp, msg.sender))) % (distributors.length-1);
        return distributors[rand+1];
    }

    function gen_session_id(address _sender, address _distributor, bytes32 _song) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(_sender, _distributor, _song));
    }

    function chunks_length(bytes32 song) external view returns (uint) {
        return songs[song].chunks.length;
    }

    //  - Pay for a given chunk
    function get_chunk(bytes32 session, uint chunk_index) external activeSession(session) {
        Session storage session_obj = sessions[session];
        Song storage song_obj = songs[session_obj.song];
        require(msg.sender == session_obj.listener, "User is not allowed to pay for chunk");
        require(!session_obj.is_chunk_paid[chunk_index], "Chunk has already been paid");

        // Distribute balance
        uint author_compensation = session_obj.price / song_obj.chunks.length;
        uint dist_compensation = compute_distributor_fee(author_compensation);
        session_obj.balance -= author_compensation + dist_compensation;
        users[song_obj.author].balance += author_compensation;
        users[session_obj.distributor].balance += dist_compensation;

        // Mark as paid
        session_obj.is_chunk_paid[chunk_index] = true;
    }

    //  - Check chunk
    function check_chunk(bytes32 song, uint index, bytes32 _chunk) external view returns (bool) {
        return songs[song].chunks[index] == _chunk;
    }

    function is_chunk_paid(bytes32 session, uint index) external view returns (bool) {
        return sessions[session].is_chunk_paid[index];
    }

    //  - Close session
    function close_session(bytes32 session) external activeSession(session) {
        Session storage session_obj = sessions[session];
        require(msg.sender == session_obj.listener || msg.sender == session_obj.distributor, "Not allowed to close this session");

        // Return unspent balance
        users[session_obj.listener].balance += session_obj.balance;

        // Deactivate session
        session_obj.balance = 0;
        session_obj.active = false;
    }
}