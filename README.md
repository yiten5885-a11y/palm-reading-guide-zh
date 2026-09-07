# 素掌纪 Palm Editorial

`palm-reading-guide-zh` 是一个中文掌纹文化观察 Skill。它把用户自愿提供的手掌照片整理为“可见观察、传统说法、反思问题”三层内容，并可生成高端极简的自包含 HTML 报告；在宿主环境具备浏览器排版或图像渲染能力时，也会指导 Agent 另行制作中文图卡。

本项目不把掌纹包装成科学测量、人格测验或命运预测。生命线不代表寿命，智慧线不代表智力或心理状态，感情线不证明忠诚或关系结局；Skill 也不会依据手掌给出医疗、法律、投资、身份或敏感属性结论。

## 核心能力

- 先检查照片覆盖、焦点、反光、透视和镜像不确定性，再决定能否个体化观察。
- 每个特征都记录可见证据、视觉置信度和观察限制；看不清就写“不可辨”。
- 把中性观察、传统手相称呼、象征性联想与自我反思问题分开。
- 按请求交付对话解读或 HTML 白皮书；用户要 PNG 时，必须实际渲染并逐张核对尺寸，缺少渲染能力就明确标为阻塞。
- 使用确定性 HTML/CSS 排版长段中文，AI 插画只承担通用线稿或装饰视觉。
- 不收集姓名、生日等无关信息，不上传或公开真实掌纹照片。

## 安装

### Codex

```bash
cp -R skills/palm-reading-guide-zh ~/.codex/skills/
```

重启或刷新 Skill 列表后，可显式调用：

```text
$palm-reading-guide-zh 请根据我上传的手掌照片，做一份观察与传统说法分开的中文娱乐性指南。
```

### 其他支持 SKILL.md 的 Agent

把 `skills/palm-reading-guide-zh` 整个目录复制到该 Agent 的用户级 Skills 目录。不要只复制 `SKILL.md`；报告模板、引用资料和生成脚本都属于完整包。

## 目录

```text
skills/palm-reading-guide-zh/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── report-template.html
├── references/
│   ├── image-prompt-template.md
│   ├── palmistry-dictionary.md
│   ├── report-controlled-vocabulary.json
│   └── report-data-schema.md
├── scripts/
│   └── build_report.py
└── tests/
    ├── fixtures/
    │   └── sample-report.json
    ├── test_build_report.py
    └── test_package_contract.py
```

## 报告生成

先按 [报告数据契约](skills/palm-reading-guide-zh/references/report-data-schema.md) 准备 JSON，再运行：

```bash
python3 skills/palm-reading-guide-zh/scripts/build_report.py report-data.json report.html
```

生成器只使用 Python 标准库，会校验字段、闭集报告词表和 Unicode 字符，阻断自定义姓名、地点、高风险及确定性断言，要求三大主线各出现一次，转义动态 HTML，并锁定经过审计的内置模板、受控词表及不可删除的民俗娱乐性质说明。输入 JSON 与输出 HTML 必须放在同一目录；输出名必须是尚不存在的 `.html` 文件，生成器不会覆盖已有文件。

生成器只产出响应式长页 HTML，不包含 PNG 渲染器；PNG 需要宿主环境另行提供浏览器排版或图像渲染能力。它也不负责判断文案是否真的有照片证据；这一步由 Skill 的观察门禁和最终人工或 Agent 核对完成。

## 本地验证

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/palm-reading-guide-zh
python3 -m unittest discover -s skills/palm-reading-guide-zh/tests -v
python3 -m py_compile skills/palm-reading-guide-zh/scripts/build_report.py
git diff --check
```

结构校验和单元测试只能证明包结构与生成器行为；它们不等于个体化掌纹回复已经通过安全与照片证据审查。

## 隐私与素材

仓库只包含新写的通用工作流、文本、代码和抽象 SVG 示意图。不要把真实手掌照片、原始来源文档、EXIF、图像哈希、个人资料或未经授权的版式素材提交到 GitHub。测试数据必须是纯文本合成示例。

## 许可

[MIT License](LICENSE)
