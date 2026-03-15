"""
4S店电话销售对话数据分析系统
使用 REST API 直接调用 Gemini，替代已弃用的 google-generativeai SDK
"""
import io
import os
from flask import Flask, render_template, request, jsonify
import pandas as pd
from dotenv import load_dotenv
from gemini_rest import _call_gemini
import json

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')


def _parse_temperature(value, default=0.5):
    """将前端传入的温度字符串安全转换为 [0, 1] 区间内的 float"""
    try:
        t = float(value)
    except (TypeError, ValueError):
        return default
    if t < 0:
        return 0.0
    if t > 1:
        return 1.0
    return t


def parse_excel(file_content, filename):
    """解析对话数据文件，返回按对话ID分组的对话文本

    支持：
    - .xlsx / .xls：表格形式（对话ID / 对话内容）
    - .md：整份 markdown 作为一段长对话
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.md':
        # 将整个 markdown 内容视作一段对话
        try:
            text = file_content.decode('utf-8', errors='replace')
        except Exception:
            text = str(file_content)
        preview = [{
            '对话ID': 'MD-1',
            '对话内容': (text.strip().splitlines() or [''])[0][:80]
        }]
        return text, 1, preview
    if ext == '.xlsx':
        df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
    elif ext == '.xls':
        try:
            df = pd.read_excel(io.BytesIO(file_content), engine='xlrd')
        except Exception as e:
            raise ValueError(f'.xls 解析失败，建议使用 .xlsx 格式: {e}')
    else:
        raise ValueError('仅支持 .xlsx / .xls / .md 格式')

    id_col = content_col = None
    for col in df.columns:
        s = str(col).strip()
        if '对话ID' in s:
            id_col = col
        if '对话内容' in s:
            content_col = col

    if id_col is None or content_col is None:
        raise ValueError('表格必须包含「对话ID」和「对话内容」两列')

    df = df[[id_col, content_col]].dropna(subset=[content_col])
    df.columns = ['对话ID', '对话内容']
    grouped = df.groupby('对话ID')['对话内容'].apply(lambda x: '\n'.join(str(s) for s in x)).to_dict()

    parts = [f"【对话ID: {k}】\n{v}" for k, v in grouped.items()]
    return '\n\n---\n\n'.join(parts), len(grouped), df.head(10).to_dict('records')


def parse_json_excel(file_content, filename):
    """解析「id + JSON」结构的 Excel，展开为结构化行数据"""
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.xlsx':
        df = pd.read_excel(io.BytesIO(file_content), header=None, engine='openpyxl')
    elif ext == '.xls':
        try:
            df = pd.read_excel(io.BytesIO(file_content), header=None, engine='xlrd')
        except Exception as e:
            raise ValueError(f'.xls 解析失败，建议使用 .xlsx 格式: {e}')
    else:
        raise ValueError('仅支持 .xlsx / .xls 格式')

    if df.shape[1] < 2:
        raise ValueError('Excel 至少需要两列：第 1 列为 id，后面至少一列为 JSON 内容')

    output_rows = []
    for _, row in df.iterrows():
        row_id = row.iloc[0]

        # 从第 2 列开始，自动寻找看起来像 JSON 的那一列（包含 "{"）
        raw_json = None
        for v in row.iloc[1:]:
            if pd.isna(v):
                continue
            s = str(v)
            if '{' in s and '}' in s:
                raw_json = s
                break

        if raw_json is None:
            continue

        clean_json = raw_json.strip()

        # 兼容 markdown / 代码块：去掉 ```json / ``` 包裹
        if clean_json.startswith('```'):
            # 去掉首行 ```json 或 ``` 标记
            nl = clean_json.find('\n')
            if nl != -1:
                clean_json = clean_json[nl + 1 :]
        if clean_json.endswith('```'):
            clean_json = clean_json[:-3]

        # 去掉 markdown 表格中的前导竖线和 <br> 换行标记
        clean_json = (
            clean_json.replace('<br>', '')
            .replace('<br/>', '')
            .replace('<br />', '')
        )
        lines = []
        for line in clean_json.splitlines():
            line = line.lstrip()
            if line.startswith('|'):
                line = line.lstrip('|').lstrip()
            lines.append(line)
        clean_json = '\n'.join(lines).strip()

        # 某些导出会把内部双引号变成 ""，尝试修复
        if clean_json.count('""') > 0 and clean_json.count('"') % 2 != 0:
            clean_json = clean_json.replace('""', '"')

        try:
            data = json.loads(clean_json)
        except Exception:
            # 某些行可能不是合法 JSON，直接跳过
            continue

        dims = (data.get("dimensions") or {}) or {}
        rel = (dims.get("relevance") or {}) or {}
        loop = (dims.get("no_looping") or {}) or {}
        wf = (dims.get("workflow_adherence") or {}) or {}
        rigid = (dims.get("non_rigid") or {}) or {}
        colloq = (dims.get("colloquialism_degree") or {}) or {}
        biz = (dims.get("business_value") or {}) or {}

        out_row = {
            "id": row_id,
            "status": data.get("status"),
            "total_score": data.get("total_score"),
            "relevance_score": rel.get("score"),
            "relevance_comment": rel.get("comment"),
            "no_looping_score": loop.get("score"),
            "no_looping_comment": loop.get("comment"),
            "workflow_adherence_score": wf.get("score"),
            "workflow_adherence_comment": wf.get("comment"),
            "non_rigid_score": rigid.get("score"),
            "non_rigid_comment": rigid.get("comment"),
            "colloquialism_score": colloq.get("score"),
            "colloquialism_comment": colloq.get("comment"),
            "business_value_score": biz.get("score"),
            "business_value_comment": biz.get("comment"),
            "overall_analysis": data.get("overall_analysis"),
            "critical_flags": ", ".join(data.get("critical_flags", []))
            if isinstance(data.get("critical_flags"), list)
            else data.get("critical_flags"),
        }
        output_rows.append(out_row)

    return output_rows


def get_default_analyze_instruction():
    """返回默认分析指令"""
    return """你是一个4S店电话销售对话分析专家。

