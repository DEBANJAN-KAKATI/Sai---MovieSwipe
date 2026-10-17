// Rebuild the Android APK from the current code: `npm run apk`
//
// 1. type-checks and builds the web app with the PC's Wi-Fi address baked in as the default server
// 2. copies it into the Capacitor Android project
// 3. runs Gradle (JDK 21 + Android SDK from D:\Android, override with JAVA_HOME / ANDROID_HOME)
// 4. copies the APK to ../sai.apk and ../apk-share/sai.apk (the download folder)
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { networkInterfaces } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const project = resolve(frontend, "..");
const toolchain = process.env.MOVIESWIPE_TOOLCHAIN ?? "D:\\Android";

function lanAddress() {
  // Prefer the real Wi-Fi/Ethernet adapter over VirtualBox/Hyper-V/VPN adapters.
  const candidates = [];
  for (const [name, addrs] of Object.entries(networkInterfaces())) {
    if (/vethernet|virtual|vmware|vbox|loopback|bluetooth|tailscale|zerotier|wsl/i.test(name)) continue;
    for (const a of addrs ?? []) {
      if (a.family === "IPv4" && !a.internal && !a.address.startsWith("169.254.")) {
        candidates.push({ name, address: a.address, score: /wi-?fi|wlan|wireless/i.test(name) ? 2 : /ethernet/i.test(name) ? 1 : 0 });
      }
    }
  }
  candidates.sort((x, y) => y.score - x.score);
  return candidates[0]?.address ?? "127.0.0.1";
}

function findJdk() {
  if (process.env.JAVA_HOME && /jdk-?(17|21)/i.test(process.env.JAVA_HOME)) return process.env.JAVA_HOME;
  const jdk = existsSync(toolchain) ? readdirSync(toolchain).find((d) => d.startsWith("jdk-21")) : null;
  if (!jdk) throw new Error(`JDK 21 not found in ${toolchain}; set JAVA_HOME to a JDK 17 or 21`);
  return join(toolchain, jdk);
}

function run(cmd, args, opts = {}) {
  console.log(`\n> ${cmd} ${args.join(" ")}`);
  const res = spawnSync(cmd, args, { stdio: "inherit", shell: true, ...opts });
  if (res.status !== 0) {
    console.error(`\n✖ ${cmd} failed (exit ${res.status})`);
    process.exit(res.status ?? 1);
  }
}

const apiBase = process.env.VITE_API_BASE ?? `http://${lanAddress()}:8000`;
console.log(`Building sai APK — default server ${apiBase}`);

run("npx", ["tsc", "-b"], { cwd: frontend });
run("npx", ["vite", "build"], { cwd: frontend, env: { ...process.env, VITE_API_BASE: apiBase } });
run("npx", ["cap", "sync", "android"], { cwd: frontend });

const android = join(frontend, "android");
const gradlew = process.platform === "win32" ? `"${join(android, "gradlew.bat")}"` : "./gradlew";
run(gradlew, ["assembleDebug", "--console=plain"], {
  cwd: android,
  env: {
    ...process.env,
    JAVA_HOME: findJdk(),
    ANDROID_HOME: process.env.ANDROID_HOME ?? join(toolchain, "sdk"),
    GRADLE_USER_HOME: process.env.GRADLE_USER_HOME ?? join(toolchain, "gradle-home"),
  },
});

const apk = join(android, "app", "build", "outputs", "apk", "debug", "app-debug.apk");
const share = join(project, "apk-share");
mkdirSync(share, { recursive: true });
copyFileSync(apk, join(project, "sai.apk"));
copyFileSync(apk, join(share, "sai.apk"));
const mb = (statSync(apk).size / 1024 / 1024).toFixed(1);
console.log(`\n✔ sai.apk (${mb} MB) updated in the project folder and apk-share/ — server ${apiBase}`);
