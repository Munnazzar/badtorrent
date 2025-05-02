import bencodepy
import sys
import hashlib

""""
A torrent file (also known as a metainfo file) contains a bencoded dictionary with the following keys and values:

    announce:
        URL to a "tracker", which is a central server that keeps track of peers participating in the sharing of a torrent.
    info:
        A dictionary with keys:
            length: size of the file in bytes, for single-file torrents
            name: suggested name to save the file / directory as
            piece length: number of bytes in each piece
            pieces: concatenated SHA-1 hashes of each piece

"""
def decodeTorrentFile(filename):
    metadata = bencodepy.decode_from_file(filename)

    tracker_URL = metadata.get(b"announce").decode('utf-8')

    info_dict = metadata.get(b"info")
    if info_dict is None:
        raise ValueError("Missing 'info' dictionary in torrent file")

    length = info_dict.get(b"length")
    bencoded_info = bencodepy.encode(info_dict)
    info_hash = hashlib.sha1(bencoded_info).hexdigest()

    return (tracker_URL, length, info_hash)