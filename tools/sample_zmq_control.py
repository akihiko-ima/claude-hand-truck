import zmq
import json
from enum import StrEnum

ctx = zmq.Context()
sock = ctx.socket(zmq.REQ)
sock.connect("tcp://localhost:5556")


class Command(StrEnum):
    INIT = "INIT"
    CAM_START = "CAM_START"
    CAM_STOP = "CAM_STOP"
    MP_START = "MP_START"
    MP_STOP = "MP_STOP"
    FINALIZE = "FINALIZE"
    STATUS = "STATUS"


if __name__ == "__main__":
    sock.send_string(json.dumps({"command": Command.MP_STOP}))
    print(json.loads(sock.recv_string()))
