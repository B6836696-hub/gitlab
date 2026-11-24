// Lab 04 simulator: small UX helpers only.
// No framework, no network calls, no change to submitted data.
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  ready(function () {
    var tabs = document.querySelectorAll(".analysis-tab");
    var button = document.querySelector("button[type=submit]");
    var radios = document.querySelectorAll("input[name=analysis]");

    function syncTabs() {
      var selected = document.querySelector("input[name=analysis]:checked");
      tabs.forEach(function (tab) {
        var radio = tab.querySelector("input[name=analysis]");
        tab.classList.toggle("on", radio === selected);
      });
      if (button && selected) {
        var label = selected.getAttribute("data-label") || selected.value.toUpperCase();
        var code = selected.getAttribute("data-code") || "";
        button.textContent = "Run " + label + (code ? " \u00b7 " + code : "");
      }
    }

    radios.forEach(function (radio) {
      radio.addEventListener("change", syncTabs);
    });
    syncTabs();

    // After a real run the results card is below the fold on small screens.
    var results = document.getElementById("results");
    if (results && /SUCCESS|ERROR/.test(results.textContent || "")) {
      try {
        results.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (e) {
        results.scrollIntoView();
      }
    }
  });
})();
