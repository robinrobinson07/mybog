import json
import utils


def read(path: str):
    with open("database.json", "r", encoding="utf8") as f:
        data = json.loads(f.read())
        return utils.access_path(path, data)


def write(path: str, data: any):
    with open("database.json", "r", encoding="utf8") as f:
        db = json.loads(f.read())
    with open("database.json", "w", encoding="utf8") as f:
        p = path.split(".")
        output = db.copy()
        destination = output
        for i in p:
            destination = destination.get(i)
        destination = data
        f.write(json.dumps(output))
