import os, sys
os.environ["DB_BACKEND"]="memory"; os.environ["OPENAI_API_KEY"]="test"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from app.services import chat_service, summary_service
c = TestClient(app)

s = c.get("/api/data/summary"); assert s.status_code==200; S=s.json()
print("SUMMARY:", S["period"], S["count"], S["trend"]); print(" current:", S["current_month"]); print(" top:", S["top_categories"][:3])
print("PROMPT:\n" + chat_service.build_system_prompt(S))

r = c.get("/api/data?limit=3"); assert r.status_code==200 and len(r.json())==3; print("LIST desc first:", r.json()[0])
r = c.get("/api/data?start=2026-03-01&end=2026-03-31&order=asc"); assert all(x["date"].startswith("2026-03") for x in r.json()); print("MAR rows", len(r.json()))
r = c.post("/api/data", json={"date":"2026-10-30","value":45000,"memo":"식비 | 저녁 외식"}); assert r.status_code==201; new=r.json()
assert c.get("/api/data/summary").json()["count"]==S["count"]+1   # cache invalidated
r = c.put(f"/api/data/{new['id']}", json={"value":50000}); assert r.json()["value"]==50000 and r.json()["memo"]=="식비 | 저녁 외식"
assert c.put(f"/api/data/{new['id']}", json={}).status_code==400
assert c.put("/api/data/nope", json={"value":1}).status_code==404
assert c.delete(f"/api/data/{new['id']}").status_code==204
assert c.delete(f"/api/data/{new['id']}").status_code==404
# validation
for bad in [{"date":"2026-13-01","value":1},{"date":"2026-01-01","value":-5},{"date":"2026-01-01","value":10**9},{"date":"2026-01-01","value":1,"memo":"x"*201}]:
    assert c.post("/api/data", json=bad).status_code==422, bad
print("CRUD + validation OK")

# chat with mocked OpenAI
fake = MagicMock(); fake.chat.completions.create.return_value.choices=[MagicMock(message=MagicMock(content="이번 달은 월평균보다 적게 쓰고 있어요."))]
with patch.object(chat_service, "_get_client", return_value=fake):
    r = c.post("/api/chat", json={"message":"이번 달 지출 어때?"}); assert r.status_code==200, r.text; cid=r.json()["conversation_id"]
    sent = fake.chat.completions.create.call_args.kwargs
    assert "[사용자 지출 데이터 요약]" in sent["messages"][0]["content"] and sent["max_completion_tokens"]==500
    r = c.post("/api/chat", json={"message":"식비 줄이는 법?","conversation_id":cid}); assert r.status_code==200
    assert len(fake.chat.completions.create.call_args.kwargs["messages"])==4  # system + 2 history + user
    assert c.post("/api/chat", json={"message":"hi","conversation_id":"nope"}).status_code==404
assert c.post("/api/chat", json={"message":"   "}).status_code==422
fake.chat.completions.create.side_effect=RuntimeError("boom")
with patch.object(chat_service, "_get_client", return_value=fake):
    assert c.post("/api/chat", json={"message":"x"}).status_code==502
print("CHAT OK")

# conversations
r = c.post("/api/conversations", json={"messages":[{"role":"user","content":"수동 저장"},{"role":"assistant","content":"네"}]}); assert r.status_code==201
lst = c.get("/api/conversations").json(); assert len(lst)==2 and "messages" not in lst[0]; print("CONV LIST:", lst)
d = c.get(f"/api/conversations/{cid}").json(); assert d["message_count"]==4 and len(d["messages"])==4
assert c.delete(f"/api/conversations/{cid}").status_code==204 and c.get(f"/api/conversations/{cid}").status_code==404
assert c.post("/api/conversations", json={"messages":[]}).status_code==422
assert c.get("/docs").status_code==200 and c.get("/health").json()=={"status":"ok"}
# CORS preflight
r = c.options("/api/data", headers={"Origin":"http://localhost:5500","Access-Control-Request-Method":"POST"}); assert r.headers.get("access-control-allow-origin")=="http://localhost:5500"
r = c.options("/api/data", headers={"Origin":"http://evil.com","Access-Control-Request-Method":"POST"}); assert "access-control-allow-origin" not in r.headers
print("ALL TESTS PASSED")
