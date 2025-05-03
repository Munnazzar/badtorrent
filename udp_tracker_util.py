import socket, struct, random, time

def udp_tracker_connect(host, port, retries=3, timeout=5):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout * attempt)   # back off timeout
            protocol_id = 0x41727101980
            action = 0
            transaction_id = random.randint(0, 0x7FFFFFFF)
            msg = struct.pack(">QII", protocol_id, action, transaction_id)
            sock.sendto(msg, (host, port))

            data, _ = sock.recvfrom(16)
            res_action, res_trans, connection_id = struct.unpack(">IIQ", data)
            if res_action != action or res_trans != transaction_id:
                raise Exception("Invalid connect response")
            return sock, connection_id

        except socket.timeout as e:
            last_exc = e
            print(f"Connect attempt {attempt} timed out; retrying...")
            time.sleep(1)
        except Exception:
            sock.close()
            raise
    raise last_exc

def udp_tracker_announce(sock, connection_id, host, port, info_hash, peer_id,
                         downloaded, left, uploaded, event=0, ip=0, key=None,
                         num_want=-1, port_out=6881, timeout=5):
    sock.settimeout(timeout)
    action = 1  # announce
    transaction_id = random.randint(0, 0x7FFFFFFF)
    key = key or random.randint(0, 0x7FFFFFFF)

    # >QII20s20sQQQIIIiH
    # connection_id, action, transaction_id,
    # info_hash (20b), peer_id (20b),
    # downloaded (Q), left (Q), uploaded (Q),
    # event (I), IP (I), key (I), num_want (i), port (H)
    msg = struct.pack(
        ">QII20s20sQQQIIIiH",
        connection_id, action, transaction_id,
        info_hash, peer_id,
        downloaded, left, uploaded,
        event, ip, key, num_want, port_out
    )
    sock.sendto(msg, (host, port))

    # Response header: >IIIII   (action, transaction_id, interval, leechers, seeders)
    # Followed by N * 6-byte peers
    header = sock.recv(20)
    res_action, res_trans, interval, leechers, seeders = struct.unpack(">IIIII", header)
    if res_action != action or res_trans != transaction_id:
        raise Exception("Invalid announce response")

    # Now read the rest: peer list
    peers_binary = sock.recv(6 * leechers)  # or just sock.recv(4096) until enough
    return peers_binary
