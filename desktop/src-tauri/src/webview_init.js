// Force custom scrollbars on WebView2 (covers textarea.editor — the real scroller)
(function () {
  var css =
    ".list,.pane,.cache-list,textarea.editor{scrollbar-width:thin!important;}" +
    ".list::-webkit-scrollbar,.pane::-webkit-scrollbar,.cache-list::-webkit-scrollbar,textarea.editor::-webkit-scrollbar{width:8px!important;height:8px!important;}" +
    ".list::-webkit-scrollbar-track,.pane::-webkit-scrollbar-track,.cache-list::-webkit-scrollbar-track,textarea.editor::-webkit-scrollbar-track{background:transparent!important;}" +
    ".list::-webkit-scrollbar-thumb,.pane::-webkit-scrollbar-thumb,.cache-list::-webkit-scrollbar-thumb,textarea.editor::-webkit-scrollbar-thumb{" +
    "background:rgba(0,0,0,.16)!important;border-radius:99px!important;border:2px solid transparent!important;background-clip:padding-box!important;}" +
    ".list::-webkit-scrollbar-thumb:hover,.pane::-webkit-scrollbar-thumb:hover,.cache-list::-webkit-scrollbar-thumb:hover,textarea.editor::-webkit-scrollbar-thumb:hover{" +
    "background:rgba(0,0,0,.28)!important;border:2px solid transparent!important;background-clip:padding-box!important;}" +
    ":root[data-theme=dark] .list::-webkit-scrollbar-thumb,:root[data-theme=dark] .pane::-webkit-scrollbar-thumb," +
    ":root[data-theme=dark] .cache-list::-webkit-scrollbar-thumb,:root[data-theme=dark] textarea.editor::-webkit-scrollbar-thumb{" +
    "background:rgba(255,255,255,.16)!important;border:2px solid transparent!important;background-clip:padding-box!important;}" +
    ":root[data-theme=dark] .list::-webkit-scrollbar-thumb:hover,:root[data-theme=dark] .pane::-webkit-scrollbar-thumb:hover," +
    ":root[data-theme=dark] .cache-list::-webkit-scrollbar-thumb:hover,:root[data-theme=dark] textarea.editor::-webkit-scrollbar-thumb:hover{" +
    "background:rgba(255,255,255,.28)!important;border:2px solid transparent!important;background-clip:padding-box!important;}";
  function inject() {
    if (document.getElementById("pi-scrollbar-fix")) return;
    var s = document.createElement("style");
    s.id = "pi-scrollbar-fix";
    s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
  }
  inject();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  }
  // Re-inject after React paints
  setTimeout(inject, 50);
  setTimeout(inject, 300);
})();
