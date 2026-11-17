// Sprachumschalter und deutsche Beschriftung der Darstellungswahl.
// Language switch (same page in the other language) and German theme labels.
(function () {
  var cfg = window.FREYA_LANG;
  if (!cfg) return;
  // Buchwurzel aus path_to_root (von mdBook gesetzt).
  var root = new URL(typeof path_to_root === "string" ? path_to_root : "./", location.href);
  var rel = location.href.slice(root.href.length).split("#")[0].split("?")[0];
  if (rel === "") rel = "index.html";
  var target = cfg.map[rel] || "index.html";
  var other = new URL("../" + cfg.other + "/" + target, root);
  var link = document.createElement("a");
  link.className = "freya-lang";
  link.href = other.href;
  link.hreflang = cfg.other;
  link.textContent = cfg.label;
  var right = document.querySelector(".right-buttons");
  if (right) right.prepend(link);

  if (cfg.lang === "de") {
    var labels = { "mdbook-theme-default_theme": "System", "mdbook-theme-light": "Hell", "mdbook-theme-coal": "Dunkel" };
    Object.keys(labels).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = labels[id];
    });
  } else {
    var dark = document.getElementById("mdbook-theme-coal");
    if (dark) dark.textContent = "Dark";
    var auto = document.getElementById("mdbook-theme-default_theme");
    if (auto) auto.textContent = "System";
  }
})();
