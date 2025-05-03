import bencodepy
import sys
import hashlib
import os

"""
A torrent file (also known as a metainfo file) contains a bencoded dictionary with the following keys and values:

    announce:
        URL to a "tracker", which is a central server that keeps track of peers participating in the sharing of a torrent.
    info:   
        A dictionary with keys:
            For single-file torrents:
                length: size of the file in bytes
                name: suggested name to save the file as
                piece length: number of bytes in each piece
                pieces: concatenated SHA-1 hashes of each piece
            For multi-file torrents:
                files: list of dictionaries, each containing:
                    length: size of the file in bytes
                    path: list of strings representing the path and filename
                name: suggested name to save the directory as
                piece length: number of bytes in each piece
                pieces: concatenated SHA-1 hashes of each piece
"""

class TorrentInfo:
    def __init__(self, tracker_url, info_hash, piece_hashes, piece_length, name, files=None):
        self.tracker_url = tracker_url
        self.info_hash = info_hash
        self.piece_hashes = piece_hashes
        self.piece_length = piece_length
        self.name = name
        self.files = files  # None for single-file torrents, list of (path, length) tuples for multi-file
        self.total_length = sum(f[1] for f in files) if files else None

def decodeTorrentFile(filename):
    metadata = bencodepy.decode_from_file(filename)

    tracker_URL = metadata.get(b"announce").decode('utf-8')

    info_dict = metadata.get(b"info")
    if info_dict is None:
        raise ValueError("Missing 'info' dictionary in torrent file")

    # Get common fields
    piece_length = info_dict.get(b"piece length")
    if piece_length is None:
        raise ValueError("Torrent file is missing piece length information")
    
    name = info_dict.get(b"name").decode('utf-8')
    pieces = info_dict.get(b"pieces")
    if pieces is None:
        raise ValueError("Torrent file is missing pieces information")
    
    piece_hashes = [pieces[i:i+20].hex() for i in range(0, len(pieces), 20)]
    bencoded_info = bencodepy.encode(info_dict)
    info_hash = hashlib.sha1(bencoded_info).hexdigest()

    # Handle single-file vs multi-file torrents
    if b"files" in info_dict:
        # Multi-file torrent
        files = []
        for file_info in info_dict[b"files"]:
            path = os.path.join(*[p.decode('utf-8') for p in file_info[b"path"]])
            length = file_info[b"length"]
            files.append((path, length))
        return TorrentInfo(tracker_URL, info_hash, piece_hashes, piece_length, name, files)
    else:
        # Single-file torrent
        length = info_dict.get(b"length")
        if length is None:
            raise ValueError("Torrent file is missing length information")
        return TorrentInfo(tracker_URL, info_hash, piece_hashes, piece_length, name, [(name, length)])