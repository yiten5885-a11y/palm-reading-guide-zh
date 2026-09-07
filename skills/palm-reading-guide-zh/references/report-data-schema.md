# 报告数据契约

视觉报告先写成结构化 JSON，再交给 `scripts/build_report.py`。这样可以把事实观察、传统说法和反思问题稳定分栏，并避免动态文本破坏 HTML。

## JSON 结构

```json
{
  "guide_title": "你的手相解析指南",
  "hand_label": "右手 掌心正面 镜像状态未知",
  "image_quality": "中",
  "coverage_note": "指尖至腕横纹完整；小指侧略有反光",
  "overall": [
    {
      "label": "掌面比例",
      "observation": "掌面视觉上略偏长，透视影响较小。",
      "confidence": "中",
      "tradition": "部分手相流派会把修长比例作为感受与联想主题的象征。",
      "reflection": "哪些环境最容易激发你的观察力？",
      "limitation": "照片只显示单手，不能做双手比较。"
    }
  ],
  "major_lines": [
    {
      "name": "生命线",
      "observation": "可见一条环绕拇指根部的弧线，中段受反光影响。",
      "confidence": "中",
      "tradition": "部分流派会借弧幅谈生活投入的范围。",
      "reflection": "你更喜欢多种体验，还是长期专注少数重点？",
      "limitation": "中段连续性不可辨。"
    },
    {
      "name": "智慧线",
      "observation": "掌心中部横向纹路较清楚，整体略向下。",
      "confidence": "中",
      "tradition": "传统叙事有时借下斜走向谈联想式思考。",
      "reflection": "你解决问题时更常依赖拆解，还是先形成整体图景？",
      "limitation": "末端被裁切。"
    },
    {
      "name": "感情线",
      "observation": "指根下方横纹可见，局部分支不清。",
      "confidence": "低",
      "tradition": "这里只介绍传统名称，不延伸到现实关系判断。",
      "reflection": "你通常如何表达在意和边界？",
      "limitation": "小指侧反光明显。"
    }
  ],
  "minor_lines": [
    {
      "name": "命运线",
      "observation": "掌心纵向细纹不可辨。",
      "confidence": "不可辨",
      "tradition": "本次不展开个体化解释。",
      "reflection": "",
      "limitation": "分辨率不足。"
    }
  ],
  "reflection_questions": [
    "哪些现实经历最能支持或反驳上面的传统联想？",
    "你希望保留哪一种习惯，又想调整哪一种？"
  ]
}
```

这只是合成结构示例，不对应任何真实手掌。

## 字段规则

- `guide_title`：只能使用 `你的手相解析指南`、`手相解析指南`、`掌纹观察指南`、`民俗掌纹观察报告`、`素掌纪` 之一，不能写姓名或自定义身份标题。
- `hand_label`：按“手别＋视角＋可选镜像状态”组合。手别只能是 `左手`、`右手`、`手别未知`；视角只能是 `掌心正面`、`掌心斜视`、`视角未知`；镜像状态可省略，或使用 `镜像状态未知`、`已确认镜像`、`已确认未镜像`。
- `image_quality`：只能是 `高`、`中`、`低`。
- `coverage_note`：1–200 个字符。
- `overall`：1–6 项；`label` 只能是 `掌面比例`、`掌面宽窄`、`手指比例`、`手指轮廓`、`掌丘轮廓`、`可见区域`。
- `major_lines`：必须正好包含 `生命线`、`智慧线`、`感情线` 各一次。看不清时仍保留该项，并把 `confidence` 写成 `不可辨`。
- `minor_lines`：0–6 项，只收录照片中确有观察价值的线纹；名称只能是 `命运线`、`玉柱纹`、`太阳线`、`水星线`、`腕横纹`、`小指下方短横纹`，同名不得重复。
- 每个观察项都包含 `observation`、`confidence`、`tradition`、`reflection`、`limitation`；其中 `confidence` 只能是 `高`、`中`、`低`、`不可辨`。
- `reflection_questions`：0–5 项；应能让用户结合现实经验自我核对。
- `coverage_note`、`observation`、`tradition`、`reflection`、`limitation` 和 `reflection_questions` 必须逐字选自 [受控报告词表](report-controlled-vocabulary.json)。生成器不接受这些字段中的自定义文本；这是为了让姓名、地点、同义改写和确定性断言一律失败关闭。
- 所有输入仍会做 Unicode 规范化，只允许中文、数字、空格和常用标点；零宽字符、双向控制符、医疗诊断、寿命或死亡时间、隐私字段、敏感属性、高风险结果、年龄年份或确定性预测内容会被拒绝。相关边界只能由模板中的固定声明表达。
- “不可推出的结论”由生成器写入固定内容，输入 JSON 不接受 `cannot_conclude` 或任何替代字段，避免调用者伪造或弱化边界。

生成命令只接受同一目录中的 `.json` 输入和新建 `.html` 输出，并固定使用经过审计的内置模板。例如在数据文件所在目录执行：

```bash
python3 /path/to/palm-reading-guide-zh/scripts/build_report.py report-data.json report.html
```

不要添加生日、姓名、原图路径、图像哈希、EXIF、疾病史或其他不必要的个人信息。脚本会进行结构、长度和高风险词句校验，但不会判断掌纹解读是否有照片证据；生成者仍须完成 `SKILL.md` 的逐项证据检查。
