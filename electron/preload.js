const { contextBridge } = require("electron");

// Expose only what the renderer needs — nothing sensitive.
contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
});
