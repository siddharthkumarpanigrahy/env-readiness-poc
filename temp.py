import json

with open("db_config.json") as f:
    config = json.load(f)

print(config["Smoke2"]["host"])
print(config["Smoke3"]["service_name"])
