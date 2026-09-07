#!/usr/bin/env python3
"""Build a self-contained palm-culture report from validated JSON data."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ALLOWED_QUALITY = {"高", "中", "低"}
ALLOWED_CONFIDENCE = ALLOWED_QUALITY | {"不可辨"}
MAJOR_LINE_NAMES = ("生命线", "智慧线", "感情线")
MINOR_LINE_NAMES = {
    "命运线",
    "玉柱纹",
    "太阳线",
    "水星线",
    "腕横纹",
    "小指下方短横纹",
}
OVERALL_LABELS = {"掌面比例", "掌面宽窄", "手指比例", "手指轮廓", "掌丘轮廓", "可见区域"}
ALLOWED_GUIDE_TITLES = {
    "你的手相解析指南",
    "手相解析指南",
    "掌纹观察指南",
    "民俗掌纹观察报告",
    "素掌纪",
}
HAND_LABEL_PATTERN = re.compile(
    r"^(?:左手|右手|手别未知) "
    r"(?:掌心正面|掌心斜视|视角未知)"
    r"(?: (?:镜像状态未知|已确认镜像|已确认未镜像))?$"
)
ROOT_KEYS = {
    "guide_title",
    "hand_label",
    "image_quality",
    "coverage_note",
    "overall",
    "major_lines",
    "minor_lines",
    "reflection_questions",
}
COMMON_ITEM_KEYS = {"observation", "confidence", "tradition", "reflection", "limitation"}
PLACEHOLDER_PATTERN = re.compile(r"{{[A-Z0-9_]+}}")
MANDATORY_TEMPLATE_TEXT = (
    "科学预测置信度：不适用",
    "不构成科学测量、医疗诊断、法律意见、投资建议或未来预测",
)
FIXED_CANNOT_CONCLUDE = (
    "不能由掌纹判断健康、疾病、寿命或死亡时间。",
    "不能由掌纹预测法律结果、投资收益、婚姻结局或具体未来。",
    "不能由手部外观识别身份或推断敏感属性。",
)
UNSAFE_DYNAMIC_TERMS = re.compile(
    r"健康|寿命|享寿|长寿|短命|长命|死亡|离世|去世|猝死|大限|寒暑|"
    r"病|症|患|癌|肿瘤|白血|怀孕|生育|流产|器官|血压|血糖|药物|治疗|诊断|"
    r"抑郁|焦虑|自闭|双相|精神状态|智商|人格|性格真值|"
    r"忠诚|出轨|婚姻|婚期|结婚|离婚|会分手|将分手|分手时间|分手结局|恋爱结局|"
    r"背叛|婚恋|伴侣|破产|投资|股票|基金|债券|虚拟币|收益|回报|获利|"
    r"赚钱|稳赚|赔钱|亏损|钱财|金钱|财富|彩票|中奖|大奖|暴富|"
    r"官司|诉讼|判决|胜诉|败诉|会赢|会输|坐牢|判刑|违法|犯罪|"
    r"性别|族群|民族|种族|宗教|残障|国籍|政治倾向|"
    r"注定|必然|一定|绝对|肯定|保证|毫无疑问|百分之|概率|预示|"
    r"诅咒|凶|煞|灾|祸|克夫|克妻|付费化解|转运|发财|富贵|贫穷|"
    r"横财|赌博|未来|命格|寿元|寿数|阳寿|天年|终老|春秋"
)
AGE_OR_PREDICTION_PATTERN = re.compile(
    r"(?:\d+|[一二三四五六七八九十百零〇两有]+)\s*(?:岁|年|%|％|个寒暑)|"
    r"明年|后年|某年|某岁|年内|将至|必将"
)
GENERAL_PREDICTION_PATTERN = re.compile(
    r"(?:会|将|能|必)(?:在|于|有|得|获|遇|成|变|赢|输|发生|出现|成为|通过|"
    r"升|降|结|赚|赔|患|活)|明天|后天|下周|下月|下个月|近期|不久后|很快"
)
CLAIM_PATTERN = re.compile(r"表示|代表|意味着|预示|暗示|断定|推断|看出|算出")
PERSONAL_SUBJECT_PATTERN = re.compile(r"你|您|他|她|此人|命主|掌主|孩子|本人")
PRIVACY_TERMS = re.compile(
    r"姓名|身份证|住址|地址|电话|手机|微信|邮箱|学校|班级|公司|账号|住在|来自|"
    r"先生|女士|同学|老师|的左手|的右手|的手掌|的掌纹"
)
LONG_NUMBER_PATTERN = re.compile(r"\d{5,}|[零〇一二三四五六七八九十两]{7,}")
ALLOWED_TEXT_PATTERN = re.compile(
    r"^[\u3400-\u4dbf\u4e00-\u9fff0-9\s，。；：、？！“”‘’《》（）【】—…·,.!?;:<>/&\"'＋－×]+$"
)
EXPECTED_TEMPLATE_SHA256 = "30e2f5e8fd03f5c7a1723ca2817e88d1f40736bc1f3ce822c051df9dbea98224"
EXPECTED_VOCABULARY_SHA256 = "145b87e425f7b2a92d161378e1cfaab3b988191dd535d39850a38b3be25b02b6"
VOCABULARY_KEYS = {
    "coverage_notes",
    "observations",
    "traditions",
    "reflections",
    "limitations",
}
REQUIRED_PLACEHOLDER_COUNTS = {
    "{{GUIDE_TITLE}}": 2,
    "{{HAND_LABEL}}": 1,
    "{{IMAGE_QUALITY}}": 1,
    "{{COVERAGE_NOTE}}": 1,
    "{{OVERALL_HTML}}": 1,
    "{{MAJOR_LINES_HTML}}": 1,
    "{{MINOR_LINES_HTML}}": 1,
    "{{REFLECTION_QUESTIONS_HTML}}": 1,
    "{{CANNOT_CONCLUDE_HTML}}": 1,
}
UNSAFE_TEMPLATE_TAGS = {
    "script",
    "iframe",
    "object",
    "embed",
    "link",
    "form",
    "base",
    "template",
}
EXTERNAL_ATTRIBUTE_NAMES = {
    "src",
    "href",
    "srcset",
    "action",
    "formaction",
    "poster",
    "background",
    "cite",
    "ping",
    "manifest",
}


class ReportDataError(ValueError):
    """Raised when report data does not satisfy the public contract."""


class TemplateAuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible_parts: list[str] = []
        self.ignored_depth = 0
        self.body_depth = 0
        self.unsafe_tags: list[str] = []
        self.unsafe_attributes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered == "body":
            self.body_depth += 1
        if lowered in {"style", "script", "noscript"}:
            self.ignored_depth += 1
        if lowered in UNSAFE_TEMPLATE_TAGS:
            self.unsafe_tags.append(lowered)
        for name, value in attrs:
            attribute = name.lower()
            if (attribute in EXTERNAL_ATTRIBUTE_NAMES or attribute.endswith(":href")) and value:
                self.unsafe_attributes.append(f"{lowered}.{attribute}")
            if attribute == "hidden" or attribute == "style" or attribute.startswith("on"):
                self.unsafe_attributes.append(f"{lowered}.{attribute}")
            if lowered == "meta" and attribute == "http-equiv":
                self.unsafe_attributes.append(f"{lowered}.{attribute}")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"style", "script", "noscript"} and self.ignored_depth:
            self.ignored_depth -= 1
        if lowered == "body" and self.body_depth:
            self.body_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.body_depth and not self.ignored_depth:
            self.visible_parts.append(data)


def require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportDataError(f"{field} 必须是对象")
    return value


def require_list(value: Any, field: str, minimum: int, maximum: int) -> list[Any]:
    if not isinstance(value, list):
        raise ReportDataError(f"{field} 必须是数组")
    if not minimum <= len(value) <= maximum:
        raise ReportDataError(f"{field} 项数必须在 {minimum} 到 {maximum} 之间")
    return value


def require_text(value: Any, field: str, minimum: int = 1, maximum: int = 240) -> str:
    if not isinstance(value, str):
        raise ReportDataError(f"{field} 必须是字符串")
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in value):
        raise ReportDataError(f"{field} 不得含控制字符、零宽字符或双向控制符")
    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    if not minimum <= len(normalized) <= maximum:
        raise ReportDataError(f"{field} 长度必须在 {minimum} 到 {maximum} 个字符之间")
    if normalized and not ALLOWED_TEXT_PATTERN.fullmatch(normalized):
        raise ReportDataError(f"{field} 只能包含中文、数字、空格和常用标点")
    return normalized


def reject_unsafe_semantics(value: str, field: str) -> None:
    if (
        UNSAFE_DYNAMIC_TERMS.search(value)
        or AGE_OR_PREDICTION_PATTERN.search(value)
        or GENERAL_PREDICTION_PATTERN.search(value)
        or CLAIM_PATTERN.search(value)
        or PRIVACY_TERMS.search(value)
        or LONG_NUMBER_PATTERN.search(value)
    ):
        raise ReportDataError(f"{field} 含医疗、隐私、高风险或确定性预测内容")


def reject_personal_subject(value: str, field: str) -> None:
    if PERSONAL_SUBJECT_PATTERN.search(value):
        raise ReportDataError(f"{field} 不得包含个人称谓或对特定人物的断言")


def object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReportDataError(f"JSON 含重复字段: {key}")
        result[key] = value
    return result


def load_controlled_vocabulary() -> dict[str, set[str]]:
    vocabulary_path = (
        Path(__file__).resolve().parents[1] / "references" / "report-controlled-vocabulary.json"
    )
    try:
        vocabulary_text = vocabulary_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReportDataError("受控报告词表不可读取") from exc
    vocabulary_hash = hashlib.sha256(vocabulary_text.encode("utf-8")).hexdigest()
    if vocabulary_hash != EXPECTED_VOCABULARY_SHA256:
        raise ReportDataError("受控报告词表指纹不匹配")
    try:
        raw = json.loads(vocabulary_text, object_pairs_hook=object_without_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ReportDataError(f"受控报告词表无法解析: {exc}") from exc
    vocabulary = require_mapping(raw, "vocabulary")
    reject_unknown_keys(vocabulary, VOCABULARY_KEYS, "vocabulary")
    missing = sorted(VOCABULARY_KEYS - set(vocabulary))
    if missing:
        raise ReportDataError(f"vocabulary 缺少字段: {', '.join(missing)}")

    result: dict[str, set[str]] = {}
    for key in sorted(VOCABULARY_KEYS):
        values = require_list(vocabulary[key], f"vocabulary.{key}", 1, 200)
        minimum = 0 if key in {"reflections", "limitations"} else 1
        normalized = {
            require_text(value, f"vocabulary.{key}[{index}]", minimum=minimum)
            for index, value in enumerate(values)
        }
        if len(normalized) != len(values):
            raise ReportDataError(f"vocabulary.{key} 不得包含重复值")
        result[key] = normalized
    return result


def reject_unknown_keys(mapping: dict[str, Any], allowed: set[str], field: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ReportDataError(f"{field} 含未声明字段: {', '.join(unknown)}")


def validate_item(
    raw: Any,
    field: str,
    name_key: str,
    vocabulary: dict[str, set[str]],
) -> dict[str, str]:
    item = require_mapping(raw, field)
    required = {name_key} | COMMON_ITEM_KEYS
    reject_unknown_keys(item, required, field)
    missing = sorted(required - set(item))
    if missing:
        raise ReportDataError(f"{field} 缺少字段: {', '.join(missing)}")

    confidence = require_text(item["confidence"], f"{field}.confidence", maximum=4)
    if confidence not in ALLOWED_CONFIDENCE:
        raise ReportDataError(f"{field}.confidence 只能是高、中、低或不可辨")

    heading = require_text(item[name_key], f"{field}.{name_key}", maximum=30)
    observation = require_text(item["observation"], f"{field}.observation", maximum=220)
    tradition = require_text(item["tradition"], f"{field}.tradition", maximum=240)
    reflection = require_text(item["reflection"], f"{field}.reflection", minimum=0, maximum=180)
    limitation = require_text(item["limitation"], f"{field}.limitation", minimum=0, maximum=180)
    for key, value in (
        ("observation", observation),
        ("tradition", tradition),
        ("reflection", reflection),
        ("limitation", limitation),
    ):
        reject_unsafe_semantics(value, f"{field}.{key}")
        if key != "reflection":
            reject_personal_subject(value, f"{field}.{key}")
    if name_key == "label":
        if heading not in OVERALL_LABELS:
            raise ReportDataError(f"{field}.{name_key} 不在允许的观察标签中")
        reject_unsafe_semantics(heading, f"{field}.{name_key}")
    controlled_values = (
        ("observation", observation, "observations"),
        ("tradition", tradition, "traditions"),
        ("reflection", reflection, "reflections"),
        ("limitation", limitation, "limitations"),
    )
    for item_key, value, vocabulary_key in controlled_values:
        if value not in vocabulary[vocabulary_key]:
            raise ReportDataError(f"{field}.{item_key} 不在受控报告词表中")

    return {
        name_key: heading,
        "observation": observation,
        "confidence": confidence,
        "tradition": tradition,
        "reflection": reflection,
        "limitation": limitation,
    }


def validate_report_data(raw: Any) -> dict[str, Any]:
    vocabulary = load_controlled_vocabulary()
    data = require_mapping(raw, "root")
    reject_unknown_keys(data, ROOT_KEYS, "root")
    missing = sorted(ROOT_KEYS - set(data))
    if missing:
        raise ReportDataError(f"root 缺少字段: {', '.join(missing)}")

    image_quality = require_text(data["image_quality"], "image_quality", maximum=2)
    if image_quality not in ALLOWED_QUALITY:
        raise ReportDataError("image_quality 只能是高、中或低")

    overall_raw = require_list(data["overall"], "overall", 1, 6)
    overall = [
        validate_item(item, f"overall[{index}]", "label", vocabulary)
        for index, item in enumerate(overall_raw)
    ]

    major_raw = require_list(data["major_lines"], "major_lines", 3, 3)
    major_lines = [
        validate_item(item, f"major_lines[{index}]", "name", vocabulary)
        for index, item in enumerate(major_raw)
    ]
    major_names = [item["name"] for item in major_lines]
    if sorted(major_names) != sorted(MAJOR_LINE_NAMES):
        raise ReportDataError("major_lines 必须正好包含生命线、智慧线、感情线各一次")

    minor_raw = require_list(data["minor_lines"], "minor_lines", 0, 6)
    minor_lines = [
        validate_item(item, f"minor_lines[{index}]", "name", vocabulary)
        for index, item in enumerate(minor_raw)
    ]
    invalid_minor_names = sorted({item["name"] for item in minor_lines} - MINOR_LINE_NAMES)
    if invalid_minor_names:
        raise ReportDataError(f"minor_lines 含不支持的传统名称: {', '.join(invalid_minor_names)}")
    minor_names = [item["name"] for item in minor_lines]
    if len(minor_names) != len(set(minor_names)):
        raise ReportDataError("minor_lines 不得包含重复名称")

    reflection_raw = require_list(data["reflection_questions"], "reflection_questions", 0, 5)
    reflection_questions = [
        require_text(value, f"reflection_questions[{index}]", maximum=180)
        for index, value in enumerate(reflection_raw)
    ]
    for index, value in enumerate(reflection_questions):
        reject_unsafe_semantics(value, f"reflection_questions[{index}]")
        if value not in vocabulary["reflections"] or not value:
            raise ReportDataError(f"reflection_questions[{index}] 不在受控报告词表中")

    guide_title = require_text(data["guide_title"], "guide_title", maximum=40)
    hand_label = require_text(data["hand_label"], "hand_label", maximum=80)
    coverage_note = require_text(data["coverage_note"], "coverage_note", maximum=200)
    if guide_title not in ALLOWED_GUIDE_TITLES:
        raise ReportDataError("guide_title 只能使用数据契约列出的通用标题")
    if not HAND_LABEL_PATTERN.fullmatch(hand_label):
        raise ReportDataError("hand_label 只能包含受控的手别、视角和镜像状态")
    if coverage_note not in vocabulary["coverage_notes"]:
        raise ReportDataError("coverage_note 不在受控报告词表中")
    reject_unsafe_semantics(guide_title, "guide_title")
    reject_unsafe_semantics(hand_label, "hand_label")
    reject_unsafe_semantics(coverage_note, "coverage_note")
    reject_personal_subject(coverage_note, "coverage_note")

    return {
        "guide_title": guide_title,
        "hand_label": hand_label,
        "image_quality": image_quality,
        "coverage_note": coverage_note,
        "overall": overall,
        "major_lines": major_lines,
        "minor_lines": minor_lines,
        "reflection_questions": reflection_questions,
    }


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def optional_row(label: str, value: str) -> str:
    if not value:
        return ""
    return f'<p class="detail"><b>{esc(label)}</b>{esc(value)}</p>'


def observation_card(item: dict[str, str], heading_key: str, card_class: str = "card") -> str:
    return "".join(
        [
            f'<article class="{card_class}">',
            '<div class="card-head">',
            f'<h3>{esc(item[heading_key])}</h3>',
            f'<span class="confidence">视觉置信度 {esc(item["confidence"])}</span>',
            "</div>",
            f'<p class="observation"><b>可见观察</b>{esc(item["observation"])}</p>',
            f'<p class="tradition"><b>传统说法</b>{esc(item["tradition"])}</p>',
            optional_row("反思问题", item["reflection"]),
            optional_row("观察限制", item["limitation"]),
            "</article>",
        ]
    )


def list_html(items: list[str], empty_text: str) -> str:
    if not items:
        return f'<p class="empty">{esc(empty_text)}</p>'
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def render_report(data: dict[str, Any], template: str) -> str:
    template_hash = hashlib.sha256(template.encode("utf-8")).hexdigest()
    if template_hash != EXPECTED_TEMPLATE_SHA256:
        raise ReportDataError("只能使用经过审计的内置模板，模板指纹不匹配")
    invalid_placeholder_counts = sorted(
        placeholder
        for placeholder, expected_count in REQUIRED_PLACEHOLDER_COUNTS.items()
        if template.count(placeholder) != expected_count
    )
    if invalid_placeholder_counts:
        raise ReportDataError("内置模板缺少必要报告区块或含重复占位符")
    lowered_template = template.lower()
    if re.search(r"@import|url\s*\(|expression\s*\(", lowered_template):
        raise ReportDataError("模板不得加载外部资源或动态样式")
    parser = TemplateAuditParser()
    parser.feed(template)
    if parser.unsafe_tags or parser.unsafe_attributes:
        raise ReportDataError("模板不得包含脚本、表单、嵌入内容或不安全属性")
    visible_template_text = " ".join(parser.visible_parts)
    missing_boundary = [text for text in MANDATORY_TEMPLATE_TEXT if text not in visible_template_text]
    if missing_boundary:
        raise ReportDataError("模板缺少不可删除的性质说明")

    overall_html = "".join(observation_card(item, "label") for item in data["overall"])
    major_lines_html = "".join(
        observation_card(item, "name", "card line-card") for item in data["major_lines"]
    )
    if data["minor_lines"]:
        minor_lines_html = "".join(
            observation_card(item, "name", "card compact-card") for item in data["minor_lines"]
        )
    else:
        minor_lines_html = '<p class="empty">本次没有足够清楚的其他线纹可供个体化观察。</p>'

    replacements = {
        "{{GUIDE_TITLE}}": esc(data["guide_title"]),
        "{{HAND_LABEL}}": esc(data["hand_label"]),
        "{{IMAGE_QUALITY}}": esc(data["image_quality"]),
        "{{COVERAGE_NOTE}}": esc(data["coverage_note"]),
        "{{OVERALL_HTML}}": overall_html,
        "{{MAJOR_LINES_HTML}}": major_lines_html,
        "{{MINOR_LINES_HTML}}": minor_lines_html,
        "{{REFLECTION_QUESTIONS_HTML}}": list_html(
            data["reflection_questions"], "本次不额外添加反思问题。"
        ),
        "{{CANNOT_CONCLUDE_HTML}}": list_html(list(FIXED_CANNOT_CONCLUDE), ""),
    }
    output = template
    for placeholder, value in replacements.items():
        output = output.replace(placeholder, value)

    leftovers = sorted(set(PLACEHOLDER_PATTERN.findall(output)))
    if leftovers:
        raise ReportDataError(f"模板仍含未替换占位符: {', '.join(leftovers)}")
    return output


def build_report(input_path: Path, output_path: Path) -> None:
    if input_path.suffix.lower() != ".json":
        raise ReportDataError("输入文件必须使用 .json 后缀")
    if output_path.suffix.lower() != ".html":
        raise ReportDataError("输出文件必须使用 .html 后缀")
    if input_path.is_symlink() or output_path.is_symlink():
        raise ReportDataError("输入和输出路径不得是符号链接")
    try:
        resolved_input = input_path.resolve(strict=True)
        resolved_output_parent = output_path.parent.resolve(strict=True)
    except OSError as exc:
        raise ReportDataError(f"输入文件或输出目录不可用: {exc}") from exc
    if not resolved_input.is_file():
        raise ReportDataError("输入路径必须是普通 JSON 文件")
    if resolved_input.stat().st_size > 262_144:
        raise ReportDataError("输入 JSON 不得超过 256 KiB")
    if resolved_input.parent != resolved_output_parent:
        raise ReportDataError("输出 HTML 必须与输入 JSON 位于同一目录")
    if output_path.exists():
        raise ReportDataError("输出文件已存在；为避免覆盖，请使用新文件名")

    try:
        raw = json.loads(
            resolved_input.read_text(encoding="utf-8"),
            object_pairs_hook=object_without_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise ReportDataError(f"JSON 无法解析: {exc}") from exc
    except UnicodeError as exc:
        raise ReportDataError("输入 JSON 必须是有效的 UTF-8 文本") from exc

    data = validate_report_data(raw)
    template_path = Path(__file__).resolve().parents[1] / "assets" / "report-template.html"
    template = template_path.read_text(encoding="utf-8")
    rendered = render_report(data, template)
    with output_path.open("x", encoding="utf-8") as output_file:
        output_file.write(rendered)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从安全的结构化 JSON 生成素掌纪 HTML 报告")
    parser.add_argument("input_json", type=Path, help="报告数据 JSON")
    parser.add_argument("output_html", type=Path, help="输出 HTML")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        build_report(args.input_json, args.output_html)
    except (OSError, ReportDataError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Created {args.output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
