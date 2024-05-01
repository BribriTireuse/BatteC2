from uuid import UUID

from flask import Flask, render_template, redirect, url_for

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


if __name__ == '__main__':
    with c2:
        app.run()
