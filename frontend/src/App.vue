<template>
  <div id="app-container">
    <router-view />
  </div>
</template>

<script setup>
</script>

<style>
:root {
  --ink-950: #102a43;
  --ink-800: #243b53;
  --ink-600: #486581;
  --ink-400: #829ab1;
  --paper: #f7f9fc;
  --surface: #ffffff;
  --line: #d9e2ec;
  --aqua: #0f9f9a;
  --aqua-dark: #087f7a;
  --aqua-soft: #e6f7f5;
  --amber: #f0a83a;
  --shadow-sm: 0 1px 2px rgba(16, 42, 67, .05), 0 8px 24px rgba(16, 42, 67, .06);
  --shadow-lg: 0 24px 70px rgba(16, 42, 67, .16);
  --el-color-primary: #0f9f9a;
  --el-color-primary-light-3: #48b8b3;
  --el-color-primary-light-5: #7ccdc9;
  --el-color-primary-light-7: #afe2df;
  --el-color-primary-light-9: #e6f7f5;
  --el-border-radius-base: 10px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app, #app-container {
  height: 100%;
  width: 100%;
  font-family: Inter, "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--ink-950);
  background: var(--paper);
}

button, input, textarea { font: inherit; }

::selection { background: #bdebe8; color: var(--ink-950); }

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #bcccdc; border-radius: 8px; }
::-webkit-scrollbar-track { background: transparent; }

.el-button { font-weight: 650; letter-spacing: .01em; }
.el-card, .el-dialog { border-color: var(--line) !important; }
.el-input__wrapper, .el-textarea__inner { box-shadow: 0 0 0 1px var(--line) inset !important; }
.el-input__wrapper.is-focus, .el-textarea__inner:focus { box-shadow: 0 0 0 2px rgba(15,159,154,.25) inset !important; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
</style>
