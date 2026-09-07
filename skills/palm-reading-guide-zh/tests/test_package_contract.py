from __future__ import annotations

import html
import importlib.util
import json
import re
import unittest
from pathlib import Path

import yaml


SKILL_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_ROOT / "scripts" / "build_report.py"
SPEC = importlib.util.spec_from_file_location("build_report_contract", MODULE_PATH)
assert SPEC and SPEC.loader
BUILD_REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_REPORT)

FORBIDDEN_SUFFIXES = {
    ".7z",
    ".avif",
    ".bmp",
    ".bz2",
    ".cab",
    ".doc",
    ".docx",
    ".dmg",
    ".gif",
    ".gz",
    ".heic",
    ".heif",
    ".ico",
    ".j2k",
    ".jp2",
    ".jpeg",
    ".jpg",
    ".jxl",
    ".lz",
    ".lzma",
    ".m4v",
    ".mov",
    ".mp4",
    ".pdf",
    ".png",
    ".psd",
    ".pyc",
    ".rar",
    ".rtf",
    ".svg",
    ".tar",
    ".tgz",
    ".tif",
    ".tiff",
    ".webm",
    ".webp",
    ".xz",
    ".zip",
    ".zst",
}
MEDIA_OR_ARCHIVE_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"\xff\x0a",
    b"\x00\x00\x00\x0cJXL \r\n\x87\n",
    b"\x00\x00\x00\x0cjP  \r\n\x87\n",
    b"GIF87a",
    b"GIF89a",
    b"BM",
    b"8BPS",
    b"%PDF-",
    b"PK\x03\x04",
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
    b"II*\x00",
    b"MM\x00*",
    b"\x1f\x8b",
    b"BZh",
    b"\xfd7zXZ\x00",
    b"\x28\xb5\x2f\xfd",
    b"Rar!\x1a\x07",
    b"7z\xbc\xaf\x27\x1c",
    b"{\\rtf",
)


def contains_encoded_media_uri(payload: bytes) -> bool:
    text = payload.decode("utf-8", errors="ignore")
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return bool(re.search(r"data\s*:\s*(?:image|video|audio|application/pdf)", text, re.I))


def is_forbidden_package_payload(path: Path, payload: bytes) -> bool:
    is_webp = payload.startswith(b"RIFF") and payload[8:12] == b"WEBP"
    is_iso_media = payload[4:8] == b"ftyp"
    is_tar = len(payload) >= 262 and payload[257:262] == b"ustar"
    return (
        path.suffix.lower() in FORBIDDEN_SUFFIXES
        or payload.startswith(MEDIA_OR_ARCHIVE_SIGNATURES)
        or is_webp
        or is_iso_media
        or is_tar
        or contains_encoded_media_uri(payload)
    )


