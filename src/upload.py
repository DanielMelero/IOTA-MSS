import os
import hashlib
from mutagen.mp3 import MP3

def keccak(data):
    return '0x' + hashlib.sha3_256(data).hexdigest()

class Upload():
    def __init__(self, filename, chunk_len):
        with open(filename, 'rb') as fd:
            # Get data's length
            data = fd.read()
            self.data = data
            self.length = len(data)
            # Double hash each chunk
            self.chunks = [keccak(data[i:i+chunk_len]) for i in range(0, len(data), chunk_len)]
        # Get song's duration
        self.duration = MP3(filename).info.length
        # Get song's name and price from user input
        print()
        self.name = input("Song's name: ")
        self.price = self.input_float("Song's price (in Mi): ")

    def input_float(self, msg):
        while True:
            try:
                return float(input(msg))
            except ValueError:
                continue

    def save(self):
        # Save data to downloads
        if not os.path.exists('downloads'):
            os.makedirs('downloads')
        with open(f'downloads/{self.id}.mp3', 'wb') as fd:
            fd.seek(0)
            fd.truncate()
            fd.write(self.data)

    def pprint(self, username):
        print(f"""
New song uploaded: {self.name} by {username}

    id:       {self.id}
    price:    {self.price} Mi
    duration: {self.duration}
    length:   {self.length}
    chunks:   {len(self.chunks)}

        """)