我将提供多段真实电话销售顾问与客户的对话记录。请完成以下任务：

1. **流程节点总结**：归纳该店销售顾问的完整沟通流程，按时间顺序列出节点（如：开场问候、需求探询、产品介绍、报价、试驾邀约、异议处理、成交促成等）

2. **话术提取**：从对话中提取每个节点销售顾问使用的典型话术，至少1-2条

3. **输出格式**：以结构化的JSON格式输出，包含 flow_nodes 数组，每个节点含 order、name、scripts、key_points 等字段。若无JSON则用清晰段落描述。

请基于提供的对话内容进行分析，不要编造。"""


def get_default_rewrite_instruction():
    """返回默认改写指令"""
    return """你是一个AI提示词优化专家，专注4S店电话销售场景。

你将收到两份输入：
1. **分析结果**：从真实对话中提炼的流程节点和话术
2. **原提示词**：用户现有的AI电话机器人提示词模板

请完成改写：
- 保留原提示词的角色设定、约束条件和整体结构
- 用分析结果中的流程节点和话术，替换原提示词中对应的流程和话术描述
- 确保改写后的话术自然、符合电话销售场景
- 若原提示词缺少某流程节点，可依据分析结果补充
- 直接输出完整的改写后提示词，无需额外解释"""


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/json-eval')
def json_eval_page():
    """JSON 打分结果解析页面"""
    return render_template('json_eval.html')


@app.route('/progressive-rate')
def progressive_rate_page():
    """差额定率累进计算页面"""
    return render_template('progressive_rate.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未选择文件'}), 400
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': '未选择文件'}), 400

        content = file.read()
        conv_text, count, preview = parse_excel(content, file.filename)
        return jsonify({
            'success': True,
            'count': count,
            'preview': preview,
            'conversations_text': conv_text
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'解析失败: {str(e)}'}), 500


@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        conv_text = data.get('conversations_text')
        sys_inst = (data.get('system_instructions') or '').strip() or get_default_analyze_instruction()
        api_key = (data.get('api_key') or '').strip() or os.getenv('GEMINI_API_KEY')
        model_name = (data.get('model') or '').strip() or GEMINI_MODEL
        temperature = _parse_temperature(data.get('temperature'), 0.5)

        if not conv_text:
            return jsonify({'error': '请先上传对话数据'}), 400

        prompt = f"请根据以下真实4S店电话销售顾问与客户的对话内容进行分析：\n\n{conv_text}"
        ok, result = _call_gemini(api_key, model_name, prompt, system_instruction=sys_inst, temperature=temperature)
        if ok:
            return jsonify({'success': True, 'analysis': result})
        return jsonify({'error': f'分析失败: {result}'}), 500
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'分析失败: {str(e)}'}), 500


@app.route('/api/rewrite', methods=['POST'])
def rewrite():
    try:
        data = request.get_json()
        analysis_result = data.get('analysis_result', '')
        original_prompt = data.get('original_prompt', '')
        sys_inst = (data.get('system_instructions') or '').strip() or get_default_rewrite_instruction()
        api_key = (data.get('api_key') or '').strip() or os.getenv('GEMINI_API_KEY')
        model_name = (data.get('model') or '').strip() or GEMINI_MODEL
        temperature = _parse_temperature(data.get('temperature'), 0.5)

        if not analysis_result:
            return jsonify({'error': '请先执行分析获取分析结果'}), 400
        if not original_prompt:
            return jsonify({'error': '请输入原提示词'}), 400

        prompt = f"""## 分析结果
{analysis_result}

