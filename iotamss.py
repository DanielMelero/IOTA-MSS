import glob
import os
import threading
import signal
from tkinter import filedialog
from src.server import Server
from src.session import Session
from src.buffer import Buffer
from src.upload import Upload
from src.chain import Chain
MAGIC_BYTES = b'ID3'
CHUNK_LEN = 30000

class User:
    def __init__(self):
        print("""
 __      __   _                             
 \ \    / /__| |__ ___ _ __  ___            
  \ \/\/ / -_) / _/ _ \ '  \/ -_)           
   \_/\_/\___|_\__\___/_|_|_\___|           
                                            
  _         ___ ___ _____ _      __  __ ___ 
 | |_ ___  |_ _/ _ \_   _/_\ ___|  \/  / __|
 |  _/ _ \  | | (_) || |/ _ \___| |\/| \__ \\
  \__\___/ |___\___/ |_/_/ \_\  |_|  |_|___/
                                                                                                                                      
    """)
        # Connect to chain as a user
        self.chain = Chain()
        self.name = self.chain.get_user_info()[1]
        # Initialize state
        self.serving = False
        self.session = None
        self.server = None
        # Set handler for Ctrl+C signal
        signal.signal(signal.SIGINT, self.handler)

    def listen(self, song):
        _, name, auth, _ = song
        self.session = Session(self.chain, CHUNK_LEN)
        buffer = Buffer(f'{name} by {auth}', self.session)
        while True and self.session.active:
            # Attempt to listen to song until completion
            try:
                # Create session in smart contract
                self.session.create(song)
                # Initialize media player
                buffer.start()
                # Load only when necessary
                buffer.prudent_loading()
                # Wait for song or session to end
                while self.session.active and buffer.running:
                    continue
                break
            except Exception as e:
                print(e)
                if str(e).startswith('\nInsufficient'):
                    break
            finally:
                buffer.close()
                if self.session.active:
                    self.session.close()
                if self.session.on_chain:
                    self.session.close_on_chain()

    def download(self, song):
        song_id, name, auth, _ = song
        if not os.path.exists('downloads'):
            os.makedirs('downloads')
        self.session = Session(self.chain, CHUNK_LEN)
        print()
        while True and self.session.active:
            # Attempt to download until completion
            try:
                self.session.create(song)
                with open(f'downloads/{song_id}.mp3', 'wb') as fd:
                    fd.seek(0)
                    fd.truncate()
                    i = 0
                    while self.session.active and i < self.session.chunks_len:
                        fd.write(self.session.get_chunk(i))
                        fd.flush()
                        print(f"{name} by {auth}: {'{:.01%}'.format((i+1)/self.session.chunks_len)}", end='\r')
                        i +=1
                print()
                return
            except Exception as e:
                print(e)
                if str(e).startswith('\nInsufficient'):
                    break
            finally:
                if self.session.active:
                    self.session.close()
                if self.session.on_chain:
                    self.session.close_on_chain()
    
    def upload(self, src_file):
        # Process file
        upload = Upload(src_file, CHUNK_LEN)
        # Upload song to smart contract
        upload.id = self.chain.upload(upload)
        if not upload.id:
            print('\nExecution failed')
            return
        upload.pprint(self.name)
        # Start serving song
        upload.save()
        self.serve((upload.id, upload.name, self.name), True)

    def start_server(self):
        # Start server on a free port
        port = 10000
        while not self.serving:
            try:
                # Start server
                self.server = Server(port, self.chain, CHUNK_LEN)
                # Set url in Smart Contract
                if not self.chain.edit_url(self.server.url).status:
                    self.exit()
                    raise Exception('Execution failed')
                self.serving = True
            except OSError:
                port += 1
        self.server_handle = threading.Thread(target=self.server.run)
        self.server_handle.start()

    def serve(self, song, uploading=False):
        if not self.serving:
            try:
                self.start_server()
            except Exception as e:
                print(e)
                return
        if not uploading:
            print()
            if not self.chain.distribute(song[0]).status:
                print('Execution failed')
                return
        self.server.new_song(song)
    
    def exit(self):
        if self.serving:
            self.chain.undistribute_all(self.server.songs.keys())
            self.serving = False
            self.server.close()
            self.server_handle.join()
            print('Server Closed')

    def handler(self, signum, frame):
        # Close song
        if self.session is not None and self.session.active:
            self.session.close()
            return
        # Stop monitoring server
        if self.server is not None and self.server.debug:
            self.server.debug = False
            return
        # Exit program
        self.exit()
        exit(1)

def choose_song(songs):
    list = [f'\n\t({i+1}) {s} by {a} - {p} Mi' for i,(_,s,a,p) in enumerate(songs)]
    index = choose_option(list)
    return songs[index] if index is not None else None

def choose_file(song_info, distributing):
    songs = [] 
    for x in glob.glob("downloads/*.mp3"):
        with open(x, 'rb') as fd:
            if fd.read(3) == MAGIC_BYTES:
                id = os.path.basename(x).split('.')[0]
                info = song_info(id)
                if info and not distributing(id):
                    name,auth,_ = info
                    songs.append((id,name,auth))
    list = [f'\n\t({i+1}) {n} by {a}' for i,(_,n,a) in enumerate(songs)]
    index = choose_option(list)
    return songs[index] if index is not None else None

def choose_option(list):
    while True:
        print(f"\nChoose a song:{''.join(list)}\n\t(b) Back\n")
        i = input('> ')
        try:
            return int(i)-1
        except:
            if i == 'b':
                return None
            else:
                print('undefined song')

def amount_to_transfer():
    print()
    while True:
        try:
            return float(input('Amount (in Mi): '))
        except ValueError:
            continue
    
def valid_audio(filename):
    if filename and filename.split('.')[-1] == 'mp3':
        with open(filename, 'rb') as fd:
            if fd.read(3) == MAGIC_BYTES:
                return filename
    print('\nInvalid file uploaded')
    return None


if __name__ == '__main__':
    user = User()
    print(f'Welcome {user.name}!\n')
    print(f'Your chain address is {user.chain.account.address}')
    while True:
        print(user.chain.get_balances())
        print("\nChoose an action:\n\t(l) Listen\n\t(d) Download\n\t(s) Serve\n\t(m) Monitor server\n\t(u) Upload\n\t(t) Transfer\n\t(e) Exit\n")
        i = input('> ')
        match i:
            case 'l':
                song = choose_song(user.chain.get_song_list())
                if song is not None:
                    user.listen(song)
            case 'd':
                song = choose_song(user.chain.get_song_list())
                if song is not None:
                    user.download(song)
            case 's':
                song = choose_file(user.chain.get_valid_song_info, user.chain.is_distributing)
                if song is not None:
                    user.serve(song)
            case 'm':
                if user.serving:
                    user.server.monitor()
                    while user.server.debug:
                        continue
            case 'u':
                file = valid_audio(filedialog.askopenfilename())
                if file is not None:
                    user.upload(file)
            case 't':
                try:
                    if not user.chain.deposit(amount_to_transfer()).status:
                        print('\nExecution failed')
                except Exception as e:
                    print(f'\n{e}')
            case 'e':
                user.exit()
                print('Bye Bye')
                exit(1)
            case _:
                print('undefined action')

    
    