/* Static documentation UI; all page content remains available without JS. */
const root = document.body.dataset.root;
const dialog = document.querySelector("#search-dialog");
const search = document.querySelector("#search-input");
const results = document.querySelector("#search-results");
let indexPromise;
let searchVersion = 0;
const plain = (text) => {
  const node = document.createElement("div");
  node.innerHTML = text;
  return node.textContent.replace(/\s+/g, " ").trim();
};
const showEmpty = (text) => {
  results.replaceChildren();
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = text;
  results.append(p);
};
document.querySelector(".search-trigger").addEventListener("click", () => {
  dialog.showModal();
  search.focus();
  if (!search.value) showEmpty("输入关键词，查找章节、接口与完整示例。");
});
document.addEventListener("keydown", (event) => {
  if (
    event.key === "/" &&
    !dialog.open &&
    !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)
  ) {
    event.preventDefault();
    document.querySelector(".search-trigger").click();
  }
});
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) {
    const r = dialog.getBoundingClientRect();
    if (
      event.clientX < r.left ||
      event.clientX > r.right ||
      event.clientY < r.top ||
      event.clientY > r.bottom
    )
      dialog.close();
  }
});
search.addEventListener("input", async () => {
  const version = ++searchVersion;
  const terms = search.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return showEmpty("输入关键词，查找章节、接口与完整示例。");
  try {
    indexPromise ||= fetch(root + "search.json")
      .then((response) => {
        if (!response.ok) throw new Error("Search unavailable");
        return response.json();
      })
      .then((entries) =>
        entries.map((entry) => ({ ...entry, text: plain(entry.text) })),
      )
      .catch((error) => {
        indexPromise = undefined;
        throw error;
      });
    const entries = await indexPromise;
    if (version !== searchVersion) return;
    const found = entries
      .map((entry) => {
        const title = entry.title.toLowerCase();
        const text = entry.text.toLowerCase();
        return {
          ...entry,
          score: terms.every((term) => (title + " " + text).includes(term))
            ? terms.reduce(
                (sum, term) => sum + (title.includes(term) ? 10 : 1),
                0,
              )
            : 0,
        };
      })
      .filter((entry) => entry.score)
      .sort((a, b) => b.score - a.score)
      .slice(0, 25);
    results.replaceChildren();
    if (!found.length) return showEmpty("没有找到相关内容，请换一个关键词。");
    for (const entry of found) {
      const link = document.createElement("a");
      link.href = root + entry.url;
      const title = document.createElement("b");
      title.textContent = entry.title;
      const excerpt = document.createElement("p");
      const offset = Math.max(
        0,
        entry.text.toLowerCase().indexOf(terms[0]) - 35,
      );
      excerpt.textContent =
        (offset ? "…" : "") + entry.text.slice(offset, offset + 150);
      const source = document.createElement("small");
      source.textContent = entry.source;
      link.append(title, excerpt, source);
      results.append(link);
    }
  } catch {
    if (version === searchVersion)
      showEmpty(
        "搜索暂时不可用；可继续通过章节导航阅读。请使用本地 HTTP 预览。",
      );
  }
});
const menu = document.querySelector(".menu-toggle");
menu.addEventListener("click", () => {
  const open = document.body.classList.toggle("nav-open");
  menu.setAttribute("aria-expanded", String(open));
  menu.setAttribute("aria-label", open ? "收起导航" : "展开导航");
});
document.querySelector("main").addEventListener("click", () => {
  document.body.classList.remove("nav-open");
  menu.setAttribute("aria-expanded", "false");
});
let toastTimer;
document.querySelectorAll(".copy-code").forEach((button) =>
  button.addEventListener("click", async () => {
    const code = button
      .closest(".code-block")
      .querySelector("code").textContent;
    try {
      await navigator.clipboard.writeText(code);
      const toast = document.querySelector("#toast");
      toast.textContent = "代码已复制";
      toast.classList.add("visible");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove("visible"), 1800);
      button.textContent = "已复制";
      setTimeout(() => {
        button.textContent = "复制";
      }, 1800);
    } catch {
      button.textContent = "复制失败，请选取代码";
    }
  }),
);
const tocLinks = [...document.querySelectorAll(".toc>a")];
if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (visible)
        tocLinks.forEach((link) =>
          link.classList.toggle(
            "active",
            decodeURIComponent(link.hash.slice(1)) === visible.target.id,
          ),
        );
    },
    { rootMargin: "-80px 0px -65% 0px" },
  );
  tocLinks.forEach((link) => {
    const target = document.getElementById(
      decodeURIComponent(link.hash.slice(1)),
    );
    if (target) observer.observe(target);
  });
}
