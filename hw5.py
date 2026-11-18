"""
Where solution code to HW5 should be written.  No other files should
be modified.
"""

import socket
import io
import time
import typing
import struct
import homework5
import homework5.logging


def send(sock: socket.socket, data: bytes):
    """
    Implementation of the sending logic for sending data over a slow,
    lossy, constrained network.

    Args:
        sock -- A socket object, constructed and initialized to communicate
                over a simulated lossy network.
        data -- A bytes object, containing the data to send over the network.
    """

    # Naive implementation where we chunk the data to be sent into
    # packets as large as the network will allow, and then send them
    # over the network, pausing half a second between sends to let the
    # network "rest" :)
    logger = homework5.logging.get_logger("hw5-sender")
    chunk_size = homework5.MAX_PACKET - 5
    packets = []
    seq = 0
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        seq_bytes = seq.to_bytes(4, "big")
        header = b"D" + seq_bytes
        packet = header + chunk
        packets.append(packet)
        seq += 1
    packets.append(b"F" + len(packets).to_bytes(4, "big"))
    timeout = 2.0
    estimate = None
    change = None
    seq = 0
    for packet in packets:
        while True:
            start = time.time()
            sock.send(packet)
            sock.settimeout(timeout)
            try:
                ack = sock.recv(homework5.MAX_PACKET)
                if len(ack) == 5:
                    kind = ack[0:1]
                    ack_seq = int.from_bytes(ack[1:5], "big")
                    if kind == b"A" and ack_seq == seq:
                        rtt = time.time() - start
                        if estimate is None:
                            estimate = rtt
                            change = rtt / 2
                        else:
                            difference = abs(estimate - rtt)
                            change = 0.75 * change + 0.25 * difference
                            estimate = 0.875 * estimate + 0.125 * rtt
                        timeout = estimate + 4 * change
                        if timeout < 0.1:
                            timeout = 0.1
                        if timeout > 5.0:
                            timeout = 5.0
                        logger.info("Received ACK %d", seq)
                        break
            except socket.timeout:
                logger.info("Timeout: resending seq %d", seq)
                timeout = timeout * 2
                if timeout > 5.0:
                    timeout = 5.0
        seq += 1

def recv(sock: socket.socket, dest: io.BufferedIOBase) -> int:
    """
    Implementation of the receiving logic for receiving data over a slow,
    lossy, constrained network.

    Args:
        sock -- A socket object, constructed and initialized to communicate
                over a simulated lossy network.

    Return:
        The number of bytes written to the destination.
    """
    logger = homework5.logging.get_logger("hw5-receiver")
    num = 0
    expected = 0
    done = False
    while True:
        try:
            packet = sock.recv(homework5.MAX_PACKET)
        except socket.timeout:
            if done:
                return num
            continue
        kind = packet[0:1]
        seq = int.from_bytes(packet[1:5], "big")
        if kind == b"D":
            if seq == expected:
                chunk = packet[5:]
                dest.write(chunk)
                dest.flush()
                num += len(chunk)
                expected += 1
                logger.info("Received packet %d", seq)
            if seq < expected:
                ack = b"A" + seq.to_bytes(4, "big")
                sock.send(ack)
        elif kind == b"F" and seq == expected:
            logger.info("Received FIN")
            ack = b"A" + seq.to_bytes(4, "big")
            sock.send(ack)
            done = True
            sock.settimeout(6.0)