from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_ROOT / "scripts" / "build_report.py"
SPEC = importlib.util.spec_from_file_location("build_report", MODULE_PATH)
assert SPEC and SPEC.loader
BUILD_REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_REPORT)


class VisibleTextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "script"}:
            self.ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def sample_data() -> dict:
    item = {
        "observation": "可见一条弧形纹路。",
        "confidence": "中",
        "tradition": "部分流派会借它作为一种象征叙事。",
        "reflection": "现实经历是否支持这种联想？",
        "limitation": "局部反光。",
    }
    return {
        "guide_title": "手相解析指南",
        "hand_label": "右手 掌心正面",
        "image_quality": "中",
        "coverage_note": "掌面完整；小指侧略有反光",
        "overall": [{"label": "掌面比例", **item}],
        "major_lines": [
            {"name": "生命线", **item},
            {"name": "智慧线", **item},
            {"name": "感情线", **item},
        ],
        "minor_lines": [],
        "reflection_questions": ["这段文化联想与你的现实经验是否一致？"],
    }


class BuildReportTests(unittest.TestCase):
    def test_builds_self_contained_escaped_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.json"
            output_path = root / "report.html"
            input_path.write_text(json.dumps(sample_data(), ensure_ascii=False), encoding="utf-8")

            BUILD_REPORT.build_report(
                input_path,
                output_path,
            )

            rendered = output_path.read_text(encoding="utf-8")
            self.assertNotRegex(rendered, r"{{[A-Z0-9_]+}}")
            self.assertIn("科学预测置信度：不适用", rendered)
            self.assertIn("不构成科学测量、医疗诊断、法律意见、投资建议或未来预测", rendered)

    def test_escaping_helper_handles_markup_characters(self) -> None:
        self.assertEqual(
            BUILD_REPORT.esc('<危险> & "引号"'),
            "&lt;危险&gt; &amp; &quot;引号&quot;",
        )

    def test_rejects_dynamic_text_outside_controlled_vocabulary(self) -> None:
        mutations = (
            ("coverage_note", "照片拍于北京朝阳区张三家中。"),
            ("observation", "可见张三专属纹路。"),
            ("tradition", "部分流派会借断续形态谈命不久矣。"),
            ("reflection", "你是否应该马上停药？"),
            ("limitation", "照片来自张三家中。"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                data = sample_data()
                if field == "coverage_note":
                    data[field] = value
                else:
                    data["major_lines"][0][field] = value
                with self.assertRaises(BUILD_REPORT.ReportDataError):
                    BUILD_REPORT.validate_report_data(data)

    def test_rejects_unknown_root_fields(self) -> None:
        data = sample_data()
        data["source_photo_path"] = "/private/example.jpg"
        with self.assertRaises(BUILD_REPORT.ReportDataError):
            BUILD_REPORT.validate_report_data(data)

    def test_requires_each_major_line_once(self) -> None:
        data = sample_data()
        data["major_lines"][2]["name"] = "命运线"
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "生命线、智慧线、感情线"):
            BUILD_REPORT.validate_report_data(data)

    def test_rejects_predictive_confidence_values(self) -> None:
        data = sample_data()
        data["major_lines"][0]["confidence"] = "百分之九十"
        with self.assertRaises(BUILD_REPORT.ReportDataError):
            BUILD_REPORT.validate_report_data(data)

    def test_rejects_template_without_fixed_boundary(self) -> None:
        validated = BUILD_REPORT.validate_report_data(sample_data())
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "内置模板"):
            BUILD_REPORT.render_report(validated, "<html>{{GUIDE_TITLE}}</html>")

    def test_rejects_disclaimer_only_in_comment(self) -> None:
        validated = BUILD_REPORT.validate_report_data(sample_data())
        template = (
            "<!-- 科学预测置信度：不适用；"
            "不构成科学测量、医疗诊断、法律意见、投资建议或未来预测 -->"
            "<html><body>{{GUIDE_TITLE}}</body></html>"
        )
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "内置模板"):
            BUILD_REPORT.render_report(validated, template)

    def test_rejects_external_script_template(self) -> None:
        validated = BUILD_REPORT.validate_report_data(sample_data())
        template = (
            "<html><body><p>科学预测置信度：不适用</p>"
            "<p>不构成科学测量、医疗诊断、法律意见、投资建议或未来预测</p>"
            '<script src="https://example.invalid/track.js"></script>'
            "{{GUIDE_TITLE}}</body></html>"
        )
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "内置模板"):
            BUILD_REPORT.render_report(validated, template)

    def test_rejects_hidden_or_event_handler_template(self) -> None:
        validated = BUILD_REPORT.validate_report_data(sample_data())
        template = (
            '<html><body onload="执行"><p hidden>科学预测置信度：不适用</p>'
            "<p>不构成科学测量、医疗诊断、法律意见、投资建议或未来预测</p>"
            "{{GUIDE_TITLE}}</body></html>"
        )
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "内置模板"):
            BUILD_REPORT.render_report(validated, template)

    def test_rejects_lifespan_or_age_prediction(self) -> None:
        data = sample_data()
        data["major_lines"][0]["tradition"] = "这条纹路表示会在五十二岁离世。"
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "确定性预测"):
            BUILD_REPORT.validate_report_data(data)

    def test_rejects_euphemistic_lifespan_predictions(self) -> None:
        claims = (
            "部分流派会借它说明你会享寿七十有二。",
            "部分流派会借它说明你大限将至。",
            "部分流派会借它说明你能走过七十二个寒暑。",
            "部分流派会借它谈寿元绵长。",
            "部分流派会借它谈终老九十春秋。",
        )
        for claim in claims:
            with self.subTest(claim=claim):
                data = sample_data()
                data["major_lines"][0]["tradition"] = claim
                with self.assertRaises(BUILD_REPORT.ReportDataError):
                    BUILD_REPORT.validate_report_data(data)

    def test_rejects_medical_financial_and_legal_synonyms(self) -> None:
        claims = ("会患白血病。", "购买基金一定赚钱。", "这场诉讼肯定会赢。")
        for claim in claims:
            with self.subTest(claim=claim):
                data = sample_data()
                data["major_lines"][0]["tradition"] = f"部分流派会借它说明{claim}"
                with self.assertRaises(BUILD_REPORT.ReportDataError):
                    BUILD_REPORT.validate_report_data(data)

    def test_rejects_personal_identity_in_hand_label(self) -> None:
        data = sample_data()
        data["hand_label"] = "张三的右手 掌心正面"
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "受控"):
            BUILD_REPORT.validate_report_data(data)

    def test_rejects_personal_subject_or_claim_verbs_in_observation(self) -> None:
        values = ("可见你拥有特殊纹路。", "可见纹路表示好运。", "可见纹路预示很快有好事。")
        for value in values:
            with self.subTest(value=value):
                data = sample_data()
                data["major_lines"][0]["observation"] = value
                with self.assertRaises(BUILD_REPORT.ReportDataError):
                    BUILD_REPORT.validate_report_data(data)

    def test_rejects_zero_width_bidi_and_non_chinese_text(self) -> None:
        values = ("掌面寿\u200b命很长", "掌面\u202e纹路清楚", "掌面ＡＢＣ", "掌面てのひら")
        for value in values:
            with self.subTest(value=value):
                data = sample_data()
                data["coverage_note"] = value
                with self.assertRaises(BUILD_REPORT.ReportDataError):
                    BUILD_REPORT.validate_report_data(data)

    def test_rejects_user_supplied_boundary_override(self) -> None:
        data = sample_data()
        data["cannot_conclude"] = ["任何事情都能推出"]
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "未声明字段"):
            BUILD_REPORT.validate_report_data(data)

    def test_accepts_minor_line_alias_and_rejects_duplicates(self) -> None:
        data = sample_data()
        item = {
            "name": "玉柱纹",
            "observation": "掌心纵向细纹不可辨。",
            "confidence": "不可辨",
            "tradition": "本次不展开个体化解释。",
            "reflection": "",
            "limitation": "分辨率不足。",
        }
        data["minor_lines"] = [item]
        BUILD_REPORT.validate_report_data(data)
        data["minor_lines"] = [item, dict(item)]
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "重复"):
            BUILD_REPORT.validate_report_data(data)

    def test_rejects_non_html_or_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.json"
            input_path.write_text(json.dumps(sample_data(), ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "html"):
                BUILD_REPORT.build_report(input_path, root / "report.png")
            existing = root / "report.html"
            existing.write_text("保留", encoding="utf-8")
            with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "已存在"):
                BUILD_REPORT.build_report(input_path, existing)
            self.assertEqual(existing.read_text(encoding="utf-8"), "保留")

    def test_rejects_output_outside_input_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "输入"
            output_dir = root / "输出"
            input_dir.mkdir()
            output_dir.mkdir()
            input_path = input_dir / "input.json"
            input_path.write_text(json.dumps(sample_data(), ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "同一目录"):
                BUILD_REPORT.build_report(input_path, output_dir / "report.html")

    def test_rejects_symlink_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.json"
            input_path.write_text(json.dumps(sample_data(), ensure_ascii=False), encoding="utf-8")
            symlink_path = root / "linked.json"
            try:
                os.symlink(input_path, symlink_path)
            except (OSError, NotImplementedError):
                self.skipTest("当前平台不支持符号链接")
            with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "符号链接"):
                BUILD_REPORT.build_report(symlink_path, root / "report.html")

    def test_rejects_duplicate_json_keys(self) -> None:
        with self.assertRaisesRegex(BUILD_REPORT.ReportDataError, "重复字段"):
            json.loads(
                '{"guide_title":"手相解析指南","guide_title":"素掌纪"}',
                object_pairs_hook=BUILD_REPORT.object_without_duplicate_keys,
            )

    def test_sample_report_visible_text_is_chinese_only(self) -> None:
        fixture = json.loads(
            (SKILL_ROOT / "tests" / "fixtures" / "sample-report.json").read_text(encoding="utf-8")
        )
        template = (SKILL_ROOT / "assets" / "report-template.html").read_text(encoding="utf-8")
        rendered = BUILD_REPORT.render_report(BUILD_REPORT.validate_report_data(fixture), template)
        collector = VisibleTextCollector()
        collector.feed(rendered)
        self.assertNotRegex("".join(collector.parts), r"[A-Za-z]")


if __name__ == "__main__":
    unittest.main()
