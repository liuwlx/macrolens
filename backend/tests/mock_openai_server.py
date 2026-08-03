from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self) -> dict:
        length = int(self.headers.get("content-length", "0") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def _send(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send({"ok": True})
        else:
            self._send({"error": {"message": "not found"}}, 404)

    def do_POST(self) -> None:  # noqa: N802
        payload = self._json()
        if self.path.endswith("/embeddings"):
            inputs = payload.get("input") or []
            if isinstance(inputs, str):
                inputs = [inputs]
            self._send(
                {
                    "object": "list",
                    "model": payload.get("model", "text-embedding-3-small"),
                    "data": [
                        {"object": "embedding", "index": index, "embedding": [0.001] * 1536}
                        for index, _ in enumerate(inputs)
                    ],
                    "usage": {"prompt_tokens": len(inputs), "total_tokens": len(inputs)},
                }
            )
            return
        if self.path.endswith("/responses"):
            model = payload.get("model", "gpt-5.6-terra")
            text = (
                "核心结论：通胀动能边际回落，但服务价格仍需观察。[1]\n\n"
                "数据摘要：上下文中的最新证据支持谨慎判断。[1]\n\n"
                "影响判断：政策路径仍然取决于后续数据。[1]\n\n"
                "风险情景：若服务通胀反弹，宽松时点可能后移。[1]\n\n"
                "后续关注：下一期通胀与就业数据。[1]"
            )
            self._send(
                {
                    "id": "resp_acceptance",
                    "object": "response",
                    "created_at": int(time.time()),
                    "status": "completed",
                    "model": model,
                    "output": [
                        {
                            "id": "msg_acceptance",
                            "type": "message",
                            "status": "completed",
                            "role": "assistant",
                            "content": [
                                {"type": "output_text", "text": text, "annotations": []}
                            ],
                        }
                    ],
                    "usage": {
                        "input_tokens": 120,
                        "output_tokens": 80,
                        "total_tokens": 200,
                    },
                }
            )
            return
        self._send({"error": {"message": "unsupported path"}}, 404)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()
