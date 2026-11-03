import json
import threading

import pytest
from fastapi.testclient import TestClient
from opendataframework.context import Context
from test_ui_conversations import MESSAGES, TICKETS, support_ns

from odf.ui import chat_history
from odf.ui.chat_history import ChatHistory, assistant_key, thread_key
from odf.ui.server import UiServer


def test_append_starts_a_conversation_titled_by_its_first_question(tmp_path):
    history = ChatHistory(tmp_path / "chat.json", limit=10)
    history.append(
        assistant_key("a1"),
        [
            {"role": "user", "content": "Why is   Thursday's\nbake so big?", "ts": 1.0},
            {"role": "assistant", "content": "Because…", "ts": 2.0},
        ],
    )

    assert history.conversations() == [
        {"id": "a1", "title": "Why is Thursday's bake so big?", "updated": 2.0, "turns": 2}
    ]
    assert [t["role"] for t in history.turns(assistant_key("a1"))] == ["user", "assistant"]


def test_conversations_list_assistant_ones_changed_last_first_leaving_out_threads(tmp_path):
    history = ChatHistory(tmp_path / "chat.json", limit=10)
    history.append(assistant_key("old"), [{"role": "user", "content": "a", "ts": 1.0}])
    history.append(assistant_key("new"), [{"role": "user", "content": "b", "ts": 5.0}])
    history.append(thread_key("support", "ada"), [{"role": "user", "content": "c", "ts": 9.0}])

    assert [c["id"] for c in history.conversations()] == ["new", "old"]
    assert history.get(thread_key("support", "ada"))["updated"] == 9.0
    assert "title" not in history.get(thread_key("support", "ada"))


def test_only_the_latest_turns_up_to_the_limit_are_kept(tmp_path):
    history = ChatHistory(tmp_path / "chat.json", limit=3)
    for i in range(5):
        history.append(assistant_key("a"), [{"role": "user", "content": str(i), "ts": float(i)}])

    assert [t["content"] for t in history.turns(assistant_key("a"))] == ["2", "3", "4"]


def test_a_turn_with_no_time_gets_the_time_it_was_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_history.time, "time", lambda: 42.0)
    history = ChatHistory(tmp_path / "chat.json", limit=3)
    history.append(assistant_key("a"), [{"role": "user", "content": "hi"}])

    assert history.turns(assistant_key("a"))[0]["ts"] == 42.0


@pytest.mark.parametrize(
    "turn", [{"role": "tool", "content": "x"}, {"role": "user", "content": 3}, {"content": "x"}]
)
def test_append_refuses_anything_but_user_and_assistant_text(tmp_path, turn):
    history = ChatHistory(tmp_path / "chat.json", limit=3)

    with pytest.raises(ValueError, match="not a chat turn"):
        history.append(assistant_key("a"), [turn])
    assert not (tmp_path / "chat.json").exists()


def test_delete_removes_a_conversation(tmp_path):
    history = ChatHistory(tmp_path / "chat.json", limit=3)
    history.append(assistant_key("a"), [{"role": "user", "content": "hi"}])

    assert history.delete(assistant_key("a")) is True
    assert history.delete(assistant_key("a")) is False
    assert history.conversations() == []


def test_a_file_that_isnt_json_is_refused_not_replaced(tmp_path):
    path = tmp_path / "chat.json"
    path.write_text("{oops")
    history = ChatHistory(path, limit=3)

    with pytest.raises(ValueError, match="not valid JSON"):
        history.append(assistant_key("a"), [{"role": "user", "content": "hi"}])
    assert path.read_text() == "{oops"


def test_the_file_is_plain_json_any_script_can_read(tmp_path):
    path = tmp_path / "nested" / "chat.json"
    ChatHistory(path, limit=3).append(
        thread_key("support", "ada"), [{"role": "user", "content": "x"}]
    )

    data = json.loads(path.read_text())
    assert data["version"] == 1
    assert list(data["conversations"]) == ["support/ada"]


