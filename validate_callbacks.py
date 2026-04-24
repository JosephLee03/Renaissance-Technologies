import requests
import json
import sys

base_url = "http://127.0.0.1:8068"
failures = 0

try:
    # 1. GET /_dash-layout
    r_layout = requests.get(f"{base_url}/_dash-layout")
    print(f"GET /_dash-layout status: {r_layout.status_code}")
    if r_layout.status_code != 200: failures += 1

    # 2. GET /_dash-dependencies
    r_deps = requests.get(f"{base_url}/_dash-dependencies")
    print(f"GET /_dash-dependencies status: {r_deps.status_code}")
    if r_deps.status_code != 200: 
        failures += 1
        deps = []
    else:
        deps = r_deps.json()

    # 3. POST for each dependency
    # We'll just try one simple update if possible, or iterate a bit.
    # Dash expects 'output', 'outputs', 'inputs', 'changedPropIds'
    for dep in deps[:5]: # Cap at 5 for brevity
        output_spec = dep['output']
        payload = {
            "output": output_spec,
            "outputs": dep.get('outputs', output_spec),
            "inputs": [{"id": i['id'], "property": i['property'], "value": None} for i in dep['inputs']],
            "changedPropIds": []
        }
        r_upd = requests.post(f"{base_url}/_dash-update-component", json=payload)
        print(f"POST {output_spec} status: {r_upd.status_code}")
        if r_upd.status_code not in [200, 204]: failures += 1

    print(f"Total failures: {failures}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
