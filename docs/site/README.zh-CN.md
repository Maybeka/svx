# Cookbook 文档网站

[English](README.md)

网站将现有中文 Cookbook 呈现为分阶段的学习路径。教程以 Markdown 为内容来源：
构建时将章节、引用文档、示例指南与引用源码一并转成静态页面。首页提供最小入口、
Register Lab 和真实 OpenTitan UART 迁移三个起点。示例原有的英文指南可通过语言
链接阅读；网站并未另外生成整份英文 Cookbook。

在仓库根目录执行：

```sh
python -m pip install -e '.[docs]'
python docs/site/build.py
python -m http.server 8765 --directory docs/site/_build --bind 127.0.0.1
```

打开 `http://127.0.0.1:8765`。本地 HTTP 服务用于搜索和浏览器剪贴板功能；页面
本身不依赖服务端程序。也可用 `--output /path/to/site` 指定其他输出位置。

构建器显式以 UTF-8 读取仓库文本和写入 HTML、JSON、CSS，不依赖 Windows
系统代码页，也不要求设置编码环境变量。输出目录可以含中文；终端状态使用
ASCII 安全的 JSON 表示路径，网页中的中文仍按 UTF-8 保存。

网站包含全文搜索、站内源码阅读、语法高亮、代码复制、上下节导航、本页目录与
移动端导航。它不会在浏览器内运行仿真。运行方法和验收条件仍来自原指南；网页
构建不会重新验证或扩大这些结果所声明的范围。

构建产物不由 Git 跟踪，也不进入源码分发包；网站源码随源码分发包提供。运行时
不需要 JavaScript 依赖、CDN、外部字体、统计服务或在线搜索服务。生成结果可在
静态托管的子目录下直接使用；上传网站或调整 GitHub Pages 是独立的部署操作。

构建器沿已有文档链接收集可发布内容，不复制私有开发记录、隐藏目录、milestone、
审阅文档或仓库外文件。未发布引用保留文字与提示，不暴露本机文件路径。
修改 Markdown 后重新构建即可，不需要维护第二份网页教程。

## UVMX 实现图解

构建后打开 `uvmx.html`，或从站内“参考资料”进入。独立的中文图解页先展示
五步准备路径：默认 uvm_test 不运行生成器，自定义基类与数据契约按需
增加。集中操作说明见[准备和使用 UVMX](../UVMX_GETTING_STARTED.zh-CN.md)。此外提供职责
分层、Python / SV 用例启动路径切换、五个 phase 的调用顺序，以及免重编译边界、
已有验证和当前限制。它是 `incubator/uvmx` 当前实现的讲解，不是在浏览器内执行
UVM。页面模板在 `uvmx.html`，交互与样式在 `assets/uvmx.js`、`assets/uvmx.css`；
源码链接与示例指南随站点一起构建。UVMX 实现改变时需要同步更新此讲解。
SVX 源码分发包不含临时 UVMX；在缺少该源码时构建器会省略此页面及其导航入口。

## 检查

```sh
python -m pytest -q tests/python/test_cookbook_site.py
```

这些检查需要 `docs` 可选依赖。浏览器还应检查首页、章节页、搜索、代码复制、
移动导航与真实项目指南。两项构建依赖不会成为 SVX 运行时的依赖。

UVMX 准备步骤在构建时直接从中文准备指南生成，折叠展开即可查看完整代码。
修改该 Markdown 即可同步网页，不再另写一套 HTML 操作说明。侧栏的文档地图和
生成与增量构建入口用于按问题查找唯一的权威说明。
