USAGE_CHOICES = [
    ("general_chat", "通用对话"),
    ("requirement_integrator", "需求整合"),
    ("testcase_writer", "用例生成"),
    ("testcase_enhancer", "用例增强"),
    ("testcase_reviewer", "用例评审"),
    ("vision_analyzer", "图片理解"),
    ("embedding", "文本向量"),
    ("automation_agent", "自动化 Agent"),
]

ROLE_TYPE_CHOICES = [
    ("general_chat", "通用对话助手"),
    ("requirement_integrator", "需求整合专家"),
    ("testcase_writer", "测试用例生成专家"),
    ("testcase_enhancer", "测试用例增强专家"),
    ("testcase_reviewer", "测试用例评审专家"),
    ("vision_analyzer", "图片理解专家"),
    ("embedding", "文本向量角色"),
    ("automation_agent", "自动化执行 Agent"),
]

USAGE_PROTOCOLS = {
    "general_chat": ["openai_compatible", "gemini"],
    "requirement_integrator": ["openai_compatible", "gemini"],
    "testcase_writer": ["openai_compatible", "gemini"],
    "testcase_enhancer": ["openai_compatible", "gemini"],
    "testcase_reviewer": ["openai_compatible", "gemini"],
    "vision_analyzer": ["openai_responses", "gemini"],
    "embedding": ["gemini"],
    "automation_agent": ["openai_compatible", "gemini"],
}

PROVIDER_DEFAULTS = {
    "chatgpt": {
        "protocol": "openai_compatible",
        "base_url": "https://api.openai.com",
    },
    "deepseek": {
        "protocol": "openai_compatible",
        "base_url": "https://api.deepseek.com",
    },
    "gemini": {
        "protocol": "gemini",
        "base_url": "https://generativelanguage.googleapis.com",
    },
    "qwen": {
        "protocol": "openai_compatible",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode",
    },
}

PROTOCOL_PROVIDERS = {
    "openai_compatible": ["chatgpt", "deepseek", "qwen"],
    "openai_responses": ["chatgpt"],
    "gemini": ["gemini"],
}


def usage_label(usage):
    return dict(USAGE_CHOICES).get(usage, usage)


def role_label(role_type):
    return dict(ROLE_TYPE_CHOICES).get(role_type, role_type)
