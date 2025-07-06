
from flask import Flask
from time import sleep
import random

app = Flask(__name__)

@app.route("/")
def index():
    sleep(random.uniform(0.1, 0.3))
    return "Hello from the test webserver!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
