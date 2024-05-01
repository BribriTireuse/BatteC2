from flask import Flask, render_template

from c2 import C2

c2 = C2(("127.0.0.1", 1337))
app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html", c2=c2)


if __name__ == '__main__':
    with c2:
        app.run()
