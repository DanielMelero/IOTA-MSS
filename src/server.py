import os
import ssl
import socket
from OpenSSL import crypto
CRT_FILE, KEY_FILE = "tmp/server.crt", "tmp/priv.key"

class Server:
    def __init__(self, port, chain, chunk_len, debug=False):
        self.chain = chain
        self.chunk_len = chunk_len
        self.debug = debug

        # Create a TCP/IP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(0.2)

        # Create SSL context
        cert_gen()
        self.context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.context.load_cert_chain(certfile=CRT_FILE, keyfile=KEY_FILE)

        # Bind the socket to the port
        server_address = ('localhost', port)
        self.sock.bind(server_address)
        with open(CRT_FILE, 'r') as c:
            self.url = f'{server_address[0]}:{server_address[1]}:{c.read()}'

        # Listen for incoming connections
        self.sock.listen(1)

        # Initialize song dictionary
        self.songs = {}
        self.closed = False

        print(f'serving music on {self.url.split(":")[:-1]}')

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
                ssl_conn = self.context.wrap_socket(conn, server_side=True)
                try:
                    msg = ssl_conn.recv(256)
                    self.respond(ssl_conn, msg)
                finally:
                    ssl_conn.close()
            except socket.timeout:
                continue

def cert_gen(
    emailAddress="emailAddress",
    commonName="commonName",
    countryName="NT",
    localityName="localityName",
    stateOrProvinceName="stateOrProvinceName",
    organizationName="organizationName",
    organizationUnitName="organizationUnitName"):
    # Create a key pair
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    # Create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = countryName
    cert.get_subject().ST = stateOrProvinceName
    cert.get_subject().L = localityName
    cert.get_subject().O = organizationName
    cert.get_subject().OU = organizationUnitName
    cert.get_subject().CN = commonName
    cert.get_subject().emailAddress = emailAddress
    cert.set_serial_number(0)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')
    # Write public and private key files
    if not os.path.exists('tmp'):
            os.makedirs('tmp')
    with open(CRT_FILE, "w") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    with open(KEY_FILE, "w") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))