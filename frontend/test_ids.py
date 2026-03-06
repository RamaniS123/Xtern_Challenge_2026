import re

with open('app.js') as f:
    app = f.read()

ids_in_app = re.findall(r'document\.getElementById\([\'"](.*?)[\'"]\)', app)
unique_app_ids = set(ids_in_app)

with open('index.html') as f:
    html = f.read()

ids_in_html = set(re.findall(r'id=[\'"](.*?)[\'"]', html))

missing = [id for id in unique_app_ids if id not in ids_in_html]
print('MISSING IDs in index.html:', missing)
