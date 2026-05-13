import http.client
import json

def parse_sse(data: bytes) -> list[dict]:
    messages = []
    current_data = []
    for line in data.decode("utf-8").splitlines():
        if line.startswith("data: "):
            current_data.append(line[6:])
        elif line.strip() == "" and current_data:
            messages.append(json.loads("".join(current_data)))
            current_data = []
    if current_data:
        messages.append(json.loads("".join(current_data)))
    return messages

def send(conn: http.client.HTTPConnection, method: str, params: dict | None, msg_id: int | None, session_id: str = "") -> tuple[bytes, str]:
    payload: dict = {"jsonrpc": "2.0", "method": method}
    if msg_id is not None:
        payload["id"] = msg_id
    if params is not None:
        payload["params"] = params
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream, */*",
        "Connection": "keep-alive",
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    conn.request("POST", "/mcp", body=body, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    new_session = resp.getheader("mcp-session-id", session_id)
    return data, new_session

def test():
    conn = http.client.HTTPConnection("127.0.0.1", 8080)
    
    # 1. initialize
    data, session_id = send(conn, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "Ludens-Flow", "version": "3.0.0"}
    }, 1)
    print(f"Session ID: {session_id}")
    for m in parse_sse(data):
        print(f"initialize -> {list(m.keys())}")
    
    # 2. notifications/initialized
    data, session_id = send(conn, "notifications/initialized", None, None, session_id)
    print(f"initialized -> status ok, session: {session_id}")
    
    # 3. tools/list
    data, session_id = send(conn, "tools/list", {}, 2, session_id)
    print(f"tools/list raw: {data.decode('utf-8', errors='replace')[:500]}")
    for m in parse_sse(data):
        print(f"tools/list -> {list(m.keys())}")
        if "result" in m:
            tools = m["result"].get("tools", [])
            print(f">>> Found {len(tools)} tools:")
            for t in tools:
                print(f"  - {t.get('name')}")
    
    conn.close()

if __name__ == "__main__":
    test()