class PackageContractTests(unittest.TestCase):
    def test_skill_links_resolve_inside_package(self) -> None:
        markdown_files = list(SKILL_ROOT.rglob("*.md"))
        link_count = 0
        for markdown_path in markdown_files:
            markdown_text = markdown_path.read_text(encoding="utf-8")
            links = re.findall(r"!?\[[^\]]+\]\(([^)]+)\)", markdown_text)
            links.extend(
                re.findall(
                    r"^\s*\[[^\]]+\]:\s*<?([^\s>]+)>?",
                    markdown_text,
                    re.MULTILINE,
                )
            )
            link_count += len(links)
            for relative in links:
                self.assertFalse(relative.startswith(("http://", "https://", "/")))
                target = (markdown_path.parent / relative).resolve()
                self.assertTrue(target.is_relative_to(SKILL_ROOT.resolve()), relative)
                self.assertTrue(target.is_file(), relative)
            self.assertNotRegex(
                markdown_text,
                r"(?i)<(?:a|img|script|link|iframe|object|embed|video|audio|source|frame)\b",
            )
            self.assertNotRegex(markdown_text, r"(?i)(?:https?://|mailto:)")
        self.assertGreaterEqual(link_count, 3)

    def test_package_contains_no_real_image_or_source_document(self) -> None:
        offenders: list[str] = []
        for path in SKILL_ROOT.rglob("*"):
            if path.is_symlink() or path.name == ".DS_Store" or "__pycache__" in path.parts:
                offenders.append(path.relative_to(SKILL_ROOT).as_posix())
                continue
            if not path.is_file():
                continue
            payload = path.read_bytes()
            if is_forbidden_package_payload(path, payload):
                offenders.append(path.relative_to(SKILL_ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_media_gate_recognizes_renamed_and_encoded_payloads(self) -> None:
        samples = {
            "jxl.bin": b"\xff\x0a" + b"x" * 20,
            "jp2.bin": b"\x00\x00\x00\x0cjP  \r\n\x87\n" + b"x" * 20,
            "video.bin": b"\x00\x00\x00\x18ftypmp42" + b"x" * 20,
            "document.bin": b"{\\rtf1\\ansi sample}",
            "archive.bin": b"x" * 257 + b"ustar" + b"x" * 20,
            "encoded.txt": b"data" + b"&#58;" + b"image/png;base64,AAAA",
        }
        for name, payload in samples.items():
            with self.subTest(name=name):
                self.assertTrue(is_forbidden_package_payload(Path(name), payload))

    def test_interface_prompt_names_the_skill(self) -> None:
        interface_path = SKILL_ROOT / "agents" / "openai.yaml"
        interface_data = yaml.safe_load(interface_path.read_text(encoding="utf-8"))
        self.assertIsInstance(interface_data, dict)
        interface = interface_data["interface"]
        self.assertIn("$palm-reading-guide-zh", interface["default_prompt"])
        self.assertIn("本人或已获照片主体授权", interface["default_prompt"])
        self.assertGreaterEqual(len(interface["short_description"]), 25)
        self.assertLessEqual(len(interface["short_description"]), 64)

    def test_template_keeps_fixed_boundary_statement(self) -> None:
        template = (SKILL_ROOT / "assets" / "report-template.html").read_text(encoding="utf-8")
        self.assertIn("科学预测置信度：不适用", template)
        self.assertIn("不构成科学测量、医疗诊断、法律意见、投资建议或未来预测", template)

    def test_cli_uses_only_the_bundled_template(self) -> None:
        script = (SKILL_ROOT / "scripts" / "build_report.py").read_text(encoding="utf-8")
        self.assertNotIn('add_argument("--template"', script)
        self.assertIn('"assets" / "report-template.html"', script)

    def test_schema_example_matches_generator_contract(self) -> None:
        schema_text = (SKILL_ROOT / "references" / "report-data-schema.md").read_text(
            encoding="utf-8"
        )
        match = re.search(r"```json\n(.*?)\n```", schema_text, re.DOTALL)
        self.assertIsNotNone(match)
        example = json.loads(match.group(1))
        BUILD_REPORT.validate_report_data(example)

    def test_dictionary_examples_exist_in_controlled_vocabulary(self) -> None:
        dictionary_text = (SKILL_ROOT / "references" / "palmistry-dictionary.md").read_text(
            encoding="utf-8"
        )
        traditions: set[str] = set()
        reflections: set[str] = set()
        for line in dictionary_text.splitlines():
            if not line.startswith("|") or "---" in line:
                continue
            columns = [column.strip() for column in line.strip("|").split("|")]
            traditions.update(
                BUILD_REPORT.require_text(value, "dictionary.tradition")
                for value in re.findall(r"“([^”]+)”", line)
            )
            if len(columns) == 5 and columns[0] not in {"传统称呼", "可见形态"}:
                traditions.add(
                    BUILD_REPORT.require_text(columns[3].strip("“”"), "dictionary.tradition")
                )
                if columns[4].endswith("？"):
                    reflections.add(
                        BUILD_REPORT.require_text(columns[4], "dictionary.reflection")
                    )
            elif len(columns) == 4 and columns[0] not in {"传统称呼", "可见形态"}:
                candidate = columns[3].strip("“”")
                if candidate.endswith("？"):
                    reflections.add(
                        BUILD_REPORT.require_text(candidate, "dictionary.reflection")
                    )
                elif "象征" in candidate or "流派" in candidate or "传统" in candidate:
                    traditions.add(
                        BUILD_REPORT.require_text(candidate, "dictionary.tradition")
                    )
        vocabulary = BUILD_REPORT.load_controlled_vocabulary()
        self.assertTrue(traditions.issubset(vocabulary["traditions"]), traditions - vocabulary["traditions"])
        self.assertTrue(
            reflections.issubset(vocabulary["reflections"]),
            reflections - vocabulary["reflections"],
        )

    def test_controlled_vocabulary_is_semantically_clean(self) -> None:
        vocabulary = BUILD_REPORT.load_controlled_vocabulary()
        for key, values in vocabulary.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    BUILD_REPORT.reject_unsafe_semantics(value, f"vocabulary.{key}")
                    if key in {"observations", "traditions", "limitations"}:
                        BUILD_REPORT.reject_personal_subject(value, f"vocabulary.{key}")

    def test_bundled_template_matches_audited_fingerprint(self) -> None:
        template = (SKILL_ROOT / "assets" / "report-template.html").read_text(encoding="utf-8")
        BUILD_REPORT.render_report(
            BUILD_REPORT.validate_report_data(
                json.loads(
                    (SKILL_ROOT / "tests" / "fixtures" / "sample-report.json").read_text(
                        encoding="utf-8"
                    )
                )
            ),
            template,
        )


if __name__ == "__main__":
    unittest.main()
