# PDF Invoice Reviewer · 发票核对工具

[English](README.md) · [60 秒操作演示](docs/demo.mp4) · [评测记录](docs/evaluation.md)

供应商发来 PDF，运营人员需要把它整理进表格：上传带文本的发票，对照原始页面检查提取值，确认后下载 CSV。缺字段、金额不符或重复单据会被拦截，不能混进导出结果。

`PDF → 对照原文 → 修改或拒绝 → 确认 → CSV`

这是使用合成发票的本地单人审核作品，适合供应商范围明确的英文文档。不读扫描件，不连接财务、支付或 AI 服务。供应商字段标签可以通过配置调整，无需修改 Python；新布局仍需用样例验证。

[![原始 PDF 与可编辑字段并排展示](docs/screenshots/01-review-source.jpg)](docs/demo.mp4)

## 先看一遍实际流程

[视频](docs/demo.mp4)由实际浏览器操作中截取的 12 张画面组成，每步停留 5 秒并附字幕。这是关键步骤展示，不是连续录屏，也不代表原始操作速度。可以用仓库附带的 PDF 在本地复现：

1. 上传 `fixtures/development/01-normal.pdf`，打开日期的来源证据。将 `2026-09-01` 改为同一天的另一种写法 `01 Sep 2026`，填写审核说明，先不保存。
2. 上传 `fixtures/development/07-amount-mismatch.pdf`，再用草稿筛选返回第一张发票，日期和说明仍保留。需要稍后再审，可点击 **Save changes** 保存为待确认记录；**Discard draft** 恢复已保存的值。本页签只要还有草稿，CSV 下载按钮就不可用。
3. 按原文核对正常发票后点击 **Confirm**，日期会保存为 `2026-09-01`。处理完草稿后点击 **Export saved CSV**。[真实导出示例](docs/example-reviewed.csv)只有一张已确认发票 `DEMO-1001`，总额 USD `218.63`。只有已保存、已确认、当前仍通过校验的记录会进入文件。[查看确认后的界面](docs/screenshots/02-confirmed.jpg)。
4. 返回金额异常的发票。原文税前金额加税额是 `702.07`，总额却写着 `707.07`。确认会被拦截，显示差额 `+5.00`，审核说明仍保留。对照原文后填写说明并拒绝，或取得经核实的更正；不能只为通过计算而改数字。[查看拦截界面](docs/screenshots/03-amount-blocked.jpg)。

同目录的 `08-missing-tax.pdf` 缺少税额，应用保持空值，不会倒算补齐。`09-cross-page.pdf` 的总额来源链接 **p.2** 会打开第二页。重复上传同一文件可查看查重拦截，拒绝额外副本后解除冲突。

## 本地启动

需要 Git 和 Python 3.11+；已记录的运行环境为 Windows、Python 3.12.14。无需 API key。

```bash
git clone https://github.com/myp81607-dot/pdf-invoice-reviewer.git
cd pdf-invoice-reviewer
python -m venv .venv
```

