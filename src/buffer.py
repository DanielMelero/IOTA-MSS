import os
import vlc
import threading

class Buffer:
    # Default buffer size is approx. 2s - 4s ahead
    def __init__(self, title, session, waiting_limit=5000):
        # Start new temporary file
        if not os.path.exists('tmp'):
            os.makedirs('tmp')
        self.fd = open('tmp/listening.mp3', 'wb')
        self.fd.seek(0)
        self.fd.truncate()
        # Set VLC player
        self.player = vlc.MediaPlayer()
        self.media = vlc.Media(self.fd.name)
        self.player.set_media(self.media)
        # Initialize state
        self.title = title
        self.session = session
        self.waiting_limit = waiting_limit
        self.loaded = 0
        self.last_stop_load = 0
        self.last_pos = 0
        self.running = False
        
    def start(self):
        self.running = True
        self.handle = threading.Thread(target=self.run)
        self.handle.start()

    def add_chunk(self, chunk):
        # Append chunk to temp file
        self.fd.write(chunk)
        self.fd.flush()
        self.loaded += len(chunk)

        if not self.player.is_playing():
            if self.get_time_left() > self.waiting_limit:
                self.player.play()

    def get_time_left(self):
        pos = 0 if self.loaded == 0 else self.player.get_position() * self.last_stop_load / self.loaded
        if pos > 0:
            # Approx from player time and position
            return self.player.get_time() / pos * (1-pos) 
        else: 
            # Approx from percentage loaded of duration
            return self.session.duration * 1000 * (self.loaded/self.session.length)

    def prudent_loading(self):
        i, past_time  = 0, -1
        while i < self.session.chunks_len and self.session.active:
            try:
                # TODO: Get chunks synchronously
                t = self.get_time_left()
                if t != past_time and t < self.waiting_limit:
                    past_time = t
                    self.add_chunk(self.session.get_chunk(i))
                    i += 1
            except Exception as e:
                self.close()
                raise e

    def close(self):
        if self.running:
            self.running = False
            self.handle.join()
            print()

    def get_progress(self):
        vlc_loaded = self.loaded if self.player.is_playing() else self.last_stop_load
        return  vlc_loaded * self.player.get_position()  / self.session.length

    def print_state(self):
        state = '_ ' if self.player.is_playing() else 'p '
        print(f"{state} {'{:.01%}'.format(self.get_progress())} {'{:.01%}'.format(self.loaded/self.session.length)} - {self.title}{' '*9}", end='\r')

    def run(self):
        print()
        while self.get_progress() < 0.99 and self.running:
            self.print_state()
            # Update load state
            if self.player.is_playing():
                self.last_stop_load = self.loaded
            pos = self.player.get_position()
            if self.last_pos != pos:
                # Pause and wait for next chunk
                if self.get_time_left() < self.waiting_limit//2 and self.loaded != self.session.length:
                    self.player.pause()
                self.last_pos = pos
        # Close buffer
        self.player.stop()
        self.running = False
        print()