def test_appends_from_many_threads_at_once_all_land(tmp_path):
    history = ChatHistory(tmp_path / "chat.json", limit=100)

    def add(i):
        history.append(assistant_key("a"), [{"role": "user", "content": str(i), "ts": float(i)}])

    workers = [threading.Thread(target=add, args=(i,)) for i in range(20)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()

    assert len(history.turns(assistant_key("a"))) == 20


def test_a_limit_below_1_is_refused(tmp_path):
    with pytest.raises(ValueError, match="at least 1"):
        ChatHistory(tmp_path / "chat.json", limit=0)


class RecordingEngine:
    """Answers "Sure" and records what each turn was sent."""

    model = "stub"

    def __init__(self):
        self.turns = []

    async def stream(self, messages, context=None):
        self.turns.append((list(messages), context))
        yield {"type": "token", "content": "Su"}
        yield {"type": "token", "content": "re"}


def events_of(response):
    return [json.loads(line) for line in response.text.strip().split("\n")]


def client_for(ctx, tmp_path, engine, **kwargs):
    server = UiServer(ctx, "proj", chat_engine=engine, chat_file=tmp_path / "chat.json", **kwargs)
    return TestClient(server._app)


def test_a_new_assistant_conversation_is_kept_and_continued(tmp_path):
    engine = RecordingEngine()
    with Context(namespaces=set()) as ctx:
        client = client_for(ctx, tmp_path, engine)
        first = client.post("/api/chat", json={"text": "hello"})
        (started, *_) = events_of(first)
        conversation_id = started["id"]
        client.post("/api/chat", json={"text": "and then?", "conversation": conversation_id})
        listed = client.get("/api/chat/conversations").json()
        read = client.get(f"/api/chat/conversations/{conversation_id}").json()
        config = client.get("/api/chat/config").json()

    assert started["type"] == "conversation"
    assert config["history"] is True
    assert [c["id"] for c in listed] == [conversation_id]
    assert [(t["role"], t["content"]) for t in read["turns"]] == [
        ("user", "hello"),
        ("assistant", "Sure"),
        ("user", "and then?"),
        ("assistant", "Sure"),
    ]
    sent, context = engine.turns[1]
    assert [m["content"] for m in sent] == ["hello", "Sure", "and then?"]
    assert context is None


def test_deleting_a_conversation_forgets_it(tmp_path):
    with Context(namespaces=set()) as ctx:
        client = client_for(ctx, tmp_path, RecordingEngine())
        conversation_id = events_of(client.post("/api/chat", json={"text": "hi"}))[0]["id"]
        deleted = client.delete(f"/api/chat/conversations/{conversation_id}")
        gone = client.get(f"/api/chat/conversations/{conversation_id}")
        again = client.delete(f"/api/chat/conversations/{conversation_id}")

    assert deleted.status_code == 204
    assert gone.status_code == 404
    assert again.status_code == 404


def test_asking_in_a_thread_sends_the_thread_and_keeps_the_turn_as_a_note(tmp_path):
    NS, *_ = support_ns(MESSAGES, TICKETS)
    engine = RecordingEngine()
    with Context(namespaces={NS}) as ctx:
        client = client_for(ctx, tmp_path, engine)
        r = client.post(
            "/api/chat",
            json={"text": "close it", "thread": {"channel": "support", "thread": "ada"}},
        )
        items = client.get("/api/channels/support/threads/ada").json()
        listed = client.get("/api/chat/conversations").json()

    assert [e["type"] for e in events_of(r)] == ["token", "token"]
    _, context = engine.turns[0]
    assert 'the "ada" thread of the "support" channel' in context
    assert "received from ada@example.com: My order is late" in context
    assert "sent: Sorry, it's on its way" in context
    assert ".close-ticket.call(ticket_id=10)" in context
    assert "Wrong size" not in context  # bob's thread
    notes = [(i["role"], i["text"]) for i in items if i["kind"] == "note"]
    assert notes == [("user", "close it"), ("assistant", "Sure")]
    assert items[-1]["kind"] == "note"
    assert listed == []  # a thread's conversation isn't an assistant one


def test_a_whole_conversation_sent_by_the_caller_is_kept_nowhere(tmp_path):
    NS, *_ = support_ns(MESSAGES, TICKETS)
    engine = RecordingEngine()
    with Context(namespaces={NS}) as ctx:
        client = client_for(ctx, tmp_path, engine)
        client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "thread": {"channel": "support", "thread": "ada"},
            },
        )

    assert engine.turns[0][1] is not None
    assert not (tmp_path / "chat.json").exists()


def test_a_kept_turn_needs_history_on(tmp_path):
    with Context(namespaces=set()) as ctx:
        client = client_for(ctx, tmp_path, RecordingEngine(), chat_history=0)
        r = client.post("/api/chat", json={"text": "hi"})
        listed = client.get("/api/chat/conversations")
        config = client.get("/api/chat/config").json()

    assert r.status_code == 409
    assert listed.status_code == 404
    assert config["history"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"text": ""},
        {"text": 3},
        {"text": "hi", "conversation": "../etc"},
        {"text": "hi", "thread": "ada"},
        {"text": "hi", "thread": {"channel": "support"}},
    ],
)
def test_a_malformed_turn_is_refused(tmp_path, body):
    NS, *_ = support_ns(MESSAGES, TICKETS)
    with Context(namespaces={NS}) as ctx:
        r = client_for(ctx, tmp_path, RecordingEngine()).post("/api/chat", json=body)

    assert r.status_code == 400


def test_asking_in_a_thread_of_an_unknown_channel_answers_404(tmp_path):
    with Context(namespaces=set()) as ctx:
        r = client_for(ctx, tmp_path, RecordingEngine()).post(
            "/api/chat", json={"text": "hi", "thread": {"channel": "nope", "thread": "ada"}}
        )

    assert r.status_code == 404


def test_the_drawer_lists_kept_conversations_and_asks_in_threads():
    from odf.ui import themes

    html = (themes.STATIC_DIR / "index.html").read_text()
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert 'id="chat-delete"' in html
    assert "fetch('/api/chat/conversations')" in script
    assert "chatKept = chatEnabled && Boolean(cfg.history);" in script
    assert (
        "return thread ? { thread, text } : { conversation: view.id || undefined, text };" in script
    )
    for theme in sorted((themes.STATIC_DIR / "themes").iterdir()):
        css = (theme / "theme.css").read_text()
        assert ".chat-msg.note.user{" in css, theme.name
        assert "#chat-delete[hidden]" in css, theme.name
