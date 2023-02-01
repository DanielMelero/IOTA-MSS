import os
import ssl
import socket
import hashlib
CRT_FILE = "tmp/other.crt"

def keccak(data):
    return '0x' + hashlib.sha3_256(data).hexdigest()

class Session:
    def __init__(self, chain, chunk_len):
        self.chain = chain
        self.chunk_len = chunk_len
        self.active = True
        self.on_chain = False
        self.paid_chunks = []

    def create(self, song):
        self.song_id, self.song_name, self.song_auth, self.song_p = song
        # Check balance
        funds = self.chain.get_contract_balance()
        if self.song_p > funds:
            raise Exception(f'\nInsufficient contract funds: {self.song_p-funds} Mi left')
        # Create session in ISC
        self.id, dist = self.chain.create_session(self.song_id)
        if not self.id:
            raise Exception('Execution failed (create_session)')
        self.on_chain = True
        # Get metadata from ISC
        self.length, self.duration, self.chunks_len = self.chain.get_song_metadata(self.song_id)
        # Get session provider
        try:
            self.dist_name = self.chain.get_user_info(dist)[1]
            ip_addr, port, cert = self.chain.get_user_info(dist)[3].split(':')
            self.server_address = (ip_addr, int(port))
            if not os.path.exists('tmp'):
                os.makedirs('tmp')
            with open(CRT_FILE, "w") as f:
                f.write(cert)
        except:
            raise Exception(f'Invalid distributor server ({dist})')

    def pay_chunk(self, index):
        if not self.chain.get_chunk(self.id, index).status:
            raise Exception('Execution failed (get_chunk)')
        self.paid_chunks.append(index)

    def request_chunk(self, index):
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Create SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(CRT_FILE)
        # Connect the socket to the server
        sock.connect(self.server_address)
        ssl_sock = context.wrap_socket(sock)
        try:
            # Form message with session id and chunk index
            msg = f'{self.id}:{index}'
            # Sign message
            signed_msg = f'{msg}:{self.chain.sign_message(msg)}'
            # Send data
            ssl_sock.sendall(str.encode(signed_msg))
            # https://stackoverflow.com/questions/52139071/python-ssl-recv-being-offset-when-data-larger-than-1400
            d = ssl_sock.recv(16384)
            data = d
            while len(d) > 0:
                d = ssl_sock.recv(16384)
                data += d
            return data if data else None
        finally:
            sock = ssl_sock.close()

    def is_valid(self, index, chunk):
        return self.chain.check_chunk(self.song_id, index, chunk)

    def get_chunk(self, index):
        if index not in self.paid_chunks:
            self.pay_chunk(index)
        chunk = self.request_chunk(index)
        if not chunk or not self.is_valid(index, keccak(chunk)):
            raise Exception('Chunk received is not valid')
        return chunk

    def print_bill(self):
        total_paid = self.song_p * (len(self.paid_chunks) / self.chunks_len)
        auth_paid = total_paid / 1.1
        dist_paid = total_paid - auth_paid
        print(f"""
    Amount paid:
        Author ({self.song_auth}): {auth_paid} Mi
        Distributor ({self.dist_name}): {dist_paid} Mi
        Total: {total_paid} Mi
        """)
 
    def close_on_chain(self):
        if not self.chain.close_session(self.id).status:
            print('something went wrong while closing session')
        self.on_chain = False
        self.print_bill()

    def close(self):
        self.active = False
        