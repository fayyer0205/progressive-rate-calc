"""
Gemini REST API 调用模块 - 替代已弃用的 google-generativeai SDK
支持超时、systemInstruction、完整错误处理
"""
import json
import http.client
import os
import ssl
import time
import urllib.request
import urllib.error

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = None

# 模型调用 API 地址：
# - 默认使用 Zenlayer Gateway（与文档 https://docs.console.zenlayer.com/... 一致）
# - 如需改回官方地址，可在 .env 中设置 GEMINI_BASE=https://generativelanguage.googleapis.com/v1beta/models
GEMINI_BASE = os.environ.get("GEMINI_BASE", "https://gateway.theturbo.ai/v1/v1beta/models")
DEFAULT_TIMEOUT = 120  # 秒
# 最大输出 token，避免长分析/改写被截断；可在 .env 中设置 GEMINI_MAX_OUTPUT_TOKENS（部分模型上限 8192）
MAX_OUTPUT_TOKENS = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
# 连接瞬断/EOF 等网络抖动重试次数
MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "2"))


def _call_gemini(api_key, model_name, user_prompt, system_instruction=None, temperature=0.5, timeout=DEFAULT_TIMEOUT):
    """
    调用 Gemini REST API
    返回 (success: bool, result_or_error: str)
    """
    api_key = (api_key or "").strip()
    if not api_key:
        return False, "请设置 API Key：在页面顶部「Gemini API Key」输入框填写，或在项目根目录创建 .env 并设置 GEMINI_API_KEY=你的密钥。获取地址：https://aistudio.google.com/app/apikey"
    model_name = (model_name or "gemini-2.0-flash").strip()

    base = GEMINI_BASE.rstrip("/")
    # 如果是官方域名，继续使用 ?key= 方式；否则（如 Zenlayer Gateway）改用请求头 x-goog-api-key
    is_official = "generativelanguage.googleapis.com" in base
    if is_official:
        url = f"{base}/{model_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
    else:
        url = f"{base}/{model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": float(temperature),
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    kwargs = {"timeout": timeout}
    if _SSL_CONTEXT:
        kwargs["context"] = _SSL_CONTEXT

    last_transient_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, **kwargs) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            try:
                err_json = json.loads(body)
                msg = err_json.get("error", {}).get("message", body) or str(e)
            except Exception:
                msg = body or str(e)
            if e.code == 404:
                return False, f"模型不存在或不可用: {model_name}。请尝试 gemini-2.0-flash 或 gemini-2.5-flash（在页面上方切换模型）"
            if e.code == 403:
                return False, f"API Key 无效或无权访问: {msg}"
            if e.code == 429:
                return False, f"请求过于频繁或配额不足: {msg}。请将上方模型改为「gemini-2.0-flash」或「gemini-2.5-flash」后重试。"
            return False, f"API 错误 ({e.code}): {msg}"
        except urllib.error.URLError as e:
            msg = str(e.reason) if hasattr(e, "reason") else str(e)
            low = msg.lower()
            # 常见瞬断/EOF/连接重置：可重试
            if any(k in low for k in ["remote end closed", "connection reset", "eof occurred", "unexpected eof", "tlsv1 alert", "broken pipe"]):
                last_transient_err = msg
            elif "timed out" in low or "timeout" in low:
                return False, f"请求超时（{timeout}秒），请减少数据量或更换模型"
            else:
                return False, f"网络错误: {msg}"
        except (http.client.RemoteDisconnected, ConnectionResetError, TimeoutError) as e:
            last_transient_err = str(e)
        except Exception as e:
            return False, str(e)

        # 仅对瞬断类错误重试
        if attempt < MAX_RETRIES and last_transient_err:
            time.sleep(0.6 * (2 ** attempt))
            continue
        if last_transient_err:
            return False, f"网络抖动导致连接被对端关闭（{last_transient_err}），请稍后重试；或降低数据量/降低 GEMINI_MAX_OUTPUT_TOKENS。"
    else:
        # 理论上不会走到这里（for-else）
        return False, "请求失败，请稍后重试"

    # 解析响应
    candidates = out.get("candidates", [])
    if not candidates:
        fb = out.get("promptFeedback", {})
        block_reason = fb.get("blockReason", "UNKNOWN")
        return False, f"模型拒绝生成: {block_reason}"
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not parts:
        return False, "响应为空"
    text = parts[0].get("text", "")
    return True, text
