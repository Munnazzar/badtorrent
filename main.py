import json
import sys
import bencodepy
import os
import socket
from urllib.parse import urlparse
import requests
from torrent_file_parser import decodeTorrentFile, TorrentInfo
from request_sending_utility import decode_peers
from udp_tracker_util import udp_tracker_announce, udp_tracker_connect
from download_utils import download_piece
from torrent_downloader import download_torrent

def bytes_to_str(obj):
    if isinstance(obj, dict):
        return {bytes_to_str(k): bytes_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [bytes_to_str(i) for i in obj]
    elif isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return obj.hex()  # Fallback for non-decodable bytes
    else:
        return obj

our_id = b'-PC0001-' + os.urandom(12)  # 8 + 12 = 20 bytes

def print_torrent_info(torrent_info):
    """Print information about the torrent"""
    print(f"Tracker URL: {torrent_info.tracker_url}")
    print(f"Name: {torrent_info.name}")
    print(f"Piece Length: {torrent_info.piece_length} bytes")
    print(f"Total Size: {torrent_info.total_length / (1024*1024):.2f} MB")
    print(f"Number of Pieces: {len(torrent_info.piece_hashes)}")
    
    if len(torrent_info.files) == 1:
        print("\nSingle File:")
        print(f"  - {torrent_info.files[0][0]} ({torrent_info.files[0][1] / (1024*1024):.2f} MB)")
    else:
        print("\nMultiple Files:")
        for path, length in torrent_info.files:
            print(f"  - {path} ({length / (1024*1024):.2f} MB)")

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <command> <torrent_file> [options]")
        print("Commands:")
        print("  decode <bencoded_value> - Decode a bencoded value")
        print("  info <torrent_file> - Show information about a torrent")
        print("  peers <torrent_file> - Show peers for a torrent")
        print("  handshake <torrent_file> <peer> - Perform handshake with a peer")
        print("  download_piece <torrent_file> <save_path> <piece_index> - Download a single piece")
        print("  download <torrent_file> <save_path> - Download entire torrent")
        sys.exit(1)

    command = sys.argv[1]

    if command == "decode":
        bencoded_value = sys.argv[2].encode()
        decoded = bencodepy.decode(bencoded_value)
        print(json.dumps(bytes_to_str(decoded), indent=2))
        sys.exit()
    
    if len(sys.argv) < 3:
        print("Error: torrent file not specified")
        sys.exit(1)

    filename = sys.argv[2]
    if not os.path.exists(filename):
        print(f"Error: file '{filename}' not found")
        sys.exit(1)

    try:
        torrent_info = decodeTorrentFile(filename)
    except Exception as e:
        print(f"Error parsing torrent file: {e}")
        sys.exit(1)

    if command == "info":
        print_torrent_info(torrent_info)
    elif command == "peers":
        try:
            if torrent_info.tracker_url.startswith(("http://", "https://")):
                response = requests.get(torrent_info.tracker_url, params={
                    "info_hash": bytes.fromhex(torrent_info.info_hash),
                    "peer_id": our_id,
                    "port": 6881,
                    "uploaded": 0,
                    "downloaded": 0,
                    "left": torrent_info.total_length,
                    "compact": 1
                })
                response_dict = bencodepy.decode(response.content)
                peers_binary = response_dict[b"peers"]
                if isinstance(peers_binary, list):
                    for peer in peers_binary:
                        print(bytes_to_str(peer))
                else:
                    print(decode_peers(peers_binary))
            elif torrent_info.tracker_url.startswith("udp://"):
                u = urlparse(torrent_info.tracker_url)
                sock, connection_id = udp_tracker_connect(u.hostname, u.port)
                peers_binary = udp_tracker_announce(
                    sock, connection_id, u.hostname, u.port,
                    bytes.fromhex(torrent_info.info_hash), our_id,
                    downloaded=0, left=torrent_info.total_length, uploaded=0
                )
                peers = decode_peers(peers_binary)
                for p in peers:
                    print(p)
            else:
                print(f"Unknown tracker protocol in URL: {torrent_info.tracker_url}")
        except Exception as e:
            print(f"Error getting peers: {e}")
    elif command == "handshake":
        if len(sys.argv) < 4:
            print("Error: peer address not specified")
            sys.exit(1)
        ip, port = sys.argv[3].split(":")
        handshake = b"\x13BitTorrent protocol" + 8*b"\x00" + bytes.fromhex(torrent_info.info_hash) + our_id
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ip, int(port)))
            s.send(handshake)
            print(f"Peer ID: {s.recv(68)[48:].hex()}")
    elif command == "download_piece":
        if len(sys.argv) < 5:
            print("Error: save path and piece index not specified")
            sys.exit(1)
        save_path = sys.argv[3]
        piece_index = sys.argv[4]
        try:
            piece_len = download_piece(filename, save_path, piece_index, our_id)
            print(f"Piece {piece_index} downloaded to {save_path}")
            print(f"Piece length: {piece_len} bytes")
        except Exception as e:
            print(f"Error downloading piece: {e}")
    elif command == "download":
        if len(sys.argv) < 4:
            print("Error: save path not specified")
            sys.exit(1)
        save_path = sys.argv[3]
        try:
            download_torrent(filename, save_path, our_id)
        except Exception as e:
            print(f"Error downloading torrent: {e}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
