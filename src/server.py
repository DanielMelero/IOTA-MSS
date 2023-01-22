import socket

class Server:
    def __init__(self, port, chain, chunk_len, debug=False):
        self.chain = chain
        self.chunk_len = chunk_len
        self.debug = debug

        # Create a TCP/IP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(0.2)

        # Bind the socket to the port
        server_address = ('localhost', port)
        self.sock.bind(server_address)
        self.url = f'{server_address[0]}:{server_address[1]}'

        # Listen for incoming connections
        self.sock.listen(1)

        # Initialize song dictionary
        self.songs = {}
        self.closed = False

        print(f'serving music on {self.url}')

    def monitor(self):
        self.debug = True
        print(f"""
Currently serving {len(self.songs.keys())} songs.
        """)

    def new_song(self, song):
        id,name,auth = song
        filename = f'downloads/{id}.mp3'
        with open(filename, 'rb') as f:
            data = f.read()
        self.songs[id] = [data[i:i+self.chunk_len] for i in range(0, len(data), self.chunk_len)]
        print(f'Serving new song: {name} by {auth}')

    def close(self):
        self.closed = True

    def respond(self, conn, msg):
        try:
            id, index, signature = tuple(msg.decode().split(':'))
            # Get session information
            active,addr,dist,song_id,p,_ = tuple(self.chain.get_session_info(id))
            # Check session is correct
            if not active or dist != self.chain.account.address:
                raise Exception('session not active or incorrect distributor')
            # Check sender is session listener
            if not self.chain.verify_message(f'{id}:{index}', signature, addr):
                raise Exception('message sender does not correspond with session listener')
            # Check chunk is paid
            if not self.chain.is_chunk_paid(id, int(index)):
                raise Exception('chunk index has not yet been paid')
            # send chunk
            chunk = self.songs[song_id][int(index)]
            conn.sendall(chunk)
            if self.debug:
                print(f"Sent chunk {index} of {song_id} to {addr}: {p/len(self.songs[song_id]) * 0.1} Mi received")
        except Exception as e:
            if self.debug:
                print(f'Bad request: {e}\n\twith msg: {msg}')

    def run(self):
        while not self.closed:
            try:
                # Wait for a connection or timeout
                conn, _ = self.sock.accept()
                try:
                    msg = conn.recv(256)
                    self.respond(conn, msg)
                finally:
                    conn.close()
            except socket.timeout:
                continue