Windows PowerShell 用 `.venv\Scripts\Activate.ps1` 激活环境，macOS/Linux 用 `source .venv/bin/activate`，然后执行：

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8766
```

打开 [localhost:8766](http://127.0.0.1:8766)。示例 PDF 已在仓库中，不用先运行生成器。如果端口被占用，把命令和浏览器地址中的端口一起改掉。

## 换成自己的发票

先选几份有权处理的文档，确认在 PDF 阅读器里能选中文本。至少检查一份正常单据、一份缺项或错误单据，以及实际存在的跨页版式，再开始处理一批文件。输出字段固定为供应商、单据号、日期、币种、税前金额、税额和总额；CSV 另带本地记录 ID。

定制某类供应商时，需要准备代表性 PDF、每份单据七个字段的预期值，以及业务上的接受/拒绝规则。附上重复单据和不常见标签样例。只要保留版式，脱敏件或合成件也可以。新的日期习惯、额外输出字段或不同页面结构，需要修改代码并单独验证。

如果只是已支持版式中的标签名称不同，可以复制 [`config/labels.example.json`](config/labels.example.json)，修改相应字段。别名按普通文本匹配、不区分大小写，和内置标签一起生效：

```json
{
  "supplier": ["Supplier name"],
  "invoice_number": ["Document reference"]
}
```

启动应用前，在 PowerShell 设置配置路径：

```powershell
$env:INVOICE_LABELS = "config/labels.example.json"
```

macOS/Linux 改为：

```bash
export INVOICE_LABELS=config/labels.example.json
```

运行 `python scripts/make_custom_sample.py` 会生成 `data/custom-supplier.pdf`，使用上面两个别名的合成发票。带上述配置启动应用，上传样例并对照原文检查这两个字段。修改配置后重启应用，对新上传的文档生效；已有记录保留原始提取结果。这个入口只增加字段叫法，不会增加 OCR 或任意版式识别能力。

PDF、字段和审核历史保存在 `data/invoices.sqlite3`，Git 会忽略它。需要独立工作区时，先停止服务，用同样的环境变量语法把 `INVOICE_DB` 设为另一个数据库路径，再重启。数据库应保密，只处理获得授权的数据。

## 修改与导出的关系

每条发票在当前浏览器页签中有独立草稿，字段和审核说明在切换记录、筛选及上传后保留。应用使用浏览器会话存储支持刷新恢复，有草稿时请求浏览器显示离开提醒。存储检查已通过，但本轮未能验证完整的浏览器刷新及原生提示交互（[详情](docs/evaluation.md#review-workflow-revision-2026-09-19)）。关闭页签后不能保证恢复，所以应先保存或丢弃。草稿不是已保存记录，也不会进入导出。

保存、确认、拒绝都要填写说明。保存后回到待确认；确认会检查本次提交的值；拒绝后不能导出。历史保留改前/改后值、说明和 UTC 时间，原始提取依据仍可查看。如果另一个页签已修改已保存记录，应用保留当前草稿并提示冲突。先核对最新保存值，再丢弃旧草稿，重新填写仍需保留的修改。

后端在确认和导出时检查必填字段、日期、币种、精确的 `Decimal` 金额计算和重复项。文件完全相同，或供应商与单据号相同，都会被拦截；因此新上传的重复件也可能让先前确认的单据暂时无法导出。供应商名只按大小写和空白归一化，不识别公司别名。疑似电子表格公式的 CSV 字符串会加单引号前缀。下载得到当前快照，不是财务过账操作。

## 支持的输入与限制

英文、带文本、有明确标签的 PDF，支持标签和值同行、分开的左右单元格、标签在上值在下，以及字段跨页。同行供应商标签需要冒号。提取依赖邻近字词坐标，换行、过大间距或密集布局可能失败；具体[坐标限制](docs/evaluation.md#remaining-boundaries)见评测文档。

| 字段 | 内置标签 |
|---|---|
| 供应商 | Supplier、Vendor、Seller |
| 单据号 | Invoice number、Invoice reference/ref、Invoice no.、Invoice ID、Invoice # |
| 日期 | Invoice date、Date issued、Issued on |
| 币种 | Currency |
| 税前金额 | Subtotal、Net amount |
| 税额 | Tax、VAT amount |
| 总额 | Total、Total payable、Grand total、Amount due |

标签不区分大小写。日期接受 `YYYY-MM-DD` 或明确英文月份的 `DD Month YYYY` / `DD Mon YYYY`。币种仅 USD、EUR、GBP、CNY，不换汇。金额须为非负、点作小数点、最多两位小数，可带规范千位逗号。只核对“税前金额 + 税额 = 总额”，不核对行项目或判定税务政策。

单文件最多 10 MB、12 页。不支持扫描件、混合 PDF 中的纯图像页、加密、手写、无标签字段、仅 Logo 表示的供应商、贷项通知单和多语言布局。文本发票的缺项可凭经核实的来源和说明人工填写；不支持的文档仍被拦截。错误文本层可能给出看似合理的错值，校验通过不能代替人工看原文。

服务没有鉴权或生产上传隔离，请保留上述回环地址绑定。共享部署、多用户审批、ERP 接入及留存规则需另行实现。本地审核历史不是签名合规证据。

## 验证记录与实现

运行 `python -m pytest -q`：**22 项测试通过**，包括原有 12 项流程检查，以及 10 项版本冲突和配置检查。可选的前端状态检查命令为 `node --test tests/drafts.test.mjs`，**4 项通过**。Node 只用于这些检查，运行应用不需要它。

运行 `python scripts/evaluate.py` 检查提取回归。之前的合成布局评测保留了首次独立样本 **0/66**、另一批首次测试 **35/41** 的已有字段正确数。修复已观察的问题后，35 份文本 PDF 的回归为 **238/238** 已有字段正确、7 个缺项保持空值；另有一份纯图像扫描件被拒绝。本轮没有改变这些布局结果。这是回归表现，不是真实业务准确率。[完整分母、失败与运行证据](docs/evaluation.md)均保留。

后端为 FastAPI、SQLite、pdfplumber，界面使用原生 HTML/CSS/JavaScript，ReportLab 生成合成样例。主要入口是 [`app/extraction.py`](app/extraction.py)、[`app/main.py`](app/main.py) 和 [`tests/test_workflow.py`](tests/test_workflow.py)。应用不包含外部模型或财务集成，因此没有这些系统的实连验证。

字段与来源证据、坐标规则、审核流程、校验、查重和界面在本仓库实现。使用 AI 辅助编码和审查，独立代理在不读取解析器的情况下编写评测布局。[invoice2data 文档与模板源码](https://github.com/invoice-x/invoice2data)提供了明确标签的思路，未打包其运行时和模板库；[pdfplumber 文档与页面源码](https://github.com/jsvine/pdfplumber)用于实际调用文本、字词坐标和页面渲染接口。两份参考均于 2026-09-19 查阅，MIT 许可保存在 [`docs/licenses`](docs/licenses)。本项目代码及合成样例使用 [MIT 许可](LICENSE)。
