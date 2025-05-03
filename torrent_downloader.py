import os
import threading
import queue
import time
import hashlib
from download_utils import download_piece
from torrent_file_parser import decodeTorrentFile, TorrentInfo

class TorrentDownloader:
    def __init__(self, torrent_info, save_path, our_id, max_connections=5):
        self.torrent_info = torrent_info
        self.save_path = save_path
        self.our_id = our_id
        self.max_connections = max_connections
        self.piece_queue = queue.Queue()
        self.downloaded_pieces = set()
        self.lock = threading.Lock()
        self.total_pieces = len(torrent_info.piece_hashes)
        self.downloaded_bytes = 0
        self.start_time = time.time()

    def create_directory_structure(self):
        """Create necessary directories for multi-file torrents"""
        if len(self.torrent_info.files) > 1:
            os.makedirs(os.path.join(self.save_path, self.torrent_info.name), exist_ok=True)
            for file_path, _ in self.torrent_info.files:
                full_path = os.path.join(self.save_path, self.torrent_info.name, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

    def get_piece_path(self, piece_index):
        """Get the path where a piece should be saved"""
        if len(self.torrent_info.files) == 1:
            return os.path.join(self.save_path, f"piece_{piece_index}")
        else:
            return os.path.join(self.save_path, self.torrent_info.name, f"piece_{piece_index}")

    def download_worker(self):
        """Worker thread that downloads pieces from the queue"""
        while True:
            try:
                piece_index = self.piece_queue.get_nowait()
            except queue.Empty:
                break

            piece_path = self.get_piece_path(piece_index)
            try:
                piece_length = download_piece(
                    self.torrent_info,
                    piece_path,
                    piece_index,
                    self.our_id
                )
                
                with self.lock:
                    self.downloaded_pieces.add(piece_index)
                    self.downloaded_bytes += piece_length
                    
                # Verify piece hash
                with open(piece_path, 'rb') as f:
                    piece_data = f.read()
                    piece_hash = hashlib.sha1(piece_data).hexdigest()
                    if piece_hash != self.torrent_info.piece_hashes[piece_index]:
                        print(f"Hash mismatch for piece {piece_index}, retrying...")
                        self.piece_queue.put(piece_index)
                        continue

                print(f"Downloaded piece {piece_index + 1}/{self.total_pieces} "
                      f"({len(self.downloaded_pieces)/self.total_pieces*100:.1f}%)")
                
            except Exception as e:
                print(f"Error downloading piece {piece_index}: {e}")
                self.piece_queue.put(piece_index)  # Retry later
            finally:
                self.piece_queue.task_done()

    def assemble_files(self):
        """Assemble downloaded pieces into final files"""
        print("Assembling files...")
        if len(self.torrent_info.files) == 1:
            # Single file torrent
            file_path = os.path.join(self.save_path, self.torrent_info.files[0][0])
            with open(file_path, 'wb') as out:
                for i in range(self.total_pieces):
                    piece_path = self.get_piece_path(i)
                    with open(piece_path, 'rb') as f:
                        out.write(f.read())
                    os.remove(piece_path)
        else:
            # Multi-file torrent
            current_offset = 0
            for file_path, file_length in self.torrent_info.files:
                full_path = os.path.join(self.save_path, self.torrent_info.name, file_path)
                with open(full_path, 'wb') as out:
                    remaining = file_length
                    while remaining > 0:
                        piece_index = current_offset // self.torrent_info.piece_length
                        piece_offset = current_offset % self.torrent_info.piece_length
                        piece_path = self.get_piece_path(piece_index)
                        
                        with open(piece_path, 'rb') as f:
                            if piece_offset > 0:
                                f.seek(piece_offset)
                            chunk = f.read(min(remaining, self.torrent_info.piece_length - piece_offset))
                            out.write(chunk)
                            remaining -= len(chunk)
                            current_offset += len(chunk)
                
                # Clean up piece files
                for i in range(self.total_pieces):
                    piece_path = self.get_piece_path(i)
                    if os.path.exists(piece_path):
                        os.remove(piece_path)

    def download(self):
        """Start the download process"""
        print(f"Starting download of {self.torrent_info.name}")
        print(f"Total size: {self.torrent_info.total_length / (1024*1024):.2f} MB")
        print(f"Number of pieces: {self.total_pieces}")
        
        self.create_directory_structure()
        
        # Add all pieces to the queue
        for i in range(self.total_pieces):
            self.piece_queue.put(i)
        
        # Start download threads
        threads = []
        for _ in range(self.max_connections):
            t = threading.Thread(target=self.download_worker)
            t.start()
            threads.append(t)
        
        # Monitor progress
        while any(t.is_alive() for t in threads):
            time.sleep(1)
            elapsed = time.time() - self.start_time
            speed = self.downloaded_bytes / elapsed if elapsed > 0 else 0
            print(f"\rProgress: {len(self.downloaded_pieces)}/{self.total_pieces} pieces "
                  f"({len(self.downloaded_pieces)/self.total_pieces*100:.1f}%) "
                  f"Speed: {speed/1024/1024:.2f} MB/s", end='')
        
        print("\nDownload complete!")
        self.assemble_files()
        print("Files assembled successfully!")

def download_torrent(torrent_file, save_path, our_id, max_connections=5):
    """Main function to download a complete torrent"""
    torrent_info = decodeTorrentFile(torrent_file)
    downloader = TorrentDownloader(torrent_info, save_path, our_id, max_connections)
    downloader.download() 