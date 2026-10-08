import json

transcript_paths = [
    "/home/jenil/.gemini/antigravity/brain/ab767f6f-bbb1-49a6-8fc5-a17e0cee60e5/.system_generated/logs/transcript_full.jsonl",
    "/home/jenil/.gemini/antigravity/brain/822bbd67-1a41-487d-bba8-3f00b149abf5/.system_generated/logs/transcript_full.jsonl",
    "/home/jenil/.gemini/antigravity/brain/81e709df-0dbd-4918-8754-62d4f9d7a973/.system_generated/logs/transcript_full.jsonl"
]

content = ""

for path in transcript_paths:
    try:
        with open(path, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if "tool_calls" in data:
                        for call in data["tool_calls"]:
                            if "ChatArea.jsx" in call.get("args", {}).get("TargetFile", ""):
                                name = call.get("name")
                                args = call.get("args", {})
                                if name == "write_to_file":
                                    content = args.get("CodeContent", "")
                                elif name == "replace_file_content" and "assistant-ui" not in args.get("Instruction", "") and "Thread" not in args.get("Instruction", "") and "Thread" not in args.get("ReplacementContent", ""):
                                    target = args.get("TargetContent", "")
                                    replacement = args.get("ReplacementContent", "")
                                    content = content.replace(target, replacement)
                                elif name == "multi_replace_file_content" and "assistant-ui" not in args.get("Instruction", "") and "Thread" not in args.get("Instruction", ""):
                                    for chunk in args.get("ReplacementChunks", []):
                                        target = chunk.get("TargetContent", "")
                                        replacement = chunk.get("ReplacementContent", "")
                                        content = content.replace(target, replacement)
                except Exception as e:
                    pass
    except FileNotFoundError:
        pass

with open("/home/jenil/Pluto/ui/src/components/ChatArea.jsx", "w") as f:
    f.write(content)
print("Restored ChatArea.jsx")
