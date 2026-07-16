/* OIA-241: show/hide OAuth2 fields on @@omnia-ai-settings.
 * Progressive enhancement — without this script all fields stay visible. */
(function () {
  "use strict";

  var OAUTH_FIELDS = [
    "oauth_grant_type",
    "oauth_client_id",
    "oauth_client_secret",
    "oauth_token_url",
    "oauth_scope",
    "oauth_client_auth_method",
    "oauth_username",
    "oauth_password",
  ];
  var ROPC_FIELDS = ["oauth_username", "oauth_password"];

  function row(name) {
    return document.getElementById("formfield-form-widgets-" + name);
  }

  function setVisible(names, visible) {
    names.forEach(function (name) {
      var el = row(name);
      if (el) {
        el.style.display = visible ? "" : "none";
      }
    });
  }

  function toggle() {
    var authType = document.getElementById("form-widgets-auth_type");
    var grantType = document.getElementById("form-widgets-oauth_grant_type");
    if (!authType) {
      return;
    }
    var oauth = authType.value === "oauth2";
    setVisible(OAUTH_FIELDS, oauth);
    if (oauth && grantType) {
      setVisible(ROPC_FIELDS, grantType.value === "password");
    }
  }

  function init() {
    toggle();
    ["form-widgets-auth_type", "form-widgets-oauth_grant_type"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) {
        el.addEventListener("change", toggle);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
