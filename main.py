import json
import sys
import bencodepy
import os
from torrent_file_parser import decodeTorrentFile

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

def main():
    command = sys.argv[1]

    if command == "decode":
        bencoded_value = sys.argv[2].encode()
        decoded = bencodepy.decode(bencoded_value)
        print(json.dumps(bytes_to_str(decoded), indent=2))
    elif command == "info":
        filename = sys.argv[2]
        try :
            os.path.exists(filename)
            filepath = os.path.abspath(filename)
        except :
            raise NotImplemented("FILE NOT FOUND!")
        tracker_URL, length, info_hash = decodeTorrentFile(filepath)
        print(f"Tracker URL: {tracker_URL}, \nLength: {length} \nInfo: {info_hash}")
    else:
        raise NotImplementedError(f"Unknown command {command}")

if __name__ == "__main__":
    main()
