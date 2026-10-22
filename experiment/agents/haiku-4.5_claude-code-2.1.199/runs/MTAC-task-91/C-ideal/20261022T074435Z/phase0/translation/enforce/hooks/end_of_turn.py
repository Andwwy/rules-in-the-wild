"""Stop: the reply rules R1, R2, R3, R4, R8 on the reply (their routes: Response sent, before / at; R4: always); R6 on
every code file of the project (its route: File write / edit, after: at the end of the turn, every file); and R5 and
R7 on every code file again (on_disk.py), for what shell commands wrote. A violation sends the agent back to work,
with the violations as feedback."""
import json
import sys

sys.path.insert(0, "/opt/enforce")
sys.path.insert(0, "/opt/enforce/hooks")
import R1_reply_start, R2_self_reference, R3_address_user, R4_chinese, R6_ai_note, R8_reply_end   # noqa: E402,E401
from common import code_files, read                             # noqa: E402
from on_disk import r5_r7                                       # noqa: E402


def text_of(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def reply_from_transcript(path: str) -> str:
    """The turn's last non-empty assistant text: the reply that the user gets."""
    reply = ""
    try:
        rows = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
    except (OSError, ValueError):
        return ""
    for row in rows:
        msg = row.get("message") or {}
        if row.get("type") == "user" and not row.get("isMeta") and isinstance(msg.get("content"), str):
            reply = ""                                          # a new prompt: a new turn
        elif row.get("type") == "assistant" and text_of(msg).strip():
            reply = text_of(msg)
    return reply


def main() -> int:
    event = json.load(sys.stdin)
    reply = event.get("last_assistant_message")
    if not isinstance(reply, str) or not reply.strip():
        reply = reply_from_transcript(event.get("transcript_path", ""))
    found = []
    for rule in (R1_reply_start, R2_self_reference, R3_address_user, R4_chinese, R8_reply_end):
        found += rule.problems(reply, "the reply")
    for f in code_files():
        found += R6_ai_note.problems(read(f), f)
    found += r5_r7()
    if found:
        reason = ("The project's enforcement of CLAUDE.md: the turn cannot end yet. Fix every violation below, then "
                  "end the turn with the whole reply written again (complete, as the user should get it), not a note "
                  "about the fix.\n" + "\n".join(found))
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
