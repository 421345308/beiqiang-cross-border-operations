import json
import sys
import urllib.request

node_name = sys.argv[1]
info = json.load(urllib.request.urlopen("http://127.0.0.1:8188/object_info"))
if node_name == "--video-image-loaders":
    names = []
    for name, node in info.items():
        output = node.get("output") or []
        if "video" in name.lower() and "IMAGE" in output:
            names.append({"name": name, "output": output, "input": node.get("input")})
    print(json.dumps(names, ensure_ascii=True))
else:
    node = info[node_name]
    print(json.dumps({"input": node.get("input"), "output": node.get("output")}, ensure_ascii=True))
