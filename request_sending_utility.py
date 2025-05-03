import sys
import bencodepy
import hashlib
import urllib.parse
import requests
import struct

def get_info_hash(info_dict):
    
    info_encoded = bencodepy.encode(info_dict)
    return hashlib.sha1(info_encoded).digest()

def decode_peers(peers_binary):
    """
    Decodes a compact peer list from the tracker response.
    
    Each peer is represented using 6 bytes:
        - First 4 bytes: IP address
        - Last 2 bytes: Port number
    
    Args:
        peers_binary (bytes): The compact peer list from the tracker.
        
    Returns:
        list[str]: A list of peer addresses in the format "IP:PORT".
    """
    peers = []
    for i in range(0, len(peers_binary), 6):
        ip = ".".join(str(b) for b in peers_binary[i:i+4])
        port = struct.unpack("!H", peers_binary[i+4:i+6])[0]
        peers.append(f"{ip}:{port}")
    return peers

