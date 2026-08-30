from omni_memory.schemas.memory import Episode

EXTRACTION_SYSTEM_PROMPT = """
你是证据优先的小说记忆抽取器。请只从用户提供的 episode 原文中抽取明确表达的事实。
每条事实必须包含 statement、evidence_quote、confidence，并输出合法 JSON。

规则：
1. evidence_quote 必须逐字复制 episode 原文中的连续片段，不能改写、翻译或补全。
2. statement 可以是简洁规范化表达，但不得增加原文没有的信息。
3. 不确定、推测或仅凭常识得到的信息不要抽取。
4. 没有可靠事实时返回 {"facts": []}。
5. 只输出 JSON 对象，格式为 {"facts": [{"kind": "semantic|episodic|procedural", "statement": "...", "evidence_quote": "...", "valid_at": null, "confidence": 0.0, "status": "candidate"}]}。
""".strip()


def build_extraction_user_prompt(episode: Episode) -> str:
    return (
        "请分析下面这条 episode，并按照要求输出 JSON。不要使用 episode 之外的信息。\n\n"
        f"episode_id: {episode.episode_id}\n"
        f"source: {episode.source}\n"
        f"episode_text:\n{episode.text}"
    )
