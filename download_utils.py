import json
import sys
import os
import socket
import struct
import hashlib
import bencodepy
import requests
from urllib.parse import urlparse
from torrent_file_parser import decodeTorrentFile
from request_sending_utility import decode_peers
from udp_tracker_util import udp_tracker_connect, udp_tracker_announce

def download_piece(torrent_info, save_path, piece_index, our_id):
    """
    Download a single piece from a peer and save it to disk.

    Steps:
    1. Get a peer via tracker (HTTP or UDP announce).
    2. TCP handshake with peer.
    3. Exchange bitfield, send 'interested', wait for 'unchoke'.
    4. Break piece into 16 KiB blocks, request each, collect data.
    5. Write piece data to `save_path`.

    Returns:
        Number of bytes written.
    """
    info_hash = bytes.fromhex(torrent_info.info_hash)

    # 1. Get one peer's address
    if torrent_info.tracker_url.startswith(('http://', 'https://')):
        response = requests.get(torrent_info.tracker_url, params={
            'info_hash': info_hash,
            'peer_id': our_id,
            'port': 6881,
            'uploaded': 0,
            'downloaded': 0,
            'left': torrent_info.total_length,
            'compact': 1
        })
        peers_bin = bencodepy.decode(response.content)[b'peers']
    else:
        u = urlparse(torrent_info.tracker_url)
        sock, conn_id = udp_tracker_connect(u.hostname, u.port)
        peers_bin = udp_tracker_announce(
            sock, conn_id, u.hostname, u.port,
            info_hash, our_id, downloaded=0,
            left=torrent_info.total_length, uploaded=0
        )
    if isinstance(peers_bin, list):
        peers = [
            f"{pd[b'ip'].decode('utf-8')}:{pd[b'port']}"
            for pd in peers_bin
        ]
    elif isinstance(peers_bin, bytes):
        peers = decode_peers(peers_bin)
    else:
        raise ValueError("Unexpected peers format from tracker")

    # Try connecting to each peer until we find one that works
    s = None
    for peer in peers:
        ip, port = peer.split(':')
        print(f"Attempting to connect to peer {ip}:{port}")
        
        try:
            # Create new socket for each attempt
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(15)  # Increase timeout
            s.connect((ip, int(port)))
            print(f"Successfully connected to peer {ip}:{port}")
            break  # Exit loop if connection successful
        except socket.timeout:
            print(f"Connection to {ip}:{port} timed out")
            if s:
                s.close()
            continue
        except Exception as e:
            print(f"Failed to connect to {ip}:{port}: {e}")
            if s:
                s.close()
            continue
    
    if s is None:
        raise ConnectionError("Could not connect to any peers")

    # 2. TCP handshake
    pstr = b'BitTorrent protocol'
    handshake = bytes([len(pstr)]) + pstr + 8*b'\x00' + info_hash + our_id
    s.sendall(handshake)
    resp = s.recv(68)
    peer_id_received = resp[48:68]

    # 3. Read bitfield (msg ID 5), then express interest
    length_prefix = s.recv(4)
    msg_len = struct.unpack('>I', length_prefix)[0]
    msg_id = s.recv(1)
    s.recv(msg_len - 1)
    # send 'interested'
    s.sendall(struct.pack('>IB', 1, 2))
    # wait for 'unchoke' (msg ID 1)
    while True:
        lp = s.recv(4)
        ml = struct.unpack('>I', lp)[0]
        mid = s.recv(1)
        if mid == b'\x01':
            break
        s.recv(ml - 1)

    # 4. Request and collect blocks
    if torrent_info.total_length is None:
        raise ValueError("Torrent file is missing length information")
    
    # Calculate piece length
    piece_len = torrent_info.piece_length
    if int(piece_index) == len(torrent_info.piece_hashes) - 1:
        piece_len = torrent_info.total_length - piece_len * (len(torrent_info.piece_hashes) - 1)
    
    with open(save_path, 'wb') as out:
        offset = 0
        while offset < piece_len:
            block_size = min(16*1024, piece_len - offset)
            req = struct.pack('>IBIII', 13, 6, int(piece_index), offset, block_size)
            s.sendall(req)
            # wait for piece (msg ID 7)
            lp = s.recv(4)
            ml = struct.unpack('>I', lp)[0]
            mid = s.recv(1)
            payload = s.recv(ml - 1)
            # payload: index(4), begin(4), block data
            block_data = payload[8:]
            out.write(block_data)
            offset += block_size
    s.close()
    return piece_len