## 原提示词
{original_prompt}

请根据 System Instructions 完成改写，直接输出改写后的完整提示词。"""
        ok, result = _call_gemini(api_key, model_name, prompt, system_instruction=sys_inst, temperature=temperature)
        if ok:
            return jsonify({'success': True, 'rewritten': result})
        return jsonify({'error': f'改写失败: {result}'}), 500
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'改写失败: {str(e)}'}), 500


@app.route('/api/execute', methods=['POST'])
def execute():
    """一键执行：分析 + 改写"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '请上传对话数据文件'}), 400
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': '请上传对话数据文件'}), 400

        conv_text, _, _ = parse_excel(file.read(), file.filename)
        sys_inst_1 = (request.form.get('system_instructions_1') or '').strip() or get_default_analyze_instruction()
        sys_inst_2 = (request.form.get('system_instructions_2') or '').strip() or get_default_rewrite_instruction()
        original_prompt = (request.form.get('original_prompt') or '').strip()
        api_key = (request.form.get('api_key') or '').strip() or os.getenv('GEMINI_API_KEY')
        model_name_1 = (request.form.get('model_1') or '').strip()
        model_name_2 = (request.form.get('model_2') or '').strip()
        temperature_1 = _parse_temperature(request.form.get('temperature_1'), 0.5)
        temperature_2 = _parse_temperature(request.form.get('temperature_2'), 0.5)

        if not original_prompt:
            return jsonify({'error': '请输入原提示词'}), 400

        # 分析
        ok1, analysis_result = _call_gemini(
            api_key, model_name_1 or GEMINI_MODEL,
            f"请根据以下对话内容进行分析：\n\n{conv_text}",
            system_instruction=sys_inst_1,
            temperature=temperature_1,
        )
        if not ok1:
            return jsonify({'error': f'分析失败: {analysis_result}'}), 500

        # 改写
        prompt2 = f"""## 分析结果
{analysis_result}

## 原提示词
{original_prompt}

请输出改写后的完整提示词。"""
        ok2, rewritten = _call_gemini(
            api_key, model_name_2 or GEMINI_MODEL,
            prompt2,
            system_instruction=sys_inst_2,
            temperature=temperature_2,
        )
        if not ok2:
            return jsonify({'error': f'改写失败: {rewritten}'}), 500

        return jsonify({'success': True, 'analysis': analysis_result, 'rewritten': rewritten})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'执行失败: {str(e)}'}), 500


@app.route('/api/defaults', methods=['GET'])
def defaults():
    """获取默认 System Instructions"""
    return jsonify({
        'analyze': get_default_analyze_instruction(),
        'rewrite': get_default_rewrite_instruction()
    })


@app.route('/api/json-eval/parse', methods=['POST'])
def json_eval_parse():
    """上传 Excel（id + JSON）并解析为结构化行数据"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未选择文件'}), 400
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': '未选择文件'}), 400

        rows = parse_json_excel(file.read(), file.filename)
        return jsonify({'success': True, 'rows': rows})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'解析失败: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)
