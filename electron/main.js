const { app, BrowserWindow, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const http = require("http");

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const API_PORT = 8000;
const NEXT_PORT = 3000;
const IS_DEV = process.env.NODE_ENV === "development" || !app.isPackaged;

// In packaged builds, resources live at process.resourcesPath
const RESOURCES = app.isPackaged
  ? process.resourcesPath
  : path.join(__dirname, "..");

// ---------------------------------------------------------------------------
// Backend process management
// ---------------------------------------------------------------------------
let apiProcess = null;

function startApiServer() {
  const backendDir = path.join(RESOURCES, "backend");
  const packagedPython =
    process.platform === "win32"
      ? path.join(RESOURCES, "venv", "Scripts", "python.exe")
      : path.join(RESOURCES, "venv", "bin", "python");
  const pythonCmd = fs.existsSync(packagedPython)
    ? packagedPython
    : process.platform === "win32"
      ? "python"
      : "python3";

  apiProcess = spawn(
    pythonCmd,
    [
      "-m",
      "uvicorn",
      "main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(API_PORT),
    ],
    {
      cwd: backendDir,
      env: {
        ...process.env,
        PYTHONPATH: path.join(RESOURCES, "utilities_data", "transcribe"),
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  apiProcess.stdout.on("data", (d) => process.stdout.write(`[api] ${d}`));
  apiProcess.stderr.on("data", (d) => process.stderr.write(`[api] ${d}`));

  apiProcess.on("error", (err) => {
    console.error("[api] Failed to start:", err.message);
  });

  apiProcess.on("close", (code) => {
    if (code !== 0 && !app.isQuitting) {
      console.error(`[api] Exited with code ${code}`);
    }
  });
}

function stopApiServer() {
  if (apiProcess) {
    apiProcess.kill("SIGTERM");
    apiProcess = null;
  }
}

// ---------------------------------------------------------------------------
// Wait for a local port to be ready
// ---------------------------------------------------------------------------
function waitForPort(port, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
        if (res.statusCode === 200) resolve();
        else retry();
      });
      req.on("error", retry);
      req.setTimeout(500, () => {
        req.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() - start > timeout) {
        reject(new Error(`Port ${port} not ready after ${timeout}ms`));
      } else {
        setTimeout(check, 300);
      }
    };
    check();
  });
}

// ---------------------------------------------------------------------------
// Next.js server (production: `next start`; dev: external process)
// ---------------------------------------------------------------------------
let nextProcess = null;

function startNextServer() {
  if (IS_DEV) return Promise.resolve(); // started externally by concurrently

  const frontendDir = path.join(RESOURCES, "frontend");
  const serverEntry = path.join(frontendDir, "server.js");

  nextProcess = spawn(process.execPath, [serverEntry], {
    cwd: frontendDir,
    env: {
      ...process.env,
      ELECTRON_RUN_AS_NODE: "1",
      PORT: String(NEXT_PORT),
      HOSTNAME: "127.0.0.1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  nextProcess.stdout.on("data", (d) => process.stdout.write(`[next] ${d}`));
  nextProcess.stderr.on("data", (d) => process.stderr.write(`[next] ${d}`));

  return Promise.resolve();
}

function stopNextServer() {
  if (nextProcess) {
    nextProcess.kill("SIGTERM");
    nextProcess = null;
  }
}

// ---------------------------------------------------------------------------
// Main window
// ---------------------------------------------------------------------------
let mainWindow = null;

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 960,
    height: 720,
    minWidth: 720,
    minHeight: 560,
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    backgroundColor: "#0a0a0a",
    icon: path.join(RESOURCES, "frontend", "public", "logo.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Open external links in the default browser, not in Electron
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  const appUrl = IS_DEV
    ? `http://localhost:${NEXT_PORT}`
    : `http://127.0.0.1:${NEXT_PORT}`;

  mainWindow.loadURL(appUrl);

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------
app.on("ready", async () => {
  startApiServer();
  startNextServer();

  // Wait for both servers before showing the window
  const readyChecks = [waitForPort(API_PORT)];
  if (!IS_DEV) {
    // In dev, Next.js is already running before Electron starts (via concurrently + wait-on)
    readyChecks.push(
      waitForPort(NEXT_PORT, 60000).catch((e) =>
        console.error("Next.js did not start in time:", e.message),
      ),
    );
  }

  try {
    await Promise.all(readyChecks);
  } catch (e) {
    console.error("A server did not start in time:", e.message);
  }

  await createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (mainWindow === null) createWindow();
});

app.on("before-quit", () => {
  app.isQuitting = true;
  stopApiServer();
  stopNextServer();
});
