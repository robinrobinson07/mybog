import os
from flask import Flask

app = Flask(__name__)

@app.get("/")
def ping():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
