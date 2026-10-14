"use strict";
const setup = document.body.dataset.setup === "true";
if (setup) {
  document.querySelector("#loginTitle").textContent = "首次设置本机密码";
  document.querySelector("#loginSubmit").textContent = "设置并登录";
  document.querySelector("#repeatLabel").hidden = false;
  document.querySelector("#repeatPassword").hidden = false;
  document.querySelector("#repeatPassword").required = true;
  document.querySelector("#password").minLength = 12;
  document.querySelector("#password").autocomplete = "new-password";
}
document.querySelector("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#loginError");
  const button = document.querySelector("#loginSubmit");
  const password = document.querySelector("#password").value;
  if (setup && password !== document.querySelector("#repeatPassword").value) {
    error.textContent = "两次密码不一致";
    return;
  }
  button.disabled = true;
  try {
    const response = await fetch(setup ? "/api/setup" : "/api/login", {
      method: "POST",
      headers: {"Content-Type":"application/json", "X-CSRF-Token":document.querySelector('meta[name="csrf"]').content},
      body: JSON.stringify({username:"admin", password}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "登录失败");
    document.querySelector("#password").value = "";
    location.reload();
  } catch (reason) {
    error.textContent = reason.message;
    button.disabled = false;
  }
});
