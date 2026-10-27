"use strict";

const sources = {
  launcher: "incubator/uvmx/sv/uvmx_bridge.source.html",
  registration: "incubator/uvmx/python/uvmx/bootstrap.source.html",
  factory: "incubator/uvmx/sv/uvmx_factory.source.html"
};
const shared = [
  {
    title: "先让 Python 用例进入运行时",
    description: "launcher 初始化 SVX，加载用户模块和 uvmx.bootstrap。装饰器记录 canonical_id、factory_name 和 sv_base，并把实际 Python 类注册给公开 CallbackAdapter。",
    label: "SV · launcher", source: sources.launcher,
    code: 'svx_init();\nsvx_load(python_module);\nsvx_load("uvmx.bootstrap");'
  },
  {
    title: "把名称加入原有 UVM factory",
    description: "Python 通过 SvTypes 注册记录发布声明，SV 并行消费。每个名称获得一个 wrapper；wrapper 复用所选 SV 基类桥接，不为每个 Python Test 生成 SV 类。原有 SV 名称照常保留。",
    label: "SV · uvmx_base_registry.register_test", source: sources.factory,
    code: "wrapper = bases[declaration.sv_base].make(\n  declaration.factory_name,\n  declaration.canonical_id\n);\nfactory.register(wrapper);"
  },
  {
    title: "由 UVM 决定运行哪一个用例",
    description: "优先读取标准 +UVM_TESTNAME，进入原生 uvm_pkg::run_test()。Python 与 SV 的名称都在同一个 factory 中查找；不存在另一套 Python 用例选择器。",
    label: "SV · 原有 UVM 入口", source: sources.launcher,
    code: 'if ($value$plusargs("UVM_TESTNAME=%s",\n                   canonical_name)) begin\n  uvm_pkg::run_test();\nend'
  }
];
const pythonSteps = [
  ...shared,
  {
    title: "SV bridge 与实际 Python Test 绑定",
    description: "UVM wrapper 创建参数化 Test bridge。bridge 构造 CallbackAdapter 生成的接入对象，复用 SVX 的对象工厂，在 Python 初始化前绑定真正的用户 Test 实例。没有额外的 Python 委托实例。",
    label: "SV · wrapper.create_component", source: sources.factory,
    code: "uvmx_test_bridge#(BASE) instance;\ninstance = new(name, parent, canonical_id,\n               factory_name, this);\nreturn instance;\n\n// bridge 构造内\ncallbacks = new(canonical_id);"
  },
  {
    title: "UVM 驱动 phase，Python 执行验证意图",
    description: "bridge 保留 SV super 调用，再将 phase 转发到同一个 Python Test。run_phase 期间自动持有 objection；Python 普通方法同步执行，需要等待时使用 SVX 原语，由 SV 调度。",
    label: "SV · bridge.run_phase", source: sources.factory,
    code: 'super.run_phase(phase);\nphase.raise_objection(this,\n                      "Python test active");\ncallbacks.run_phase();\nphase.drop_objection(this,\n                     "Python test completed");'
  }
];
const svSteps = [
  ...shared,
  {
    title: "原有 SV wrapper 创建原有 SV Test",
    description: "选择 legacy_sv_test 时，UVM 使用该类原先的 factory 注册和构造函数。不会创建对应的 Python Test，也不会把它转换成 Python 用例；启动前已经完成的 Python 注册不改变这条路径。",
    label: "原有 SV 用例 · 路径示意", source: sources.factory,
    code: "// UVM factory 找到已有 SV wrapper\n// 调用该 wrapper 的 create_component\n// 得到原有 legacy_sv_test 实例\n// 不进入 Python Test bridge"
  },
  {
    title: "原有 SV phase 行为保持原样",
    description: "UVM 继续运行 SV Test 的 build、connect、run 等 phase，由原有 SV 代码管理 objection。若 SV 用例主动调用 SVX，可继续复用 Python 场景，但这不是选择 SV 用例的前提。",
    label: "原有 UVM 执行 · 路径示意", source: sources.launcher,
    code: "// 原有 SV Test 的 phase 实现\n// 原有 driver / monitor / scoreboard\n// 正常 UVM phase 与 objection\n// run_test 返回后统一清理 SVX"
  }
];

let origin = "python";
let step = 0;
const stepButtons = [...document.querySelectorAll("[data-step]")];
const originButtons = [...document.querySelectorAll("[data-origin]")];
function renderStep() {
  const data = (origin === "python" ? pythonSteps : svSteps)[step];
  stepButtons.forEach((button, index) => button.setAttribute("aria-pressed", String(index === step)));
  originButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.origin === origin)));
  document.getElementById("selected-plusarg").textContent = "+UVM_TESTNAME=" + (origin === "python" ? "py_smoke_test" : "legacy_sv_test");
  document.getElementById("create-caption").textContent = origin === "python" ? "bridge + Python Test" : "原有 SV Test";
  document.getElementById("execute-caption").textContent = origin === "python" ? "同步 Python 回调" : "原有 SV phase";
  document.getElementById("step-kicker").textContent = `0${step + 1} / ${stepButtons[step].querySelector("strong").textContent}`;
  document.getElementById("step-title").textContent = data.title;
  document.getElementById("step-description").textContent = data.description;
  document.getElementById("step-code-label").textContent = data.label;
  document.getElementById("step-code").textContent = data.code;
  document.getElementById("step-source").href = data.source;
}
stepButtons.forEach(button => button.addEventListener("click", () => { step = Number(button.dataset.step); renderStep(); }));
originButtons.forEach(button => button.addEventListener("click", () => { origin = button.dataset.origin; renderStep(); }));

const phaseButtons = [...document.querySelectorAll("[data-phase]")];
function renderPhase(name) {
  const task = name === "run_phase";
  phaseButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.phase === name)));
  document.getElementById("phase-kind").textContent = task ? "TASK CONTEXT" : "FUNCTION CONTEXT";
  document.getElementById("phase-title").textContent = name + "(self)";
  document.getElementById("phase-description").textContent = task
    ? "先执行 SV super.run_phase，再 raise objection，随后同步调用 Python run_phase。Python 可使用 svx.delay() 或阻塞通道；返回后 drop objection。不是 asyncio 协程。"
    : `先调用 SV 基类 ${name}，再同步进入 Python ${name}。可创建 Python 状态、完成配置；不能延时或调用阻塞原语。`;
  const labels = task
    ? ["SV super.run_phase", "raise objection", "Python run_phase", "drop objection"]
    : [`SV super.${name}`, `Python ${name}`, "返回 UVM"];
  const sequence = document.getElementById("phase-sequence");
  sequence.replaceChildren();
  labels.forEach((label, index) => {
    if (index) { const arrow = document.createElement("b"); arrow.textContent = "↓"; sequence.append(arrow); }
    const item = document.createElement("span"); item.textContent = label; sequence.append(item);
  });
}
phaseButtons.forEach(button => button.addEventListener("click", () => renderPhase(button.dataset.phase)));

if ("IntersectionObserver" in window) {
  const navLinks = [...document.querySelectorAll("nav a")];
  const observer = new IntersectionObserver(entries => {
    const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
    if (!visible.length) return;
    navLinks.forEach(link => {
      if (link.hash === "#" + visible[0].target.id) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }, {rootMargin: "-15% 0px -55% 0px"});
  document.querySelectorAll("main section").forEach(section => observer.observe(section));
}
renderStep();
